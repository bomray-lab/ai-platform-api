from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.analysis.llm import CloudflareClient, OpenAiClient, build_llm
from app.settings import Settings


class _IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture(autouse=True)
def _no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def _settings(values: dict[str, Any]) -> Settings:
    return _IsolatedSettings(llm_model="m", **values)


@pytest.mark.parametrize(
    "values, client_type",
    [
        (
            {
                "llm_provider": "cloudflare",
                "cloudflare_account_id": "acc",
                "workers_ai_api_token": "token",
            },
            CloudflareClient,
        ),
        ({"llm_provider": "openai", "openai_api_key": "sk-test"}, OpenAiClient),
    ],
)
def test_provider_selects_client(values: dict[str, Any], client_type: type) -> None:
    assert isinstance(build_llm(_settings(values)), client_type)


def test_default_provider_is_cloudflare() -> None:
    settings = _settings({"cloudflare_account_id": "acc", "workers_ai_api_token": "token"})

    assert settings.llm_provider == "cloudflare"


@pytest.mark.parametrize(
    "values, missing",
    [
        ({}, "CLOUDFLARE_ACCOUNT_ID"),
        ({"llm_provider": "cloudflare", "cloudflare_account_id": "acc"}, "WORKERS_AI_API_TOKEN"),
        ({"llm_provider": "openai"}, "OPENAI_API_KEY"),
    ],
)
def test_provider_requires_its_keys(values: dict[str, Any], missing: str) -> None:
    with pytest.raises(ValidationError, match=missing):
        _settings(values)
