"""환경변수 설정.

루트 .env는 모든 서비스 컨테이너가 같이 읽으므로, rag-chat 전용 값은 RAG_ 접두사를 붙인다.
(ANTHROPIC_API_KEY만 SDK가 기본으로 읽는 이름을 그대로 쓴다.)
"""
from __future__ import annotations

import os
from dataclasses import dataclass

RETRIEVERS = {"http", "mock"}
LLM_PROVIDERS = {"anthropic", "none"}


@dataclass(frozen=True)
class Settings:
    retriever: str  # http: vector-store 호출 / mock: 폴더 안 샘플 원문으로 검색 흉내
    vector_store_url: str
    vector_store_timeout: float
    llm_provider: str  # anthropic / none(LLM 없이 관련 원문만 돌려줌)
    llm_model: str
    llm_timeout: float
    search_top_k: int  # vector-store에서 넉넉히 받아 올 개수 (중복 정리 후 줄인다)
    min_score: float  # 이 점수 미만 검색 결과는 버린다 (코사인 유사도)


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def load_settings() -> Settings:
    retriever = _env("RAG_RETRIEVER", "http").lower()
    if retriever not in RETRIEVERS:
        raise ValueError(f"RAG_RETRIEVER는 {sorted(RETRIEVERS)} 중 하나여야 합니다: {retriever!r}")

    # 따로 정하지 않으면 API 키가 있을 때만 LLM을 쓴다.
    default_provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "none"
    llm_provider = _env("RAG_LLM_PROVIDER", default_provider).lower()
    if llm_provider not in LLM_PROVIDERS:
        raise ValueError(f"RAG_LLM_PROVIDER는 {sorted(LLM_PROVIDERS)} 중 하나여야 합니다: {llm_provider!r}")
    if llm_provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("RAG_LLM_PROVIDER=anthropic인데 ANTHROPIC_API_KEY가 없습니다. 루트 .env에 키를 넣거나 none으로 두세요.")

    return Settings(
        retriever=retriever,
        vector_store_url=_env("RAG_VECTOR_STORE_URL", "http://vector-store:8003").rstrip("/"),
        vector_store_timeout=float(_env("RAG_VECTOR_STORE_TIMEOUT", "10")),
        llm_provider=llm_provider,
        llm_model=_env("RAG_LLM_MODEL", "claude-haiku-5-5"),
        llm_timeout=float(_env("RAG_LLM_TIMEOUT", "30")),
        search_top_k=int(_env("RAG_SEARCH_TOP_K", "10")),
        min_score=float(_env("RAG_MIN_SCORE", "0.25")),
    )
