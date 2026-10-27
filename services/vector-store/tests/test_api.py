"""API 테스트. 모델 다운로드 없이 돌도록 해시 임베딩을 쓴다.

컨테이너 안에서 실행:
  docker compose run --rm -e EMBED_BACKEND=hash -e DB_PATH=:memory: vector-store pytest -q
"""
import os

os.environ["EMBED_BACKEND"] = "hash"
os.environ["DB_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.textproc import chunk_text, clean_ocr_text, is_meaningful

ARTICLE = (
    "Large language models are trained on vast amounts of text. "
    "They can answer questions, summarize documents, and translate languages. "
    "However, they sometimes produce confident but incorrect statements."
)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.delete("/documents", params={"confirm": "true"})
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["dim"] == 384


def test_ingest_and_search(client):
    r = client.post("/documents", json={"text": ARTICLE, "source": "test", "frame_id": "f1"})
    body = r.json()
    assert r.status_code == 200
    assert body["stored"] >= 1

    r = client.post("/search", json={"query": "translate languages and summarize", "top_k": 3})
    results = r.json()["results"]
    assert results and "translate" in results[0]["text"]
    assert results[0]["frame_id"] == "f1"
    assert results[0]["score"] > 0

    assert client.get("/search", params={"q": "language models"}).json()["results"]


def test_exact_duplicate_skipped(client):
    client.post("/documents", json={"text": ARTICLE})
    # 연속 프레임: 대소문자·공백·줄바꿈만 다른 같은 문장
    noisy = ARTICLE.upper().replace(". ", ".\n  ")
    body = client.post("/documents", json={"text": noisy}).json()
    assert body["stored"] == 0
    assert all(c["status"] == "duplicate" for c in body["chunks"])


def test_near_duplicate_skipped(client):
    client.post("/documents", json={"text": ARTICLE})
    # OCR이 단어 하나를 잘못 읽은 경우 → 벡터가 거의 같으므로 near_duplicate
    variant = ARTICLE.replace("vast", "vasl")
    body = client.post("/documents", json={"text": variant}).json()
    assert body["stored"] == 0
    assert {c["status"] for c in body["chunks"]} == {"near_duplicate"}


def test_garbage_filtered(client):
    body = client.post("/documents", json={"text": "| ~ 3# ."}).json()
    assert body["stored"] == 0


def test_stats_list_delete(client):
    client.post("/documents", json={"text": ARTICLE})
    s = client.get("/stats").json()
    assert s["chunks"] >= 1 and s["documents"] == 1

    items = client.get("/documents").json()["items"]
    rid = items[0]["id"]
    assert client.get(f"/documents/{rid}").json()["id"] == rid
    assert client.delete(f"/documents/{rid}").status_code == 200
    assert client.get(f"/documents/{rid}").status_code == 404
    assert client.delete("/documents").status_code == 400  # confirm 없으면 거부


def test_batch_and_embed(client):
    r = client.post(
        "/documents/batch",
        json={"items": [{"text": ARTICLE}, {"text": "The weather today is sunny with a light breeze."}]},
    )
    assert len(r.json()) == 2
    e = client.post("/embed", json={"texts": ["hello world"]}).json()
    assert len(e["vectors"][0]) == e["dim"]


def test_textproc():
    assert clean_ocr_text("inter-\nnational   news\nhere") == "international news here"
    long = " ".join(f"Sentence number {i} is here." for i in range(60))
    chunks = chunk_text(long, max_chars=200)
    assert len(chunks) > 1 and all(len(c) <= 200 for c in chunks)
    assert not is_meaningful("ab ;;")
    assert is_meaningful("This is a real sentence.")
