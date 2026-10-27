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

<!-- Dockerfile 구성과 실행·확인 방법을 적는다 -->

## 주고받는 데이터

<!-- 받는 입력 / 내보내는 출력 형식을 적는다 -->
