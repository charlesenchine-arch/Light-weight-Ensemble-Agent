"""Multiline composer and multi-turn conversation packing for the LEA REPL."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from agentflow import theme

REPL_COMMANDS = {
    "/exit",
    "/quit",
    "/help",
    "/theme",
    "/models",
    "/model",
    "/use",
    "/mode",
    "/currency",
    "/budget",
    "/cost",
    "/chart",
    "/doctor",
    "/new",
    "/clear",
    "/undo",
    "/retry",
    "/diff",
    "/keys",
    "/shortcuts",
    "/?",
}
BARE_COMMANDS = {"exit", "quit", "help", "undo", "retry"}

_HISTORY = Path.home() / ".lea" / "history"
_prompt_session = None
_PROMPT_CTX: dict = {
    "toolbar": None,
    "on_f2": None,
    "multiline": False,
    "workspace": None,
}


def enter_should_submit() -> bool:
    return not bool(_PROMPT_CTX.get("multiline"))


def reset_prompt_session() -> None:
    global _prompt_session
    _prompt_session = None


DIALOG_TITLE = " lea "
DIALOG_FOOTER = "Enter 发送  ·  Ctrl+S 打断并发送  ·  Ctrl+J 换行  ·  Ctrl+C 打断"


def dialog_footer() -> str:
    engine = _PROMPT_CTX.get("queue")
    if engine is not None and getattr(engine, "busy", False):
        n = int(getattr(engine, "queued", 0) or 0)
        extra = f"  ·  排队 {n} 条" if n else ""
        return f"工作中{extra}  ·  Enter 排队  ·  Ctrl+S 打断并发送  ·  Esc 打断"
    if _PROMPT_CTX.get("multiline"):
        return "多行开  ·  Enter 换行  ·  Ctrl+S 发送  ·  Esc Esc 清空"
    return DIALOG_FOOTER


def refresh_dialog() -> None:
    app = _PROMPT_CTX.get("app")
    if app is None:
        return
    try:
        app.invalidate()
    except Exception:
        pass


@dataclass
class Turn:
    user: str
    summary: str = ""
    changed: list[str] = field(default_factory=list)


def command_line(text: str) -> str | None:
    """If the message is a REPL slash/bare command, return that first line."""
    first = text.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0].strip()
    if not first:
        return None
    if first in BARE_COMMANDS:
        return first
    if first.startswith("/"):
        name = first.split()[0]
        if name in REPL_COMMANDS:
            return first
    return None


def join_continued_lines(lines: list[str]) -> str:
    """Join a trailing-backslash continuation (fallback when prompt_toolkit is off)."""
    out: list[str] = []
    buf = ""
    for raw in lines:
        line = raw.replace("\r\n", "\n").rstrip("\r")
        if line.endswith("\\") and not line.endswith("\\\\"):
            buf += line[:-1]
            continue
        buf += line
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)


def pack_conversation(turns: list[Turn], message: str, *, limit: int = 6) -> str:
    """Build the agent-facing task so a follow-up sees prior work, compactly."""
    message = message.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not turns:
        return message
    recent = turns[-limit:]
    blocks = [
        "You are continuing an in-progress LEA session. "
        "Do not restart the project. Apply this follow-up on top of work already done."
    ]
    for i, turn in enumerate(recent, 1):
        user = turn.user.strip()
        if len(user) > 800:
            user = user[:800] + "…"
        block = f"[turn {i}] user:\n{user}"
        if turn.changed:
            block += "\nchanged: " + ", ".join(turn.changed[:24])
        summary = (turn.summary or "").strip()
        if summary:
            if len(summary) > 1200:
                summary = summary[:1200] + "…"
            block += "\nresult:\n" + summary
        blocks.append(block)
    blocks.append("[current] user:\n" + message)
    return "\n\n".join(blocks)


def adjust_for_followup(classification, message: str):
    """Skip a full re-plan on short follow-ups; keep plan/design if the user asks."""
    from agentflow.router import KEYWORD_DESIGN, KEYWORD_HARD, KEYWORD_PLAN, looks_like_question
    from agentflow.types import TaskClass

    current: TaskClass = classification.model_copy(deep=True)
    text = (message or "").strip()
    if looks_like_question(text):
        current.intent = "explain"
        current.complexity = "trivial" if len(text) < 80 else "standard"
        current.needs_plan = False
        current.needs_review = False
        current.needs_design = False
        current.summary = text[:240]
        return current
    asks_plan = bool(KEYWORD_PLAN.search(text) or KEYWORD_HARD.search(text))
    asks_design = bool(KEYWORD_DESIGN.search(text))
    short = len(text) < 160
    if current.intent == "implement" and short and not asks_plan:
        current.intent = "fix"
        current.complexity = "trivial" if len(text) < 40 else "standard"
    if current.intent in {"fix", "explain"} or (short and not asks_plan):
        current.needs_plan = False
    if not asks_design:
        current.needs_design = False
    current.summary = text[:240]
    return current


class _LeaCompleter:
    """Slash commands and @file paths. Instantiated lazily so tests need no TTY."""

    def __init__(self):
        from prompt_toolkit.completion import Completer

        self._base = Completer

    def get_completions(self, document, complete_event):
        from prompt_toolkit.completion import Completion

        text = document.text_before_cursor
        if text.startswith("/") and " " not in text:
            for cmd in sorted(REPL_COMMANDS):
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text), display=cmd)
            return
        at = text.rfind("@")
        if at < 0:
            return
        prefix = text[at + 1 :]
        if any(ch.isspace() for ch in prefix):
            return
        root = _PROMPT_CTX.get("workspace")
        if not root:
            return
        import os

        from agentflow.workspace import IGNORE_DIRS

        root = Path(root)
        needle = prefix.replace("\\", "/").lower()
        count = 0
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
                for name in filenames:
                    rel = (Path(dirpath) / name).relative_to(root).as_posix()
                    if needle and needle not in rel.lower():
                        continue
                    yield Completion(rel, start_position=-len(prefix), display=rel)
                    count += 1
                    if count >= 30:
                        return
        except OSError:
            return


def run_dialog(
    *,
    on_submit,
    on_interrupt=None,
    workspace: Path | None = None,
    default: str = "",
) -> None:
    """Keep the framed composer on screen. Submit does not tear it down.

    on_submit(text, force) -> 'quit' to close, anything else stays open.
    While a turn runs (TurnQueue.busy), Enter queues the next message.
    """
    if workspace is not None:
        _PROMPT_CTX["workspace"] = workspace
    try:
        _run_dialog_app(on_submit, on_interrupt, default)
    except EOFError:
        return


def _run_dialog_app(on_submit, on_interrupt, default: str) -> None:
    from prompt_toolkit.application import Application, run_in_terminal
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.key_binding.defaults import load_key_bindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.processors import BeforeInput
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import Frame

    class LeaCompleter(_LeaCompleter, Completer):
        pass

    _HISTORY.parent.mkdir(parents=True, exist_ok=True)
    skin = theme.current()
    buf = Buffer(
        history=FileHistory(str(_HISTORY)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=LeaCompleter(),
        complete_while_typing=True,
        multiline=True,
        enable_history_search=True,
    )
    if default:
        buf.text = default
        buf.cursor_position = len(default)

    control = BufferControl(
        buffer=buf,
        input_processors=[BeforeInput([("class:prompt", " ❯ ")])],
        focusable=True,
    )
    body = Window(
        content=control,
        wrap_lines=True,
        height=Dimension(min=2, preferred=2, max=2),
        dont_extend_height=False,
        style="class:input",
    )
    frame = Frame(body, title=DIALOG_TITLE, style="class:dialog")

    def _footer(_=None):
        return [("class:footer", "  " + dialog_footer() + "  ")]

    root = HSplit(
        [
            frame,
            Window(FormattedTextControl(_footer), height=1, style="class:footer"),
        ]
    )

    kb = KeyBindings()

    def _newline(event) -> None:
        event.current_buffer.insert_text("\n")

    def _submit(event, force: bool = False) -> None:
        text = event.current_buffer.text
        event.current_buffer.reset()
        event.app.invalidate()
        try:
            result = on_submit(text, force)
        except Exception:
            result = None
        if result == "quit":
            event.app.exit()

    def _force_submit(event) -> None:
        _submit(event, True)

    def _enter(event) -> None:
        if enter_should_submit():
            _submit(event)
        else:
            _newline(event)

    def _toggle_multiline(event) -> None:
        _PROMPT_CTX["multiline"] = not bool(_PROMPT_CTX.get("multiline"))
        event.app.invalidate()

    def _open_cost(event) -> None:
        action = _PROMPT_CTX.get("on_f2")
        if action:
            run_in_terminal(action)

    def _clear_draft(event) -> None:
        event.current_buffer.reset()

    def _do_interrupt(event) -> None:
        if on_interrupt:
            on_interrupt()
        event.app.invalidate()

    def _esc_interrupt(event) -> None:
        engine = _PROMPT_CTX.get("queue")
        if engine is not None and getattr(engine, "busy", False):
            _do_interrupt(event)

    def _ctrl_c(event) -> None:
        engine = _PROMPT_CTX.get("queue")
        busy = engine is not None and getattr(engine, "busy", False)
        if busy:
            _do_interrupt(event)
            return
        if event.current_buffer.text.strip():
            event.current_buffer.reset()
            return
        import time

        now = time.time()
        last = float(_PROMPT_CTX.get("ctrl_c") or 0)
        if now - last < 1.2:
            event.app.exit()
            return
        _PROMPT_CTX["ctrl_c"] = now

    def _eof(event) -> None:
        if not event.current_buffer.text.strip():
            event.app.exit()

    kb.add("enter")(_enter)
    kb.add("c-s")(_force_submit)
    kb.add("escape", "enter")(_force_submit)
    try:
        kb.add("c-enter")(_force_submit)
    except (ValueError, KeyError):
        pass
    kb.add("c-j")(_newline)
    try:
        kb.add("s-enter")(_newline)
    except (ValueError, KeyError):
        pass
    kb.add("c-m")(_toggle_multiline)
    kb.add("f2")(_open_cost)
    kb.add("escape")(_esc_interrupt)
    kb.add("escape", "escape")(_clear_draft)
    kb.add("c-c")(_ctrl_c)
    kb.add("c-d")(_eof)

    style = Style.from_dict(
        {
            "dialog": f"bg:{skin.surface}",
            "dialog.border": skin.border,
            "frame.border": skin.border,
            "frame.title": f"bold {skin.accent}",
            "frame.label": f"bold {skin.accent}",
            "prompt": f"bold {skin.accent}",
            "input": skin.text,
            "footer": f"italic {skin.muted}",
            "completion-menu.completion": f"bg:{skin.surface} {skin.text}",
            "completion-menu.completion.current": f"bg:{skin.accent} #1A140C",
        }
    )
    app = Application(
        layout=Layout(root, focused_element=body),
        key_bindings=merge_key_bindings([load_key_bindings(), kb]),
        style=style,
        full_screen=False,
        mouse_support=True,
        include_default_pygments_style=False,
    )
    _PROMPT_CTX["app"] = app
    try:
        with patch_stdout(raw=True):
            app.run()
    finally:
        _PROMPT_CTX["app"] = None


def read_message(
    prompt: str = "  ❯ ",
    *,
    toolbar=None,
    on_f2=None,
    default: str = "",
    workspace: Path | None = None,
) -> str | None:
    """One-shot read (non-interactive fallback). The live REPL uses run_dialog."""
    _PROMPT_CTX["toolbar"] = toolbar
    _PROMPT_CTX["on_f2"] = on_f2
    if workspace is not None:
        _PROMPT_CTX["workspace"] = workspace
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        return data if data else None
    held: list[str] = []

    def _grab(text: str, force: bool = False):
        held.append(text)
        return "quit"

    try:
        run_dialog(on_submit=_grab, workspace=workspace, default=default or "")
    except KeyboardInterrupt:
        raise
    except Exception:
        return _read_basic(prompt)
    if not held:
        return None
    return held[0].replace("\r\n", "\n").replace("\r", "\n")


def _read_basic(prompt: str) -> str | None:
    chunks: list[str] = []
    while True:
        try:
            line = input(prompt if not chunks else "  … ")
        except EOFError:
            if not chunks:
                return None
            break
        if line.endswith("\\") and not line.endswith("\\\\"):
            chunks.append(line[:-1])
            continue
        chunks.append(line)
        break
    return join_continued_lines(chunks)
