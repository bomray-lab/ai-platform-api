import base64
import json
from collections.abc import Callable

import httpx
import pytest

from app.analysis.errors import LlmBusy, LlmFailed, LlmQuotaExceeded, LlmRejected
from app.analysis.llm import CloudflareClient, json_schema
from app.analysis.models import Extraction, Judgment
from tests.fakes import judgment_payload

Handler = Callable[[httpx.Request], httpx.Response]
_JUDGMENT_JSON = json.dumps(judgment_payload(), ensure_ascii=False)


def _cloudflare(handler: Handler) -> CloudflareClient:
    return CloudflareClient(
        account_id="acc",
        api_token="token",
        model="@cf/test/model",
        timeout=5,
        transport=httpx.MockTransport(handler),
    )


def _reply(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


def test_json_schema_inlines_refs() -> None:
    schema = json_schema(Extraction)

    assert "$defs" not in schema
    assert "$ref" not in json.dumps(schema)
    assert schema["properties"]["turns"]["items"]["properties"]["speaker"]["enum"] == [
        "me",
        "other",
        "unknown",
    ]


def test_cloudflare_calls_account_endpoint_with_token_and_images() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return _reply(_JUDGMENT_JSON)

    result = _cloudflare(handler).parse(
        instructions="지시", text="본문", images=[b"png-bytes"], text_format=Judgment
    )

    assert result == Judgment.model_validate(judgment_payload())
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acc/ai/v1/chat/completions"
    assert seen["auth"] == "Bearer token"
    body = seen["body"]
    assert body["model"] == "@cf/test/model"
    assert body["messages"][0] == {"role": "system", "content": "지시"}
    assert body["response_format"]["json_schema"]["schema"] == json_schema(Judgment)
    assert body["messages"][1]["content"] == [
        {"type": "text", "text": "본문"},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64.b64encode(b'png-bytes').decode()}"
            },
        },
    ]


def test_cloudflare_sends_only_text_when_no_images() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return _reply(_JUDGMENT_JSON)

    _cloudflare(handler).parse(instructions="지시", text="본문", text_format=Judgment)

    assert seen["messages"][1]["content"] == [{"type": "text", "text": "본문"}]


def test_cloudflare_accepts_json_in_code_fence() -> None:
    client = _cloudflare(lambda request: _reply(f"```json\n{_JUDGMENT_JSON}\n```"))

    result = client.parse(instructions="지시", text="본문", text_format=Judgment)

    assert result == Judgment.model_validate(judgment_payload())


@pytest.mark.parametrize(
    "reply",
    [
        _reply('{"temperature": "lukewarm"}'),
        httpx.Response(200, json={"choices": []}),
    ],
)
def test_schema_mismatch_is_rejected(reply: httpx.Response) -> None:
    client = _cloudflare(lambda request: reply)

    with pytest.raises(LlmRejected):
        client.parse(instructions="지시", text="본문", text_format=Judgment)


def test_http_error_is_llm_failure() -> None:
    client = _cloudflare(lambda request: httpx.Response(404, json={"error": "not found"}))

    with pytest.raises(LlmFailed) as caught:
        client.parse(instructions="지시", text="본문", text_format=Judgment)
    assert type(caught.value) is LlmFailed


def _cloudflare_error(code: int, message: str) -> httpx.Response:
    return httpx.Response(
        429, json={"success": False, "errors": [{"code": code, "message": message}]}
    )


@pytest.mark.parametrize(
    "reply, expected",
    [
        (_cloudflare_error(3036, "You have used up your daily free allocation"), LlmQuotaExceeded),
        (_cloudflare_error(3040, "Capacity temporarily exceeded"), LlmBusy),
    ],
)
def test_cloudflare_429_distinguishes_daily_limit_from_busy(
    reply: httpx.Response, expected: type[LlmFailed]
) -> None:
    client = _cloudflare(lambda request: reply)

    with pytest.raises(LlmFailed) as caught:
        client.parse(instructions="지시", text="본문", text_format=Judgment)
    assert type(caught.value) is expected
