# rag-chat — RAG · 챗봇

- 담당: 우진
- 할 일: 저장된 원문으로 질문에 답변
- 브랜치: `base/rag-chat` → `feature/rag-chat-<기능>`
- 컨테이너 주소: `http://rag-chat:8004` (포트 8004, `0.0.0.0`에서 열기)

## 작업 규칙

- 이 서비스의 모든 파일(코드, `Dockerfile`, `requirements.txt` 등)은 **이 폴더(`services/rag-chat/`) 안에만** 둔다.
- 이 폴더의 `Dockerfile`로 컨테이너를 만들어 실행한다. 호스트 PC에 직접 설치해 돌리지 않는다.
- 실행: 저장소 루트에서 `docker compose up --build rag-chat`
- 다른 서비스는 컨테이너 주소(예: `http://ocr-extract:8002`)로 부른다. `localhost`가 아니다.

## 구성

| 항목 | 내용 |
|---|---|
| 서버 | FastAPI + uvicorn (포트 8004) |
| 검색 | vector-store `POST /search` 호출. 임베딩은 vector-store가 한다 (같은 모델 보장) |
| LLM | 컨테이너 안의 작은 모델 `Qwen2.5-1.5B-Instruct` (4비트 GGUF, 약 1GB)를 llama.cpp로 CPU에서 돌린다. 키·비용 없음. 사전학습 모델을 가져다 쓰기만 함 |
| 호출하는 쪽 | dashboard 서버 (`/api/ask` → `http://rag-chat:8004/ask`). 브라우저가 직접 부르지 않으므로 CORS는 열지 않는다 |

처리 흐름:

```
질문 ─▶ ① 검색어 만들기 ─▶ ② vector-store 검색 ─▶ ③ 중복 정리 ─▶ ④ 답변 생성 ─▶ 답변 + 출처
        한국어면 LLM으로      top 10, 점수 0.25 미만 버림  같은 문장·같은 카드   근거 없으면 LLM 안 부름
        영어 검색어로 변환                                  하나만 남김
```

①이 필요한 이유: vector-store의 임베딩 모델(`all-MiniLM-L6-v2`)이 영어 전용이라 한국어 질문으로는 영어 원문이 거의 검색되지 않는다.

모델을 준비하지 못하면(내려받기 실패 등) 서비스는 멈추지 않고 LLM 없이 뜬다. 이때는 번역·답변 생성 없이 가장 관련 있는 원문을 그대로 돌려주고, `/health`의 `llm.error`에 이유가 나온다.

```
services/rag-chat/
├── Dockerfile
├── requirements.txt        실행 의존성
├── requirements-dev.txt    테스트 의존성 (pytest)
├── pytest.ini
├── app/
│   ├── main.py             API (/ask, /health)
│   ├── pipeline.py         검색어 변환 → 검색 → 중복 정리 → 답변
│   ├── retriever.py        vector-store 호출 + mock 검색
│   ├── llm.py              LLM 호출 (로컬 모델 · Anthropic 선택)
│   ├── prompt.py           프롬프트 · 제목 만들기
│   ├── config.py           환경 변수
│   └── sample_data.json    mock 검색 · 시드용 샘플 영어 원문
├── scripts/seed.py         샘플 원문을 vector-store에 넣기
└── tests/test_api.py
```

## 실행

```bash
# 저장소 루트에서
docker compose up --build rag-chat
```

- 첫 빌드는 llama.cpp 컴파일과 모델(약 1GB) 내려받기 때문에 몇 분 걸린다. 모델은 빌드할 때 이미지에 넣어 둔다.
- 실행 중 메모리를 약 2GB 쓴다. Docker Desktop의 메모리 한도(Settings → Resources)가 작으면 늘린다.
- 답변은 CPU로 만들어서 질문 하나에 수 초~수십 초 걸린다 (PC 사양에 따라 다름). 한국어 질문은 번역 + 답변으로 모델을 두 번 부른다.
- 확인: http://localhost:8004/health (내 PC 브라우저 기준) → `retriever`, `vector_store.reachable`, `llm.ready` 값을 본다.
- API 눌러 보기: http://localhost:8004/docs
- 코드를 고치면 `Ctrl+C` 후 같은 명령으로 다시 빌드한다.

### vector-store 없이 혼자 확인 (mock)

루트 `.env`에 아래 한 줄을 넣고 실행하면 `app/sample_data.json`의 샘플 원문으로 검색을 흉내 낸다. vector-store를 띄우지 않고 rag-chat만 고칠 때 쓴다.

```
RAG_RETRIEVER=mock
```

mock은 영어 단어 겹침으로 찾는다. 로컬 모델이 준비돼 있으면 한국어 질문도 영어 검색어로 바뀌어 찾아진다. 모델 없이(`RAG_LLM_PROVIDER=none`) 빠르게 확인할 때는 영어로 질문한다 (예: `What water temperature kills yeast?`).

### vector-store와 연동

내 브랜치에 `services/vector-store/` 코드가 있어야 한다. 없으면 `base/rag-chat`에 dev를 먼저 받아온다 (`git switch base/rag-chat && git pull && git pull origin dev && git push`).

```bash
docker compose up -d --build vector-store
docker compose run --rm rag-chat python scripts/seed.py   # 샘플 원문 넣기 (여러 번 해도 중복은 안 쌓임)
docker compose up --build rag-chat
```

vector-store는 볼륨이 없어서 다시 빌드하면 데이터가 비므로, 그때마다 시드를 다시 넣는다.

### 테스트

실제 모델과 vector-store 없이 mock과 가짜 객체로 돈다.

```bash
docker compose run --rm rag-chat pytest -q
```

### 환경 변수 (루트 `.env`, 모두 선택)

루트 `.env`는 모든 서비스가 같이 읽으므로 rag-chat 전용 값은 `RAG_` 접두사를 붙였다. `.env`는 커밋하지 않는다.

| 이름 | 기본값 | 설명 |
|---|---|---|
| `RAG_LLM_PROVIDER` | `local` | `local`(작은 모델) · `anthropic`(Claude API) · `none`(LLM 없이 관련 원문만) |
| `RAG_LOCAL_MODEL_FILE` | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | 쓸 GGUF 파일. 없으면 시작할 때 아래 저장소에서 받는다 |
| `RAG_LOCAL_MODEL_REPO` | `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | 모델을 받을 Hugging Face 저장소. 비우면 받지 않는다 |
| `RAG_LOCAL_THREADS` | (자동) | 모델이 쓸 CPU 스레드 수 |
| `RAG_LOCAL_CTX` | `4096` | 한 번에 다룰 토큰 수 (질문 + 원문 + 답변) |
| `RAG_ANTHROPIC_MODEL` | `claude-haiku-5-5` | `anthropic`일 때만. `ANTHROPIC_API_KEY`도 필요 |
| `RAG_RETRIEVER` | `http` | `mock`이면 vector-store 없이 샘플 원문으로 검색 |
| `RAG_VECTOR_STORE_URL` | `http://vector-store:8003` | |
| `RAG_SEARCH_TOP_K` | `10` | vector-store에서 받아 올 개수 (중복 정리 전) |
| `RAG_MIN_SCORE` | `0.25` | 이 점수(코사인 유사도) 미만은 버린다. 실제 OCR 데이터로 다시 맞출 것 |

## 주고받는 데이터

모든 요청·응답은 JSON.

### 질문 — `POST /ask` (dashboard → rag-chat)

요청:
```json
{"question": "효모가 죽는 물 온도는?", "top_k": 5, "source": null}
```
`question`만 필수. `top_k`는 답변 근거로 쓸 원문 개수(1~20, 기본 5), `source`는 vector-store의 source 필터를 그대로 전달한다.

응답:
```json
{
  "answer": "약 60도보다 뜨거운 물이면 효모가 죽어요 [1].",
  "sources": [
    {"n": 1, "id": "a1b2...", "title": "Why Bread Rises", "text": "Yeast feeds on ...", "score": 0.71,
     "created_at": 1761540000.12, "frame_id": "frame_000123"}
  ],
  "found": true,
  "search_query": "water temperature that kills yeast"
}
```

- dashboard 화면이 쓰는 `{answer, sources: [{id, title}]}` 형식을 그대로 포함한다. 나머지 필드는 필요할 때만 쓰면 된다.
- `n`은 답변 속 `[1]` 인용 번호다. vector-store의 `id`는 32자리라서 화면 출처 표시는 `n`을 쓰는 것을 권한다.
- `title`: 원문 `metadata.title`이 있으면 그것, 없으면 원문 앞 8단어.
- 같은 `metadata.title` + `chunk_index`인 원문은 점수가 높은 하나만 남긴다. ocr-extract가 같은 카드를 더 정확히 읽으면 같은 title로 다시 보내기 때문이다.
- `found: false`면 `sources`는 비어 있고 `answer`는 "저장된 원문에서 관련 내용을 찾지 못했어요." (영어 질문이면 영어)
- `search_query`는 실제로 검색한 문장 (디버깅용).

오류:

| 코드 | 언제 |
|---|---|
| 400 | `question`이 비어 있음 |
| 422 | 요청 형식 오류 (`question` 없음, `top_k` 범위 밖 등) |
| 502 | LLM 호출 실패 (모델 실행 오류, API 키 오류 등) |
| 503 | vector-store에 연결할 수 없음 |

### 상태 — `GET /health`

```json
{"service": "rag-chat", "ok": true, "retriever": "http",
 "vector_store": {"reachable": true, "url": "http://vector-store:8003", "status": "ok", "model": "...", "dim": 384},
 "llm": {"provider": "local", "ready": true, "model": "qwen2.5-1.5b-instruct-q4_k_m.gguf", "error": null}}
```

### rag-chat이 부르는 API

- vector-store `POST /search` `{query, top_k, min_score, source}` — 형식은 `services/vector-store/README.md` 참고.

## 다른 서비스와 연결 상태

- **dashboard**: `/api/ask`가 `http://rag-chat:8004/ask`를 부르고 `n`·`id`·`title`을 화면에 쓴다. 응답을 **60초**까지 기다리므로 답변 길이를 300토큰으로 제한했다. 느린 PC에서 시간 초과(502)가 나면 dashboard 쪽 시간 제한을 늘리거나 `RAG_LLM_PROVIDER=none`으로 확인한다.
- **ocr-extract → vector-store**: 카드 제목을 `metadata.title`에 넣어 저장한다. rag-chat은 이 값을 출처 제목과 중복 정리(같은 카드를 다시 읽은 경우)에 쓴다.

## 협의 필요

- **진아 (vector-store)**: 세션별 검색이 필요하면 `metadata.session` 필터 추가 (ocr-extract가 이미 `metadata.session`을 넣고 있다).
