# ocr-extract — OCR

- 담당: 도은
- 할 일: 이미지 → 영어 텍스트 추출, 잘린 카드 걸러내기
- 브랜치: `base/ocr-extract` → `feature/ocr-extract-<기능>`
- 컨테이너 주소: `http://ocr-extract:8002` (포트 8002, `0.0.0.0`에서 열기)

## 작업 규칙

- 이 서비스의 모든 파일(코드, `Dockerfile`, `requirements.txt` 등)은 **이 폴더(`services/ocr-extract/`) 안에만** 둔다.
- 이 폴더의 `Dockerfile`로 컨테이너를 만들어 실행한다. 호스트 PC에 직접 설치해 돌리지 않는다.
- 실행: 저장소 루트에서 `docker compose up --build ocr-extract`
- 다른 서비스는 컨테이너 주소(예: `http://ocr-extract:8002`)로 부른다. `localhost`가 아니다.

## 실행

- 모델: PaddleOCR **PP-OCRv5 영어 인식 모델**, RapidOCR(ONNX Runtime, CPU)로 추론
- `Dockerfile`: `python:3.12-slim` → `requirements.txt` 설치 → 빌드할 때 OCR 모델 파일을 미리 받아둠 → `uvicorn`으로 8002 포트 실행

```bash
docker compose up --build ocr-extract
```

확인: 브라우저에서 http://localhost:8002/docs (호스트에서 확인할 때만 localhost)

| 파일 | 내용 |
|---|---|
| `server.py` | HTTP API (FastAPI) |
| `ocr_module.py` | 카드 찾기 · 잘린 카드 걸러내기 · OCR · 중복 제거 |

## 주고받는 데이터

**받는 입력** (frame-capture → ocr-extract) — `POST /ocr`, multipart

| 필드 | 필수 | 내용 |
|---|---|---|
| `file` | ✅ | 프레임 이미지 1장 (jpg/png) |
| `session` | | 세션 ID. vector-store `metadata.session`에 붙임 |
| `frame_id` | | 프레임 ID. vector-store `frame_id`에 붙임 |

```python
import httpx
r = httpx.post("http://ocr-extract:8002/ocr",
               files={"file": ("frame.jpg", jpeg_bytes, "image/jpeg")},
               data={"session": "a8f3k2"})
```

**내보내는 출력 ①** (ocr-extract → frame-capture) — 응답: 새로 인식된 카드 목록

```json
{
  "count": 1,
  "cards": [
    {
      "title": "HOW BREAD FAILS",
      "text": "A dense loaf usually means the yeast was tired ...",
      "confidence": 0.982,
      "timestamp": "2026-10-27T14:03:21"
    }
  ],
  "stored": true
}
```

- `stored`: vector-store 저장 요청 성공 `true` / 실패 `false` / 보낼 카드가 없음 `null`
- 걸러내는 것: 흔들린 프레임, 사진 끝에 걸린 카드, 컨베이어 영역 끝에서 잘린 카드(정상 폭보다 8% 이상 좁은 카드)
- 같은 카드는 한 번만 보냄. 단, 더 정확하게 읽히면 같은 `title`로 다시 보냄 (vector-store가 중복을 한 번 더 거름)
- 카드가 없으면 `{"count": 0, "cards": [], "stored": null}`
- 이미지가 아니면 `400`

**내보내는 출력 ②** (ocr-extract → vector-store) — 카드가 인식되면 `POST http://vector-store:8003/documents/batch`

```json
{
  "items": [
    {
      "text": "HOW BREAD FAILS\nA dense loaf usually means the yeast was tired ...",
      "source": "ocr-extract",
      "frame_id": "frame_000123",
      "metadata": {"title": "HOW BREAD FAILS", "confidence": 0.982, "ocr_at": "2026-10-27T14:03:21", "session": "a8f3k2"}
    }
  ]
}
```

- `frame_id`, `metadata.session`은 입력으로 받았을 때만 붙음
- vector-store가 꺼져 있어도 OCR 응답은 정상으로 돌려줌 (`stored: false`, 로그에 경고)
- 주소는 환경 변수 `VECTOR_STORE_URL`로 바꿀 수 있음 (기본값 `http://vector-store:8003`)

**기타**
- `POST /reset` — 중복 기록 초기화 (새 세션 시작할 때)
- `GET /health` — 상태 확인, `{"status": "ok"}`
