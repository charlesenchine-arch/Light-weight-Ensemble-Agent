"""Deterministic catalog benchmark for LEA's cost-aware routing policy."""

from __future__ import annotations

from dataclasses import dataclass

from agentflow.catalog import estimate_stage, get_model
from agentflow.config import ENV_KEYS
from agentflow.router import build_pipeline, heuristic_classify
from agentflow.types import Mode


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    task: str


@dataclass(frozen=True)
class BenchmarkRow:
    case: str
    roles: tuple[str, ...]
    route: tuple[str, ...]
    providers: int
    lea_usd: float
    baseline_usd: float
    savings_percent: float

    def as_dict(self) -> dict[str, object]:
        return {
            "case": self.case,
            "roles": list(self.roles),
            "route": list(self.route),
            "providers": self.providers,
            "lea_usd": self.lea_usd,
            "baseline_usd": self.baseline_usd,
            "savings_percent": self.savings_percent,
        }


DEFAULT_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase("Backend feature", "Add pagination and validation to the users API"),
    BenchmarkCase("Frontend UI", "Redesign and implement a responsive login page UI"),
    BenchmarkCase("Hard architecture", "Refactor the payment pipeline for concurrency safety"),
    BenchmarkCase("Bug fix", "Fix the failing authentication test"),
)


def run_catalog_benchmark(
    *,
    mode: Mode = "balanced",
    baseline_model: str = "grok-4.6",
    cases: tuple[BenchmarkCase, ...] = DEFAULT_CASES,
) -> list[BenchmarkRow]:
    """Compare LEA routing with one model doing the same estimated stages.

    This is a price-model benchmark, not a quality claim. Both sides use the
    same role-specific typical token counts from the public catalog.
    """
    baseline = get_model(baseline_model)
    # The published benchmark compares hosted API routes. Ollama is opt-in and its
    # hardware-dependent local cost is deliberately outside this price comparison.
    available = {provider: provider not in {"openrouter", "ollama"} for provider in ENV_KEYS}
    rows: list[BenchmarkRow] = []

    for case in cases:
        classification = heuristic_classify(case.task)
        pipeline = build_pipeline(
            classification,
            mode,
            available,
            pins={},
        )
        lea_cost = round(sum(estimate_stage(stage.model, stage.role) for stage in pipeline.stages), 6)
        baseline_cost = round(
            sum(estimate_stage(baseline, stage.role) for stage in pipeline.stages),
            6,
        )
        savings = 0.0
        if baseline_cost > 0:
            savings = round((1 - (lea_cost / baseline_cost)) * 100, 1)
        rows.append(
            BenchmarkRow(
                case=case.name,
                roles=tuple(stage.role for stage in pipeline.stages),
                route=tuple(stage.model.id for stage in pipeline.stages),
                providers=len({stage.model.provider for stage in pipeline.stages}),
                lea_usd=lea_cost,
                baseline_usd=baseline_cost,
                savings_percent=savings,
            )
        )
    return rows


def benchmark_summary(rows: list[BenchmarkRow]) -> dict[str, float]:
    lea_total = round(sum(row.lea_usd for row in rows), 6)
    baseline_total = round(sum(row.baseline_usd for row in rows), 6)
    savings = round((1 - lea_total / baseline_total) * 100, 1) if baseline_total else 0.0
    return {
        "lea_usd": lea_total,
        "baseline_usd": baseline_total,
        "savings_percent": savings,
    }
