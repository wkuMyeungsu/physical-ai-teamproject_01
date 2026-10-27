"""rag-chat API 테스트. LLM·vector-store 없이 mock과 가짜 객체로 돈다.

실행 (저장소 루트에서): docker compose run --rm rag-chat pytest -q
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError
from app.main import app
from app.prompt import TRANSLATE_SYSTEM, make_title
from app.retriever import HttpRetriever


class FakeLLM:
    name = "fake"

    def __init__(self, translation="", answer="answer [1]", fail=False):
        self.translation, self.answer, self.fail = translation, answer, fail
        self.calls = []

    async def complete(self, system, user, max_tokens=500):
        self.calls.append((system, user))
        if system == TRANSLATE_SYSTEM:
            return self.translation
        if self.fail:
            raise LLMError("boom")
        return self.answer


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAG_RETRIEVER", "mock")
    monkeypatch.setenv("RAG_LLM_PROVIDER", "none")
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["ok"] and body["retriever"] == "mock" and body["llm"] == "none"


def test_ask_without_llm_returns_top_passage(client):
    body = client.post("/ask", json={"question": "What water temperature kills yeast?"}).json()
    assert body["found"] is True
    assert body["sources"][0]["title"] == "Why Bread Rises"
    assert body["sources"][0]["n"] == 1
    assert body["answer"].startswith("(LLM 미설정)")


def test_not_found_skips_llm(client):
    llm = FakeLLM()
    client.app.state.llm = llm
    body = client.post("/ask", json={"question": "zzzz qqqq"}).json()
    assert body == {"answer": "No related text was found in the saved captures.", "sources": [], "found": False, "search_query": "zzzz qqqq"}
    assert llm.calls == []


def test_korean_question_is_translated_for_search(client):
    llm = FakeLLM(translation="water temperature that kills yeast", answer="약 60도 이상의 물이에요 [1].")
    client.app.state.llm = llm
    body = client.post("/ask", json={"question": "효모가 죽는 물 온도는?"}).json()
    assert body["search_query"] == "water temperature that kills yeast"
    assert body["found"] and body["sources"][0]["title"] == "Why Bread Rises"
    assert body["answer"] == "약 60도 이상의 물이에요 [1]."
    assert llm.calls[0][0] == TRANSLATE_SYSTEM
    assert "[1] Yeast feeds" in llm.calls[1][1]


def test_empty_question(client):
    assert client.post("/ask", json={"question": "   "}).status_code == 400


def test_llm_error_is_502(client):
    client.app.state.llm = FakeLLM(fail=True)
    r = client.post("/ask", json={"question": "What does optical character recognition do?"})
    assert r.status_code == 502


def test_vector_store_down_is_503(monkeypatch):
    monkeypatch.setenv("RAG_RETRIEVER", "http")
    monkeypatch.setenv("RAG_VECTOR_STORE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("RAG_LLM_PROVIDER", "none")
    with TestClient(app) as c:
        r = c.post("/ask", json={"question": "What is OCR?"})
        assert r.status_code == 503
        assert c.get("/health").json()["vector_store"]["reachable"] is False


def test_http_retriever_payload_and_dedupe(client):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        rec = {"id": "a1", "text": "Paper was first made in China.", "score": 0.8, "metadata": {}, "created_at": 1.0}
        dup = {**rec, "id": "a2", "text": "paper was first made in China", "score": 0.79}
        other = {"id": "b1", "text": "Another passage about paper mills in Europe.", "score": 0.5, "metadata": {}}
        return httpx.Response(200, json={"query": "q", "results": [rec, dup, other]})

    transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.app.state.retriever = HttpRetriever("http://vector-store:8003", client=transport_client)
    body = client.post("/ask", json={"question": "When was paper made?", "top_k": 5, "source": "s1"}).json()
    assert seen["url"] == "http://vector-store:8003/search"
    assert b'"source":"s1"' in seen["body"].replace(b" ", b"")
    assert [s["id"] for s in body["sources"]] == ["a1", "b1"]  # 대소문자·문장부호만 다른 a2는 빠진다
    assert body["sources"][0]["title"] == "Paper was first made in China."


def test_make_title():
    assert make_title({"text": "one two three", "metadata": {"title": "T"}}) == "T"
    assert make_title({"text": "a b c d e f g h i j"}) == "a b c d e f g h…"


def test_dedupe_same_card_title_keeps_best_score():
    from app.pipeline import dedupe

    results = [
        {"id": "new", "text": "A dense loaf usually means the yeast was tired.", "chunk_index": 0, "metadata": {"title": "HOW BREAD FAILS"}},
        {"id": "old", "text": "A dense lcaf usualy means the yeast was tired.", "chunk_index": 0, "metadata": {"title": "How Bread Fails"}},
        {"id": "part2", "text": "Second part of the same long card.", "chunk_index": 1, "metadata": {"title": "HOW BREAD FAILS"}},
    ]
    assert [r["id"] for r in dedupe(results)] == ["new", "part2"]


def test_anthropic_without_key_fails_at_startup(monkeypatch):
    from app.config import load_settings

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("RAG_LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_translation_uses_first_line(client):
    client.app.state.llm = FakeLLM(translation='"yeast water temperature"\n(translated)', answer="ok [1]")
    body = client.post("/ask", json={"question": "효모 물 온도"}).json()
    assert body["search_query"] == "yeast water temperature"
