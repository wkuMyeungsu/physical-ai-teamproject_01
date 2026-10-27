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

## 실행

<!-- Dockerfile 구성과 실행·확인 방법을 적는다 -->

## 주고받는 데이터

<!-- 받는 입력 / 내보내는 출력 형식을 적는다 -->
