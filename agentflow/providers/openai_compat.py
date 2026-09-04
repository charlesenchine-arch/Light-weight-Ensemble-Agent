from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from openai import OpenAI

from agentflow.config import api_key
from agentflow.types import ChatMessage, ChatResult, ProviderName, ToolCall, Usage

BASE_URLS: dict[ProviderName, str | None] = {
    "xai": "https://api.x.ai/v1",
    "openai": None,
    "deepseek": "https://api.deepseek.com",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "moonshot": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

_DASHSCOPE_REGIONS = {
    "cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "beijing": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "intl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "singapore": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "us": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
}


def base_url_for(provider: ProviderName) -> str | None:
    """Resolve the OpenAI-compatible base URL, honoring optional region overrides."""
    if provider == "moonshot":
        return os.environ.get("MOONSHOT_BASE_URL", "").strip() or BASE_URLS["moonshot"]
    if provider == "qwen":
        explicit = (
            os.environ.get("DASHSCOPE_BASE_URL", "").strip()
            or os.environ.get("QWEN_BASE_URL", "").strip()
        )
        if explicit:
            return explicit
        region = os.environ.get("DASHSCOPE_REGION", "cn").strip().lower()
        return _DASHSCOPE_REGIONS.get(region, BASE_URLS["qwen"])
    return BASE_URLS.get(provider)

HEADERS: dict[ProviderName, dict[str, str]] = {
    "openrouter": {
        "HTTP-Referer": "https://github.com/agent-flow",
        "X-Title": "Agent-flow",
    }
}


def _client(provider: ProviderName) -> OpenAI:
    key = api_key(provider)
    if not key:
        raise RuntimeError(f"Missing API key for {provider}")
    kwargs: dict[str, Any] = {"api_key": key}
    base = base_url_for(provider)
    if base:
        kwargs["base_url"] = base
    extra = HEADERS.get(provider)
    if extra:
        kwargs["default_headers"] = extra
    return OpenAI(**kwargs)


SKIP_THOUGHT_SIGNATURE = "skip_thought_signature_validator"


def _dump_obj(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _dump_obj(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_dump_obj(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict) and extra:
        return _dump_obj(extra)
    data = getattr(obj, "__dict__", None)
    if isinstance(data, dict) and data:
        return {k: _dump_obj(v) for k, v in data.items() if not k.startswith("_") and v is not None}
    return None


def extra_content_from(obj: Any) -> dict[str, Any] | None:
    """Pull Gemini extra_content (thought_signature) off an SDK object or dict."""
    if obj is None:
        return None
    extra = getattr(obj, "extra_content", None)
    if extra is None and isinstance(obj, dict):
        extra = obj.get("extra_content")
    if extra is None:
        model_extra = getattr(obj, "model_extra", None)
        if isinstance(model_extra, dict):
            extra = model_extra.get("extra_content")
    dumped = _dump_obj(extra)
    return dumped if isinstance(dumped, dict) and dumped else None


def _tool_call_payload(call: ToolCall, *, fill_google_signatures: bool) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.name,
            "arguments": json.dumps(call.arguments, ensure_ascii=False),
        },
    }
    extra = call.extra_content
    if fill_google_signatures and not extra:
        extra = {"google": {"thought_signature": SKIP_THOUGHT_SIGNATURE}}
    if extra:
        item["extra_content"] = extra
    return item


def to_openai_messages(
    messages: list[ChatMessage],
    *,
    fill_google_signatures: bool = False,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "",
                    "content": msg.content,
                }
            )
            continue
        item: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
        if msg.extra_content:
            item["extra_content"] = msg.extra_content
        if msg.role == "assistant" and msg.tool_calls:
            item["content"] = msg.content or None
            item["tool_calls"] = [
                _tool_call_payload(call, fill_google_signatures=fill_google_signatures)
                for call in msg.tool_calls
            ]
        out.append(item)
    return out


def _parse_args(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        return {"_raw": raw}


def _usage_from(resp_usage: Any) -> Usage:
    if not resp_usage:
        return Usage()
    cached = 0
    details = getattr(resp_usage, "prompt_tokens_details", None)
    if details is not None:
        cached = int(getattr(details, "cached_tokens", 0) or 0)
    cached = cached or int(getattr(resp_usage, "cache_read_input_tokens", 0) or 0)
    return Usage(
        input_tokens=int(getattr(resp_usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(resp_usage, "completion_tokens", 0) or 0),
        cached_input_tokens=cached,
    )


def _message_from_choice(choice_msg: Any) -> ChatMessage:
    tool_calls: list[ToolCall] = []
    for call in getattr(choice_msg, "tool_calls", None) or []:
        fn = getattr(call, "function", None)
        tool_calls.append(
            ToolCall(
                id=getattr(call, "id", "") or "",
                name=getattr(fn, "name", "") if fn else "",
                arguments=_parse_args(getattr(fn, "arguments", "") if fn else ""),
                extra_content=extra_content_from(call),
            )
        )
    return ChatMessage(
        role="assistant",
        content=choice_msg.content or "",
        tool_calls=tool_calls,
        extra_content=extra_content_from(choice_msg),
    )


class _StreamAcc:
    def __init__(self) -> None:
        self.content: list[str] = []
        self.tools: dict[int, dict[str, Any]] = {}
        self.extra_content: dict[str, Any] | None = None
        self.finish = "stop"
        self.usage = Usage()

    def push(self, chunk: Any, on_text: Callable[[str], None] | None) -> None:
        usage = getattr(chunk, "usage", None)
        if usage:
            self.usage = _usage_from(usage)
        if not chunk.choices:
            return
        choice = chunk.choices[0]
        self.finish = choice.finish_reason or self.finish
        delta = choice.delta
        extra = extra_content_from(delta)
        if extra and not self.extra_content:
            self.extra_content = extra
        if delta.content:
            self.content.append(delta.content)
            if on_text:
                on_text(delta.content)
        for call in delta.tool_calls or []:
            idx = int(getattr(call, "index", 0) or 0)
            slot = self.tools.setdefault(
                idx, {"id": "", "name": "", "arguments": "", "extra_content": None}
            )
            if call.id:
                slot["id"] = call.id
            fn = getattr(call, "function", None)
            if fn:
                if fn.name:
                    slot["name"] += fn.name
                if fn.arguments:
                    slot["arguments"] += fn.arguments
            call_extra = extra_content_from(call)
            if call_extra and not slot["extra_content"]:
                slot["extra_content"] = call_extra

    def result(self, model: str, provider: str) -> ChatResult:
        tool_calls = [
            ToolCall(
                id=slot["id"] or f"call_{idx}",
                name=slot["name"],
                arguments=_parse_args(slot["arguments"]),
                extra_content=slot.get("extra_content"),
            )
            for idx, slot in sorted(self.tools.items())
            if slot["name"]
        ]
        return ChatResult(
            message=ChatMessage(
                role="assistant",
                content="".join(self.content),
                tool_calls=tool_calls,
                extra_content=self.extra_content,
            ),
            usage=self.usage,
            model=model,
            provider=provider,
            raw_finish=self.finish or "stop",
        )


def complete(
    *,
    provider: ProviderName,
    model: str,
    messages: list[ChatMessage],
    tools: list[dict[str, Any]] | None = None,
    json_mode: bool = False,
    max_tokens: int = 8192,
    on_text: Callable[[str], None] | None = None,
) -> ChatResult:
    from agentflow.cancel import check as cancel_check
    from agentflow.cancel import register_closer, unregister_closer

    client = _client(provider)
    fill_sigs = provider == "google"
    # Streamed Gemini tool-calls often drop thought_signature → 400 on the next turn.
    if provider == "google" and tools:
        on_text = None
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": to_openai_messages(messages, fill_google_signatures=fill_sigs),
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    def _once(payload: dict[str, Any]):
        try:
            return client.chat.completions.create(**payload)
        except Exception as exc:
            message = str(exc).lower()
            if "max_tokens" in message and "max_completion_tokens" in message:
                payload = dict(payload)
                payload["max_completion_tokens"] = payload.pop("max_tokens")
                return client.chat.completions.create(**payload)
            if "stream_options" in message:
                payload = dict(payload)
                payload.pop("stream_options", None)
                return client.chat.completions.create(**payload)
            if "response_format" in message:
                payload = dict(payload)
                payload.pop("response_format", None)
                return client.chat.completions.create(**payload)
            if provider == "google" and "thought_signature" in message:
                patched = dict(payload)
                patched["messages"] = to_openai_messages(messages, fill_google_signatures=True)
                return client.chat.completions.create(**patched)
            raise

    def _create(payload: dict[str, Any]):
        from agentflow.retry import run_with_rate_limit_retry

        return run_with_rate_limit_retry(lambda: _once(payload), provider=provider, attempts=3)

    closer = client.close
    register_closer(closer)
    try:
        if on_text is not None:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
            acc = _StreamAcc()
            stream = _create(kwargs)
            for chunk in stream:
                cancel_check()
                acc.push(chunk, on_text)
            cancel_check()
            return acc.result(model, provider)

        resp = _create(kwargs)
        cancel_check()
        choice = resp.choices[0]
        return ChatResult(
            message=_message_from_choice(choice.message),
            usage=_usage_from(resp.usage),
            model=model,
            provider=provider,
            raw_finish=choice.finish_reason or "stop",
        )
    except Exception:
        cancel_check()
        raise
    finally:
        unregister_closer(closer)
        try:
            client.close()
        except Exception:
            pass
