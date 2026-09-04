from agentflow.agent.loop import RoleOutcome, run_role
from agentflow.agent.pipeline import is_pass, run_pipeline
from agentflow.budget import BudgetPlan
from agentflow.catalog import get_model
from agentflow.config import Settings
from agentflow.cost import BudgetExceeded, Ledger
from agentflow.types import Pipeline, Stage, TaskClass
from agentflow.workspace import Workspace


def test_is_pass_tokens():
    assert is_pass("pass")
    assert is_pass("通过")
    assert is_pass("LGTM")
    assert not is_pass("按钮颜色不对")


def test_review_loop_uses_fix_role_after_first_review(monkeypatch, tmp_path):
    classification = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=False,
        needs_review=True,
    )
    stages = [
        Stage(role="code", model=get_model("deepseek-v4-flash"), reason="code", tools="all"),
        Stage(role="review", model=get_model("claude-sonnet-5"), reason="review", tools="read"),
        Stage(role="fix", model=get_model("deepseek-v4-flash"), reason="fix", tools="all"),
    ]
    pipeline = Pipeline(classification=classification, mode="balanced", stages=stages)
    calls: list[str] = []
    reviews = iter([1, 0])

    monkeypatch.setattr("agentflow.agent.pipeline.require_any_provider", lambda: None)
    monkeypatch.setattr("agentflow.agent.pipeline.classify_task", lambda *args: classification)
    monkeypatch.setattr("agentflow.agent.pipeline.build_pipeline", lambda *args, **kwargs: pipeline)
    monkeypatch.setattr(
        "agentflow.budget.fit_budget",
        lambda *args, **kwargs: BudgetPlan(
            mode="balanced",
            skip_review=False,
            skip_design=False,
            harvest=False,
            max_review_rounds=2,
            expected="test",
            estimated_usd=1,
        ),
    )

    def fake_run_role(stage, *args, **kwargs):
        calls.append(stage.role)
        blocking = next(reviews) if stage.role == "review" else 0
        return RoleOutcome(text=stage.role, finished=True, blocking_issues=blocking)

    monkeypatch.setattr("agentflow.agent.pipeline.run_role", fake_run_role)
    settings = Settings(
        workspace=tmp_path,
        mode="balanced",
        max_cost_usd=10,
        max_code_review_rounds=2,
        harvest_skills=False,
    )
    result = run_pipeline("implement endpoint", settings)

    assert result.stopped is None
    assert calls == ["code", "review", "fix", "review"]


def test_run_role_refuses_api_call_that_cannot_fit_budget(monkeypatch, tmp_path):
    called = False

    def fake_complete(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider should not be called")

    monkeypatch.setattr("agentflow.agent.loop.complete", fake_complete)
    settings = Settings(workspace=tmp_path, max_cost_usd=0.000001)
    stage = Stage(
        role="review",
        model=get_model("claude-sonnet-5"),
        reason="test",
        max_steps=1,
        tools="read",
    )

    try:
        run_role(
            stage,
            "review",
            TaskClass(intent="review"),
            Workspace(tmp_path),
            settings,
            Ledger(cap_usd=settings.max_cost_usd),
            {},
        )
        raise AssertionError("should have raised BudgetExceeded")
    except BudgetExceeded:
        pass
    assert called is False
