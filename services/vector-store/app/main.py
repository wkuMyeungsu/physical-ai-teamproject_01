"""vector-store 서비스: OCR 텍스트 → 임베딩 → 실시간 저장 · 유사도 검색.

포트 8003. 자세한 API는 README.md의 "주고받는 데이터" 참고.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .embedder import load_embedder
from .store import VectorStore
from .textproc import chunk_text, clean_ocr_text, is_meaningful, text_hash

DB_PATH = os.getenv("DB_PATH", "/app/data/vectors.db")
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "500"))
DEDUP_THRESHOLD = float(os.getenv("DEDUP_THRESHOLD", "0.95"))


# ---------- 요청 · 응답 형식 ----------
class IngestRequest(BaseModel):
    text: str = Field(..., description="OCR로 뽑은 영어 원문")
    source: str | None = Field(None, description="출처 (예: 서비스 이름, URL, 세션 ID)")
    frame_id: str | None = Field(None, description="frame-capture가 붙인 프레임 ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="그 밖의 자유 정보")


class BatchIngestRequest(BaseModel):
    items: list[IngestRequest]


class ChunkResult(BaseModel):
    status: str  # stored | duplicate | near_duplicate | too_short
    text: str
    id: str | None = None
    duplicate_of: str | None = None
    similarity: float | None = None


class IngestResponse(BaseModel):
    doc_id: str
    stored: int
    skipped: int
    chunks: list[ChunkResult]


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)
    min_score: float = Field(0.0, ge=-1.0, le=1.0)
    source: str | None = None


class EmbedRequest(BaseModel):
    texts: list[str]


# ---------- 실시간 알림 (SSE) ----------
class EventHub:
    def __init__(self):
        self._subs: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def _put(self, event: dict) -> None:
        for q in list(self._subs):
            if q.full():  # 느린 구독자는 오래된 이벤트부터 버린다
                q.get_nowait()
            q.put_nowait(event)

    def publish(self, event: dict) -> None:
        """작업 스레드에서도 안전하게 부를 수 있다."""
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._put, event)


hub = EventHub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.loop = asyncio.get_running_loop()
    embedder = load_embedder()
    app.state.embedder = embedder
    app.state.store = VectorStore(DB_PATH, embedder.dim, embedder.name)
    app.state.started_at = time.time()
    yield


app = FastAPI(title="vector-store", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _store(request: Request) -> VectorStore:
    return request.app.state.store


# ---------- 적재 ----------
def ingest_one(app_: FastAPI, req: IngestRequest) -> IngestResponse:
    store: VectorStore = app_.state.store
    embedder = app_.state.embedder
    doc_id = uuid.uuid4().hex
    results: list[ChunkResult] = []

    cleaned = clean_ocr_text(req.text)
    pieces = chunk_text(cleaned, max_chars=CHUNK_MAX_CHARS) if cleaned else []

    # 1) 너무 짧은 조각 · 완전히 같은 문장은 임베딩 전에 거른다
    candidates: list[tuple[str, str]] = []
    seen_in_request: set[str] = set()
    for p in pieces:
        h = text_hash(p)
        if not is_meaningful(p):
            results.append(ChunkResult(status="too_short", text=p))
        elif h in seen_in_request or store.has_hash(h):
            results.append(ChunkResult(status="duplicate", text=p))
        else:
            seen_in_request.add(h)
            candidates.append((p, h))

    # 2) 남은 조각만 한 번에 임베딩하고, 거의 같은 내용(연속 프레임)은 건너뛴다
    vecs = embedder.encode([p for p, _ in candidates]) if candidates else []
    for idx, ((p, h), v) in enumerate(zip(candidates, vecs)):
        near_id, sim = store.nearest(v)
        if near_id is not None and sim >= DEDUP_THRESHOLD:
            results.append(
                ChunkResult(status="near_duplicate", text=p, duplicate_of=near_id, similarity=round(sim, 4))
            )
            continue
        rec = store.add(doc_id, idx, p, h, v, req.source, req.frame_id, req.metadata)
        results.append(ChunkResult(status="stored", text=p, id=rec.id))
        hub.publish({"type": "stored", "record": rec.to_dict(), "total": store.count()})

    stored = sum(r.status == "stored" for r in results)
    return IngestResponse(doc_id=doc_id, stored=stored, skipped=len(results) - stored, chunks=results)


@app.post("/documents", response_model=IngestResponse)
def add_document(req: IngestRequest, request: Request):
    """OCR 텍스트 1건을 정리 → 청크 → 임베딩 → 저장한다."""
    return ingest_one(request.app, req)


@app.post("/documents/batch", response_model=list[IngestResponse])
def add_documents(req: BatchIngestRequest, request: Request):
    return [ingest_one(request.app, item) for item in req.items]


# ---------- 조회 · 검색 ----------
@app.post("/search")
def search(req: SearchRequest, request: Request):
    """질문과 비슷한 원문 청크를 점수 높은 순으로 돌려준다 (rag-chat · dashboard용)."""
    if not req.query.strip():
        raise HTTPException(400, "query가 비어 있습니다.")
    qvec = request.app.state.embedder.encode([req.query])[0]
    hits = _store(request).search(qvec, req.top_k, req.min_score, req.source)
    return {
        "query": req.query,
        "results": [{**rec.to_dict(), "score": round(score, 4)} for rec, score in hits],
    }


@app.get("/search")
def search_get(
    request: Request,
    q: str = Query(..., description="검색어"),
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.0, ge=-1.0, le=1.0),
):
    return search(SearchRequest(query=q, top_k=top_k, min_score=min_score), request)


@app.post("/embed")
def embed(req: EmbedRequest, request: Request):
    """텍스트를 벡터로만 바꿔 준다 (저장 X). 같은 모델로 임베딩하고 싶은 서비스용."""
    emb = request.app.state.embedder
    vecs = emb.encode(req.texts)
    return {"model": emb.name, "dim": emb.dim, "vectors": vecs.tolist()}


@app.get("/documents")
def list_documents(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    since: float | None = Query(None, description="이 시각(unix 초) 이후 저장된 것만"),
):
    """최근 저장된 청크 목록 (최신순)."""
    s = _store(request)
    return {"total": s.count(), "items": [r.to_dict() for r in s.list(limit, offset, since)]}


@app.get("/documents/{rid}")
def get_document(rid: str, request: Request):
    rec = _store(request).get(rid)
    if rec is None:
        raise HTTPException(404, "없는 id입니다.")
    return rec.to_dict()


@app.delete("/documents/{rid}")
def delete_document(rid: str, request: Request):
    if not _store(request).delete(rid):
        raise HTTPException(404, "없는 id입니다.")
    hub.publish({"type": "deleted", "id": rid, "total": _store(request).count()})
    return {"deleted": rid}


@app.delete("/documents")
def clear_documents(request: Request, confirm: bool = Query(False)):
    """전체 삭제. 실수 방지를 위해 ?confirm=true 가 있어야 한다."""
    if not confirm:
        raise HTTPException(400, "전체 삭제하려면 ?confirm=true 를 붙이세요.")
    n = _store(request).clear()
    hub.publish({"type": "cleared", "total": 0})
    return {"deleted": n}


# ---------- 상태 · 실시간 ----------
@app.get("/health")
def health(request: Request):
    emb = request.app.state.embedder
    return {"status": "ok", "model": emb.name, "dim": emb.dim}


@app.get("/stats")
def stats(request: Request):
    """대시보드의 '실시간 저장 현황'용 요약."""
    s = _store(request)
    emb = request.app.state.embedder
    return {
        "chunks": s.count(),
        "documents": s.doc_count(),
        "last_stored_at": s.last_created_at(),
        "model": emb.name,
        "dim": emb.dim,
        "uptime_sec": round(time.time() - request.app.state.started_at, 1),
    }


@app.get("/events")
async def events(request: Request):
    """새로 저장될 때마다 이벤트를 밀어 주는 SSE 스트림 (text/event-stream)."""
    q = hub.subscribe()

    async def gen():
        try:
            yield f"data: {json.dumps({'type': 'hello', 'total': _store(request).count()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # 연결 유지
        finally:
            hub.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
