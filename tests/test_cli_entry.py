from agentflow.cli import rewrite_argv


def test_bare_lea_unchanged():
    assert rewrite_argv(["lea"]) == ["lea"]


def test_subcommand_unchanged():
    assert rewrite_argv(["lea", "doctor"]) == ["lea", "doctor"]
    assert rewrite_argv(["lea", "cost"]) == ["lea", "cost"]
    assert rewrite_argv(["lea", "run", "x"]) == ["lea", "run", "x"]
    assert rewrite_argv(["lea", "-m", "fast"]) == ["lea", "-m", "fast"]


def test_free_text_becomes_run():
    assert rewrite_argv(["lea", "给登录页换布局"]) == ["lea", "run", "给登录页换布局"]
    assert rewrite_argv(["lea", "fix", "the", "tests"]) == ["lea", "run", "fix the tests"]
