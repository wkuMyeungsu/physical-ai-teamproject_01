"""샘플 영어 원문(app/sample_data.json)을 vector-store에 넣는다.

vector-store는 볼륨이 없어서 다시 빌드하면 데이터가 비므로, 테스트 전에 빠르게 채울 때 쓴다.
같은 내용을 여러 번 넣어도 vector-store가 중복으로 걸러서 다시 저장되지 않는다.

실행 (저장소 루트에서, vector-store가 먼저 떠 있어야 한다):
    docker compose up -d vector-store
    docker compose run --rm rag-chat python scripts/seed.py
"""
import json
import os
import sys
from pathlib import Path

import httpx

URL = os.getenv("RAG_VECTOR_STORE_URL", "http://vector-store:8003").rstrip("/")
DATA = Path(__file__).resolve().parent.parent / "app" / "sample_data.json"


def main() -> int:
    passages = json.loads(DATA.read_text(encoding="utf-8"))
    items = [{"text": p["text"], "source": "rag-chat-seed", "metadata": {"title": p["title"]}} for p in passages]
    try:
        r = httpx.post(f"{URL}/documents/batch", json={"items": items}, timeout=120)
        r.raise_for_status()
    except httpx.HTTPError as e:
        print(f"실패: {URL} ({type(e).__name__}: {e})", file=sys.stderr)
        return 1
    results = r.json()
    stored = sum(x["stored"] for x in results)
    skipped = sum(x["skipped"] for x in results)
    print(f"{URL}: 저장 {stored}개, 건너뜀 {skipped}개 (중복·잡음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
