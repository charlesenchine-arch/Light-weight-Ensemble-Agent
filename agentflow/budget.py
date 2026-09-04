"""Map a dollar cap onto mode + which stages we can afford."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentflow.router import build_pipeline
from agentflow.types import Mode, ProviderName, TaskClass


@dataclass
class BudgetPlan:
    mode: Mode
    skip_review: bool
    skip_design: bool
    harvest: bool
    max_review_rounds: int
    expected: str
    estimated_usd: float
    warnings: list[str] = field(default_factory=list)


def _estimate(task: TaskClass, mode: Mode, available: dict[ProviderName, bool] | None, **flags) -> float:
    pipe = build_pipeline(task, mode, available, skip_review=flags.get("skip_review", False), skip_design=flags.get("skip_design", False))
    return pipe.estimated_usd


def _target_mode(budget_usd: float, complexity: str) -> Mode:
    if budget_usd < 0.08:
        return "fast"
    if budget_usd < 0.35:
        return "budget"
    if budget_usd >= 2.0 and complexity == "hard":
        return "quality"
    return "balanced"


def _downgrade(mode: Mode) -> list[Mode]:
    order: list[Mode] = ["quality", "balanced", "budget", "fast"]
    try:
        return order[order.index(mode) :]
    except ValueError:
        return ["budget", "fast"]


def fit_budget(
    task: TaskClass,
    budget_usd: float | None,
    available: dict[ProviderName, bool] | None = None,
    preferred_mode: Mode | None = None,
) -> BudgetPlan:
    if budget_usd is None or budget_usd <= 0:
        mode = preferred_mode or "balanced"
        pipe = build_pipeline(task, mode, available)
        return BudgetPlan(
            mode=mode,
            skip_review=mode in {"fast", "budget"} and task.complexity != "hard",
            skip_design=False,
            harvest=True,
            max_review_rounds=3 if mode == "quality" else 2 if mode == "balanced" else 1,
            expected={"quality": "高质量", "balanced": "稳妥", "budget": "省钱", "fast": "尽快"}[mode],
            estimated_usd=pipe.estimated_usd,
        )

    start = preferred_mode or _target_mode(budget_usd, task.complexity)
    headroom = budget_usd * 0.85

    for mode in _downgrade(start):
        full = _estimate(task, mode, available)
        if full <= headroom:
            return BudgetPlan(
                mode=mode,
                skip_review=mode == "fast" or (mode == "budget" and task.complexity != "hard"),
                skip_design=False,
                harvest=mode not in {"fast"},
                max_review_rounds=1 if mode in {"fast", "budget"} else 2,
                expected={"quality": "高质量", "balanced": "稳妥", "budget": "省钱", "fast": "尽快"}[mode],
                estimated_usd=full,
            )
        no_review = _estimate(task, mode, available, skip_review=True)
        if no_review <= headroom:
            return BudgetPlan(
                mode=mode,
                skip_review=True,
                skip_design=False,
                harvest=mode not in {"fast"},
                max_review_rounds=1,
                expected="省钱（无审核）",
                estimated_usd=no_review,
                warnings=[
                    f"预算不够覆盖「{mode} + 审核」（估 ${full:.3f}），已取消审核模型。",
                    "风险：正确性、安全和设计偏差不会有第二双眼睛。改完请自己扫 diff。",
                ],
            )

    austere = _estimate(task, "fast", available, skip_review=True, skip_design=True)
    return BudgetPlan(
        mode="fast",
        skip_review=True,
        skip_design=True,
        harvest=False,
        max_review_rounds=1,
        expected="最低可用",
        estimated_usd=austere,
        warnings=[
            f"预算 ${budget_usd:.3f} 远低于工作量预估，已降到最低路径（无规划升级 / 无审核 / 无设计）。",
            "风险：可能漏测、漏安全和实现不完整。不适合生产改动。",
        ],
    )
