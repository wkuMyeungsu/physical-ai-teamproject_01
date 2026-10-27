FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    DB_PATH=/app/data/vectors.db

WORKDIR /app

# CPU 전용 torch를 먼저 깔아 이미지 크기를 줄인다 (GPU 버전은 수 GB)
RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# 임베딩 모델을 빌드할 때 미리 받아 둔다 (첫 실행이 빨라짐). 실패해도 실행 시 다시 받는다.
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['EMBED_MODEL'])" \
    || echo "모델 미리 받기 실패 — 컨테이너 시작 시 다운로드합니다"

COPY app ./app
COPY tests ./tests

EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
