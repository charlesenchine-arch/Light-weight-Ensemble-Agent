from types import SimpleNamespace
from unittest.mock import patch

from agentflow.catalog import get_model
from agentflow.providers.factory import resolve_transport
from agentflow.providers.openai_compat import (
    SKIP_THOUGHT_SIGNATURE,
    _client,
    base_url_for,
    extra_content_from,
    to_openai_messages,
)
from agentflow.types import ChatMessage, ToolCall


def test_roundtrip_thought_signature():
    sig = {"google": {"thought_signature": "SIG-ABC"}}
    messages = [
        ChatMessage(role="user", content="write it"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="write_file",
                    arguments={"path": "a.py", "content": "x"},
                    extra_content=sig,
                )
            ],
        ),
        ChatMessage(role="tool", tool_call_id="call_1", content="Wrote a.py"),
    ]
    out = to_openai_messages(messages)
    tool_msg = out[1]
    assert tool_msg["tool_calls"][0]["extra_content"] == sig
    assert tool_msg["tool_calls"][0]["function"]["name"] == "write_file"


def test_google_fills_skip_signature_when_missing():
    messages = [
        ChatMessage(
            role="assistant",
            tool_calls=[ToolCall(id="c1", name="write_file", arguments={})],
        )
    ]
    out = to_openai_messages(messages, fill_google_signatures=True)
    extra = out[0]["tool_calls"][0]["extra_content"]
    assert extra["google"]["thought_signature"] == SKIP_THOUGHT_SIGNATURE
    plain = to_openai_messages(messages, fill_google_signatures=False)
    assert "extra_content" not in plain[0]["tool_calls"][0]


def test_extra_content_from_sdk_object():
    call = SimpleNamespace(
        extra_content=SimpleNamespace(
            model_dump=lambda exclude_none=True: {"google": {"thought_signature": "xyz"}}
        )
    )
    assert extra_content_from(call) == {"google": {"thought_signature": "xyz"}}
    assert extra_content_from({"extra_content": {"google": {"thought_signature": "z"}}}) == {
        "google": {"thought_signature": "z"}
    }


def test_ollama_transport_uses_configured_model_and_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3-coder:30b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    assert resolve_transport(get_model("ollama-local")) == ("ollama", "qwen3-coder:30b")
    assert base_url_for("ollama") == "http://localhost:11434/v1"


def test_ollama_client_uses_ignored_dummy_key(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    with patch("agentflow.providers.openai_compat.OpenAI") as constructor:
        _client("ollama")
    constructor.assert_called_once_with(
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    )
