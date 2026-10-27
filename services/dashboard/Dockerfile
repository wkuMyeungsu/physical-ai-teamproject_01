FROM python:3.12-slim

WORKDIR /app

# 의존성 먼저 설치해 코드만 바뀔 때는 캐시를 재사용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
