from pathlib import Path

from agentflow.cancel import (
    Cancelled,
    check,
    clear,
    register_closer,
    request,
    requested,
    unregister_closer,
)
from agentflow.composer import (
    _PROMPT_CTX,
    DIALOG_FOOTER,
    DIALOG_TITLE,
    command_line,
    dialog_footer,
    enter_should_submit,
    reset_prompt_session,
)
from agentflow.tools import Toolbelt, restore_backups
from agentflow.workspace import Workspace


def test_composer_dialog_chrome():
    assert "lea" in DIALOG_TITLE.lower()
    assert "Enter" in DIALOG_FOOTER
    assert "发送" in dialog_footer()


def test_readme_demo_is_present_and_lightweight():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    demo = root / "assets" / "lea-demo.gif"
    assert "assets/lea-demo.gif" in readme
    assert demo.read_bytes().startswith((b"GIF87a", b"GIF89a"))
    assert demo.stat().st_size < 1_000_000


def test_pypi_workflow_uses_scoped_oidc_without_secrets():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "username:" not in workflow
    assert "password:" not in workflow
    assert "PYPI_API_TOKEN" not in workflow


def test_slash_commands_include_undo_retry():
    assert command_line("/undo") == "/undo"
    assert command_line("/retry") == "/retry"
    assert command_line("/keys") == "/keys"
    assert command_line("undo") == "undo"


def test_enter_submits_unless_multiline():
    reset_prompt_session()
    _PROMPT_CTX["multiline"] = False
    assert enter_should_submit() is True
    _PROMPT_CTX["multiline"] = True
    assert enter_should_submit() is False
    _PROMPT_CTX["multiline"] = False


def test_cancel_flag():
    clear()
    assert requested() is False
    request()
    assert requested() is True
    try:
        check()
        raise AssertionError("should have cancelled")
    except Cancelled:
        pass
    clear()
    check()


def test_cancel_closes_inflight_resource():
    clear()
    closed: list[bool] = []

    def closer() -> None:
        closed.append(True)

    register_closer(closer)
    request()
    unregister_closer(closer)
    assert closed == [True]
    clear()


def test_undo_restores_and_deletes_new_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("old\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    belt = Toolbelt(ws)
    belt._write_file({"path": "a.py", "content": "new\n"})
    belt._write_file({"path": "b.py", "content": "created\n"})
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "new\n"
    assert (tmp_path / "b.py").is_file()
    notes = restore_backups(tmp_path, belt.backups)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / "b.py").exists()
    assert notes
