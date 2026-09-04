from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from agentflow.config import api_key
from agentflow.types import ChatMessage, ChatResult, ToolCall, Usage

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _split_messages(messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    pending_tools: list[dict[str, Any]] = []

    def flush_tools() -> None:
        nonlocal pending_tools
        if pending_tools:
            out.append({"role": "user", "content": pending_tools})
            pending_tools = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
            continue
        if msg.role == "tool":
            pending_tools.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content[:80_000],
                }
            )
            continue
        flush_tools()
        if msg.role == "assistant":
            content: list[dict[str, Any]] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for call in msg.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            if not content:
                content.append({"type": "text", "text": ""})
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": msg.content})
    flush_tools()
    if not out:
        out.append({"role": "user", "content": ""})
    return "\n\n".join(system_parts), out


def _tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    converted = []
    for item in tools:
        fn = item.get("function", item)
        converted.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return converted


def complete(
    *,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    json_mode: bool = False,
    max_tokens: int = 8192,
    on_text: Callable[[str], None] | None = None,
) -> ChatResult:
    from agentflow.cancel import check as cancel_check
    from agentflow.cancel import register_closer, unregister_closer

    key = api_key("anthropic")
    if not key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")
    system, anth_messages = _split_messages(messages)
    if json_mode and system:
        system += "\n\nReply with a single JSON object and nothing else."
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": anth_messages,
    }
    if system:
        payload["system"] = system
    converted = _tools(tools)
    if converted:
        payload["tools"] = converted
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    client = httpx.Client(timeout=180.0)
    closer = client.close
    register_closer(closer)
    try:
        resp = client.post(API_URL, headers=headers, json=payload)
        cancel_check()
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        cancel_check()
        raise
    finally:
        unregister_closer(closer)
        try:
            client.close()
        except Exception:
            pass

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in data.get("content") or []:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text") or "")
        elif btype == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=block.get("id") or "",
                    name=block.get("name") or "",
                    arguments=block.get("input") or {},
                )
            )
    text = "".join(text_parts)
    if on_text and text:
        on_text(text)
    usage_raw = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(usage_raw.get("input_tokens") or 0),
        output_tokens=int(usage_raw.get("output_tokens") or 0),
        cached_input_tokens=int(usage_raw.get("cache_read_input_tokens") or 0),
    )
    return ChatResult(
        message=ChatMessage(role="assistant", content=text, tool_calls=tool_calls),
        usage=usage,
        model=model,
        provider="anthropic",
        raw_finish=data.get("stop_reason") or "stop",
    )
