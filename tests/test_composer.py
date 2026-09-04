from agentflow.composer import (
    Turn,
    adjust_for_followup,
    command_line,
    join_continued_lines,
    pack_conversation,
)
from agentflow.router import heuristic_classify


def test_command_line_detects_slash_and_bare():
    assert command_line("/exit") == "/exit"
    assert command_line("exit") == "exit"
    assert command_line("/mode balanced") == "/mode balanced"
    assert command_line("/new") == "/new"
    assert command_line("/cost") == "/cost"
    assert command_line("/chart") == "/chart"
    assert command_line("给登录页换布局") is None
    assert command_line("/tmp/foo.py 修一下") is None
    assert command_line("/help\n还有别的") == "/help"


def test_join_continued_lines():
    text = join_continued_lines(["first line\\", "second", "third"])
    assert text == "first linesecond\nthird"


def test_pack_first_turn_is_identity():
    assert pack_conversation([], "hello") == "hello"


def test_pack_includes_prior_and_current():
    turns = [
        Turn(user="加登录页", summary="added login", changed=["app/login.py"]),
        Turn(user="再加记住我", summary="checkbox", changed=["app/login.py"]),
    ]
    packed = pack_conversation(turns, "按钮改成红色")
    assert "continuing" in packed.lower() or "follow-up" in packed.lower()
    assert "加登录页" in packed
    assert "app/login.py" in packed
    assert packed.strip().endswith("按钮改成红色")
    assert packed.count("[current]") == 1


def test_followup_question_stays_explain():
    adjusted = adjust_for_followup(heuristic_classify("那这个参数是什么意思？"), "那这个参数是什么意思？")
    assert adjusted.intent == "explain"
    assert adjusted.needs_plan is False


def test_followup_skips_replan_on_short_tweak():
    prior = heuristic_classify("实现一个登录接口，带 JWT")
    current = heuristic_classify("把超时改成 30 秒")
    adjusted = adjust_for_followup(current, "把超时改成 30 秒")
    assert adjusted.needs_plan is False
    assert adjusted.intent in {"fix", "implement"}
    assert adjusted.needs_design is False
    assert prior.needs_plan is True


def test_followup_keeps_plan_when_asked():
    current = heuristic_classify("重新出一份架构方案")
    adjusted = adjust_for_followup(current, "重新出一份架构方案")
    assert adjusted.intent == "plan"
    assert adjusted.needs_plan is True


def test_followup_pipeline_omits_plan():
    from agentflow.config import ENV_KEYS
    from agentflow.router import build_pipeline

    message = "把超时改成 30 秒"
    adjusted = adjust_for_followup(heuristic_classify(message), message)
    flags = {k: k == "xai" for k in ENV_KEYS}
    pipe = build_pipeline(adjusted, "balanced", flags)
    roles = [s.role for s in pipe.stages]
    assert "plan" not in roles
    assert "code" in roles
