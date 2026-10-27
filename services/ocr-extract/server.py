"""
OCR 서버 (포트 8002)

다른 컨테이너에서 http://ocr-extract:8002 로 호출한다.
    POST /ocr     프레임 이미지 한 장 -> 새로 인식된 카드 목록 (vector-store로도 저장 요청)
    POST /reset   중복 기록 초기화 (새 세션 시작할 때)
    GET  /health  살아있는지 확인

실행 (저장소 루트에서):
    docker compose up --build ocr-extract
"""
import logging
import os

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

import ocr_module

VECTOR_STORE_URL = os.getenv("VECTOR_STORE_URL", "http://vector-store:8003").rstrip("/")

log = logging.getLogger("uvicorn.error")
app = FastAPI(title="OCR", version="1.1")


def to_document(card, session, frame_id):
    """OCR 카드 한 장 -> vector-store POST /documents 요청 형식"""
    doc = {
        "text": f"{card['title']}\n{card['text']}",
        "source": "ocr-extract",
        "metadata": {
            "title": card["title"],
            "confidence": card["confidence"],
            "ocr_at": card["timestamp"],
        },
    }
    if frame_id:
        doc["frame_id"] = frame_id
    if session:
        doc["metadata"]["session"] = session
    return doc


async def send_to_vector_store(cards, session, frame_id):
    """인식한 카드들을 vector-store에 한 번에 저장 요청. 실패해도 OCR 응답은 그대로 돌려준다"""
    items = [to_document(c, session, frame_id) for c in cards]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{VECTOR_STORE_URL}/documents/batch", json={"items": items})
            r.raise_for_status()
        return True
    except Exception as e:
        log.warning("vector-store 저장 요청 실패: %s", e)
        return False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr")
async def ocr(
    file: UploadFile = File(...),
    session: str | None = Form(None),
    frame_id: str | None = Form(None),
):
    data = await file.read()
    if ocr_module.to_image(data) is None:
        raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다 (jpg/png만 가능)")
    # OCR은 몇 초 걸리므로 다른 요청(/health 등)이 막히지 않게 별도 스레드에서 돌린다
    cards = await run_in_threadpool(ocr_module.extract, data)
    stored = await send_to_vector_store(cards, session, frame_id) if cards else None
    return {"count": len(cards), "cards": cards, "stored": stored}


@app.post("/reset")
def reset():
    ocr_module.reset()
    return {"status": "reset"}
