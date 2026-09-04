"""Model catalog: strengths, prices, and the roles each model should own.

Prices are USD per 1M tokens, verified against vendor documentation. Update
here when vendors change rates — the router never hardcodes prices.
"""

from __future__ import annotations

from agentflow.types import ModelSpec, ProviderName, Role

CATALOG_AS_OF = "2026-09-04"
QWEN_CNY_PER_USD = 7.18
CATALOG_SOURCES: dict[ProviderName, str] = {
    "xai": "https://docs.x.ai/developers/pricing",
    "anthropic": "https://docs.anthropic.com/en/docs/about-claude/pricing",
    "openai": "https://platform.openai.com/docs/models",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing",
    "moonshot": "https://platform.kimi.ai/docs/pricing/chat",
    "qwen": "https://help.aliyun.com/zh/model-studio/model-pricing",
    "ollama": "https://docs.ollama.com/api/openai-compatibility",
    "openrouter": "https://openrouter.ai/models",
}

PROVIDER_ORDER: tuple[ProviderName, ...] = (
    "xai",
    "anthropic",
    "deepseek",
    "moonshot",
    "qwen",
    "ollama",
    "google",
    "openai",
)
PROVIDER_LABEL = {
    "xai": "xAI / Grok",
    "anthropic": "Anthropic / Claude",
    "deepseek": "DeepSeek",
    "moonshot": "Moonshot / Kimi",
    "qwen": "Alibaba / Qwen",
    "ollama": "Ollama / local",
    "google": "Google / Gemini",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
}
PIN_ROLES: tuple[str, ...] = ("plan", "design", "code", "review")


def _model(**data: object) -> ModelSpec:
    provider = data.get("provider")
    if not isinstance(provider, str) or provider not in CATALOG_SOURCES:
        raise ValueError(f"Missing catalog source for provider: {provider}")
    data.setdefault("pricing_source", CATALOG_SOURCES[provider])
    data.setdefault("pricing_verified", CATALOG_AS_OF)
    return ModelSpec.model_validate(data)

# Typical tokens used to estimate a run before it starts.
TYPICAL_TOKENS: dict[Role, tuple[int, int]] = {
    "router": (1200, 400),
    "research": (6000, 1500),
    "plan": (8000, 2000),
    "design": (7000, 2200),
    "code": (18000, 6000),
    "review": (14000, 1800),
    "fix": (12000, 4000),
}

MODELS: dict[str, ModelSpec] = {
    # --- SpaceXAI / xAI -------------------------------------------------
    "grok-4-fast": _model(
        id="grok-4-fast",
        provider="xai",
        openrouter_id="x-ai/grok-4-fast",
        input_per_m=1.25,
        output_per_m=2.50,
        cached_input_per_m=0.20,
        context=1_000_000,
        speed="fast",
        quality="budget",
        strengths=["routing", "triage", "research", "long-context"],
        roles=["router", "research"],
        notes="Retired xAI alias; requests redirect to grok-4.3.",
        pricing_source="https://docs.x.ai/developers/migration/may-15-retirement",
        status="deprecated",
        replacement="grok-4.3",
    ),
    "grok-code-fast-1": _model(
        id="grok-code-fast-1",
        provider="xai",
        openrouter_id="x-ai/grok-code-fast-1",
        input_per_m=1.00,
        output_per_m=2.00,
        cached_input_per_m=0.20,
        context=256_000,
        speed="fast",
        quality="budget",
        strengths=["agentic-coding", "speed", "unit-economics"],
        roles=["code", "fix"],
        notes="Retired xAI alias; requests redirect to grok-build-0.1.",
        pricing_source="https://docs.x.ai/developers/migration/may-15-retirement",
        status="deprecated",
        replacement="grok-build-0.1",
    ),
    "grok-build-0.1": _model(
        id="grok-build-0.1",
        provider="xai",
        openrouter_id="x-ai/grok-build-0.1",
        input_per_m=1.00,
        output_per_m=2.00,
        cached_input_per_m=0.20,
        context=256_000,
        speed="fast",
        quality="standard",
        strengths=["agentic-coding", "web", "debug", "mcp"],
        roles=["code", "fix", "plan"],
        notes="Coding-tuned Grok. Balanced default implementer.",
    ),
    "grok-4.3": _model(
        id="grok-4.3",
        provider="xai",
        openrouter_id="x-ai/grok-4.3",
        input_per_m=1.25,
        output_per_m=2.50,
        cached_input_per_m=0.20,
        context=1_000_000,
        speed="medium",
        quality="standard",
        strengths=["planning", "long-context", "general"],
        roles=["plan", "research"],
        notes="Mid-tier Grok. Standard planning without frontier price.",
    ),
    "grok-4.6": _model(
        id="grok-4.6",
        provider="xai",
        openrouter_id="x-ai/grok-4.6",
        input_per_m=2.00,
        output_per_m=6.00,
        cached_input_per_m=0.50,
        context=500_000,
        speed="medium",
        quality="frontier",
        strengths=[
            "coding",
            "long-running-agents",
            "visual-ui",
            "architecture",
            "tool-calling",
        ],
        roles=["plan", "design", "code", "review", "fix", "research"],
        notes="Flagship. Hard coding, visual/UI work, long agent loops.",
    ),
    # --- Anthropic ------------------------------------------------------
    "claude-haiku-4.5": _model(
        id="claude-haiku-4.5",
        provider="anthropic",
        openrouter_id="anthropic/claude-haiku-4.5",
        input_per_m=1.00,
        output_per_m=5.00,
        cached_input_per_m=0.10,
        context=200_000,
        speed="fast",
        quality="budget",
        strengths=["triage", "cheap-review"],
        roles=["router", "review"],
        notes="Cheap Claude. Fallback router / light review.",
    ),
    "claude-sonnet-5": _model(
        id="claude-sonnet-5",
        provider="anthropic",
        openrouter_id="anthropic/claude-sonnet-5",
        input_per_m=2.00,
        output_per_m=10.00,
        cached_input_per_m=0.20,
        context=1_000_000,
        speed="medium",
        quality="standard",
        strengths=["repo-reasoning", "review", "long-horizon", "refactor"],
        roles=["review", "plan", "code"],
        notes="Cross-vendor reviewer. Catches Grok-blind spots in repos.",
    ),
    "claude-opus-5": _model(
        id="claude-opus-5",
        provider="anthropic",
        openrouter_id="anthropic/claude-opus-5",
        input_per_m=5.00,
        output_per_m=25.00,
        cached_input_per_m=0.50,
        context=1_000_000,
        speed="slow",
        quality="frontier",
        strengths=["architecture", "hard-reasoning", "review", "long-horizon"],
        roles=["plan", "review"],
        notes="Quality-mode planner/reviewer for hard architecture.",
    ),
    # --- OpenAI ---------------------------------------------------------
    "gpt-5.6-luna": _model(
        id="gpt-5.6-luna",
        provider="openai",
        openrouter_id="openai/gpt-5.6-luna",
        input_per_m=0.20,
        output_per_m=1.20,
        cached_input_per_m=0.02,
        context=1_050_000,
        speed="fast",
        quality="budget",
        strengths=["triage", "cheap-chat"],
        roles=["router", "research"],
        notes="Cheap OpenAI. Fallback router if xAI is down.",
    ),
    "gpt-5.6-terra": _model(
        id="gpt-5.6-terra",
        provider="openai",
        openrouter_id="openai/gpt-5.6-terra",
        input_per_m=2.00,
        output_per_m=12.00,
        cached_input_per_m=0.20,
        context=1_050_000,
        speed="medium",
        quality="standard",
        strengths=["general", "review", "terminal"],
        roles=["review", "code"],
        notes="Mid OpenAI. Alternate cross-vendor reviewer.",
    ),
    "gpt-5.6-sol": _model(
        id="gpt-5.6-sol",
        provider="openai",
        openrouter_id="openai/gpt-5.6-sol",
        input_per_m=4.00,
        output_per_m=20.00,
        cached_input_per_m=0.40,
        context=1_050_000,
        speed="slow",
        quality="frontier",
        strengths=["terminal", "coding-bench", "hard-debug"],
        roles=["code", "review"],
        notes="Terminal-Bench class. Quality-mode shell-heavy work only.",
    ),
    # --- Google ---------------------------------------------------------
    "gemini-3.8-flash": _model(
        id="gemini-3.8-flash",
        provider="google",
        openrouter_id=None,
        input_per_m=0.75,
        output_per_m=3.75,
        cached_input_per_m=0.075,
        context=1_048_576,
        speed="fast",
        quality="standard",
        strengths=["ui", "visual", "frontend", "coding", "long-horizon", "agents"],
        roles=["design", "code", "review", "plan"],
        notes="Latest GA Gemini Flash. Native API until an OpenRouter route is verified.",
    ),
    "gemini-3.7-flash": _model(
        id="gemini-3.7-flash",
        provider="google",
        openrouter_id="google/gemini-3.7-flash",
        input_per_m=0.75,
        output_per_m=3.75,
        cached_input_per_m=0.075,
        context=1_048_576,
        speed="fast",
        quality="standard",
        strengths=["ui", "visual", "frontend", "multimodal", "design-adherence"],
        roles=["design", "code", "review"],
        notes="UI/visual specialist. Design stage + frontend polish.",
    ),
    "gemini-3.6-flash": _model(
        id="gemini-3.6-flash",
        provider="google",
        openrouter_id="google/gemini-3.6-flash",
        input_per_m=0.75,
        output_per_m=3.75,
        cached_input_per_m=0.075,
        context=1_048_576,
        speed="fast",
        quality="standard",
        strengths=["ui", "frontend", "multimodal"],
        roles=["design", "code"],
        notes="Fallback Gemini if 3.7 is unavailable.",
    ),
    # --- DeepSeek -------------------------------------------------------
    "deepseek-v4-flash": _model(
        id="deepseek-v4-flash",
        provider="deepseek",
        openrouter_id="deepseek/deepseek-v4-flash",
        input_per_m=0.14,
        output_per_m=0.28,
        cached_input_per_m=0.0028,
        context=1_000_000,
        speed="fast",
        quality="budget",
        strengths=["bulk-code", "unit-economics", "mechanical-edits"],
        roles=["code", "fix"],
        notes="Cheapest capable coder. Budget mode and bulk refactors.",
    ),
    "deepseek-v4-pro": _model(
        id="deepseek-v4-pro",
        provider="deepseek",
        openrouter_id="deepseek/deepseek-v4-pro",
        input_per_m=0.435,
        output_per_m=0.87,
        cached_input_per_m=0.003625,
        context=1_000_000,
        speed="medium",
        quality="standard",
        strengths=["coding", "value"],
        roles=["code", "fix", "plan"],
        notes="Strong cheap coder when Grok Build is unavailable.",
    ),
    # --- Moonshot / Kimi ------------------------------------------------
    "kimi-k2.7-code": _model(
        id="kimi-k2.7-code",
        provider="moonshot",
        openrouter_id="moonshotai/kimi-k2.7-code",
        input_per_m=0.95,
        output_per_m=4.00,
        cached_input_per_m=0.19,
        context=262_144,
        speed="medium",
        quality="standard",
        strengths=["agentic-coding", "coding", "tool-calling"],
        roles=["code", "fix"],
        notes="Kimi coding specialist. Use when DeepSeek is missing or pinned.",
    ),
    "kimi-k2.7-code-highspeed": _model(
        id="kimi-k2.7-code-highspeed",
        provider="moonshot",
        openrouter_id=None,
        input_per_m=1.90,
        output_per_m=8.00,
        cached_input_per_m=0.38,
        context=262_144,
        speed="fast",
        quality="standard",
        strengths=["agentic-coding", "speed", "coding"],
        roles=["code", "fix"],
        notes="Faster K2.7 Code. Pin for latency; costs about 2× the standard coder.",
    ),
    "kimi-k3": _model(
        id="kimi-k3",
        provider="moonshot",
        openrouter_id="moonshotai/kimi-k3",
        input_per_m=3.00,
        output_per_m=15.00,
        cached_input_per_m=0.30,
        context=1_048_576,
        speed="medium",
        quality="frontier",
        strengths=["planning", "review", "long-horizon", "architecture", "coding"],
        roles=["plan", "review", "research"],
        notes="Kimi flagship. Planner/reviewer when Claude/Grok keys are missing.",
    ),
    # --- Alibaba / Qwen (DashScope OpenAI-compatible) -------------------
    # Beijing list prices converted at catalog FX (~7.18 CNY/USD).
    "qwen3.7-flash": _model(
        id="qwen3.7-flash",
        provider="qwen",
        openrouter_id="qwen/qwen3.7-flash",
        input_per_m=0.03,
        output_per_m=0.11,
        cached_input_per_m=0.003,
        context=1_000_000,
        speed="fast",
        quality="budget",
        strengths=["bulk-code", "unit-economics", "speed", "triage"],
        roles=["code", "fix", "router", "design"],
        notes="Cheapest Qwen. Budget coding and fallback router.",
    ),
    "qwen3-coder-plus": _model(
        id="qwen3-coder-plus",
        provider="qwen",
        openrouter_id="qwen/qwen3-coder-plus",
        input_per_m=0.56,
        output_per_m=2.23,
        cached_input_per_m=0.056,
        context=1_000_000,
        speed="medium",
        quality="standard",
        strengths=["agentic-coding", "coding", "tool-calling"],
        roles=["code", "fix"],
        notes="Qwen coding agent. Default Qwen implementer.",
    ),
    "qwen3.8-max": _model(
        id="qwen3.8-max",
        provider="qwen",
        openrouter_id="qwen/qwen3.8-max",
        input_per_m=1.67,
        output_per_m=5.01,
        cached_input_per_m=0.209,
        context=1_000_000,
        speed="medium",
        quality="frontier",
        strengths=["planning", "review", "coding", "architecture"],
        roles=["plan", "review", "research"],
        notes="Qwen flagship. Planner/reviewer on DashScope (CN by default).",
    ),
    # --- Local ----------------------------------------------------------
    "ollama-local": _model(
        id="ollama-local",
        provider="ollama",
        openrouter_id=None,
        input_per_m=0.0,
        output_per_m=0.0,
        cached_input_per_m=0.0,
        context=128_000,
        speed="medium",
        quality="standard",
        strengths=["local", "privacy", "zero-api-cost", "coding"],
        roles=["router", "research", "plan", "code", "review", "fix"],
        notes="User-selected Ollama model. Hardware and electricity are outside the API ledger.",
    ),
}


def models_by_provider() -> dict[str, list[ModelSpec]]:
    grouped: dict[str, list[ModelSpec]] = {p: [] for p in PROVIDER_ORDER}
    for spec in MODELS.values():
        if spec.status != "active":
            continue
        grouped.setdefault(spec.provider, []).append(spec)
    return {k: v for k, v in grouped.items() if v}


def get_model(model_id: str) -> ModelSpec:
    if model_id not in MODELS:
        raise KeyError(f"Unknown model: {model_id}")
    return MODELS[model_id]


def models_for_provider(provider: ProviderName) -> list[ModelSpec]:
    return [m for m in MODELS.values() if m.provider == provider and m.status == "active"]


def estimate_usd(model: ModelSpec, input_tokens: int, output_tokens: int) -> float:
    inp = (input_tokens / 1_000_000) * model.input_per_m
    out = (output_tokens / 1_000_000) * model.output_per_m
    return round(inp + out, 6)


def estimate_stage(model: ModelSpec, role: Role) -> float:
    inn, out = TYPICAL_TOKENS.get(role, (4000, 1000))
    return estimate_usd(model, inn, out)
