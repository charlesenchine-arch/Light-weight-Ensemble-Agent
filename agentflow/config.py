from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agentflow.types import Mode, ProviderName

ENV_KEYS: dict[ProviderName, tuple[str, ...]] = {
    "xai": ("XAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "moonshot": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    "qwen": ("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    "ollama": ("OLLAMA_MODEL",),
    "openrouter": ("OPENROUTER_API_KEY",),
}


class Settings(BaseModel):
    mode: Mode = "balanced"
    language: str = "auto"
    max_cost_usd: float = 3.0
    max_steps: dict[str, int] = Field(
        default_factory=lambda: {
            "router": 1,
            "research": 8,
            "plan": 10,
            "design": 10,
            "code": 20,
            "review": 8,
            "fix": 16,
        }
    )
    shell_policy: str = "allow"
    confirm_dangerous: bool = True
    session_dir: str = ".agentflow/sessions"
    max_code_review_rounds: int = 3
    max_trial_rounds: int = 3
    human_trial: bool = False
    allow_paths: list[str] = Field(default_factory=list)
    llm_classify: bool = False
    harvest_skills: bool = True
    compact_tool_history: bool = True
    currency: str = "cny"
    skip_review: bool = False
    skip_design: bool = False
    ask_budget: bool = True
    workspace: Path = Field(default_factory=lambda: Path.cwd())

    def steps_for(self, role: str) -> int:
        return int(self.max_steps.get(role, 12))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_settings(
    workspace: Path | None = None,
    mode: Mode | None = None,
    max_cost_usd: float | None = None,
) -> Settings:
    root = (workspace or Path.cwd()).resolve()
    # Project .env first, then CWD .env, then user env.
    load_dotenv(root / ".env", override=False)
    lea_home = os.environ.get("LEA_HOME", "").strip()
    if lea_home:
        load_dotenv(Path(lea_home) / ".env", override=False)
    load_dotenv(override=False)

    bundled = Path(__file__).resolve().parent / "defaults.yaml"
    data: dict[str, Any] = {}
    data.update(_read_yaml(bundled))
    data.update(_read_yaml(root / "agentflow.yaml"))

    if mode:
        data["mode"] = mode
    if max_cost_usd is not None:
        data["max_cost_usd"] = max_cost_usd
    data["workspace"] = root
    return Settings.model_validate(data)


def api_key(provider: ProviderName) -> str | None:
    for name in ENV_KEYS[provider]:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def available_providers() -> dict[ProviderName, bool]:
    return {name: bool(api_key(name)) for name in ENV_KEYS}


def require_any_provider() -> None:
    flags = available_providers()
    if not any(flags.values()):
        raise RuntimeError(
            "No provider configured. Set an API key or configure OLLAMA_MODEL."
        )
