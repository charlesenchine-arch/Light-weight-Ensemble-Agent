import sys
import threading
import time
from pathlib import Path

import pytest

from agentflow.cancel import Cancelled, clear, request
from agentflow.tools import Toolbelt
from agentflow.workspace import Workspace


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\nVALUE = 1\n", encoding="utf-8")
    return Workspace(tmp_path)


def test_escape_rejected(ws: Workspace):
    with pytest.raises(PermissionError):
        ws.resolve("../outside.txt")


def test_write_and_edit_and_grep(ws: Workspace):
    belt = Toolbelt(ws)
    out = belt._write_file({"path": "src/hello.py", "content": "x = 1\n"})
    assert "hello.py" in out
    edited = belt._edit_file({"path": "src/hello.py", "old_string": "x = 1", "new_string": "x = 2"})
    assert "Edited" in edited
    text = (ws.root / "src" / "hello.py").read_text(encoding="utf-8")
    assert text == "x = 2\n"
    hits = belt._grep({"pattern": "VALUE", "path": "src"})
    assert "app.py" in hits
    assert belt.changed == ["src/hello.py"]


def test_dangerous_shell_blocked(ws: Workspace):
    belt = Toolbelt(ws)
    result = belt._shell({"command": "rm -rf /"})
    assert "Blocked" in result


def test_glob_skips_ignored_dirs(ws: Workspace):
    node = ws.root / "node_modules" / "pkg"
    node.mkdir(parents=True)
    (node / "index.js").write_text("secret()", encoding="utf-8")
    (ws.root / "src" / "ok.js").write_text("ok()", encoding="utf-8")
    belt = Toolbelt(ws)
    found = belt._glob({"pattern": "**/*.js"})
    assert "ok.js" in found
    assert "node_modules" not in found


def test_git_status_does_not_use_shell_and(ws: Workspace):
    import inspect

    from agentflow.tools import Toolbelt as TB

    src = inspect.getsource(TB._git_status)
    assert "_run_argv" in src
    assert "_shell" not in src


def test_running_process_can_be_interrupted(ws: Workspace):
    clear()
    belt = Toolbelt(ws)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            belt._run_argv([sys.executable, "-c", "import time; time.sleep(10)"], timeout=20)
        except BaseException as exc:
            errors.append(exc)

    started = time.monotonic()
    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.2)
    request()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert errors and isinstance(errors[0], Cancelled)
    assert time.monotonic() - started < 3
    clear()
