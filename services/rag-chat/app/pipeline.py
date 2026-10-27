"""질문 하나를 처리하는 흐름: 검색어 만들기 → 검색 → 정리 → 답변."""
from __future__ import annotations

import logging
import re
from typing import Any

from .config import Settings
from .llm import LLMError
from .prompt import (
    ANSWER_SYSTEM,
    TRANSLATE_SYSTEM,
    build_answer_prompt,
    extractive_answer,
    has_hangul,
    make_title,
    not_found_message,
)

log = logging.getLogger("uvicorn.error")


async def to_search_query(question: str, llm) -> str:
    """한국어 질문이면 영어 검색어로 바꾼다. LLM이 없거나 실패하면 원래 질문을 그대로 쓴다."""
    if llm is None or not has_hangul(question):
        return question
    try:
        query = await llm.complete(TRANSLATE_SYSTEM, question, max_tokens=64, temperature=0.0)
    except LLMError as e:
        log.warning("검색어 번역 실패, 원래 질문으로 검색: %s", e)
        return question
    first_line = next((line for line in query.splitlines() if line.strip()), "")
    first_line = first_line.split("->")[-1]  # 예시 형식 그대로 "질문 -> 검색어"로 답한 경우
    first_line = re.sub(r"^\s*(english\s+)?(search\s+)?query\s*:\s*", "", first_line, flags=re.I)
    return first_line.strip().strip("\"'") or question


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _dedup_keys(record: dict[str, Any]) -> list[tuple]:
    keys = []
    text = _norm(record.get("text", ""))
    if text:
        keys.append(("text", text))
    title = (record.get("metadata") or {}).get("title")
    if isinstance(title, str) and _norm(title):
        # ocr-extract는 같은 카드를 더 정확히 읽으면 같은 title로 다시 보낸다.
        # 긴 카드는 vector-store가 여러 청크로 나누므로 chunk_index까지 같아야 같은 조각으로 본다.
        keys.append(("title", _norm(title), record.get("chunk_index", 0)))
    return keys


def dedupe(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """같은 원문은 점수가 가장 높은 하나만 남긴다 (vector-store가 저장할 때 1차로 거른다).

    - 대소문자·문장부호만 다른 같은 텍스트
    - metadata.title과 chunk_index가 같은 조각 (OCR이 같은 카드를 다시 읽어 보낸 것)
    """
    seen: set[tuple] = set()
    out = []
    for r in results:  # results는 점수 높은 순
        keys = _dedup_keys(r)
        if not keys or any(k in seen for k in keys):
            continue
        seen.update(keys)
        out.append(r)
    return out


async def answer_question(
    question: str,
    top_k: int,
    source: str | None,
    retriever,
    llm,
    settings: Settings,
) -> dict[str, Any]:
    search_query = await to_search_query(question, llm)

    fetch_k = min(max(settings.search_top_k, top_k * 2), 50)  # 중복을 거른 뒤에도 top_k가 남도록 넉넉히
    raw = await retriever.search(search_query, fetch_k, settings.min_score, source)
    hits = dedupe(raw)[:top_k]

    sources = [
        {
            "n": i,  # 답변 속 [n] 인용 번호
            "id": r.get("id"),
            "title": make_title(r),
            "text": r.get("text", ""),
            "score": r.get("score"),
            "created_at": r.get("created_at"),
            "frame_id": r.get("frame_id"),
        }
        for i, r in enumerate(hits, start=1)
    ]

    if not sources:  # 근거가 없으면 LLM을 부르지 않는다 (지어낸 답 방지, 비용 절약)
        return {"answer": not_found_message(question), "sources": [], "found": False, "search_query": search_query}

    if llm is None:
        answer = extractive_answer(sources)
    else:
        answer = await llm.complete(ANSWER_SYSTEM, build_answer_prompt(question, sources), max_tokens=300, temperature=0.2)

    return {"answer": answer, "sources": sources, "found": True, "search_query": search_query}
