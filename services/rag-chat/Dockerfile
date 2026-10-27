FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RAG_LOCAL_MODEL_DIR=/app/models \
    RAG_LOCAL_MODEL_REPO=Qwen/Qwen2.5-1.5B-Instruct-GGUF \
    RAG_LOCAL_MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf

WORKDIR /app

# llama-cpp-python은 설치할 때 C++로 컴파일된다 (첫 빌드에 몇 분 걸림)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN CMAKE_ARGS="-DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF" \
    pip install -r requirements.txt -r requirements-dev.txt

# 로컬 LLM 모델(약 1GB)을 빌드할 때 받아 이미지에 넣는다 (시작이 빨라짐).
# 실패해도 빌드는 계속되고, 컨테이너가 시작할 때 다시 받는다.
RUN python -c "import os; from huggingface_hub import hf_hub_download; hf_hub_download(os.environ['RAG_LOCAL_MODEL_REPO'], os.environ['RAG_LOCAL_MODEL_FILE'], local_dir=os.environ['RAG_LOCAL_MODEL_DIR'])" \
    || echo "모델 미리 받기 실패 — 컨테이너 시작 시 다시 받습니다"

COPY pytest.ini ./
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests

EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
