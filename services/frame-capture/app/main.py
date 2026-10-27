"""Stages 1-3: dashboard page, QR session pairing, and phone -> server -> dashboard live video."""
import base64
import io
import logging
import os
import secrets
import string
import time
from pathlib import Path

import qrcode
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

log = logging.getLogger("uvicorn.error")

STATIC = Path(__file__).parent / "static"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
REDIS_URL = os.getenv("REDIS_URL", "")
FRAME_QUEUE_MAXLEN = 50  # keep only the newest frames per session for the OCR worker (stage 4)
SESSION_TTL = 60 * 60 * 6

app = FastAPI(title="Conveyor OCR Demo")

redis = None
if REDIS_URL:
    import redis.asyncio as aioredis

    redis = aioredis.from_url(REDIS_URL)


class Session:
    def __init__(self, sid: str):
        self.id = sid
        self.created = time.time()
        self.dashboard: WebSocket | None = None
        self.phone: WebSocket | None = None
        self.frames = 0


# Live WebSocket objects can't live in Redis, so the session table is an in-process dict.
sessions: dict[str, Session] = {}


def new_session_id(n: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.digits
    while True:
        sid = "".join(secrets.choice(alphabet) for _ in range(n))
        if sid not in sessions:
            return sid


def prune_sessions() -> None:
    cutoff = time.time() - SESSION_TTL
    for sid in [s.id for s in sessions.values() if s.created < cutoff and not s.dashboard and not s.phone]:
        del sessions[sid]


def qr_png_base64(data: str) -> str:
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def notify_dashboard(s: Session, msg: dict) -> None:
    if s.dashboard:
        try:
            await s.dashboard.send_json(msg)
        except Exception:
            s.dashboard = None


# ---------- Stage 1: pages ----------

@app.get("/")
async def dashboard_page():
    return FileResponse(STATIC / "index.html")


@app.get("/phone")
async def phone_page():
    return FileResponse(STATIC / "phone.html")


@app.get("/health")
async def health():
    redis_ok = None
    if redis:
        try:
            redis_ok = await redis.ping()
        except Exception:
            redis_ok = False
    return {"ok": True, "sessions": len(sessions), "redis": redis_ok}


# ---------- Stage 2: session + QR pairing ----------

@app.post("/api/session")
async def create_session(request: Request):
    prune_sessions()
    sid = new_session_id()
    sessions[sid] = Session(sid)
    base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    phone_url = f"{base}/phone?session={sid}"
    return {"session_id": sid, "phone_url": phone_url, "qr_png": qr_png_base64(phone_url)}


@app.get("/api/session/{sid}")
async def get_session(sid: str):
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "unknown session")
    return {"session_id": sid, "paired": s.phone is not None, "frames": s.frames}


@app.websocket("/ws/dashboard/{sid}")
async def ws_dashboard(ws: WebSocket, sid: str):
    s = sessions.get(sid)
    await ws.accept()
    if not s:
        await ws.close(code=4404)  # accept first so the browser sees the code, not a bare 403
        return
    s.dashboard = ws
    await ws.send_json({"type": "paired" if s.phone else "waiting", "session_id": sid})
    try:
        while True:
            await ws.receive_text()  # keepalive pings from the dashboard; nothing else expected
    except WebSocketDisconnect:
        pass
    finally:
        if s.dashboard is ws:
            s.dashboard = None


# ---------- Stage 3: phone camera frames ----------

@app.websocket("/ws/phone/{sid}")
async def ws_phone(ws: WebSocket, sid: str):
    s = sessions.get(sid)
    await ws.accept()
    if not s:
        await ws.close(code=4404)  # accept first so the browser sees the code, not a bare 403
        return
    if s.phone:  # a newer phone connection replaces the old one
        try:
            await s.phone.close(code=4409)
        except Exception:
            pass
    s.phone = ws
    log.info("session %s: phone paired", sid)
    await notify_dashboard(s, {"type": "paired", "session_id": sid})
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            frame = msg.get("bytes")
            if not frame:
                continue  # text messages (e.g. hello/ping) are ignored
            s.frames += 1
            if s.dashboard:
                try:
                    await s.dashboard.send_bytes(frame)
                except Exception:
                    s.dashboard = None
            if redis:
                try:
                    key = f"frames:{sid}"
                    await redis.lpush(key, frame)
                    await redis.ltrim(key, 0, FRAME_QUEUE_MAXLEN - 1)
                except Exception as e:
                    log.warning("redis push failed: %s", e)
            if s.frames % 10 == 0:
                await notify_dashboard(s, {"type": "status", "frames": s.frames})
    except WebSocketDisconnect:
        pass
    finally:
        if s.phone is ws:
            s.phone = None
            log.info("session %s: phone disconnected", sid)
            await notify_dashboard(s, {"type": "phone_disconnected"})
