"""
OCR 서버 (포트 8002)

다른 컨테이너에서 http://ocr-extract:8002 로 호출한다.
    POST /ocr     프레임 이미지 한 장 -> 새로 인식된 카드 목록
    POST /reset   중복 기록 초기화 (새 세션 시작할 때)
    GET  /health  살아있는지 확인

실행 (저장소 루트에서):
    docker compose up --build ocr-extract
"""
from fastapi import FastAPI, File, HTTPException, UploadFile

import ocr_module

app = FastAPI(title="OCR", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    data = await file.read()
    if ocr_module.to_image(data) is None:
        raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다 (jpg/png만 가능)")
    cards = ocr_module.extract(data)
    return {"count": len(cards), "cards": cards}


@app.post("/reset")
def reset():
    ocr_module.reset()
    return {"status": "reset"}
