"""User-picked models per role. Same vendor key, different model."""

from __future__ import annotations

import os

from agentflow.catalog import MODELS, PIN_ROLES, get_model
from agentflow.money import load_prefs, save_prefs
from agentflow.types import ModelSpec

_LAST_INDEX: list[str] = []


def get_pins() -> dict[str, str]:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    raw = load_prefs().get("role_models") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for role, model_id in raw.items():
        if role in PIN_ROLES and isinstance(model_id, str) and model_id in MODELS:
            out[role] = model_id
    return out


def set_pin(role: str, model_id: str) -> ModelSpec:
    if role not in PIN_ROLES:
        raise ValueError(f"role must be one of: {', '.join(PIN_ROLES)}")
    spec = get_model(model_id)
    prefs = load_prefs()
    pins = dict(prefs.get("role_models") or {})
    pins[role] = spec.id
    prefs["role_models"] = {k: v for k, v in pins.items() if v}
    save_prefs(prefs)
    return spec


def clear_pin(role: str | None = None) -> None:
    prefs = load_prefs()
    pins = dict(prefs.get("role_models") or {})
    if role:
        pins.pop(role, None)
    else:
        pins = {}
    prefs["role_models"] = pins
    save_prefs(prefs)


def resolve_listed(token: str) -> str:
    """Accept a model id or a 1-based index from the last printed list."""
    token = (token or "").strip()
    if token.isdigit():
        idx = int(token) - 1
        if 0 <= idx < len(_LAST_INDEX):
            return _LAST_INDEX[idx]
        raise ValueError(f"no model #{token} — run `lea models` first")
    if token in MODELS:
        return token
    # prefix match
    hits = [mid for mid in MODELS if mid.startswith(token) or token in mid]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"unknown model {token!r}")


def set_last_index(ids: list[str]) -> None:
    global _LAST_INDEX
    _LAST_INDEX = list(ids)
