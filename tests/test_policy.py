from pathlib import Path

from agentflow.policy import Policy, add_allow_path, load_allow_roots
from agentflow.tools import Toolbelt
from agentflow.workspace import Workspace


def test_project_files_allowed(tmp_path: Path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert ws.resolve("a.py").is_file()


def test_outside_files_denied_until_allowlisted(tmp_path: Path):
    project = tmp_path / "proj"
    other = tmp_path / "lib"
    project.mkdir()
    other.mkdir()
    (other / "util.py").write_text("n = 1\n", encoding="utf-8")
    ws = Workspace(project)
    try:
        ws.resolve(str(other / "util.py"))
        raise AssertionError("should deny")
    except PermissionError:
        pass
    opened = Workspace(project, extra_roots=[other])
    assert opened.resolve(str(other / "util.py")).name == "util.py"


def test_computer_commands_auto_allowed(tmp_path: Path):
    policy = Policy(tmp_path)
    assert policy.allow_shell("pytest -q")
    assert policy.allow_shell("git status")
    assert policy.allow_shell("python --version")
    assert policy.allow_shell("npm test")


def test_outside_path_in_command_denied(tmp_path: Path):
    policy = Policy(tmp_path)
    outside = tmp_path.parent / "secret.txt"
    decision = policy.allow_shell(f'type "{outside}"')
    assert not decision.ok
    assert "outside" in decision.reason.lower() or "allow" in decision.reason.lower()


def test_urls_are_not_treated_as_windows_paths(tmp_path: Path):
    policy = Policy(tmp_path)
    assert policy.allow_shell("pip install https://example.com/pkg.whl")


def test_dangerous_still_blocked(tmp_path: Path):
    belt = Toolbelt(Workspace(tmp_path))
    result = belt._shell({"command": "rm -rf /"})
    assert "Blocked" in result


def test_allow_add_file(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    extra = tmp_path / "shared"
    extra.mkdir()
    monkeypatch.setattr(
        "agentflow.policy.user_allowlist_file",
        lambda: tmp_path / "user-allow.txt",
    )
    monkeypatch.setattr(
        "agentflow.policy.project_allowlist_file",
        lambda ws: project / ".agentflow" / "allow-paths.txt",
    )
    add_allow_path(extra, user=False, workspace=project)
    roots = load_allow_roots(project)
    assert extra.resolve() in roots
