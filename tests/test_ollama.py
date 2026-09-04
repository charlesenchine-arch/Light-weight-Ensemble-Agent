from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agentflow.catalog import get_model
from agentflow.providers.factory import complete
from agentflow.types import ChatMessage


class _OllamaStub(BaseHTTPRequestHandler):
    request_model = ""

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        type(self).request_model = request["model"]
        payload = json.dumps(
            {
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "created": 0,
                "model": request["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "local response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "total_tokens": 15,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_ollama_openai_compatible_round_trip(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("OLLAMA_MODEL", "test-coder:latest")
        monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
        result = complete(
            get_model("ollama-local"),
            [ChatMessage(role="user", content="fix it")],
            max_tokens=64,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert _OllamaStub.request_model == "test-coder:latest"
    assert result.message.content == "local response"
    assert result.provider == "ollama"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 3
