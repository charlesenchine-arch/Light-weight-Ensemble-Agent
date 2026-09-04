from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from agentflow.agent.prompts import ROUTER_PROMPT, system_for
from agentflow.cancel import Cancelled
from agentflow.cancel import check as cancel_check
from agentflow.config import Settings
from agentflow.context import compact_messages
from agentflow.cost import BudgetExceeded, Ledger, conservative_input_tokens
from agentflow.providers.factory import complete
from agentflow.router import heuristic_classify, parse_classification
from agentflow.tools import Toolbelt
from agentflow.types import ChatMessage, Stage, TaskClass
from agentflow.workspace import Workspace

EventFn = Callable[[str, str], None]


@dataclass
class RoleOutcome:
    text: str
    finished: bool
    blocking_issues: int = 0
    followups: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    steps: int = 0
    saved_skills: list[str] = field(default_factory=list)
    backups: dict[str, str | None] = field(default_factory=dict)


MIN_USEFUL_OUTPUT_TOKENS = 256


def _budgeted_max_tokens(ledger, model, messages, tools, requested) -> int:
    estimated_input = conservative_input_tokens(messages, tools)
    allowed = ledger.affordable_output_tokens(model, estimated_input, requested)
    if allowed < MIN_USEFUL_OUTPUT_TOKENS:
        raise BudgetExceeded(
            f"remaining ${max(ledger.remaining(), 0):.4f} cannot fund a useful "
            f"{model.id} response"
        )
    return allowed


def _complete_resilient(stage, messages, tools, max_tokens, emit, settings, ledger):
    """Retry 429 inside the provider; if still limited, hop to another model."""
    from agentflow.retry import is_rate_limited
    from agentflow.router import pick_model

    try:
        allowed = _budgeted_max_tokens(ledger, stage.model, messages, tools, max_tokens)
        if emit and allowed < max_tokens:
            emit("warn", f"预算保护：本次输出上限 {max_tokens} → {allowed} tokens")
        return complete(
            stage.model,
            messages,
            tools=tools,
            max_tokens=allowed,
            on_text=_on_text_printer(emit, stage.role),
        )
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if not is_rate_limited(exc):
            raise
        if emit:
            emit("warn", f"{stage.model.id} 限流 429，正在换其他模型")
        alt = pick_model(
            stage.role,
            settings.mode,
            avoid_provider=stage.model.provider,
            avoid_model=stage.model.id,
        )
        if alt.id == stage.model.id:
            raise
        stage.model = alt
        if emit:
            emit("info", f"改走 {alt.id}  via {alt.provider}")
        allowed = _budgeted_max_tokens(ledger, alt, messages, tools, max_tokens)
        return complete(
            alt,
            messages,
            tools=tools,
            max_tokens=allowed,
            on_text=_on_text_printer(emit, stage.role),
        )


def _on_text_printer(emit: EventFn | None, tag: str) -> Callable[[str], None] | None:
    if emit is None:
        return None

    def inner(chunk: str) -> None:
        emit("token", chunk)

    return inner


def classify_task(task: str, settings: Settings, ledger: Ledger, emit: EventFn | None) -> TaskClass:
    fallback = heuristic_classify(task)
    use_llm = settings.llm_classify or settings.mode == "quality"
    if not use_llm:
        if emit:
            emit("router", "heuristic " + fallback.model_dump_json())
        return fallback
    from agentflow.router import pick_model

    spec = pick_model("router", settings.mode)
    messages = [
        ChatMessage(role="system", content=ROUTER_PROMPT),
        ChatMessage(role="user", content=task),
    ]
    try:
        allowed = ledger.affordable_output_tokens(
            spec,
            conservative_input_tokens(messages),
            800,
        )
        if allowed < 128:
            if emit:
                emit("warn", "预算不足以运行模型分类，改用本地分类")
            return fallback
        result = complete(
            spec,
            messages,
            json_mode=True,
            max_tokens=allowed,
            on_text=None,
        )
        ledger.record("router", spec.id, result.provider, result.usage)
        parsed = parse_classification(result.message.content, fallback)
        if emit:
            emit("router", parsed.model_dump_json())
        return parsed
    except Exception as exc:  # noqa: BLE001
        if emit:
            emit("warn", f"router fallback ({exc})")
        return fallback


def run_role(
    stage: Stage,
    task: str,
    classification: TaskClass,
    workspace: Workspace,
    settings: Settings,
    ledger: Ledger,
    artifacts: dict[str, str],
    emit: EventFn | None = None,
    library=None,
    skills=None,
    catalog: str = "",
) -> RoleOutcome:
    belt = Toolbelt(
        workspace,
        shell_policy=settings.shell_policy,
        library=library,
        mcp_servers=settings.mcp_servers,
        role=stage.role,
    )
    snap_kind = "review" if stage.role == "review" else "compact"
    snapshot = workspace.snapshot(snap_kind)
    messages = [
        ChatMessage(
            role="system",
            content=system_for(
                stage,
                classification,
                snapshot,
                artifacts,
                skills=skills or [],
                catalog=catalog,
            ),
        ),
        ChatMessage(role="user", content=task),
    ]
    tools = belt.schemas(stage.tools)
    if emit:
        for warning in belt.mcp_warnings:
            emit("warn", warning)
    max_tokens = 8_000 if stage.role in {"code", "fix"} else 3_000

    last_text = ""

    def _snapshot(text: str, finished: bool, steps: int, **extra) -> RoleOutcome:
        return RoleOutcome(
            text=text,
            finished=finished,
            changed=list(belt.changed),
            steps=steps,
            saved_skills=list(belt.saved_skills),
            backups=dict(belt.backups),
            **extra,
        )

    for step in range(stage.max_steps):
        try:
            cancel_check()
        except Cancelled:
            return _snapshot("已打断", False, step)
        if ledger.over_cap():
            last_text = last_text or f"Stopped: cost cap ${settings.max_cost_usd:.2f} reached."
            break
        if emit:
            emit("step", f"{stage.role} step {step + 1}/{stage.max_steps} · {stage.model.id}  ·  Ctrl+C 打断")
        if settings.compact_tool_history:
            messages = compact_messages(messages)
        try:
            result = _complete_resilient(
                stage,
                messages,
                tools,
                max_tokens,
                emit,
                settings,
                ledger,
            )
        except KeyboardInterrupt:
            from agentflow.cancel import request as request_cancel

            request_cancel()
            return _snapshot("已打断", False, step)
        ledger.record(stage.role, stage.model.id, result.provider, result.usage)
        messages.append(result.message)
        last_text = result.message.content or last_text

        if not result.message.tool_calls:
            return _snapshot(last_text, True, step + 1)

        finished = False
        finish_payload: dict = {}
        for call in result.message.tool_calls:
            try:
                cancel_check()
            except Cancelled:
                return _snapshot("已打断", False, step + 1)
            if emit:
                emit("tool", f"{call.name} {json.dumps(call.arguments, ensure_ascii=False)[:200]}")
            output, is_finish = belt.run(call.name, call.arguments)
            if is_finish:
                finished = True
                try:
                    finish_payload = json.loads(output)
                except json.JSONDecodeError:
                    finish_payload = {"summary": output}
                output = finish_payload.get("summary", output)
                last_text = str(output)
            messages.append(
                ChatMessage(
                    role="tool",
                    content=output if isinstance(output, str) else json.dumps(output),
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
        if finished:
            return _snapshot(
                str(finish_payload.get("summary") or last_text),
                True,
                step + 1,
                blocking_issues=int(finish_payload.get("blocking_issues") or 0),
                followups=list(finish_payload.get("followups") or []),
            )

    return _snapshot(last_text or f"{stage.role} hit max steps", False, stage.max_steps)
