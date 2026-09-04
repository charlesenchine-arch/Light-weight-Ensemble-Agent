from agentflow.context import compact_messages, total_chars
from agentflow.types import ChatMessage
from agentflow.workspace import Workspace


def test_compact_shrinks_old_tool_payloads():
    big = "x" * 5000
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="do it"),
    ]
    for i in range(12):
        messages.append(ChatMessage(role="assistant", content="", tool_calls=[]))
        messages.append(
            ChatMessage(role="tool", content=big, tool_call_id=f"c{i}", name="read_file")
        )
    before = total_chars(messages)
    after_msgs = compact_messages(messages)
    after = total_chars(after_msgs)
    assert after < before
    assert after_msgs[0].content == "sys"
    assert after_msgs[1].content == "do it"
    assert len(after_msgs) == len(messages)


def test_compact_snapshot_is_small(tmp_path):
    (tmp_path / "README.md").write_text("# hi\n" + ("word " * 2000), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    for i in range(30):
        (tmp_path / f"f{i}.py").write_text("print(1)\n", encoding="utf-8")
    snap = Workspace(tmp_path).snapshot("compact")
    assert len(snap) < 8000
    assert "file tree" in snap


def test_review_snapshot_prefers_diff(tmp_path):
    snap = Workspace(tmp_path).snapshot("review")
    assert "diff" in snap.lower()
