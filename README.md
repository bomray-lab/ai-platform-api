# ai-platform-api

LLM을 활용한 API를 서비스 단위로 모아 둔 저장소다. 서비스마다 혼자 실행하고 배포할 수 있고, 필요한 웹서비스에 HTTP로 붙여 쓴다.

## 서비스

| 서비스 | 상태 | 설명 |
| --- | --- | --- |
| [conversation-analysis](services/conversation-analysis/README.md) | 단독 배포·테스트 중 | [연애DNA](https://lovedna.bomraylab.com/)에 붙이려고 만든 API. 카톡·인스타 대화 캡처를 읽고 상대의 반응과 보낼 답장을 알려준다. |

## 기술 스택

| 항목 | 버전 | 용도 |
| --- | --- | --- |
| Python | 3.13 | |
| FastAPI | 0.128+ | API 서버, Swagger 문서 |
| Pydantic / pydantic-settings | 2.x | 요청·응답 검증, LLM 출력 스키마, `.env` 설정 |
| uv | 0.13 | 패키지·가상환경 관리 |
| httpx, openai | | Cloudflare Workers AI, OpenAI 호출 |
| Pillow | 12.x | 업로드 이미지 축소·변환 |
| pytest, mypy, ruff | | 테스트, 타입 검사, 린트·포맷 |
| Docker | | 서비스별 이미지 |

## 설계에서 신경 쓴 점

- **모델 교체**: 모델 호출은 서비스마다 `llm.py` 한 곳에서만 한다. `LLM_PROVIDER`와 모델명을 `.env`에서 바꾸면 무료(Cloudflare)와 유료(OpenAI) 모델을 코드 수정 없이 오간다.
- **LLM 출력 검증**: 모델 응답을 Pydantic 스키마로 검사하고, 맞지 않으면 그럴듯한 값을 지어내지 않고 오류로 돌려준다. 근거로 낸 인용이 실제 대본에 있는지도 다시 확인한다.
- **무료 한도 보호**: 공개 API라서 토큰 인증, CORS, IP별 하루 호출 수를 차례로 검사하고, 앞에서 걸린 요청은 모델을 부르지 않는다.
- **일정한 오류 형식**: 실패는 모두 `{"error", "message"}`로 돌려주고, 모델 제공사의 한도 초과·혼잡·실패를 구분한다.
- **키 없이 도는 테스트**: LLM을 mock으로 대신해서 키나 네트워크 없이 `pytest`가 돈다.
- **데이터 미보관**: 사용자가 올린 캡처와 대본은 디스크나 DB에 남기지 않는다.

## 시작하기

[uv](https://docs.astral.sh/uv/)가 필요하다. Python 3.13은 uv가 받아 온다.

```bash
git clone https://github.com/bomray-lab/ai-platform-api.git
cd ai-platform-api/services/conversation-analysis

cp .env.example .env   # 모델 키와 API_TOKEN을 채운다
uv sync
uv run fastapi dev     # http://127.0.0.1:8000/docs
```

| 명령어 | 설명 |
| --- | --- |
| `uv run fastapi dev` | 개발 서버 실행 |
| `uv run pytest` | 테스트 (키 없이 실행) |
| `uv run ruff check app tests` | 린트 |
| `uv run ruff format --check app tests` | 포맷 검사 |
| `uv run mypy app tests` | 타입 검사 |

`.env` 항목, 요청·응답, Docker 실행은 각 서비스 README를 본다.

## 구조

```text
services/
  <서비스명>/
    app/
      api/        요청·응답, 인증, 호출 제한
      <도메인>/    서비스 로직과 LLM 호출 (예: analysis/)
      main.py
      settings.py
    tests/        LLM mock 테스트
    Dockerfile
    pyproject.toml
    README.md
```

- 서비스끼리는 코드를 공유하지 않는다. 다른 서비스 기능이 필요하면 HTTP로 호출한다.
- 서비스 안에서는 `api`가 도메인 패키지를 쓰고, 반대 방향으로는 import하지 않는다.
- 키와 모델명은 서비스별 `.env`에 두고 저장소에는 `.env.example`만 올린다.
