import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

log = logging.getLogger("uvicorn.error")

FRAME_CAPTURE_URL = os.getenv("FRAME_CAPTURE_URL", "http://frame-capture:8001")
# frame-capture는 PUBLIC_BASE_URL이 없으면 요청의 Host로 phone_url을 만든다.
# 컨테이너 주소(frame-capture:8001) 대신 브라우저·휴대폰이 닿는 주소가 들어가게 Host를 바꿔 보낸다.
FRAME_CAPTURE_PUBLIC_HOST = os.getenv("FRAME_CAPTURE_PUBLIC_HOST", "localhost:8001")
VECTOR_STORE_URL = os.getenv("VECTOR_STORE_URL", "http://vector-store:8003")
RAG_CHAT_URL = os.getenv("RAG_CHAT_URL", "http://rag-chat:8004")

app = FastAPI(title="dashboard")


@app.get("/api/health")
def health():
    return {"service": "dashboard", "ok": True}


@app.post("/api/session")
async def create_session():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(f"{FRAME_CAPTURE_URL}/api/session", headers={"Host": FRAME_CAPTURE_PUBLIC_HOST})
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"frame-capture 연결 실패: {e}")
    s = r.json()
    log.info("capture session created: %s", s["session_id"])
    return {"session_id": s["session_id"], "capture_url": s["phone_url"], "qr_png": s["qr_png"]}


@app.get("/api/stats")
async def stats():
    """② 실시간 저장 현황: vector-store의 /stats·/documents를 화면 형식으로 바꿔 준다."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            st, latest, recent = await asyncio.gather(
                client.get(f"{VECTOR_STORE_URL}/stats"),
                client.get(f"{VECTOR_STORE_URL}/documents", params={"limit": 20}),
                client.get(f"{VECTOR_STORE_URL}/documents", params={"limit": 500, "since": time.time() - 60}),
            )
            for r in (st, latest, recent):
                r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"vector-store 연결 실패: {e}")
    page = latest.json()
    return {
        "saved": st.json()["documents"],
        "per_minute": len(recent.json()["items"]),
        "latest": [
            {
                "id": r["id"],
                "no": page["total"] - i,  # 저장 순번 (최신이 가장 큼)
                "title": (r.get("metadata") or {}).get("title") or r["text"][:40],
                "text": r["text"],
                "saved_at": datetime.fromtimestamp(r["created_at"], timezone.utc).isoformat(),
            }
            for i, r in enumerate(page["items"])
        ],
    }


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


@app.post("/api/ask")
async def ask(req: AskRequest):
    """③ RAG 검색: rag-chat /ask 중계. 출처는 화면에 필요한 번호·제목만 넘긴다."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:  # LLM 답변 생성이 길어질 수 있다
            r = await client.post(f"{RAG_CHAT_URL}/ask", json={"question": req.question})
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"rag-chat 연결 실패: {e}")
    a = r.json()
    return {"answer": a["answer"], "sources": [{"n": s["n"], "id": s["id"], "title": s["title"]} for s in a.get("sources", [])]}


# API 라우트를 먼저 등록하고, 나머지 경로는 static/ 화면으로
app.mount("/", StaticFiles(directory="static", html=True), name="static")
