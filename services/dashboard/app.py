from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="dashboard")


@app.get("/api/health")
def health():
    return {"service": "dashboard", "ok": True}


# API 라우트를 먼저 등록하고, 나머지 경로는 static/ 화면으로
app.mount("/", StaticFiles(directory="static", html=True), name="static")
