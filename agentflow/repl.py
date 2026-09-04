from __future__ import annotations

from pathlib import Path

from agentflow import theme
from agentflow.cancel import request as request_cancel
from agentflow.composer import (
    _PROMPT_CTX,
    Turn,
    command_line,
    pack_conversation,
    refresh_dialog,
    run_dialog,
)
from agentflow.cost import Ledger
from agentflow.display import print_dialog_chrome
from agentflow.money import (
    RATES_PER_USD,
    fmt,
    load_prefs,
    normalize_currency,
    parse_money,
    save_prefs,
    to_usd,
)
from agentflow.turn_queue import TurnQueue

console = theme.styled_console()

SHORTCUTS = (
    "Enter 发送（忙碌时排队）   Ctrl+S 打断当前轮并发送   Ctrl+J 换行\n"
    "Esc 打断正在跑的一轮   Ctrl+C 打断（空输入再按一次退出）\n"
    "对话框发出去后还在，可继续打下一句\n"
    "/undo 撤回   /retry 重发   /diff 看改动   /new 新对话"
)


def _ask_budget(default_currency: str, default_cap_usd: float) -> tuple[str, float]:
    """One question. Enter skips and we will not nag next launch."""
    skin = theme.current()
    try:
        raw = console.input(
            f"[{skin.muted} italic]  预算[/]  [{skin.accent}]回车跳过 / 10cny / 0.5usd[/] ❯ "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    prefs = load_prefs()
    currency = default_currency
    parsed = parse_money(raw, currency) if raw else None
    if parsed:
        amount, parsed_cur = parsed
        currency = parsed_cur
        budget_usd = to_usd(amount, parsed_cur)
        console.print(theme.ok_line(f"上限 {fmt(budget_usd, currency)}"))
        prefs["skip_budget_prompt"] = False
    else:
        budget_usd = default_cap_usd
        console.print(theme.dim_line(f"未设预算，默认上限 {fmt(budget_usd, currency)}  ·  以后不再问，改用 /budget"))
        prefs["skip_budget_prompt"] = True
    prefs["currency"] = currency
    save_prefs(prefs)
    return currency, budget_usd


def start_repl(workspace: Path | None = None, mode: str = "balanced") -> None:
    from agentflow.config import load_settings
    from agentflow.tools import restore_backups
    from agentflow.workspace import Workspace as WS

    theme.load_skin_from_prefs()
    root = (workspace or Path.cwd()).resolve()
    settings = load_settings(root, mode if mode in {"budget", "fast", "balanced", "quality"} else None)
    prefs = load_prefs()
    try:
        currency = normalize_currency(prefs.get("currency") or settings.currency or "cny")
    except ValueError:
        currency = "cny"

    budget_usd = settings.max_cost_usd
    if settings.ask_budget and not prefs.get("skip_budget_prompt"):
        currency, budget_usd = _ask_budget(currency, settings.max_cost_usd)

    session = Ledger(cap_usd=budget_usd)
    current_mode = mode if mode in {"budget", "fast", "balanced", "quality"} else "balanced"
    skin = theme.current()
    print_dialog_chrome(console, session, currency, left=theme.banner(str(root), current_mode, currency))
    turns: list[Turn] = []
    last_backups: dict[str, str | None] = {}
    last_user = ""

    def _paint_chart() -> None:
        print_dialog_chrome(console, session, currency)

    def _open_cost() -> None:
        _paint_chart()

    def _run_task(message: str) -> None:
        nonlocal last_backups, last_user, session, budget_usd, currency
        from agentflow.cli import run

        last_user = message
        console.print(theme.user_turn(message, len(turns) + 1))
        leftover = max(budget_usd - session.total_usd, 0.0)
        if leftover <= 0.0001:
            console.print(theme.err_line("预算已用完。/budget 重设，或 /exit"))
            return
        packed = pack_conversation(turns, message)
        try:
            result = run(
                task=packed,
                mode=current_mode,
                workspace=root,
                max_cost=leftover,
                only=None,
                dry_run=False,
                trial=False,
                no_trial=True,
                budget=None,
                currency=currency,
                classify_as=message,
                followup=bool(turns),
                show_cost=False,
            )
        except SystemExit:
            return
        except KeyboardInterrupt:
            request_cancel()
            from agentflow.display import explain_failure

            console.print(
                theme.panel(explain_failure(stopped="interrupted"), title="这一轮没跑完")
            )
            turns.append(Turn(user=message, summary="interrupted", changed=[]))
            return
        except Exception as exc:  # noqa: BLE001
            from agentflow.display import explain_failure

            console.print(theme.panel(explain_failure(exc), title="这一轮没跑完"))
            turns.append(Turn(user=message, summary=f"FAILED: {exc}"[:400], changed=[]))
            return
        if result is None:
            return
        for event in result.ledger.events:
            session.events.append(event)
        session.cap_usd = budget_usd
        if result.backups:
            last_backups = dict(result.backups)
        summary = (
            result.artifacts.get("fix")
            or result.artifacts.get("code")
            or result.artifacts.get("review")
            or result.artifacts.get("research")
            or result.artifacts.get("plan")
            or ""
        )
        turns.append(Turn(user=message, summary=summary, changed=list(result.changed)))
        _paint_chart()

    engine = TurnQueue(_run_task, on_change=refresh_dialog)
    _PROMPT_CTX["queue"] = engine
    _PROMPT_CTX["on_f2"] = _open_cost

    def _handle(text: str, force: bool = False):
        nonlocal current_mode, currency, budget_usd, session, skin, last_user, last_backups
        message = (text or "").strip()
        if not message:
            return None
        cmd = command_line(message)
        line = cmd if cmd is not None else message
        if line in {"/exit", "/quit", "exit", "quit"}:
            engine.interrupt()
            return "quit"
        if line in {"/new", "/clear"}:
            turns.clear()
            last_backups = {}
            last_user = ""
            console.print(theme.ok_line("新对话"))
            return None
        if line in {"/help", "help", "/?"}:
            console.print(
                theme.panel(
                    "[italic]直接打字。发出去后对话框还在。忙碌时 Enter 会排队。[/]\n"
                    + SHORTCUTS
                    + "\n/mode  /theme  /budget  /models  /cost  /doctor  /exit",
                    title="help",
                )
            )
            return None
        if line in {"/keys", "/shortcuts"}:
            console.print(theme.panel(SHORTCUTS, title="keys"))
            return None
        if line in {"/undo", "undo"}:
            if not last_backups:
                console.print(theme.dim_line("没有可撤回的改动"))
                return None
            notes = restore_backups(root, last_backups)
            last_backups = {}
            console.print(theme.ok_line("已撤回本轮写过的文件"))
            if notes:
                console.print(theme.dim_line("  " + "  ·  ".join(notes[:12])))
            return None
        if line in {"/retry", "retry"}:
            if not last_user:
                console.print(theme.dim_line("没有上一条可以重发"))
                return None
            status = engine.submit(last_user)
            if status == "queued":
                console.print(theme.info_line("已排队重发"))
            return None
        if line == "/diff":
            try:
                console.print(theme.panel(WS(root).diff(max_chars=4000)[:4000], title="diff"))
            except Exception as exc:  # noqa: BLE001
                console.print(theme.err_line(str(exc)))
            return None
        if line.startswith("/theme"):
            parts = line.split()
            if len(parts) == 2:
                try:
                    theme.set_skin(parts[1])
                    skin = theme.current()
                    console.print(theme.ok_line(f"theme {skin.name}"))
                    print_dialog_chrome(
                        console, session, currency, left=theme.banner(str(root), current_mode, currency)
                    )
                except ValueError as exc:
                    console.print(theme.err_line(str(exc)))
            else:
                console.print(theme.dim_line("lea  ·  hermes  ·  claude"))
            return None
        if line in {"/models", "/model", "/use"}:
            from prompt_toolkit.application import run_in_terminal

            from agentflow.model_desk import open_desk

            run_in_terminal(open_desk)
            return None
        if line.startswith("/mode"):
            parts = line.split()
            if len(parts) == 2 and parts[1] in {"budget", "fast", "balanced", "quality"}:
                current_mode = parts[1]
                console.print(theme.ok_line(f"mode {current_mode}"))
            else:
                console.print(theme.dim_line("/mode balanced|fast|budget|quality"))
            return None
        if line.startswith("/currency"):
            parts = line.split()
            if len(parts) == 2:
                try:
                    currency = normalize_currency(parts[1])
                    prefs = load_prefs()
                    prefs["currency"] = currency
                    save_prefs(prefs)
                    console.print(theme.ok_line(f"currency {currency.upper()}"))
                except ValueError as exc:
                    console.print(theme.err_line(str(exc)))
            else:
                console.print(theme.dim_line(f"/currency {'|'.join(RATES_PER_USD)}"))
            return None
        if line.startswith("/budget"):
            rest = line[len("/budget") :].strip()
            if rest:
                parsed = parse_money(rest, currency)
                if not parsed:
                    console.print(theme.dim_line("/budget 10cny"))
                    return None
                amount, cur = parsed
                currency = cur
                budget_usd = to_usd(amount, cur)
                session = Ledger(cap_usd=budget_usd)
                console.print(theme.ok_line(f"预算 {fmt(budget_usd, currency)}"))
            else:
                from prompt_toolkit.application import run_in_terminal

                def _ask():
                    nonlocal currency, budget_usd, session
                    currency, budget_usd = _ask_budget(currency, settings.max_cost_usd)
                    session = Ledger(cap_usd=budget_usd)

                run_in_terminal(_ask)
            return None
        if line in {"/cost", "/chart"}:
            session.cap_usd = budget_usd
            _open_cost()
            return None
        if line == "/doctor":
            from prompt_toolkit.application import run_in_terminal

            from agentflow.cli import doctor

            run_in_terminal(lambda: doctor(workspace=root))
            return None
        leftover = max(budget_usd - session.total_usd, 0.0)
        if leftover <= 0.0001:
            console.print(theme.err_line("预算已用完。/budget 重设，或 /exit"))
            return None
        if message.startswith("!") and not message.startswith("!="):
            shell = message[1:].strip()
            if not shell:
                console.print(theme.dim_line("用法：!git status"))
                return None
            from agentflow.policy import load_allow_roots
            from agentflow.tools import Toolbelt

            extra = load_allow_roots(root, settings.allow_paths)
            out = Toolbelt(WS(root, extra_roots=extra), shell_policy=settings.shell_policy)._shell(
                {"command": shell}
            )
            console.print(theme.panel(out[:4000], title="shell"))
            return None
        status = engine.steer(message) if force else engine.submit(message)
        if status == "interrupting":
            console.print(theme.info_line("正在打断当前轮；这条消息将优先执行"))
            return None
        if status == "queued":
            console.print(theme.info_line(f"已排队，当前这轮结束后开始（队列 {engine.queued} 条）"))
        return None

    console.print(theme.dim_line("Enter 发送/排队 · Ctrl+S 打断并发送 · Esc 仅打断 · 对话框会一直留着"))
    try:
        run_dialog(on_submit=_handle, on_interrupt=engine.interrupt, workspace=root)
    finally:
        engine.interrupt()
        _PROMPT_CTX["queue"] = None
    console.print(theme.dim_line(f"bye  ·  session {fmt(session.total_usd, currency)}"))
