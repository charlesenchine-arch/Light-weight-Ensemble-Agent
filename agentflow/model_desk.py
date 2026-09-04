"""The one UI for changing vendor/model defaults.

Pins in ~/.lea/prefs.yaml are just defaults. Later changes all go through
this desk (or the thin `lea use` CLI that writes the same pins).
"""

from __future__ import annotations

from agentflow import theme
from agentflow.catalog import MODELS, PIN_ROLES, PROVIDER_LABEL, PROVIDER_ORDER
from agentflow.config import available_providers
from agentflow.picks import clear_pin, get_pins, set_pin

ROLE_ZH = {
    "plan": "规划",
    "design": "设计",
    "code": "编写",
    "review": "审核",
}


def _show_defaults(console) -> None:
    pins = get_pins()
    skin = theme.current()
    lines = []
    for role in PIN_ROLES:
        glyph = theme.STAGE_GLYPH.get(role, "·")
        zh = ROLE_ZH[role]
        current = pins.get(role)
        if current:
            spec = MODELS[current]
            value = f"{current}  [{spec.provider}]"
            style = f"bold {skin.accent}"
        else:
            value = "auto"
            style = f"italic {skin.muted}"
        lines.append(f"  {glyph} {zh:<4}  [{style}]{value}[/]")
    console.print(theme.panel("\n".join(lines), title="defaults"))


def _ask(console, label: str) -> str:
    skin = theme.current()
    try:
        return console.input(f"[bold {skin.accent}]  {label} ❯ [/]").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _pick_vendor(console, flags: dict) -> str | None:
    """Return provider name, 'auto', or None to cancel."""
    skin = theme.current()
    shown = [p for p in PROVIDER_ORDER if any(m.provider == p for m in MODELS.values())]
    console.print(theme.dim_line("vendor"))
    for i, provider in enumerate(shown, 1):
        ok = flags.get(provider)
        tag = f"[{skin.ok}]key[/]" if ok else f"[{skin.muted} italic]no key[/]"
        console.print(f"    {i}  {PROVIDER_LABEL.get(provider, provider)}  {tag}")
    console.print(f"    [{skin.muted}]a  auto（取消指定）[/]")
    raw = _ask(console, "vendor")
    if not raw:
        return None
    if raw.lower() in {"a", "auto"}:
        return "auto"
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(shown):
            return shown[idx - 1]
    raw = raw.lower()
    for provider in PROVIDER_ORDER:
        label = PROVIDER_LABEL.get(provider, provider).lower()
        if raw == provider or raw in label:
            return provider
    console.print(theme.err_line("unknown vendor"))
    return None


def _pick_model(console, provider: str) -> str | None:
    skin = theme.current()
    specs = [m for m in MODELS.values() if m.provider == provider]
    if not specs:
        console.print(theme.err_line("no models for that vendor"))
        return None
    console.print(theme.dim_line(f"model  ·  {PROVIDER_LABEL.get(provider, provider)}"))
    for i, spec in enumerate(specs, 1):
        console.print(
            f"    {i}  {spec.id}  [{skin.muted}]${spec.input_per_m:.2f}/${spec.output_per_m:.2f}  {spec.quality}[/]"
        )
    raw = _ask(console, "model")
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(specs):
            return specs[idx - 1].id
    hits = [s for s in specs if raw == s.id or raw in s.id]
    if len(hits) == 1:
        return hits[0].id
    console.print(theme.err_line("unknown model"))
    return None


def open_desk() -> None:
    """Interactive: pick a role, then vendor, then model. Enter on role = done."""
    console = theme.styled_console()
    flags = available_providers()
    _show_defaults(console)
    console.print(theme.dim_line("改哪一项  plan / design / code / review  ·  回车结束"))
    while True:
        role = _ask(console, "role").lower()
        if not role:
            return
        aliases = {"规划": "plan", "设计": "design", "编写": "code", "编码": "code", "审核": "review"}
        role = aliases.get(role, role)
        if role not in PIN_ROLES:
            console.print(theme.err_line("plan | design | code | review"))
            continue
        vendor = _pick_vendor(console, flags)
        if vendor is None:
            continue
        if vendor == "auto":
            clear_pin(role)
            console.print(theme.ok_line(f"{ROLE_ZH[role]} → auto"))
            _show_defaults(console)
            continue
        model_id = _pick_model(console, vendor)
        if not model_id:
            continue
        spec = set_pin(role, model_id)
        note = "" if flags.get(spec.provider) else "  （该厂商还没有 key）"
        console.print(theme.ok_line(f"{ROLE_ZH[role]} → {spec.id}{note}"))
        _show_defaults(console)
