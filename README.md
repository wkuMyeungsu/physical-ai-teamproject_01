# OCR · 벡터 임베딩 기반 영문 텍스트 추출·검색 파이프라인

웹페이지에 흘러가는 영어 원문을 휴대폰 카메라로 촬영 → OCR로 텍스트 추출 → 임베딩해 DB 저장 → RAG로 검색.

## 역할 · 폴더 · 브랜치 · 컨테이너

| 영역 | 담당 | 폴더 | 기준 브랜치 | 포트 |
|---|---|---|---|---|
| 대시보드 (QR · 실시간 현황 · RAG 검색 화면) | 명수 (팀장) | `homepage/` | `base/homepage` | 8000 |
| 수집 (QR 연동, 영상 → 이미지) | 대희 | `capture/` | `base/capture` | 8001 |
| OCR 텍스트 추출 | 도은 | `ocr/` | `base/ocr` | 8002 |
| 임베딩 · 실시간 DB 적재 | 진아 | `db/` | `base/db` | 8003 |
| RAG · 챗봇 | 우진 | `rag/` | `base/rag` | 8004 |

- 각자 **본인 폴더 안에서만** 작업하고, 본인 폴더에 `Dockerfile`을 만든다.
- 컨테이너끼리는 `docker-compose.yml`의 서비스 이름으로 부른다. 예: `http://ocr:8002`
- 모델은 가져다 쓰기만 한다 (학습 X).

## 시작하기

```bash
git clone https://github.com/wkuMyeungsu/physical-ai-teamproject_01.git
cd physical-ai-teamproject_01
git switch base/<영역>                      # 예: git switch base/ocr
git switch -c feature/<영역>-<기능>          # 예: git switch -c feature/ocr-crop-filter
```

브랜치·커밋·PR 규칙은 [AGENTS.md](AGENTS.md)를 따른다. 단계별 설명은 [docs/git-rules.html](docs/git-rules.html) (내려받아 브라우저로 열기).

## 전체 실행

```bash
docker compose up --build
```
