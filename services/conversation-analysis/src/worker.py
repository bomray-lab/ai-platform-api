"""Cloudflare Python Workers 진입점. 로컬·Docker에서는 이 파일 없이 app.main을 uvicorn으로 띄운다."""

import os
from typing import Any

from fastapi import Request
from workers import DurableObject, WorkerEntrypoint, asgi

from app.analysis.llm import llm_from_settings
from app.api.rate_limit import limiter_from_settings, utc_today
from app.main import app
from app.settings import ApiSettings, Settings, get_api_settings, get_settings

_SETTING_NAMES = [name.upper() for name in (*Settings.model_fields, *ApiSettings.model_fields)]
_settings_loaded = False


def _load_settings(env: Any) -> None:
    """Workers는 설정을 os.environ이 아니라 요청의 env로 넘긴다.

    import 시점 상태는 배포 때 스냅샷으로 굳어서 그때 읽으면 나중에 넣은 시크릿이 빠진다.
    그래서 isolate마다 첫 요청에서 한 번 옮기고, 그 전에 만들어진 설정 캐시를 비운다.
    """
    global _settings_loaded
    if _settings_loaded:
        return
    for name in _SETTING_NAMES:
        value = getattr(env, name, None)
        if isinstance(value, str) and value:
            os.environ[name] = value
    for cached in (get_settings, get_api_settings, llm_from_settings):
        cached.cache_clear()
    _settings_loaded = True


class DailyCounter(DurableObject):  # type: ignore[misc]
    """IP 하나에 하나씩 생기는 Durable Object. 오늘 날짜와 호출 수만 저장한다."""

    async def try_hit(self, day: str, limit: int) -> bool:
        stored = await self.ctx.storage.get("hits")
        stored_day, _, stored_count = (stored or "").partition(":")
        count = int(stored_count) if stored_day == day else 0
        if count >= limit:
            return False
        await self.ctx.storage.put("hits", f"{day}:{count + 1}")
        return True


class DurableDailyLimiter:
    def __init__(self, namespace: Any, limit: int) -> None:
        self._namespace = namespace
        self._limit = limit

    async def try_hit(self, key: str) -> bool:
        counter = self._namespace.getByName(key)
        return bool(await counter.try_hit(utc_today().isoformat(), self._limit))


def _durable_limiter(request: Request) -> DurableDailyLimiter:
    return DurableDailyLimiter(
        request.scope["env"].DAILY_COUNTER, get_api_settings().daily_limit_per_ip
    )


app.dependency_overrides[limiter_from_settings] = _durable_limiter


class Default(WorkerEntrypoint):  # type: ignore[misc]
    async def fetch(self, request: Any) -> Any:
        _load_settings(self.env)
        return await asgi.fetch(app, request, self.env, self.ctx)
