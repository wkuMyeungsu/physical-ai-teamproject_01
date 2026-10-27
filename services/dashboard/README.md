# dashboard — 대시보드

- 담당: 명수
- 할 일: QR 코드 표시, 실시간 저장 현황, RAG 검색 화면
- 브랜치: `base/dashboard` → `feature/dashboard-<기능>`
- 컨테이너 주소: `http://dashboard:8000` (포트 8000, `0.0.0.0`에서 열기)

## 작업 규칙

- 이 서비스의 모든 파일(코드, `Dockerfile`, `requirements.txt` 등)은 **이 폴더(`services/dashboard/`) 안에만** 둔다.
- 이 폴더의 `Dockerfile`로 컨테이너를 만들어 실행한다. 호스트 PC에 직접 설치해 돌리지 않는다.
- 실행: 저장소 루트에서 `docker compose up --build dashboard`
- 다른 서비스는 컨테이너 주소(예: `http://ocr-extract:8002`)로 부른다. `localhost`가 아니다.

## 실행

FastAPI 서버 1개가 화면(`static/`)과 API(`/api/*`)를 함께 낸다. 브라우저는 `localhost:8000`만 부르고, 다른 서비스 호출은 이 서버가 대신한다.

```
services/dashboard/
  Dockerfile         python:3.12-slim + uvicorn, 포트 8000
  requirements.txt   fastapi, uvicorn
  app.py             /api/health, 나머지 경로는 static/
  static/index.html  화면
```

```bash
docker compose up --build dashboard     # 저장소 루트에서
```

- 화면: http://localhost:8000
- 상태 확인: http://localhost:8000/api/health → `{"service":"dashboard","ok":true}`
- 코드를 고치면 `Ctrl+C` 후 같은 명령으로 다시 빌드한다.

## 주고받는 데이터

<!-- 받는 입력 / 내보내는 출력 형식을 적는다 -->
