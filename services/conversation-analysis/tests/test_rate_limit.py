import asyncio
from datetime import date

from app.api.rate_limit import MemoryDailyLimiter


class _Clock:
    def __init__(self) -> None:
        self.today = date(2026, 10, 14)

    def __call__(self) -> date:
        return self.today


def test_counts_each_key_separately() -> None:
    limiter = MemoryDailyLimiter(2, today=_Clock())

    assert [asyncio.run(limiter.try_hit("a")) for _ in range(3)] == [True, True, False]
    assert asyncio.run(limiter.try_hit("b")) is True


def test_resets_when_day_changes() -> None:
    clock = _Clock()
    limiter = MemoryDailyLimiter(1, today=clock)
    asyncio.run(limiter.try_hit("a"))

    clock.today = date(2026, 10, 15)

    assert asyncio.run(limiter.try_hit("a")) is True
