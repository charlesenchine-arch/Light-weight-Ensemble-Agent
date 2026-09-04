from agentflow.config import ENV_KEYS
from agentflow.retry import (
    clear_health,
    is_healthy,
    is_rate_limited,
    mark_unhealthy,
    run_with_rate_limit_retry,
    wait_seconds,
)
from agentflow.router import pick_model


def test_detects_429():
    assert is_rate_limited(Exception("Error code: 429 - RESOURCE_EXHAUSTED"))
    assert is_rate_limited(Exception("Rate limit exceeded"))
    assert not is_rate_limited(Exception("Error code: 400 - bad request"))


def test_backoff_grows():
    exc = Exception("429")
    assert wait_seconds(exc, 0) == 2.0
    assert wait_seconds(exc, 1) == 4.0
    assert wait_seconds(exc, 3) == 16.0


def test_retry_then_success():
    from agentflow.cancel import clear

    clear()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception("Error code: 429")
        return "ok"

    slept: list[float] = []
    assert run_with_rate_limit_retry(fn, provider="google", sleeper=slept.append) == "ok"
    assert calls["n"] == 3
    assert slept


def test_unhealthy_google_is_skipped():
    clear_health()
    flags = {k: k in {"google", "deepseek"} for k in ENV_KEYS}
    gem = pick_model("design", "balanced", flags)
    assert gem.provider == "google"
    mark_unhealthy("google", seconds=60)
    alt = pick_model("design", "balanced", flags)
    assert alt.provider != "google"
    clear_health()
    assert is_healthy("google")
