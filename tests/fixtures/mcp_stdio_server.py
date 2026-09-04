"""Tiny network-free MCP fixture used by the LEA client tests."""

import json
import sys
import time

TOOLS = [
    {
        "name": "echo",
        "description": "Return the supplied text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "sleep",
        "description": "Wait for a number of seconds.",
        "inputSchema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
        },
    },
]


def reply(request_id, result) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)


for raw in sys.stdin:
    request = json.loads(raw)
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        reply(
            request_id,
            {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "lea-test", "version": "1.0.0"},
            },
        )
    elif method == "tools/list":
        reply(request_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = request["params"]["name"]
        arguments = request["params"].get("arguments") or {}
        if name == "sleep":
            time.sleep(float(arguments.get("seconds") or 0))
            text = "awake"
        else:
            text = str(arguments.get("text") or "")
        reply(request_id, {"content": [{"type": "text", "text": text}], "isError": False})
    elif request_id is not None:
        reply(request_id, {})
