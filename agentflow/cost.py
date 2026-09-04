from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, Field

from agentflow.catalog import estimate_usd, get_model
from agentflow.types import ChatMessage, ModelSpec, Usage


class BudgetExceeded(RuntimeError):
    """Raised before an API call that cannot fit inside the remaining budget."""


def conservative_input_tokens(
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
) -> int:
    """Return a provider-agnostic upper estimate for request input tokens.

    Tokenizers differ across vendors. UTF-8 byte length is deliberately used
    instead of the usual chars/4 approximation so budget enforcement errs on
    the safe side, including for Chinese text and tool schemas.
    """
    payload = {
        "messages": [message.model_dump(exclude_none=True) for message in messages],
        "tools": tools or [],
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return len(encoded) + 256


class CostEvent(BaseModel):
    role: str
    model_id: str
    provider: str
    usage: Usage
    usd: float
    note: str = ""


class Ledger(BaseModel):
    events: list[CostEvent] = Field(default_factory=list)
    cap_usd: float = 3.0

    def record(self, role: str, model_id: str, provider: str, usage: Usage, note: str = "") -> CostEvent:
        try:
            spec = get_model(model_id)
            usd = estimate_usd(spec, usage.input_tokens, usage.output_tokens)
            if usage.cached_input_tokens and spec.cached_input_per_m is not None:
                # cached tokens were already counted in input; credit the delta
                uncached = max(usage.input_tokens - usage.cached_input_tokens, 0)
                usd = estimate_usd(spec, uncached, usage.output_tokens)
                usd += (usage.cached_input_tokens / 1_000_000) * spec.cached_input_per_m
                usd = round(usd, 6)
        except KeyError:
            usd = 0.0
        event = CostEvent(
            role=role,
            model_id=model_id,
            provider=provider,
            usage=usage,
            usd=usd,
            note=note,
        )
        self.events.append(event)
        return event

    @property
    def total_usd(self) -> float:
        return round(sum(e.usd for e in self.events), 6)

    @property
    def total_usage(self) -> Usage:
        acc = Usage()
        for event in self.events:
            acc = acc.add(event.usage)
        return acc

    def remaining(self) -> float:
        return round(self.cap_usd - self.total_usd, 6)

    def over_cap(self) -> bool:
        return self.total_usd >= self.cap_usd

    def affordable_output_tokens(
        self,
        model: ModelSpec,
        input_tokens: int,
        requested: int,
    ) -> int:
        """Largest output allowance that keeps the estimated call under cap."""
        if requested <= 0:
            return 0
        remaining = max(self.cap_usd - self.total_usd, 0.0)
        input_usd = (max(input_tokens, 0) / 1_000_000) * model.input_per_m
        if model.output_per_m <= 0:
            return requested if input_usd <= remaining else 0
        output_usd = remaining - input_usd
        if output_usd <= 0:
            return 0
        affordable = math.floor((output_usd * 1_000_000) / model.output_per_m)
        return max(0, min(int(requested), affordable))

    def by_role(self) -> dict[str, float]:
        buckets: dict[str, float] = {}
        for event in self.events:
            buckets[event.role] = round(buckets.get(event.role, 0.0) + event.usd, 6)
        return buckets
