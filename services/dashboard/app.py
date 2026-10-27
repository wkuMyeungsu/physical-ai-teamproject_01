import logging
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("uvicorn.error")

FRAME_CAPTURE_URL = os.getenv("FRAME_CAPTURE_URL", "http://frame-capture:8001")
# frame-capture는 PUBLIC_BASE_URL이 없으면 요청의 Host로 phone_url을 만든다.
# 컨테이너 주소(frame-capture:8001) 대신 브라우저·휴대폰이 닿는 주소가 들어가게 Host를 바꿔 보낸다.
FRAME_CAPTURE_PUBLIC_HOST = os.getenv("FRAME_CAPTURE_PUBLIC_HOST", "localhost:8001")

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


# API 라우트를 먼저 등록하고, 나머지 경로는 static/ 화면으로
app.mount("/", StaticFiles(directory="static", html=True), name="static")
