from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.analysis.errors import LlmBusy, LlmFailed, LlmQuotaExceeded
from app.analysis.llm import llm_from_settings
from app.analysis.models import Extraction, Judgment
from app.api.images import MAX_IMAGES
from app.api.rate_limit import DailyLimiter, limiter_from_settings
from app.main import app
from app.settings import ApiSettings, get_api_settings
from tests.fakes import FakeLlm, fixture_turns, judgment

_TOKEN = "t" * 32


def _png(width: int = 40, height: int = 20) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def client() -> Iterator[TestClient]:
    _api_token(_TOKEN)
    _limit(100)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _api_token(token: str | None) -> None:
    settings = ApiSettings.model_construct(api_token=SecretStr(token) if token else None)
    app.dependency_overrides[get_api_settings] = lambda: settings


def _use(llm: FakeLlm) -> FakeLlm:
    app.dependency_overrides[llm_from_settings] = lambda: llm
    return llm


def _limit(per_day: int) -> None:
    limiter = DailyLimiter(per_day)
    app.dependency_overrides[limiter_from_settings] = lambda: limiter


def _readable_llm() -> FakeLlm:
    return FakeLlm(
        {Extraction: Extraction(readable=True, turns=fixture_turns()), Judgment: judgment()}
    )


def _post(
    client: TestClient,
    *images: bytes,
    my_dna_type: str = "카톡 폭탄러",
    token: str | None = _TOKEN,
):
    return client.post(
        "/v1/conversations/analyze",
        data={"my_dna_type": my_dna_type},
        files=[("images", (f"{i}.png", raw, "image/png")) for i, raw in enumerate(images)],
        headers={"Authorization": f"Bearer {token}"} if token else {},
    )


def test_analyze_returns_transcript_and_judgment(client: TestClient) -> None:
    turns = fixture_turns()
    _use(FakeLlm({Extraction: Extraction(readable=True, turns=turns), Judgment: judgment()}))

    response = _post(client, _png())

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["transcript", *Judgment.model_fields]
    assert body["transcript"] == [turn.model_dump() for turn in turns]
    assert body["temperature"] == "cooling"


def test_analyze_resizes_long_side_before_sending(client: TestClient) -> None:
    llm = _use(_readable_llm())

    _post(client, _png(2560, 400))

    with Image.open(BytesIO(llm.calls[0].images[0])) as sent:
        assert sent.size == (1280, 200)


def test_unreadable_capture_returns_read_failed_without_judging(client: TestClient) -> None:
    llm = _use(FakeLlm({Extraction: Extraction(readable=False, turns=[])}))

    response = _post(client, _png())

    assert response.status_code == 422
    assert response.json()["error"] == "read_failed"
    assert [call.text_format for call in llm.calls] == [Extraction]


def test_accepts_up_to_max_images_in_upload_order(client: TestClient) -> None:
    llm = _use(_readable_llm())
    widths = [40 + i for i in range(MAX_IMAGES)]

    response = _post(client, *[_png(width) for width in widths])

    assert response.status_code == 200
    sent = llm.calls[0].images
    assert [Image.open(BytesIO(png)).width for png in sent] == widths


@pytest.mark.parametrize("count", [0, MAX_IMAGES + 1])
def test_rejects_image_count_out_of_range(client: TestClient, count: int) -> None:
    llm = _use(FakeLlm({}))

    response = _post(client, *[_png() for _ in range(count)])

    assert response.status_code == 422
    assert llm.calls == []


def test_rejects_non_image_file(client: TestClient) -> None:
    llm = _use(FakeLlm({}))

    response = _post(client, b"not an image")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_image"
    assert llm.calls == []


def test_rejects_unknown_dna_type(client: TestClient) -> None:
    llm = _use(FakeLlm({}))

    response = _post(client, _png(), my_dna_type="없는 유형")

    assert response.status_code == 422
    assert llm.calls == []


def test_daily_limit_blocks_before_calling_model(client: TestClient) -> None:
    _limit(2)
    llm = _use(_readable_llm())

    responses = [_post(client, _png()) for _ in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert responses[-1].json()["error"] == "daily_limit_exceeded"
    assert len(llm.calls) == 4


def test_invalid_upload_does_not_use_daily_limit(client: TestClient) -> None:
    _limit(1)
    _use(_readable_llm())

    assert _post(client, b"not an image").status_code == 422
    assert _post(client, _png()).status_code == 200


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    allowed = get_api_settings().cors_origins[0]

    def preflight(origin: str):
        return client.options(
            "/v1/conversations/analyze",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )

    assert preflight(allowed).headers["access-control-allow-origin"] == allowed
    assert "access-control-allow-origin" not in preflight("https://evil.example").headers


@pytest.mark.parametrize("token", [None, "x" * 32])
def test_rejects_missing_or_wrong_token(client: TestClient, token: str | None) -> None:
    llm = _use(_readable_llm())

    response = _post(client, _png(), token=token)

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"
    assert llm.calls == []


def test_unauthorized_request_does_not_use_daily_limit(client: TestClient) -> None:
    _limit(1)
    _use(_readable_llm())

    assert _post(client, _png(), token=None).status_code == 401
    assert _post(client, _png()).status_code == 200


def test_fails_closed_when_server_has_no_token(client: TestClient) -> None:
    _api_token(None)
    llm = _use(_readable_llm())

    response = _post(client, _png())

    assert response.status_code == 503
    assert response.json()["error"] == "auth_not_configured"
    assert llm.calls == []


def test_health_needs_no_token(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "failure, status_code, error",
    [
        (LlmQuotaExceeded("한도"), 503, "service_quota_exceeded"),
        (LlmBusy("혼잡"), 503, "model_busy"),
        (LlmFailed("실패"), 502, "model_failed"),
    ],
)
def test_model_failures_map_to_distinct_errors(
    client: TestClient, failure: Exception, status_code: int, error: str
) -> None:
    _use(FakeLlm({Extraction: failure}))

    response = _post(client, _png())

    assert response.status_code == status_code
    assert response.json()["error"] == error
