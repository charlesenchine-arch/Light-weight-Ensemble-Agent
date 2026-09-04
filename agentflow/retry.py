"""429 / rate-limit retries so Gemini quota blips don't kill a turn."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from agentflow.cancel import Cancelled
from agentflow.cancel import check as cancel_check
from agentflow.cancel import wait as cancel_wait

T = TypeVar("T")

_UNHEALTHY_UNTIL: dict[str, float] = {}
COOLDOWN_SEC = 90.0


def is_rate_limited(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "429",
            "rate limit",
            "rate_limit",
            "too many requests",
            "resource_exhausted",
            "resource exhausted",
            "quota exceeded",
            "quota_exceeded",
        )
    )


def wait_seconds(exc: BaseException, attempt: int) -> float:
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 1.0), 30.0)
        except (TypeError, ValueError):
            pass
    return min(2.0 * (2**attempt), 16.0)


def mark_unhealthy(provider: str, seconds: float = COOLDOWN_SEC) -> None:
    _UNHEALTHY_UNTIL[provider] = time.time() + seconds


def is_healthy(provider: str) -> bool:
    until = _UNHEALTHY_UNTIL.get(provider, 0.0)
    return time.time() >= until


def clear_health() -> None:
    _UNHEALTHY_UNTIL.clear()


def run_with_rate_limit_retry(
    fn: Callable[[], T],
    *,
    provider: str,
    attempts: int = 4,
    sleeper: Callable[[float], None] = time.sleep,
    on_wait: Callable[[float, int], None] | None = None,
) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            cancel_check()
            return fn()
        except Cancelled:
            raise
        except Exception as exc:
            if not is_rate_limited(exc) or attempt >= attempts - 1:
                if is_rate_limited(exc):
                    mark_unhealthy(provider)
                raise
            last = exc
            delay = wait_seconds(exc, attempt)
            if on_wait:
                on_wait(delay, attempt + 1)
            try:
                cancel_check()
            except Cancelled:
                raise
            if sleeper is time.sleep:
                cancel_wait(delay)
            else:
                sleeper(delay)
    assert last is not None
    mark_unhealthy(provider)
    raise last
