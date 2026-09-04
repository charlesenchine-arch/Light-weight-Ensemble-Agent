from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentflow.config import available_providers
from agentflow.providers import anthropic as anthropic_provider
from agentflow.providers import openai_compat  # noqa: F401 — keep explicit submodule import
from agentflow.types import ChatMessage, ChatResult, ModelSpec, ProviderName


def has_transport(spec: ModelSpec) -> bool:
    flags = available_providers()
    if flags.get(spec.provider):
        return True
    return bool(flags.get("openrouter") and spec.openrouter_id)


def resolve_transport(spec: ModelSpec) -> tuple[ProviderName, str]:
    flags = available_providers()
    if flags.get(spec.provider):
        return spec.provider, spec.id
    if flags.get("openrouter") and spec.openrouter_id:
        return "openrouter", spec.openrouter_id
    raise RuntimeError(f"No API key can reach model {spec.id}")


def complete(
    spec: ModelSpec,
    messages: list[ChatMessage],
    *,
    tools: list[dict[str, Any]] | None = None,
    json_mode: bool = False,
    max_tokens: int = 8192,
    on_text: Callable[[str], None] | None = None,
) -> ChatResult:
    provider, model_id = resolve_transport(spec)
    if provider == "anthropic":
        return anthropic_provider.complete(
            model=model_id,
            messages=messages,
            tools=tools,
            json_mode=json_mode,
            max_tokens=max_tokens,
            on_text=on_text,
        )
    return openai_compat.complete(
        provider=provider,
        model=model_id,
        messages=messages,
        tools=tools,
        json_mode=json_mode,
        max_tokens=max_tokens,
        on_text=on_text,
    )
