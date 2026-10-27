"""원문 검색.

- HttpRetriever: vector-store의 POST /search를 부른다 (실제 연동).
- MockRetriever: app/sample_data.json의 샘플 원문으로 검색을 흉내 낸다.
  vector-store 없이 rag-chat 혼자 끝까지 확인할 때 쓴다 (RAG_RETRIEVER=mock).

두 검색기 모두 vector-store /search의 results 항목과 같은 모양의 dict 목록을 돌려준다.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

import httpx

SAMPLE_DATA = Path(__file__).parent / "sample_data.json"


class RetrieverUnavailable(Exception):
    """검색 서비스에 연결할 수 없거나 오류를 돌려줬을 때."""


class HttpRetriever:
    name = "http"

    def __init__(self, base_url: str, timeout: float = 10.0, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def search(self, query: str, top_k: int, min_score: float, source: str | None = None) -> list[dict[str, Any]]:
        payload = {"query": query, "top_k": top_k, "min_score": min_score, "source": source}
        try:
            r = await self._client.post(f"{self.base_url}/search", json=payload)
        except httpx.RequestError as e:
            raise RetrieverUnavailable(f"{self.base_url} 연결 실패 ({type(e).__name__})") from e
        if r.status_code >= 400:
            raise RetrieverUnavailable(f"{self.base_url}/search 응답 {r.status_code}: {r.text[:200]}")
        return r.json().get("results", [])

    async def health(self) -> dict[str, Any]:
        try:
            r = await self._client.get(f"{self.base_url}/health", timeout=3.0)
            r.raise_for_status()
            return {"reachable": True, "url": self.base_url, **r.json()}
        except (httpx.HTTPError, ValueError) as e:
            return {"reachable": False, "url": self.base_url, "error": type(e).__name__}

    async def aclose(self) -> None:
        await self._client.aclose()


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how", "in",
    "is", "it", "its", "of", "on", "or", "that", "the", "their", "them", "they", "this", "to", "was",
    "what", "when", "where", "which", "who", "why", "will", "with",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS}


class MockRetriever:
    """단어 겹침 점수로 샘플 원문을 찾는다. 점수 크기가 vector-store와 달라서 min_score는 쓰지 않는다."""

    name = "mock"

    def __init__(self, path: Path = SAMPLE_DATA):
        items = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        self._records = [
            {
                "id": f"mock-{i:03d}",
                "doc_id": f"mock-doc-{i:03d}",
                "chunk_index": 0,
                "text": item["text"],
                "source": "mock",
                "frame_id": None,
                "metadata": {"title": item["title"]},
                "created_at": now,
            }
            for i, item in enumerate(items, start=1)
        ]

    async def search(self, query: str, top_k: int, min_score: float, source: str | None = None) -> list[dict[str, Any]]:
        q = _tokens(query)
        if not q:
            return []
        scored = []
        for rec in self._records:
            d = _tokens(rec["text"])
            overlap = len(q & d)
            if overlap:
                scored.append((overlap / math.sqrt(len(q) * len(d)), rec))
        scored.sort(key=lambda x: -x[0])
        return [{**rec, "score": round(score, 4)} for score, rec in scored[:top_k]]

    async def health(self) -> dict[str, Any]:
        return {"reachable": True, "mode": "mock", "passages": len(self._records)}

    async def aclose(self) -> None:
        pass
