from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent.parent

_ENV = SettingsConfigDict(
    env_file=_SERVICE_ROOT / ".env",
    env_file_encoding="utf-8",
    extra="ignore",
)

_REQUIRED_BY_PROVIDER = {
    "cloudflare": ("cloudflare_account_id", "cloudflare_api_token"),
    "openai": ("openai_api_key",),
}


class ApiSettings(BaseSettings):
    """LLM 키 없이도 앱이 뜰 수 있도록 LLM 설정과 분리한다."""

    api_token: SecretStr | None = Field(default=None, min_length=32)
    cors_origins: list[str] = ["https://lovedna.bomraylab.com"]
    daily_limit_per_ip: int = Field(default=10, ge=1)

    model_config = _ENV


class Settings(BaseSettings):
    llm_provider: Literal["cloudflare", "openai"] = "cloudflare"
    llm_model: str
    llm_timeout_seconds: float = 300

    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    openai_api_key: str | None = None

    model_config = _ENV

    @model_validator(mode="after")
    def _require_provider_keys(self) -> Self:
        missing = [
            name.upper()
            for name in _REQUIRED_BY_PROVIDER[self.llm_provider]
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                f"LLM_PROVIDER={self.llm_provider} 이면 {', '.join(missing)} 값이 필요합니다."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings()
