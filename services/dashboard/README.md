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

FastAPI 서버 1개가 화면(`static/`)과 API(`/api/*`)를 함께 낸다. 브라우저의 HTTP 호출은 `localhost:8000`으로만 가고, 다른 서비스 호출은 이 서버가 대신한다. 예외로 실시간 영상 WebSocket은 브라우저가 frame-capture(`:8001`)에 직접 붙는다.

```
services/dashboard/
  Dockerfile         python:3.12-slim + uvicorn, 포트 8000
  requirements.txt   fastapi, uvicorn, httpx
  app.py             /api/health, /api/session(frame-capture 중계), /api/stats(vector-store 중계), 나머지 경로는 static/
  static/index.html  화면
  static/app.js      API 연결부(맨 위) + 화면 갱신
```

```bash
docker compose up --build dashboard frame-capture     # 저장소 루트에서. ① 화면은 frame-capture가 있어야 동작
```

- 화면: http://localhost:8000
- 상태 확인: http://localhost:8000/api/health → `{"service":"dashboard","ok":true}`
- 코드를 고치면 `Ctrl+C` 후 같은 명령으로 다시 빌드한다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `FRAME_CAPTURE_URL` | `http://frame-capture:8001` | 대시보드 서버가 부르는 frame-capture 주소 (컨테이너 주소) |
| `FRAME_CAPTURE_PUBLIC_HOST` | `localhost:8001` | frame-capture에 `PUBLIC_BASE_URL`이 없을 때 QR 주소에 들어갈 호스트 |
| `VECTOR_STORE_URL` | `http://vector-store:8003` | 대시보드 서버가 부르는 vector-store 주소 (컨테이너 주소) |

## 주고받는 데이터

① QR 카메라 연동은 frame-capture, ② 실시간 저장 현황은 vector-store에 연결됐고, ③은 임시 데이터로 동작한다 (`static/app.js`의 `MOCK = { stats: false, ask: true }`). 아래는 화면이 기대하는 형식이다. 각 서비스 API가 정해지면 대시보드 서버(`app.py`)가 그 서비스를 불러 이 형식으로 맞춰 준다.

| 화면 | 대시보드 API | 응답 | 원본 서비스 |
|---|---|---|---|
| ① QR 카메라 연동 | `POST /api/session` | `{ session_id, capture_url, qr_png }` | frame-capture `POST /api/session` 중계 |
| ① 연결 상태·실시간 영상 | (WebSocket 직접) `ws://<호스트>:8001/ws/dashboard/{session_id}` | JSON `{type: waiting\|paired\|status\|phone_disconnected}` + JPEG 바이너리 | frame-capture |
| ② 실시간 저장 현황 | `GET /api/stats` | `{ saved, per_minute, latest: [{ id, no, title, text, saved_at }] }` (latest는 최신순 20개, no는 저장 순번) | vector-store `GET /stats`(documents 수) + `GET /documents`(최근 목록, 최근 1분) 중계 |
| ③ RAG 검색 | `POST /api/ask` `{ question }` | `{ answer, sources: [{ id, title }] }` | rag-chat (연결 전) |

- `capture_url`은 휴대폰이 열 카메라 페이지 주소. 휴대폰 카메라는 HTTPS에서만 열리므로 실제 시연 때는 frame-capture의 `PUBLIC_BASE_URL`에 HTTPS 터널 주소를 넣는다.
- `qr_png`는 frame-capture가 만든 QR PNG의 base64.
- `saved_at`은 ISO 8601 시각 문자열.
- ② 화면 갱신은 2초 간격 폴링이다.
