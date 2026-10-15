# conversation-analysis

[연애DNA](https://lovedna.bomraylab.com/)에 붙이려고 만든 대화 분석 API다. 연애DNA에서 15문항으로 나온 내 연애유형과 카톡·인스타 대화 캡처를 받아, 상대의 반응과 지금 보낼 답장을 돌려준다.

지금은 연애DNA에 연결하기 전이고, 단독으로 배포해 테스트하고 있다. 입력은 연애유형과 캡처뿐이라 다른 서비스에도 붙일 수 있다.

## 동작 방식

1. **검사** (`app/api`): API 토큰, 이미지 개수·형식·크기, IP별 하루 호출 수를 차례로 확인한다. 여기서 걸리면 모델을 부르지 않는다.
2. **이미지 정리** (`resize.py`): 사진 회전을 바로잡고 긴 변을 1280px 이하로 줄여 PNG로 바꾼다.
3. **대본 추출** (`extract.py`): 모델이 캡처에서 말풍선을 읽어 누가 한 말인지(`me`, `other`, `unknown`)와 함께 대본으로 만든다. 글자를 읽지 못하면 다음 단계로 가지 않고 `read_failed`를 돌려준다.
4. **판정** (`judge.py`): 내 연애유형과 대본만 보고 관심도, 어장 여부, 주도권, 추천 답장을 정한다. 모델이 낸 근거 인용 중 대본에 실제로 없는 문장은 버린다.

모델 응답은 단계마다 Pydantic 스키마로 검사한다. 모델 호출은 동기 방식이라 `asyncio.to_thread`로 돌려서 요청을 처리하는 이벤트 루프를 막지 않는다.

## 실행

```bash
cp .env.example .env
```

`.env`에서 사용할 모델을 고른다. 아래 [모델 교체](#모델-교체)를 참고한다.

```bash
uv sync
uv run fastapi dev
```

`GET /health`는 `{"status":"ok"}`를 반환한다. API 문서는 `http://127.0.0.1:8000/docs`에서 볼 수 있다.

## 요청

`POST /v1/conversations/analyze`

- `my_dna_type`: `카톡 폭탄러`, `연애 고수`, `잠수 장인`, `선긋기 장인`, `자유 영혼`, `걱정 마라토너`, `밀당 고수`, `밀당 유목민`
- `images`: jpeg, png, webp. 1장 이상 3장 이하, 한 장 8MB 이하

```bash
curl -s -X POST http://127.0.0.1:8000/v1/conversations/analyze \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "my_dna_type=카톡 폭탄러" \
  -F "images=@chat.png"
```

`Authorization: Bearer <API_TOKEN>` 헤더가 없거나 틀리면 `401`을 반환한다. Swagger(`/docs`)에서는 오른쪽 위 **Authorize**에 토큰을 넣는다. `GET /health`는 토큰 없이 호출할 수 있다.

여러 장은 `-F "images=@다른장.png"`를 업로드 순서대로 반복한다.

## 응답

| 필드 | 값 |
| --- | --- |
| `transcript` | 읽어 낸 대화. `speaker`는 `me`, `other`, `unknown` |
| `temperature` | 상대 관심도. `hot`, `warm`, `cooling`, `cold` |
| `anger_level` | 열받는 정도 0~100 |
| `fish_pond` | 어장 여부. `definite`, `suspicious`, `no` |
| `signal` | 계속 진행해도 되는지. `green`, `yellow`, `red` |
| `dominance` | 대화 주도권. `me`, `balanced`, `them` |
| `reason` | 판단 근거 |
| `evidence` | 근거가 된 대본 인용 |
| `recommended_replies` | 보낼 수 있는 답장 1~2개 |
| `recommended_action` | 지금 할 행동 한 줄 |

## 오류

실패하면 `{"error": "<코드>", "message": "<사용자에게 보여줄 안내>"}`를 반환한다. 프론트는 `error` 값으로 경우를 나눈다.

| HTTP | `error` | 언제 |
| --- | --- | --- |
| 401 | `unauthorized` | API 토큰이 없거나 틀림 |
| 422 | `invalid_image` | 이미지 개수·형식·크기가 맞지 않음 |
| 422 | `read_failed` | 캡처에서 글자를 읽지 못함. 반응과 답장을 추측하지 않는다 |
| 429 | `daily_limit_exceeded` | 이 IP의 하루 호출 수를 다 씀 |
| 502 | `model_failed` | 모델 호출 실패 |
| 503 | `service_quota_exceeded` | 모델 제공사의 무료 한도를 다 씀. Cloudflare는 UTC 자정(한국 시간 오전 9시)에 다시 채워진다 |
| 503 | `model_busy` | 모델 제공사가 잠시 혼잡함. `Retry-After` 헤더만큼 기다렸다 다시 시도한다 |
| 503 | `auth_not_configured` | 서버에 `API_TOKEN`이 설정되지 않음 |

`my_dna_type`이 빠졌거나 목록에 없는 값이면 FastAPI 기본 형식(`{"detail": [...]}`)의 `422`를 반환한다.

## 호출 제한

무료 모델 한도를 다른 사람이 다 써 버리지 않도록 세 가지를 막는다. 검사 순서는 토큰, 이미지, 하루 호출 수다. 토큰이나 이미지에서 걸린 요청은 호출 수에 넣지 않는다.

- **API 토큰**: `API_TOKEN`과 같은 값을 보낸 요청만 받는다. 브라우저에서 이 API를 직접 부르면 토큰이 프론트 코드에 들어가서 누구나 볼 수 있다. 그래서 브라우저에서 쓸 때는 아무나 막 부르는 것을 막는 정도로 보고, 토큰을 완전히 숨기려면 프론트와 이 API 사이에 토큰을 들고 있는 서버(예: Cloudflare Pages Functions)를 둔다.
- **CORS**: 브라우저에서는 `CORS_ORIGINS`에 있는 사이트에서만 호출할 수 있다. 기본값은 연애DNA 주소 하나다. 로컬에서 프론트를 띄워 개발할 때는 `CORS_ORIGINS=["https://lovedna.bomraylab.com","http://localhost:5173"]`처럼 그 주소를 추가한다.
- **IP별 하루 호출 수**: `DAILY_LIMIT_PER_IP`(기본 10)를 넘으면 모델을 부르지 않고 `429`를 반환한다. 날짜는 UTC 기준으로 바뀐다.

호출 횟수는 메모리에 세므로 서버를 다시 띄우면 초기화되고, 프로세스를 여러 개 띄우면 각자 따로 센다. 프록시나 로드밸런서 뒤에 두면 실제 사용자 IP를 읽도록 `FORWARDED_ALLOW_IPS` 환경 변수에 프록시 IP를 넣는다(uvicorn 설정).

## 모델 교체

키와 모델명은 코드에 없고 `.env`로만 바꾼다. 모델 호출은 `app/analysis/llm.py` 한 곳에서 한다.

| `LLM_PROVIDER` | 필요한 값 | 비용 |
| --- | --- | --- |
| `cloudflare` | `LLM_MODEL`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | 하루 10,000 뉴런까지 무료. [Workers AI](https://developers.cloudflare.com/workers-ai/) |
| `openai` | `LLM_MODEL`, `OPENAI_API_KEY` | 유료 |

캡처를 읽어야 하므로 이미지를 지원하는 모델을 써야 한다. 기본값은 Workers AI의 `@cf/google/gemma-4-26b-a4b-it`이다.

Cloudflare API 토큰은 대시보드의 **My Profile → API Tokens**에서 `Workers AI` 권한으로 만든다. 계정 ID는 대시보드 주소창이나 **Workers & Pages** 화면에서 확인한다.

## 데이터 보관

캡처와 대본은 디스크나 데이터베이스에 남기지 않는다. 회원, 로그인, 결제도 없다. 캡처는 분석을 위해 고른 모델 제공사(Cloudflare 또는 OpenAI) 서버로 보낸다. `openai`를 쓸 때는 OpenAI의 응답 보관 기능(`store`)을 끈다.

## Docker

이미지에는 `.env`를 넣지 않는다. 실행할 때 환경 변수로 키를 넘긴다.

```bash
docker build -t conversation-analysis .
docker run --rm -p 8000:8000 --env-file .env conversation-analysis
```

## 테스트와 검사

LLM은 mock으로 대신하므로 키나 모델 없이 돌아간다.

```bash
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app tests
```
