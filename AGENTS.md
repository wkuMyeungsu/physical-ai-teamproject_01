# Git 협업 규칙 (AI 프롬프트용)

이 저장소에서 Git 작업을 할 때 아래 규칙을 반드시 따른다.
저장소: `https://github.com/wkuMyeungsu/physical-ai-teamproject_01.git`

## 브랜치

합치는 방향: `feature/<영역>-<기능>` → `base/<영역>` → `dev` → `main` (모두 PR)

| 브랜치 | 역할 | 직접 push |
|---|---|---|
| `main` | 최종본 | 금지 |
| `dev` | 영역 통합·테스트 | 금지 |
| `base/<영역>` (`base/homepage`, `base/capture`, `base/ocr`, `base/db`, `base/rag`) | 영역별 기능 모음 | dev 받아오기 merge만 |
| `feature/<영역>-<기능>`, `fix/<영역>-<내용>` | 기능·수정 하나 | 허용 |

- 브랜치 이름: 영문 소문자와 하이픈만. 예: `feature/homepage-login-button`, `fix/ocr-empty-result`
- 기능·수정 브랜치는 해당 `base/<영역>`에서 만든다.
- 작업은 본인 영역 폴더(`homepage/`, `capture/`, `ocr/`, `db/`, `rag/`) 안에서만 한다.

## 커밋

- 형식: `<타입>(<영역>): <요약>` — 타입: `feat` `fix` `docs` `refactor` `chore`
- 예: `feat(homepage): 로그인 버튼 추가`
- 커밋 하나에 목적 하나. 동작하는 상태로만 커밋.
- `git add .` 대신 파일을 지정하고, 커밋 전 `git status`로 확인한다.

## 절차

```bash
# 기능 시작
git switch base/homepage && git pull
git switch -c feature/homepage-login-button
git add <파일> && git commit -m "feat(homepage): ..."
git push -u origin feature/homepage-login-button

# PR 올리기 전: 대상 브랜치를 받아와 충돌을 먼저 해결
git pull origin base/homepage && git push
# → GitHub PR: base/homepage ← feature/homepage-login-button

# 영역 → dev (영역 담당자)
git switch base/homepage && git pull && git pull origin dev && git push
# → GitHub PR: dev ← base/homepage

# dev 테스트 통과 후 → GitHub PR: main ← dev
# main 병합 후 각 base/* 에 dev 받아오기
git switch base/homepage && git pull && git pull origin dev && git push
```

- PR 병합은 **Create a merge commit**만 사용 (Squash·Rebase 금지).
- 병합된 `feature/*`, `fix/*`는 삭제한다. `base/*`는 삭제하지 않는다.
- dev 테스트에서 문제가 나오면 main으로 올리지 않고 `fix/*`로 고친 뒤 다시 PR.

## 금지

- `main`, `dev`에 직접 commit·push
- `base/*`에 작업 커밋 (dev 받아오기 merge만 허용)
- `git push --force`, `git reset --hard` 등 이력을 지우는 명령 (사용자가 명시적으로 요청한 경우 제외)
- 다른 사람의 브랜치에 push
- 비밀키·토큰·`.env` 커밋

## AI 작업 지침

- 커밋 전에 `git branch --show-current`로 현재 브랜치를 확인한다. `main`, `dev`, `base/*`이면 커밋하지 말고 알맞은 `feature/*` 브랜치를 만들자고 제안한다.
- 충돌이 나면 임의로 한쪽을 고르지 말고, 충돌 파일과 양쪽 내용을 보여주고 사용자에게 확인받는다.
- push와 PR 생성은 사용자 확인 후에만 한다.
