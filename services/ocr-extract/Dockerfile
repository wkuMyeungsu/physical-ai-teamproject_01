FROM python:3.12-slim

# OpenCV 실행에 필요한 시스템 라이브러리
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ocr_module.py server.py ./
# OCR 모델 파일을 빌드할 때 미리 받아둔다 (컨테이너 시작할 때 인터넷 없어도 되게)
RUN python -c "import numpy as np, ocr_module; ocr_module.engine(np.full((64, 256, 3), 255, np.uint8))"

EXPOSE 8002
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]
