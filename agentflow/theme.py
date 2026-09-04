"""Terminal chrome: colors, banners, badges.

The OS font cannot be changed from here. Hierarchy is bold / dim / italic
plus a warm palette in the same family as Hermes (gold) and Claude Code
(terracotta). Switch with /theme lea|hermes|claude.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agentflow.money import load_prefs, save_prefs


@dataclass(frozen=True)
class Skin:
    name: str
    accent: str
    accent_soft: str
    border: str
    text: str
    muted: str
    ok: str
    warn: str
    err: str
    tool: str
    prompt: str
    surface: str


SKINS: dict[str, Skin] = {
    "lea": Skin(
        name="lea",
        accent="#E8C547",
        accent_soft="#C4A35A",
        border="#8A7048",
        text="#F3E9D2",
        muted="#8A8175",
        ok="#6BBF8A",
        warn="#E09F3E",
        err="#E06C75",
        tool="#7EB8A8",
        prompt="#F3E9D2",
        surface="#2A241C",
    ),
    "hermes": Skin(
        name="hermes",
        accent="#FFD700",
        accent_soft="#FFBF00",
        border="#CD7F32",
        text="#FFF8DC",
        muted="#B8860B",
        ok="#4CAF50",
        warn="#FFA726",
        err="#EF5350",
        tool="#DAA520",
        prompt="#FFF8DC",
        surface="#1A1A2E",
    ),
    "claude": Skin(
        name="claude",
        accent="#D77757",
        accent_soft="#EB9F7F",
        border="#888888",
        text="#F5F0EB",
        muted="#888888",
        ok="#4EBA65",
        warn="#FFC107",
        err="#FF6B80",
        tool="#FD5DB1",
        prompt="#F5F0EB",
        surface="#373737",
    ),
}

STAGE_GLYPH = {
    "router": "·",
    "research": "✧",
    "plan": "✶",
    "design": "✻",
    "code": "✦",
    "review": "✢",
    "fix": "✳",
    "harvest": "·",
}

_current: Skin = SKINS["lea"]


def current() -> Skin:
    return _current


def set_skin(name: str) -> Skin:
    global _current
    key = (name or "lea").strip().lower()
    if key not in SKINS:
        raise ValueError(f"unknown theme {name!r} — lea | hermes | claude")
    _current = SKINS[key]
    prefs = load_prefs()
    prefs["theme"] = key
    save_prefs(prefs)
    return _current


def load_skin_from_prefs() -> Skin:
    prefs = load_prefs()
    name = str(prefs.get("theme") or "lea")
    try:
        return set_skin(name)
    except ValueError:
        return set_skin("lea")


INTRO_EN = (
    "Light-weight Ensemble Agent (LEA) – your cost is our concern. "
    "Automate multi-API workflows with low expense, full autonomy, and any modality."
)
INTRO_ZH = (
    "轻量集成 Agent（LEA）——你的成本，是我们的关切。"
    "以低花费、全自主、任意模态，自动化多 API 工作流。"
)


def banner(workspace: str, mode: str, currency: str) -> Panel:
    skin = current()
    mark = Text()
    mark.append("  ██╗     ███████╗ █████╗\n", style=f"bold {skin.accent}")
    mark.append("  ██║     ██╔════╝██╔══██╗\n", style=f"bold {skin.accent}")
    mark.append("  ██║     █████╗  ███████║\n", style=f"bold {skin.accent_soft}")
    mark.append("  ██║     ██╔══╝  ██╔══██╗\n", style=skin.accent_soft)
    mark.append("  ███████╗███████╗██║  ██║\n", style=skin.border)
    mark.append("  ╚══════╝╚══════╝╚═╝  ╚═╝", style=skin.muted)
    blurb = Text()
    blurb.append("  " + INTRO_EN + "\n", style=f"italic {skin.text}")
    blurb.append("  " + INTRO_ZH, style=f"italic {skin.muted}")
    meta = Text()
    meta.append("  ", style=skin.muted)
    meta.append("workspace", style=f"italic {skin.muted}")
    meta.append(f"  {workspace}\n", style=skin.text)
    meta.append("  ", style=skin.muted)
    meta.append("mode", style=f"italic {skin.muted}")
    meta.append(f"      {mode}    ", style=f"bold {skin.accent}")
    meta.append("currency", style=f"italic {skin.muted}")
    meta.append(f"  {currency.upper()}", style=skin.text)
    hint = Text(
        "  Enter send  ·  Ctrl+S force-send  ·  Ctrl+C interrupt  ·  /keys  /help",
        style=f"italic {skin.muted}",
    )
    body = Group(mark, Text(""), blurb, Text(""), meta, Text(""), hint)
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=skin.border,
        title=Text(" lea ", style=f"bold {skin.accent}"),
        title_align="left",
        padding=(1, 2),
    )


def hairline(label: str = "") -> Rule:
    skin = current()
    return Rule(label, style=skin.border, characters="─")


def input_rule() -> Text:
    """Claude-style dashed rule above the prompt."""
    skin = current()
    return Text("  ─ " + "· " * 18, style=skin.border)


def prompt_prefix() -> str:
    skin = current()
    return f"[bold {skin.accent}]  ❯ [/]"


def badge(role: str) -> Text:
    skin = current()
    glyph = STAGE_GLYPH.get(role, "·")
    color = {
        "plan": skin.accent,
        "design": skin.accent_soft,
        "code": skin.tool,
        "review": skin.warn,
        "fix": skin.ok,
        "research": skin.muted,
    }.get(role, skin.accent)
    t = Text(f"  {glyph} {role}", style=f"bold {color}")
    return t


def tool_line(payload: str) -> Text:
    skin = current()
    t = Text("  ┊ ", style=skin.tool)
    t.append(payload, style=f"italic {skin.muted}")
    return t


def stage_line(payload: str) -> Text:
    """payload: 'code [1/3] → deepseek-v4-flash' or similar."""
    skin = current()
    role = payload.split()[0] if payload else ""
    glyph = STAGE_GLYPH.get(role, "✶")
    color = {
        "plan": skin.accent,
        "design": skin.accent_soft,
        "code": skin.tool,
        "review": skin.warn,
        "fix": skin.ok,
    }.get(role, skin.accent)
    t = Text()
    t.append("  ─" + "─" * 22 + "─  ", style=skin.border)
    t.append(f"{glyph}  ", style=color)
    t.append(payload, style=f"bold {skin.text}")
    return t


def info_line(payload: str) -> Text:
    skin = current()
    t = Text("  · ", style=skin.ok)
    t.append(payload, style=skin.text)
    return t


def warn_line(payload: str) -> Text:
    skin = current()
    t = Text("  ! ", style=f"bold {skin.warn}")
    t.append(payload, style=skin.warn)
    return t


def err_line(payload: str) -> Text:
    skin = current()
    t = Text("  × ", style=f"bold {skin.err}")
    t.append(payload, style=skin.err)
    return t


def ok_line(payload: str) -> Text:
    skin = current()
    t = Text("  ✓ ", style=f"bold {skin.ok}")
    t.append(payload, style=skin.ok)
    return t


def dim_line(payload: str) -> Text:
    skin = current()
    return Text(f"  {payload}", style=f"italic {skin.muted}")


def user_turn(text: str, turn: int) -> Panel:
    """Full user message in scrollback so a long paste can be re-read later."""
    skin = current()
    body = Text(text or "", style=skin.text)
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=skin.accent,
        title=Text(f" you  ·  turn {turn} ", style=f"bold {skin.accent}"),
        title_align="left",
        padding=(0, 1),
        expand=True,
    )


def panel(body, *, title: str, style: str | None = None) -> Panel:
    skin = current()
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=style or skin.border,
        title=Text(f" {title} ", style=f"bold {skin.accent}"),
        title_align="left",
        padding=(0, 1),
    )


def themed_table(title: str = "") -> Table:
    skin = current()
    table = Table(
        title=Text(title, style=f"bold {skin.accent}") if title else None,
        box=box.SIMPLE,
        border_style=skin.border,
        header_style=f"italic {skin.muted}",
        expand=True,
        pad_edge=False,
    )
    return table


class _LiveStdout:
    """Route Rich output into the TUI conversation pane when it is open."""

    def _log(self):
        try:
            from agentflow.composer import _PROMPT_CTX

            return _PROMPT_CTX.get("log_append")
        except Exception:
            return None

    def write(self, data) -> int:
        if not data:
            return 0
        sink = self._log()
        if sink:
            sink(str(data))
            return len(str(data))
        text = str(data)
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            text.encode(encoding)
        except (LookupError, UnicodeEncodeError):
            # Legacy Chinese Windows consoles commonly use GBK. Decorative
            # glyphs should degrade to "?" instead of crashing the whole run.
            text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        return sys.stdout.write(text)

    def flush(self) -> None:
        if self._log():
            return None
        return sys.stdout.flush()

    def isatty(self) -> bool:
        if self._log():
            return False
        return sys.stdout.isatty()

    def fileno(self) -> int:
        return sys.stdout.fileno()

    def __getattr__(self, name):
        return getattr(sys.stdout, name)


def styled_console() -> Console:
    return Console(highlight=False, file=_LiveStdout())
