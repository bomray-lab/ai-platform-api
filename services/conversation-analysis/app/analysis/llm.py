import base64
import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Protocol

import httpx
from openai import APIError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.analysis.errors import LlmBusy, LlmFailed, LlmQuotaExceeded, LlmRejected
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
# https://developers.cloudflare.com/workers-ai/platform/errors/
_CLOUDFLARE_DAILY_LIMIT_CODE = "3036"


class LlmClient(Protocol):
    def parse[T: BaseModel](
        self,
        *,
        instructions: str,
        text: str,
        images: Sequence[bytes] = (),
        text_format: type[T],
    ) -> T: ...


def _data_url(png: bytes) -> str:
    return f"data:image/png;base64,{base64.standard_b64encode(png).decode('ascii')}"


def json_schema(text_format: type[BaseModel]) -> dict[str, Any]:
    """$ref를 펼친 JSON 스키마. 일부 모델 서버는 $ref를 해석하지 못한다."""
    schema = text_format.model_json_schema()
    defs = schema.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                return inline(defs[ref.removeprefix("#/$defs/")])
            return {key: inline(value) for key, value in node.items()}
        if isinstance(node, list):
            return [inline(item) for item in node]
        return node

    return inline(schema)


def _validate[T: BaseModel](text_format: type[T], output: str) -> T:
    cleaned = output.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        return text_format.model_validate_json(cleaned)
    except ValidationError as error:
        raise LlmRejected("모델이 스키마에 맞는 결과를 주지 않았습니다.") from error


class OpenAiClient:
    def __init__(self, *, api_key: str, model: str, timeout: float) -> None:
        self._model = model
        self._client = OpenAI(api_key=api_key, timeout=timeout)

    def parse[T: BaseModel](
        self,
        *,
        instructions: str,
        text: str,
        images: Sequence[bytes] = (),
        text_format: type[T],
    ) -> T:
        content: list[dict[str, str]] = [{"type": "input_text", "text": text}]
        content.extend(
            {"type": "input_image", "image_url": _data_url(png), "detail": "high"} for png in images
        )
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=[{"role": "user", "content": content}],  # type: ignore[list-item, misc]
                text_format=text_format,
                reasoning={"effort": "low"},
                store=False,
            )
        except RateLimitError as error:
            if error.code == "insufficient_quota":
                raise LlmQuotaExceeded("OpenAI 사용 한도를 다 썼습니다.") from error
            raise LlmBusy("OpenAI가 잠시 요청을 받지 못합니다.") from error
        except APIError as error:
            logger.exception("OpenAI 호출 실패")
            raise LlmFailed("모델 호출에 실패했습니다.") from error
        if response.output_parsed is None:
            raise LlmRejected("모델이 스키마에 맞는 결과를 주지 않았습니다.")
        return response.output_parsed


class CloudflareClient:
    """Workers AI의 OpenAI 호환 Chat Completions 엔드포인트."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        model: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.Client(
            base_url=f"{CLOUDFLARE_API}/accounts/{account_id}/ai/v1",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout,
            transport=transport,
        )

    def parse[T: BaseModel](
        self,
        *,
        instructions: str,
        text: str,
        images: Sequence[bytes] = (),
        text_format: type[T],
    ) -> T:
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        content.extend(
            {"type": "image_url", "image_url": {"url": _data_url(png)}} for png in images
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": text_format.__name__, "schema": json_schema(text_format)},
            },
            "temperature": 0,
        }
        try:
            response = self._client.post("/chat/completions", json=payload)
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                if _CLOUDFLARE_DAILY_LIMIT_CODE in response.text:
                    raise LlmQuotaExceeded("Workers AI 하루 무료 한도를 다 썼습니다.")
                raise LlmBusy("Workers AI가 잠시 요청을 받지 못합니다.")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.exception("Cloudflare 호출 실패")
            raise LlmFailed("모델 호출에 실패했습니다.") from error
        try:
            output = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LlmRejected("모델이 스키마에 맞는 결과를 주지 않았습니다.") from error
        return _validate(text_format, output)


def build_llm(settings: Settings) -> LlmClient:
    match settings.llm_provider:
        case "cloudflare":
            assert settings.cloudflare_account_id and settings.cloudflare_api_token
            return CloudflareClient(
                account_id=settings.cloudflare_account_id,
                api_token=settings.cloudflare_api_token,
                model=settings.llm_model,
                timeout=settings.llm_timeout_seconds,
            )
        case "openai":
            assert settings.openai_api_key
            return OpenAiClient(
                api_key=settings.openai_api_key,
                model=settings.llm_model,
                timeout=settings.llm_timeout_seconds,
            )


@lru_cache
def llm_from_settings() -> LlmClient:
    return build_llm(get_settings())
