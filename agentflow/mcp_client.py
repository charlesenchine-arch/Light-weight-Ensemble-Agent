"""Opt-in stdio MCP tools with per-workspace trust and cancellation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

from agentflow.cancel import Cancelled, register_closer, unregister_closer
from agentflow.config import MCPServerSettings
from agentflow.types import Role
from agentflow.workspace import Workspace

MAX_MCP_RESULT_CHARS = 8_000
MAX_MCP_SCHEMA_CHARS = 16_000
_T = TypeVar("_T")
_SCHEMA_CACHE: dict[str, list[dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def trust_file() -> Path:
    return Path.home() / ".agentflow" / "mcp-trust.json"


def server_fingerprint(workspace: Path, name: str, server: MCPServerSettings) -> str:
    payload = {
        "workspace": str(workspace.resolve()),
        "name": name,
        "server": server.model_dump(mode="json"),
    }
    packed = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _read_trust() -> dict[str, Any]:
    path = trust_file()
    if not path.is_file():
        return {"version": 1, "servers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "servers": {}}
    if not isinstance(data, dict) or not isinstance(data.get("servers"), dict):
        return {"version": 1, "servers": {}}
    return data


def _write_trust(data: dict[str, Any]) -> Path:
    path = trust_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def is_trusted(workspace: Path, name: str, server: MCPServerSettings) -> bool:
    fingerprint = server_fingerprint(workspace, name, server)
    return fingerprint in _read_trust()["servers"]


def trust_server(workspace: Path, name: str, server: MCPServerSettings) -> Path:
    data = _read_trust()
    fingerprint = server_fingerprint(workspace, name, server)
    data["servers"][fingerprint] = {
        "workspace": str(workspace.resolve()),
        "name": name,
        "command": server.command,
        "args": server.args,
        "env_names": sorted(server.env),
        "tools": server.tools,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    return _write_trust(data)


def revoke_server(workspace: Path, name: str) -> tuple[Path, int]:
    data = _read_trust()
    root = str(workspace.resolve())
    matched = [
        key
        for key, item in data["servers"].items()
        if item.get("workspace") == root and item.get("name") == name
    ]
    for key in matched:
        del data["servers"][key]
    return _write_trust(data), len(matched)


def _expand_env(values: dict[str, str]) -> dict[str, str]:
    expanded: dict[str, str] = {}
    pattern = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
    for key, value in values.items():
        match = pattern.fullmatch(value)
        if match:
            source = match.group(1)
            if source not in os.environ:
                raise RuntimeError(f"MCP environment variable is not set: {source}")
            expanded[key] = os.environ[source]
        else:
            expanded[key] = value
    return expanded


def _run_cancellable(awaitable: Awaitable[_T], timeout: float) -> _T:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(asyncio.wait_for(awaitable, timeout=timeout))

    def close_active() -> None:
        if not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)

    register_closer(close_active)
    try:
        return loop.run_until_complete(task)
    except asyncio.CancelledError as exc:
        raise Cancelled("interrupted MCP call") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"MCP call timed out after {timeout:g}s") from exc
    finally:
        unregister_closer(close_active)
        pending = asyncio.all_tasks(loop)
        for leftover in pending:
            leftover.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        asyncio.set_event_loop(None)


async def _with_session(
    workspace: Workspace,
    server: MCPServerSettings,
    operation: Callable[[Any], Awaitable[_T]],
) -> _T:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError('MCP support is not installed; run pip install "lea-agent[mcp]"') from exc

    cwd = workspace.resolve(server.cwd)
    if not cwd.is_dir():
        raise RuntimeError(f"MCP cwd is not a directory: {server.cwd}")

    # Trust is the executable boundary. We still reject command arguments that
    # match LEA's dangerous-system-command policy.
    command_line = " ".join([Path(server.command).name, *server.args])
    decision = workspace.policy.allow_shell(command_line)
    if not decision.ok:
        raise PermissionError(f"MCP server command blocked: {decision.reason}")

    parameters = StdioServerParameters(
        command=server.command,
        args=server.args,
        cwd=cwd,
        env=_expand_env(server.env),
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(parameters, errlog=errlog) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                return await operation(session)


def _tool_name(server_name: str, tool_name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", f"mcp__{server_name}__{tool_name}")
    if len(base) <= 64:
        return base
    suffix = hashlib.sha256(base.encode()).hexdigest()[:8]
    return base[:55] + "_" + suffix


def _discover_server(workspace: Workspace, server: MCPServerSettings) -> list[dict[str, Any]]:
    async def discover(session) -> list[dict[str, Any]]:
        result = await session.list_tools()
        return [tool.model_dump(mode="json", by_alias=True) for tool in result.tools]

    return _run_cancellable(
        _with_session(workspace, server, discover),
        timeout=server.timeout_seconds,
    )


def _looks_like_path(key: str) -> bool:
    lowered = key.lower()
    return lowered in {"path", "file", "directory", "cwd", "root"} or lowered.endswith(
        ("_path", "_file", "_dir", "_directory")
    )


def _check_arguments(workspace: Workspace, value: Any, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            _check_arguments(workspace, child, str(child_key))
        return
    if isinstance(value, list):
        for child in value:
            _check_arguments(workspace, child, key)
        return
    if not isinstance(value, str):
        return
    if key.lower() in {"command", "cmd", "script", "shell"}:
        decision = workspace.policy.allow_shell(value)
        if not decision.ok:
            raise PermissionError(f"MCP tool command blocked: {decision.reason}")
    if _looks_like_path(key):
        scheme = urlparse(value).scheme.lower()
        if scheme not in {"http", "https"}:
            workspace.resolve(value)


def _format_result(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
            continue
        kind = getattr(block, "type", type(block).__name__)
        if kind == "image":
            parts.append("[MCP image result omitted from text history]")
        else:
            try:
                parts.append(block.model_dump_json(exclude_none=True))
            except AttributeError:
                parts.append(str(block))
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        parts.append(json.dumps(structured, ensure_ascii=False, separators=(",", ":")))
    body = "\n".join(part for part in parts if part).strip() or "(empty MCP result)"
    if getattr(result, "is_error", False):
        body = "MCP tool error: " + body
    if len(body) > MAX_MCP_RESULT_CHARS:
        body = body[:MAX_MCP_RESULT_CHARS] + f"\n… truncated ({len(body)} chars)"
    return body


class MCPToolRegistry:
    """Discover selected MCP tools and dispatch namespaced calls."""

    def __init__(
        self,
        workspace: Workspace,
        servers: dict[str, MCPServerSettings],
        role: Role,
    ) -> None:
        self.workspace = workspace
        self.servers = servers
        self.role = role
        self.warnings: list[str] = []
        self._calls: dict[str, tuple[str, str, MCPServerSettings]] = {}
        self._schemas: list[dict[str, Any]] | None = None

    def schemas(self) -> list[dict[str, Any]]:
        if self._schemas is not None:
            return list(self._schemas)
        schemas: list[dict[str, Any]] = []
        for server_name, server in self.servers.items():
            if self.role not in server.stages:
                continue
            if not server.tools:
                self.warnings.append(f"MCP {server_name}: no tools selected")
                continue
            if not is_trusted(self.workspace.root, server_name, server):
                self.warnings.append(f"MCP {server_name}: not trusted; run lea mcp trust {server_name}")
                continue
            fingerprint = server_fingerprint(self.workspace.root, server_name, server)
            try:
                with _CACHE_LOCK:
                    discovered = _SCHEMA_CACHE.get(fingerprint)
                if discovered is None:
                    discovered = _discover_server(self.workspace, server)
                    with _CACHE_LOCK:
                        _SCHEMA_CACHE[fingerprint] = discovered
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                self.warnings.append(f"MCP {server_name}: {type(exc).__name__}: {exc}")
                continue

            available = {str(tool.get("name")): tool for tool in discovered}
            for selected in server.tools:
                tool = available.get(selected)
                if tool is None:
                    self.warnings.append(f"MCP {server_name}: selected tool not found: {selected}")
                    continue
                public_name = _tool_name(server_name, selected)
                if public_name in self._calls:
                    self.warnings.append(f"MCP tool name collision: {public_name}")
                    continue
                parameters = tool.get("inputSchema") or {"type": "object", "properties": {}}
                if len(json.dumps(parameters, ensure_ascii=False)) > MAX_MCP_SCHEMA_CHARS:
                    self.warnings.append(f"MCP {server_name}: schema too large: {selected}")
                    continue
                self._calls[public_name] = (server_name, selected, server)
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": public_name,
                            "description": (
                                f"[MCP:{server_name}] {tool.get('description') or selected}"
                            )[:1_000],
                            "parameters": parameters,
                        },
                    }
                )
        self._schemas = schemas
        return list(schemas)

    def handles(self, name: str) -> bool:
        return name in self._calls

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._calls:
            raise KeyError(name)
        _, tool_name, server = self._calls[name]
        _check_arguments(self.workspace, arguments)

        async def invoke(session) -> Any:
            return await session.call_tool(tool_name, arguments=arguments)

        result = _run_cancellable(
            _with_session(self.workspace, server, invoke),
            timeout=server.timeout_seconds,
        )
        return _format_result(result)
