"""Shrink conversation history so later steps do not re-pay for old tool dumps."""

from __future__ import annotations

from agentflow.types import ChatMessage

COMPACT_AFTER_CHARS = 20_000
KEEP_TAIL = 8
STALE_TOOL_CHARS = 400


def total_chars(messages: list[ChatMessage]) -> int:
    return sum(len(m.content or "") for m in messages)


def compact_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    if total_chars(messages) < COMPACT_AFTER_CHARS or len(messages) <= KEEP_TAIL + 2:
        return messages
    head = messages[:2]
    rest = messages[2:]
    stale, recent = rest[:-KEEP_TAIL], rest[-KEEP_TAIL:]
    shrunk: list[ChatMessage] = []
    for msg in stale:
        if msg.role == "tool" and len(msg.content) > STALE_TOOL_CHARS:
            shrunk.append(
                msg.model_copy(
                    update={"content": msg.content[:STALE_TOOL_CHARS] + "\n… compacted"}
                )
            )
        else:
            shrunk.append(msg)
    return head + shrunk + recent
