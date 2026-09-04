from __future__ import annotations

import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from agentflow.cancel import Cancelled, clear, request
from agentflow.config import MCPServerSettings, load_settings
from agentflow.context import compact_messages
from agentflow.cost import Ledger, conservative_input_tokens
from agentflow.mcp_client import MCPToolRegistry, is_trusted, revoke_server, trust_server
from agentflow.types import ChatMessage
from agentflow.workspace import Workspace


@pytest.fixture
def mcp_workspace(tmp_path: Path, monkeypatch):
    fixture = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
    shutil.copyfile(fixture, tmp_path / "mcp_stdio_server.py")
    monkeypatch.setattr("agentflow.mcp_client.trust_file", lambda: tmp_path / "user-mcp-trust.json")
    server = MCPServerSettings(
        command=sys.executable,
        args=["mcp_stdio_server.py"],
        tools=["echo"],
        stages=["code"],
        timeout_seconds=5,
    )
    return Workspace(tmp_path), server


def test_mcp_configuration_is_opt_in_and_typed(tmp_path: Path):
    (tmp_path / "agentflow.yaml").write_text(
        """
mcp_servers:
  local:
    command: python
    args: [server.py]
    tools: [echo]
    stages: [plan, code]
""".lstrip(),
        encoding="utf-8",
    )
    settings = load_settings(tmp_path)
    assert settings.mcp_servers["local"].tools == ["echo"]
    assert settings.mcp_servers["local"].stages == ["plan", "code"]


def test_untrusted_server_is_not_started_or_exposed(mcp_workspace):
    workspace, server = mcp_workspace
    registry = MCPToolRegistry(workspace, {"fixture": server}, "code")
    assert registry.schemas() == []
    assert "not trusted" in registry.warnings[0]
    assert MCPToolRegistry(workspace, {"fixture": server}, "review").schemas() == []


def test_selected_stdio_tool_is_discovered_and_called(mcp_workspace):
    workspace, server = mcp_workspace
    trust_server(workspace.root, "fixture", server)
    assert is_trusted(workspace.root, "fixture", server)

    registry = MCPToolRegistry(workspace, {"fixture": server}, "code")
    schemas = registry.schemas()
    assert [item["function"]["name"] for item in schemas] == ["mcp__fixture__echo"]
    messages = [ChatMessage(role="user", content="use the project tool")]
    assert conservative_input_tokens(messages, schemas) > conservative_input_tokens(messages)
    assert registry.call("mcp__fixture__echo", {"text": "hello from MCP"}) == "hello from MCP"
    changed = server.model_copy(update={"args": ["different_server.py"]})
    assert not is_trusted(workspace.root, "fixture", changed)

    _, count = revoke_server(workspace.root, "fixture")
    assert count == 1
    assert not is_trusted(workspace.root, "fixture", server)


def test_mcp_results_are_bounded_and_use_normal_history_compaction(mcp_workspace):
    workspace, server = mcp_workspace
    trust_server(workspace.root, "fixture", server)
    registry = MCPToolRegistry(workspace, {"fixture": server}, "code")
    registry.schemas()
    output = registry.call("mcp__fixture__echo", {"text": "x" * 10_000})
    assert len(output) < 8_100
    messages = [ChatMessage(role="system", content="system"), ChatMessage(role="user", content="go")]
    for index in range(6):
        messages.extend(
            [
                ChatMessage(role="assistant", content=""),
                ChatMessage(
                    role="tool",
                    content=output,
                    tool_call_id=str(index),
                    name="mcp__fixture__echo",
                ),
            ]
        )
    compacted = compact_messages(messages)
    assert len(compacted[3].content) < len(output)


def test_mcp_path_arguments_stay_inside_workspace(mcp_workspace):
    workspace, server = mcp_workspace
    trust_server(workspace.root, "fixture", server)
    registry = MCPToolRegistry(workspace, {"fixture": server}, "code")
    registry.schemas()
    outside = workspace.root.parent / "secret.txt"
    with pytest.raises(PermissionError):
        registry.call("mcp__fixture__echo", {"path": str(outside), "text": "no"})


def test_active_mcp_call_can_be_interrupted(mcp_workspace):
    workspace, server = mcp_workspace
    server.tools = ["sleep"]
    trust_server(workspace.root, "fixture", server)
    registry = MCPToolRegistry(workspace, {"fixture": server}, "code")
    assert registry.schemas()
    caught: list[BaseException] = []

    def invoke() -> None:
        try:
            registry.call("mcp__fixture__sleep", {"seconds": 10})
        except BaseException as exc:  # noqa: BLE001
            caught.append(exc)

    clear()
    thread = threading.Thread(target=invoke)
    thread.start()
    time.sleep(0.4)
    request()
    thread.join(timeout=5)
    clear()
    assert not thread.is_alive()
    assert caught and isinstance(caught[0], Cancelled)


def test_failing_server_does_not_touch_cost_ledger(mcp_workspace):
    workspace, _ = mcp_workspace
    server = MCPServerSettings(command="lea-missing-mcp-command", tools=["echo"], stages=["code"])
    trust_server(workspace.root, "broken", server)
    ledger = Ledger(cap_usd=1)
    registry = MCPToolRegistry(workspace, {"broken": server}, "code")
    assert registry.schemas() == []
    assert "MCP broken" in registry.warnings[0]
    assert ledger.events == []
    assert ledger.total_usd == 0
