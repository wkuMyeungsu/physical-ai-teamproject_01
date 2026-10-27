# vector-store — 임베딩 · DB 적재

- 담당: 진아
- 할 일: 텍스트 임베딩, 텍스트+벡터 실시간 저장
- 브랜치: `base/vector-store` → `feature/vector-store-<기능>`
- 컨테이너 주소: `http://vector-store:8003` (포트 8003, `0.0.0.0`에서 열기)

## 작업 규칙

- 이 서비스의 모든 파일(코드, `Dockerfile`, `requirements.txt` 등)은 **이 폴더(`services/vector-store/`) 안에만** 둔다.
- 이 폴더의 `Dockerfile`로 컨테이너를 만들어 실행한다. 호스트 PC에 직접 설치해 돌리지 않는다.
- 실행: 저장소 루트에서 `docker compose up --build vector-store`
- 다른 서비스는 컨테이너 주소(예: `http://ocr-extract:8002`)로 부른다. `localhost`가 아니다.

## 구성

| 항목 | 내용 |
|---|---|
| 서버 | FastAPI + uvicorn |
| 임베딩 모델 | `sentence-transformers/all-MiniLM-L6-v2` (영어, 384차원, CPU). 사전학습 모델을 가져다 쓰기만 함 |
| 저장 | SQLite 파일(`/app/data/vectors.db`) + 검색용 메모리 행렬(코사인 유사도) |
| 처리 흐름 | OCR 텍스트 정리 → 문장 단위 청크(최대 500자) → 잡음·중복 거르기 → 임베딩 → 저장 → 실시간 이벤트 |

연속 프레임에서 같은 화면이 계속 들어오므로 **중복을 두 단계로 거른다.**

1. `duplicate`: 대소문자·문장부호·공백만 다른 같은 문장 (해시 비교, 임베딩 전에 거름)
2. `near_duplicate`: OCR이 글자 몇 개를 다르게 읽은 거의 같은 문장 (코사인 유사도 ≥ 0.95)

```
services/vector-store/
├── Dockerfile
├── requirements.txt        실행 의존성
├── requirements-dev.txt    테스트 의존성 (pytest, httpx)
├── app/
│   ├── main.py             API
│   ├── embedder.py         텍스트 → 벡터
│   ├── store.py            SQLite 저장 · 검색
│   └── textproc.py         OCR 텍스트 정리 · 청크 · 중복 판별
└── tests/test_api.py
```

## 실행

```bash
# 저장소 루트에서
docker compose up --build vector-store
```

- 첫 빌드는 torch(CPU)와 모델을 받느라 몇 분 걸린다. 모델은 빌드할 때 이미지에 넣어 둔다.
- 뜨면 http://localhost:8003/docs 에서 모든 API를 눌러 볼 수 있다 (내 PC 브라우저 기준).
- 테스트 (모델 없이 해시 임베딩으로 빠르게):

```bash
docker compose run --rm -e EMBED_BACKEND=hash -e DB_PATH=:memory: vector-store pytest -q
```

### 환경 변수 (선택)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 임베딩 모델. 바꾸면 기존 DB와 섞이지 않게 시작 시 막는다 |
| `EMBED_BACKEND` | `sentence-transformers` | `hash`면 모델 없이 동작 (테스트용) |
| `DB_PATH` | `/app/data/vectors.db` | SQLite 파일 위치 |
| `CHUNK_MAX_CHARS` | `500` | 청크 최대 글자 수 |
| `DEDUP_THRESHOLD` | `0.95` | 이 유사도 이상이면 near_duplicate로 건너뜀 |

> ⚠️ 지금 `docker-compose.yml`에는 볼륨이 없어서 `--build`로 컨테이너를 새로 만들면 저장된 데이터가 사라진다.
> 데이터를 유지하려면 팀장과 상의해 `vector-store`에 `volumes: ["vector-data:/app/data"]` 추가가 필요하다.

## 주고받는 데이터

모든 요청·응답은 JSON. 시각은 unix 초(`float`).

### 저장 — `POST /documents` (ocr-extract → vector-store)

요청:
```json
{
  "text": "Large language models are trained on vast amounts of text. ...",
  "source": "ocr-extract",
  "frame_id": "frame_000123",
  "metadata": {"session": "abc", "confidence": 0.91}
}
```
`text`만 필수. 나머지는 선택.

응답:
```json
{
  "doc_id": "9f1c...",
  "stored": 1,
  "skipped": 1,
  "chunks": [
    {"status": "stored", "text": "Large language models ...", "id": "a1b2...", "duplicate_of": null, "similarity": null},
    {"status": "near_duplicate", "text": "...", "id": null, "duplicate_of": "c3d4...", "similarity": 0.97}
  ]
}
```
`status`: `stored` | `duplicate` | `near_duplicate` | `too_short`(OCR 잡음)

여러 건을 한 번에: `POST /documents/batch` — `{"items": [<위 요청>, ...]}` → 응답 배열

### 검색 — `POST /search` (rag-chat · dashboard → vector-store)

요청:
```json
{"query": "What are the limits of language models?", "top_k": 5, "min_score": 0.3, "source": null}
```
응답 (점수 높은 순, `score`는 코사인 유사도 -1~1):
```json
{
  "query": "What are the limits of language models?",
  "results": [
    {"id": "a1b2...", "doc_id": "9f1c...", "chunk_index": 0, "text": "...", "source": "ocr-extract",
     "frame_id": "frame_000123", "metadata": {}, "created_at": 1761540000.12, "score": 0.71}
  ]
}
```
간단히: `GET /search?q=...&top_k=5&min_score=0.3`

### 임베딩만 — `POST /embed`

`{"texts": ["..."]}` → `{"model": "...", "dim": 384, "vectors": [[...], ...]}` (저장 안 함)

### 대시보드용

| API | 설명 |
|---|---|
| `GET /stats` | `{"chunks", "documents", "last_stored_at", "model", "dim", "uptime_sec"}` |
| `GET /documents?limit=50&offset=0&since=<unix초>` | 최근 저장 목록 (최신순) `{"total", "items": [...]}` |
| `GET /documents/{id}` | 한 건 조회 |
| `GET /events` | **SSE 실시간 스트림**. 저장될 때마다 `data: {"type": "stored", "record": {...}, "total": 12}` |
| `DELETE /documents/{id}` | 한 건 삭제 |
| `DELETE /documents?confirm=true` | 전체 삭제 |
| `GET /health` | `{"status": "ok", "model", "dim"}` |

SSE 이벤트 `type`: `hello`(연결 직후) · `stored` · `deleted` · `cleared`. 15초마다 `: ping` 주석이 온다.

```js
// dashboard 예시 (브라우저에서 부를 때는 http://localhost:8003, 컨테이너끼리는 http://vector-store:8003)
const es = new EventSource("http://localhost:8003/events");
es.onmessage = (e) => { const ev = JSON.parse(e.data); if (ev.type === "stored") console.log(ev.total, ev.record.text); };
```
