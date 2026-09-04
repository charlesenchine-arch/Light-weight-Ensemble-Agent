from agentflow.budget import fit_budget
from agentflow.config import ENV_KEYS
from agentflow.money import fmt, parse_money, to_display, to_usd
from agentflow.types import TaskClass


def flags(*names: str) -> dict:
    return {k: k in names for k in ENV_KEYS}


def test_parse_money():
    assert parse_money("10cny", "usd") == (10.0, "cny")
    assert parse_money("$0.5", "cny") == (0.5, "usd")
    assert parse_money("skip", "cny") is None
    assert parse_money("2", "cny") == (2.0, "cny")


def test_fx_roundtrip():
    usd = to_usd(7.18, "cny")
    assert abs(usd - 1.0) < 0.05
    assert "CNY" in fmt(1.0, "cny")
    assert to_display(1.0, "usd") == 1.0


def test_tiny_budget_skips_review():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=True,
        needs_review=True,
        needs_design=True,
        domains=["backend"],
        summary="add endpoint",
    )
    plan = fit_budget(task, 0.001, flags("xai", "anthropic", "deepseek"))
    assert plan.skip_review is True
    assert plan.mode in {"fast", "budget"}
    assert plan.warnings


def test_large_budget_keeps_review_for_standard_work():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=True,
        needs_review=True,
        summary="add endpoint",
    )
    plan = fit_budget(task, 5.0, flags("xai", "anthropic", "deepseek"), preferred_mode="balanced")
    assert plan.mode in {"balanced", "quality"}
    assert plan.skip_review is False
