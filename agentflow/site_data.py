"""Deterministic public data for the static LEA cost lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentflow.benchmark import benchmark_summary, run_catalog_benchmark
from agentflow.catalog import (
    CATALOG_AS_OF,
    CATALOG_SOURCES,
    MODELS,
    PROVIDER_LABEL,
    TYPICAL_TOKENS,
)


def build_site_data() -> dict[str, Any]:
    rows = run_catalog_benchmark()
    summary = benchmark_summary(rows)
    models = [
        {
            "id": model.id,
            "provider": model.provider,
            "provider_label": PROVIDER_LABEL.get(model.provider, model.provider),
            "input_per_m": model.input_per_m,
            "output_per_m": model.output_per_m,
            "quality": model.quality,
        }
        for model in MODELS.values()
        if model.status == "active" and model.provider not in {"ollama", "openrouter"}
    ]
    return {
        "schema_version": 1,
        "catalog_as_of": CATALOG_AS_OF,
        "method": "catalog-price-model",
        "default_baseline": "grok-4.6",
        "summary": summary,
        "typical_tokens": {role: list(tokens) for role, tokens in TYPICAL_TOKENS.items()},
        "scenarios": [row.as_dict() for row in rows],
        "models": models,
        "pricing_sources": {
            provider: source
            for provider, source in CATALOG_SOURCES.items()
            if provider not in {"ollama", "openrouter"}
        },
        "disclaimer": (
            "A deterministic catalog price estimate using identical stage token assumptions; "
            "it does not claim equal model quality or predict an invoice."
        ),
    }


def write_site_data(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_site_data(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
