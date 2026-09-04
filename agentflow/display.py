"""Terminal cost board: per-process (plan / design / code / review) bars."""

from __future__ import annotations

import html
import sys
from collections import defaultdict

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentflow import theme
from agentflow.cost import Ledger
from agentflow.money import fmt, normalize_currency

ROLE_LABEL = {
    "router": "分类",
    "research": "检索",
    "plan": "规划",
    "design": "设计",
    "code": "编写",
    "review": "审核",
    "fix": "修补",
    "harvest": "沉淀",
}

ROLE_ORDER = ("plan", "design", "code", "review", "fix", "research", "router", "harvest")


def explain_failure(
    exc: BaseException | str | None = None,
    *,
    stage: str | None = None,
    model: str | None = None,
    stopped: str | None = None,
    changed: list[str] | None = None,
) -> str:
    """Plain-language Chinese note so a failed turn does not look like a crash."""
    raw = str(exc) if exc is not None else (stopped or "")
    low = raw.lower()
    where = ROLE_LABEL.get(stage or "", stage or "未知步骤")
    who = model or "当前模型"
    if stopped == "interrupted" or "已打断" in raw:
        reason = "你按了 Ctrl+C，这一轮停在半路。"
    elif "429" in low or "rate limit" in low or "resource_exhausted" in low or "quota" in low:
        reason = f"{who} 额度或速率用满了（429）。系统会尽量换其他模型；若仍失败，等一两分钟再试。"
    elif "401" in low or "invalid api key" in low or "incorrect api key" in low or "authentication" in low:
        reason = f"{who} 的密钥无效。打开项目里的 .env 检查对应 API key。"
    elif "thought_signature" in low:
        reason = f"{who} 的工具调用签名丢失（Gemini）。再发一次；若仍失败，把这一步改到其他厂商。"
    elif "timeout" in low or "timed out" in low:
        reason = f"{who} 请求超时。网络不稳或模型太慢。"
    elif "connection" in low or "connect" in low:
        reason = f"连不上 {who}。检查网络或该厂商是否宕机。"
    elif "no api key" in low or "no reachable" in low or "no model" in low:
        reason = "这一步没有可用模型。运行 lea doctor 看哪些厂商 ready。"
    elif "cost cap" in low or "预算" in raw:
        reason = "这一轮预算用完了。用 /budget 10cny 加一点，或 /mode fast。"
    elif raw:
        clip = raw.replace("\n", " ").strip()
        if len(clip) > 280:
            clip = clip[:280] + "…"
        reason = f"{who} 返回错误：{clip}"
    else:
        reason = "这一轮没有正常结束。"
    lines = [
        f"卡在：{where}" + (f"  ·  {who}" if model else ""),
        reason,
        "",
        "输入框已清空，直接打下一步即可。",
        "要重做刚才那句：/retry",
    ]
    if changed:
        lines.append("已改过的文件可用 /undo 撤回。")
    return "\n".join(lines)


def _bar(fraction: float, width: int = 22, color: str = "cyan") -> Text:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(width * fraction))
    body = "█" * filled + "░" * (width - filled)
    return Text(body, style=color)


def role_totals(ledger: Ledger) -> list[tuple[str, int, float, str]]:
    """role, calls, usd, models used."""
    buckets: dict[str, dict] = defaultdict(lambda: {"calls": 0, "usd": 0.0, "models": []})
    for event in ledger.events:
        slot = buckets[event.role]
        slot["calls"] += 1
        slot["usd"] += event.usd
        if event.model_id not in slot["models"]:
            slot["models"].append(event.model_id)
    ordered = [r for r in ROLE_ORDER if r in buckets]
    ordered += [r for r in buckets if r not in ROLE_ORDER]
    return [
        (role, buckets[role]["calls"], round(buckets[role]["usd"], 6), " · ".join(buckets[role]["models"]))
        for role in ordered
    ]


def render_costboard(
    ledger: Ledger,
    currency: str = "usd",
    *,
    title: str = "Cost",
    session_usd: float | None = None,
) -> Panel:
    currency = normalize_currency(currency)
    rows = role_totals(ledger)
    total = ledger.total_usd
    cap = ledger.cap_usd
    peak = max((r[2] for r in rows), default=0.0) or 1.0
    skin = theme.current()
    role_color = {
        "plan": skin.accent,
        "design": skin.accent_soft,
        "code": skin.tool,
        "review": skin.warn,
        "fix": skin.ok,
        "research": skin.muted,
        "router": skin.muted,
        "harvest": skin.muted,
    }

    table = theme.themed_table("")
    table.add_column("过程")
    table.add_column("次数", justify="right")
    table.add_column("花费", justify="right")
    table.add_column("占比", min_width=26)

    for role, calls, usd, _models in rows:
        color = role_color.get(role, skin.accent)
        glyph = theme.STAGE_GLYPH.get(role, "·")
        label = ROLE_LABEL.get(role, role)
        share = usd / total if total else 0.0
        share_cell = _bar(usd / peak, color=color)
        share_cell.append(f" {share:.0%}", style=f"italic {skin.muted}")
        table.add_row(
            Text(f"{glyph} {label}", style=f"bold {color}"),
            str(calls),
            fmt(usd, currency),
            share_cell,
        )

    spent_frac = min(1.0, total / cap) if cap else 0.0
    bar_color = skin.ok if spent_frac < 0.7 else skin.warn if spent_frac < 0.95 else skin.err
    budget_line = Text.assemble(
        ("  合计  ", f"italic {skin.muted}"),
        _bar(spent_frac, width=28, color=bar_color),
        (f"  {fmt(total, currency)} / {fmt(cap, currency)}", f"bold {skin.text}"),
    )
    leftover = max(cap - total, 0)
    extra = f"剩余 {fmt(leftover, currency)}"
    if session_usd is not None and session_usd != total:
        extra += f"  · 本会话累计 {fmt(session_usd, currency)}"
    footer = Text("  " + extra, style=f"italic {skin.muted}")

    if not rows:
        body = Text("  还没有花费", style=f"italic {skin.muted}")
    else:
        body = Group(table, Text(""), budget_line, footer)
    return theme.panel(body, title=f"{title}  ·  {currency.upper()}")


def compact_spend(ledger: Ledger, currency: str) -> str:
    return f"{fmt(ledger.total_usd, currency)} / {fmt(ledger.cap_usd, currency)}"


SIDEBAR_WIDTH = 42


def render_cost_sidebar(ledger: Ledger, currency: str = "usd", *, title: str = "花费") -> Panel:
    """Narrow chart that sits on the right of the dialog."""
    currency = normalize_currency(currency)
    rows = role_totals(ledger)
    total = ledger.total_usd
    cap = ledger.cap_usd
    peak = max((r[2] for r in rows), default=0.0) or 1.0
    skin = theme.current()
    role_color = {
        "plan": skin.accent,
        "design": skin.accent_soft,
        "code": skin.tool,
        "review": skin.warn,
        "fix": skin.ok,
        "research": skin.muted,
        "router": skin.muted,
        "harvest": skin.muted,
    }
    body = Text()
    shown = [r for r in rows if r[0] in {"plan", "design", "code", "review", "fix"}] or rows
    if not shown:
        body.append("还没有花费", style=f"italic {skin.muted}")
    else:
        for role, calls, usd, _models in shown:
            color = role_color.get(role, skin.accent)
            glyph = theme.STAGE_GLYPH.get(role, "·")
            label = ROLE_LABEL.get(role, role)
            filled = int(round(8 * (usd / peak))) if usd else 0
            filled = min(8, max(0, filled))
            if usd > 0 and filled == 0:
                filled = 1
            bar = "█" * filled + "░" * (8 - filled)
            body.append(f"{glyph} {label:<4} {bar}  ", style=f"bold {color}")
            body.append(f"{fmt(usd, currency)}", style=skin.text)
            body.append(f" ×{calls}\n", style=f"italic {skin.muted}")
        spent_frac = min(1.0, total / cap) if cap else 0.0
        bar_color = skin.ok if spent_frac < 0.7 else skin.warn if spent_frac < 0.95 else skin.err
        body.append("\n")
        body.append(_bar(spent_frac, width=16, color=bar_color))
        body.append("\n")
        body.append(f"{fmt(total, currency)} / {fmt(cap, currency)}", style=f"bold {skin.text}")
        leftover = max(cap - total, 0)
        body.append(f"\n剩余 {fmt(leftover, currency)}", style=f"italic {skin.muted}")
    return theme.panel(body, title=f"{title}  ·  {currency.upper()}")


def print_dialog_chrome(
    console: Console,
    ledger: Ledger,
    currency: str,
    *,
    left: RenderableType | None = None,
) -> None:
    """Pin the cost chart to the right (top-right when shown with the banner)."""
    sidebar = render_cost_sidebar(ledger, currency)
    width = int(getattr(console, "width", 80) or 80)
    if left is None or width < 100:
        if left is not None:
            console.print(left)
        console.print(Align.right(sidebar, width=width))
        return
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(ratio=1, overflow="fold")
    grid.add_column(width=SIDEBAR_WIDTH + 4, no_wrap=True, justify="right")
    grid.add_row(left, sidebar)
    console.print(grid)


def render_cost_dock(ledger: Ledger, currency: str = "usd") -> str:
    """One-line process bars for the bottom status strip."""
    currency = normalize_currency(currency)
    rows = role_totals(ledger)
    spent = fmt(ledger.total_usd, currency)
    cap = fmt(ledger.cap_usd, currency)
    if not rows:
        return f"  {spent} / {cap}  ·  还没有花费"
    peak = max((r[2] for r in rows), default=0.0) or 1.0
    bits: list[str] = []
    for role, _calls, usd, _models in rows:
        if role not in {"plan", "design", "code", "review", "fix"}:
            continue
        label = ROLE_LABEL.get(role, role)
        filled = int(round(4 * (usd / peak))) if usd else 0
        filled = min(4, max(0, filled))
        if usd > 0 and filled == 0:
            filled = 1
        bits.append(f"{label}{'█' * filled}{'░' * (4 - filled)}")
    bars = "  ".join(bits) if bits else "还没有花费"
    return f"  {spent} / {cap}  ·  {bars}"


def print_cost_dock(console: Console, ledger: Ledger, currency: str) -> None:
    print_dialog_chrome(console, ledger, currency)


def cost_toolbar_html(ledger: Ledger, currency: str) -> str:
    dock = render_cost_dock(ledger, currency)
    return f'<style fg="#8A8175">{html.escape(dock)}</style>'


def wait_costboard_close() -> None:
    try:
        sys.stdout.write("  回车关闭花费图 ")
        sys.stdout.flush()
        sys.stdin.readline()
    except (EOFError, KeyboardInterrupt):
        pass


def show_costboard(
    console: Console,
    ledger: Ledger,
    currency: str,
    *,
    title: str = "cost",
    session_usd: float | None = None,
    pause: bool = False,
) -> None:
    """Full per-process chart. pause=True keeps it on screen until Enter (F2 / /cost)."""
    print_costboard(console, ledger, currency, title=title, session_usd=session_usd)
    if pause:
        wait_costboard_close()


def print_costboard(
    console: Console,
    ledger: Ledger,
    currency: str,
    *,
    title: str = "Cost",
    session_usd: float | None = None,
) -> None:
    console.print(render_costboard(ledger, currency, title=title, session_usd=session_usd))
