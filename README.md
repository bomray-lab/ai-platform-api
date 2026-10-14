# ai-platform-api

LLM을 활용한 API를 서비스 단위로 모아 둔 저장소다. 서비스마다 혼자 실행하고 배포할 수 있다.

## 서비스

| 서비스 | 설명 |
| --- | --- |
| [conversation-analysis](services/conversation-analysis/README.md) | [연애DNA](https://lovedna.bomraylab.com/)에 붙인 API. 카톡·인스타 대화 캡처를 읽고 상대의 반응과 보낼 답장을 알려준다. |

## 구조

```text
services/
  <서비스명>/
    app/          FastAPI 앱
    tests/        LLM mock 테스트
    Dockerfile
    pyproject.toml
    README.md
```

- 서비스끼리는 코드를 공유하지 않는다.
- 키와 모델명은 서비스별 `.env`에 둔다.
- Python 3.13, FastAPI, uv를 쓴다.

## 앞으로

- 분석·검색 기능을 서비스로 추가
- 무료 모델을 서버에 직접 설치해 OpenAI 대신 사용
- 머신러닝 기능 추가
