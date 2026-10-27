"""rag-chat 서비스: 저장된 OCR 원문을 근거로 질문에 답한다.

포트 8004. 브라우저가 아니라 dashboard 서버가 컨테이너 주소(http://rag-chat:8004)로 부른다.
자세한 형식은 README.md의 "주고받는 데이터" 참고.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .llm import LLMError, LLMUnavailable, LocalLLM, ensure_model_file
from .pipeline import answer_question
from .retriever import HttpRetriever, MockRetriever, RetrieverUnavailable

log = logging.getLogger("uvicorn.error")


def build_llm(settings: Settings):
    """설정에 맞는 LLM을 만든다. 로컬 모델을 준비하지 못하면 LLM 없이 뜨고 이유를 돌려준다."""
    if settings.llm_provider == "local":
        try:
            path = ensure_model_file(settings.local_model_path, settings.local_model_repo, settings.local_model_file)
            llm = LocalLLM(path, n_ctx=settings.local_ctx, n_threads=settings.local_threads)
            log.info("로컬 LLM 준비 완료: %s", llm.model)
            return llm, None
        except LLMUnavailable as e:
            log.error("로컬 LLM 없이 시작합니다 (관련 원문만 돌려줌): %s", e)
            return None, str(e)
    return None, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    if settings.retriever == "mock":
        retriever = MockRetriever()
    else:
        retriever = HttpRetriever(settings.vector_store_url, settings.vector_store_timeout)
    llm, llm_error = build_llm(settings)

    app.state.settings = settings
    app.state.retriever = retriever
    app.state.llm = llm
    app.state.llm_error = llm_error
    yield
    await retriever.aclose()


app = FastAPI(title="rag-chat", version="0.1.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., max_length=1000, description="사용자 질문 (한국어·영어)")
    top_k: int = Field(5, ge=1, le=20, description="답변 근거로 쓸 원문 개수")
    source: str | None = Field(None, description="vector-store의 source 필터를 그대로 전달 (선택)")


@app.post("/ask")
async def ask(req: AskRequest, request: Request):
    """질문 → (한국어면 영어 검색어로 변환) → vector-store 검색 → 중복 정리 → LLM 답변 + 출처."""
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "question이 비어 있습니다.")
    s = request.app.state
    try:
        return await answer_question(question, req.top_k, req.source, s.retriever, s.llm, s.settings)
    except RetrieverUnavailable as e:
        raise HTTPException(503, f"vector-store에 연결할 수 없습니다: {e}") from e
    except LLMError as e:
        raise HTTPException(502, f"LLM 호출에 실패했습니다: {e}") from e


@app.get("/health")
async def health(request: Request):
    s = request.app.state
    return {
        "service": "rag-chat",
        "ok": True,
        "retriever": s.retriever.name,
        "vector_store": await s.retriever.health(),
        "llm": {
            "provider": s.settings.llm_provider,
            "ready": s.llm is not None,
            "model": getattr(s.llm, "model", None),
            "error": s.llm_error,
        },
    }
