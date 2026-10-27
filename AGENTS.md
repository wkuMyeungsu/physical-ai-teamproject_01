# 협업 규칙 (AI 프롬프트용)

이 저장소에서 작업할 때 아래 규칙을 반드시 따른다.
저장소: `https://github.com/wkuMyeungsu/physical-ai-teamproject_01.git`

## 서비스 목록

서비스 = 담당자 1명 = 폴더 1개 = 컨테이너 1개 = `base/` 브랜치 1개. 이름은 모두 같다.

| 서비스 | 폴더 | 기준 브랜치 | 컨테이너 주소 |
|---|---|---|---|
| `dashboard` | `services/dashboard/` | `base/dashboard` | `http://dashboard:8000` |
| `frame-capture` | `services/frame-capture/` | `base/frame-capture` | `http://frame-capture:8001` |
| `ocr-extract` | `services/ocr-extract/` | `base/ocr-extract` | `http://ocr-extract:8002` |
| `vector-store` | `services/vector-store/` | `base/vector-store` | `http://vector-store:8003` |
| `rag-chat` | `services/rag-chat/` | `base/rag-chat` | `http://rag-chat:8004` |

## 작업 범위 (AI 필수 준수)

1. **작업 시작 전에 내 서비스를 정한다.** `git branch --show-current`의 결과 `feature/<서비스>-<기능>` 또는 `fix/<서비스>-<내용>`에서 `<서비스>`를 읽는다. 브랜치로 알 수 없으면 사용자에게 어느 서비스인지 묻는다.
2. **파일 생성·수정·삭제는 `services/<서비스>/` 안에서만 한다.** 다른 서비스 폴더와 루트 공용 파일(`docker-compose.yml`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `docs/`)은 읽기만 한다.
3. **폴더 밖을 바꿔야 하면 멈추고 사용자에게 알린다.** 무엇을 왜 바꿔야 하는지 설명하고, 사용자가 팀장과 상의하도록 한다. 직접 고치지 않는다.
4. **모든 코드는 컨테이너로 감싸서 실행한다.**
   - `services/<서비스>/Dockerfile`을 만들고, 의존성은 같은 폴더의 `requirements.txt`(또는 `package.json`)에 적는다.
   - 컨테이너는 `docker-compose.yml`에 정해진 포트로 `0.0.0.0`에서 연다.
   - 실행·테스트는 저장소 루트에서 `docker compose up --build <서비스>`로 한다.
   - 사용자 PC(호스트)에 `pip install`, `npm install -g` 등으로 직접 설치하지 않는다.
5. **다른 서비스와는 HTTP로만 주고받는다.** 위 표의 컨테이너 주소를 쓰고, 다른 서비스 폴더의 코드를 import하지 않는다. `localhost`로 다른 서비스를 부르지 않는다 (컨테이너 안의 `localhost`는 자기 자신이다).
6. 주고받는 데이터 형식은 `services/<서비스>/README.md`의 "주고받는 데이터"에 적는다.
7. 모델은 가져다 쓰기만 한다. 학습 코드를 만들지 않는다.

## 브랜치

합치는 방향: `feature/<서비스>-<기능>` → `base/<서비스>` → `dev` → `main` (모두 PR)

| 브랜치 | 역할 | 직접 push |
|---|---|---|
| `main` | 최종본 | 금지 |
| `dev` | 서비스 통합·테스트 | 금지 |
| `base/<서비스>` | 서비스별 기능 모음 | dev 받아오기 merge만 |
| `feature/<서비스>-<기능>`, `fix/<서비스>-<내용>` | 기능·수정 하나 | 허용 |

- 브랜치 이름: 영문 소문자와 하이픈만. 예: `feature/dashboard-qr-panel`, `fix/ocr-extract-empty-result`
- 기능·수정 브랜치는 해당 `base/<서비스>`에서 만든다.
- PR을 만들 때 대상(base)을 반드시 확인한다. GitHub 기본값은 `main`이다. `feature/*`의 대상은 `base/<서비스>`다.

## 커밋

- 형식: `<타입>(<서비스>): <요약>` — 타입: `feat` `fix` `docs` `refactor` `chore`
- 예: `feat(ocr-extract): 잘린 카드 걸러내기 추가`
- 커밋 하나에 목적 하나. 동작하는 상태로만 커밋.
- `git add .` 대신 파일을 지정하고, 커밋 전 `git status`로 확인한다. `services/<서비스>/` 밖의 파일이 보이면 커밋하지 않는다.

## 절차

```bash
# 기능 시작
git switch base/ocr-extract && git pull
git switch -c feature/ocr-extract-crop-filter
git add services/ocr-extract/<파일> && git commit -m "feat(ocr-extract): ..."
git push -u origin feature/ocr-extract-crop-filter

# PR 올리기 전: 대상 브랜치를 받아와 충돌을 먼저 해결
git pull origin base/ocr-extract && git push
# → GitHub PR: base/ocr-extract ← feature/ocr-extract-crop-filter

# 서비스 → dev (서비스 담당자)
git switch base/ocr-extract && git pull && git pull origin dev && git push
# → GitHub PR: dev ← base/ocr-extract

# dev 테스트 통과 후 → GitHub PR: main ← dev
# main 병합 후 각 base/* 에 dev 받아오기
git switch base/ocr-extract && git pull && git pull origin dev && git push
```

- PR 병합은 **Create a merge commit**만 사용 (Squash·Rebase 금지).
- 병합된 `feature/*`, `fix/*`는 삭제한다. `base/*`는 삭제하지 않는다.
- dev 테스트에서 문제가 나오면 main으로 올리지 않고 `fix/*`로 고친 뒤 다시 PR.

## 금지

- `main`, `dev`에 직접 commit·push
- `base/*`에 작업 커밋 (dev 받아오기 merge만 허용)
- 내 서비스 폴더 밖의 파일 수정 (공용 파일은 팀장과 상의 후)
- 호스트 PC에 직접 의존성 설치·실행 (컨테이너로 실행)
- `git push --force`, `git reset --hard` 등 이력을 지우는 명령 (사용자가 명시적으로 요청한 경우 제외)
- 다른 사람의 브랜치에 push
- 비밀키·토큰·`.env` 커밋

## AI 작업 지침

- 커밋 전에 `git branch --show-current`로 현재 브랜치를 확인한다. `main`, `dev`, `base/*`이면 커밋하지 말고 알맞은 `feature/*` 브랜치를 만들자고 제안한다.
- 커밋 전에 `git status`로 바뀐 파일이 모두 `services/<서비스>/` 안에 있는지 확인한다.
- 충돌이 나면 임의로 한쪽을 고르지 말고, 충돌 파일과 양쪽 내용을 보여주고 사용자에게 확인받는다.
- push와 PR 생성은 사용자 확인 후에만 한다.
