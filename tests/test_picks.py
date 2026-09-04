from agentflow.config import ENV_KEYS
from agentflow.picks import resolve_listed, set_last_index
from agentflow.router import pick_model


def flags(*names: str) -> dict:
    return {k: k in names for k in ENV_KEYS}


def test_user_pin_overrides_router():
    spec = pick_model(
        "code",
        "balanced",
        flags("anthropic", "deepseek"),
        pins={"code": "deepseek-v4-pro"},
    )
    assert spec.id == "deepseek-v4-pro"


def test_pin_kimi_coder():
    spec = pick_model(
        "code",
        "balanced",
        flags("moonshot", "deepseek"),
        pins={"code": "kimi-k2.7-code"},
    )
    assert spec.id == "kimi-k2.7-code"
    assert spec.provider == "moonshot"


def test_user_pin_plan_claude():
    spec = pick_model(
        "plan",
        "budget",
        flags("anthropic", "deepseek"),
        pins={"plan": "claude-opus-5"},
    )
    assert spec.id == "claude-opus-5"


def test_review_pin_ignored_if_same_model_as_coder():
    spec = pick_model(
        "review",
        "balanced",
        flags("deepseek"),
        pins={"review": "deepseek-v4-flash"},
        avoid_model="deepseek-v4-flash",
    )
    assert spec.id != "deepseek-v4-flash"


def test_resolve_listed_index():
    set_last_index(["claude-haiku-4.5", "claude-sonnet-5", "claude-opus-5"])
    assert resolve_listed("2") == "claude-sonnet-5"
    assert resolve_listed("claude-opus-5") == "claude-opus-5"
    try:
        resolve_listed("99")
        raise AssertionError("expected failure")
    except ValueError:
        pass
