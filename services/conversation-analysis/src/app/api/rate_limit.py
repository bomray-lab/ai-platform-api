from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Protocol

from app.settings import get_api_settings


def utc_today() -> date:
    return datetime.now(UTC).date()


class DailyLimiter(Protocol):
    """키(IP)별 하루 호출 수. 한도 안이면 1 늘리고 True, 넘었으면 False."""

    async def try_hit(self, key: str) -> bool: ...


class MemoryDailyLimiter:
    """메모리에 센다. 프로세스를 다시 띄우면 초기화되고, 여러 프로세스 사이에서는 공유되지 않는다.

    날짜는 Cloudflare 무료 한도와 같은 UTC 기준으로 바뀐다.
    """

    def __init__(self, limit: int, today: Callable[[], date] = utc_today) -> None:
        self._limit = limit
        self._today = today
        self._day = today()
        self._counts: dict[str, int] = {}

    async def try_hit(self, key: str) -> bool:
        today = self._today()
        if today != self._day:
            self._day = today
            self._counts.clear()
        count = self._counts.get(key, 0)
        if count >= self._limit:
            return False
        self._counts[key] = count + 1
        return True


@lru_cache
def limiter_from_settings() -> DailyLimiter:
    return MemoryDailyLimiter(get_api_settings().daily_limit_per_ip)
