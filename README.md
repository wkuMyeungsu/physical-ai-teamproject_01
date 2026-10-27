# OCR · 벡터 임베딩 기반 영문 텍스트 추출·검색 파이프라인

웹페이지에 흘러가는 영어 원문을 휴대폰 카메라로 촬영 → OCR로 텍스트 추출 → 임베딩해 DB 저장 → RAG로 검색.

## 폴더 구조

```
docs/                   팀 문서 (git-rules.html 등)
services/               서비스 = 담당자 1명 = 컨테이너 1개
  dashboard/            명수   QR 표시 · 실시간 저장 현황 · RAG 검색 화면
  frame-capture/        대희   QR 카메라 연동, 실시간 영상 → 이미지
  ocr-extract/          도은   이미지 → 영어 텍스트 (잘린 카드 걸러내기)
  vector-store/         진아   텍스트 임베딩 · 실시간 DB 적재
  rag-chat/             우진   저장된 원문으로 질문에 답변
docker-compose.yml      모든 서비스를 한 번에 띄우는 통합 설정
AGENTS.md               협업 규칙 (AI 도구가 읽는 파일, CLAUDE.md도 이것을 불러옴)
```

## 서비스 · 담당 · 브랜치 · 포트

| 서비스 폴더 | 담당 | 기준 브랜치 | 컨테이너 주소 |
|---|---|---|---|
| `services/dashboard/` | 명수 (팀장) | `base/dashboard` | `http://dashboard:8000` |
| `services/frame-capture/` | 대희 | `base/frame-capture` | `http://frame-capture:8001` |
| `services/ocr-extract/` | 도은 | `base/ocr-extract` | `http://ocr-extract:8002` |
| `services/vector-store/` | 진아 | `base/vector-store` | `http://vector-store:8003` |
| `services/rag-chat/` | 우진 | `base/rag-chat` | `http://rag-chat:8004` |

## 작업 원칙

1. **본인 서비스 폴더 안에서만 작업한다.** 코드·설정·의존성 파일 모두 `services/<서비스>/` 안에 둔다.
2. **컨테이너로 감싸서 작업한다.** 본인 폴더에 `Dockerfile`을 만들고, 실행·테스트는 컨테이너에서 한다. 내 PC에 직접 패키지를 설치해 돌리지 않는다.
3. **다른 서비스는 컨테이너 주소로 부른다.** 예: `http://ocr-extract:8002`. 다른 서비스 폴더의 코드를 import하거나 고치지 않는다.
4. **공용 파일**(`docker-compose.yml`, `README.md`, `AGENTS.md`, `docs/`)은 팀장과 상의 후 바꾼다.
5. 모델은 가져다 쓰기만 한다 (학습 X).

## 시작하기

```bash
git clone https://github.com/wkuMyeungsu/physical-ai-teamproject_01.git
cd physical-ai-teamproject_01
git switch base/<서비스>                     # 예: git switch base/ocr-extract
git switch -c feature/<서비스>-<기능>         # 예: git switch -c feature/ocr-extract-crop-filter
```

브랜치·커밋·PR 규칙은 [AGENTS.md](AGENTS.md)를 따른다. 단계별 설명은 [docs/git-rules.html](docs/git-rules.html) (내려받아 브라우저로 열기).

## 실행

```bash
docker compose up --build <서비스>     # 내 서비스만. 예: docker compose up --build ocr-extract
docker compose up --build              # 전체 통합
```
