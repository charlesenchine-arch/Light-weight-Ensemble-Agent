from agentflow.mentions import expand_at_mentions
from agentflow.workspace import Workspace


def test_expand_at_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 42\n", encoding="utf-8")
    out = expand_at_mentions("看一下 @src/app.py 这个常量", tmp_path)
    assert "VALUE = 42" in out
    assert "Attached files" in out


def test_expand_missing_file(tmp_path):
    out = expand_at_mentions("open @nope.py", tmp_path)
    assert "file not found" in out


def test_snapshot_includes_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Use ruff. No print debugging.\n", encoding="utf-8")
    snap = Workspace(tmp_path).snapshot("compact")
    assert "AGENTS.md" in snap
    assert "Use ruff" in snap