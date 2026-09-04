from agentflow.config import ENV_KEYS
from agentflow.router import build_pipeline, heuristic_classify, pick_model
from agentflow.types import TaskClass


def flags(*names: str) -> dict:
    return {k: k in names for k in ENV_KEYS}


def test_heuristic_design_zh():
    task = heuristic_classify("给登录页做一个更现代的设计和实现")
    assert task.language == "zh"
    assert task.needs_design or "ui-design" in task.domains
    assert task.intent == "implement"
    assert task.needs_review


def test_heuristic_review():
    task = heuristic_classify("请 review 这次 diff 有没有安全问题")
    assert task.intent == "review"


def test_heuristic_question_is_explain_not_implement():
    task = heuristic_classify("这个函数是干什么的？")
    assert task.intent == "explain"
    assert task.needs_plan is False
    assert task.needs_review is False
    pipe = build_pipeline(task, "balanced", flags("xai"))
    roles = [s.role for s in pipe.stages]
    assert "research" in roles
    assert "code" not in roles


def test_how_to_still_implements():
    task = heuristic_classify("怎么做登录页？")
    assert task.intent in {"implement", "design"}


def test_balanced_uses_cheap_router_and_coding_model():
    spec = pick_model("router", "balanced", flags("xai"))
    assert spec.id == "grok-4-fast"
    coder = pick_model("code", "balanced", flags("xai"))
    assert coder.id == "grok-code-fast-1"


def test_balanced_expensive_plan_cheap_code():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=True,
        needs_review=True,
        summary="add endpoint",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "deepseek", "google", "anthropic"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["plan"].model.id in {"grok-4.6", "claude-opus-5", "claude-sonnet-5"}
    assert roles["code"].model.id == "deepseek-v4-flash"
    assert roles["plan"].model.quality in {"frontier", "standard"}


def test_ui_code_prefers_gemini_flash():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        domains=["ui-design", "frontend"],
        needs_plan=True,
        needs_design=True,
        needs_review=True,
        summary="login page",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "google", "deepseek"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["code"].model.id == "gemini-3.7-flash"


def test_hard_task_does_not_upgrade_coder():
    task = TaskClass(
        intent="implement",
        complexity="hard",
        domains=["architecture"],
        needs_plan=True,
        needs_review=True,
        summary="redesign concurrency",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "deepseek", "anthropic"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["plan"].model.id in {"grok-4.6", "claude-opus-5", "claude-sonnet-5"}
    assert roles["code"].model.id in {"deepseek-v4-flash", "gemini-3.7-flash", "grok-code-fast-1"}


def test_budget_prefers_cheap_coder():
    coder = pick_model("code", "budget", flags("xai", "deepseek"))
    assert coder.id in {"grok-code-fast-1", "deepseek-v4-flash"}


def test_cross_vendor_review_when_claude_present():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        domains=["backend"],
        needs_plan=True,
        needs_design=False,
        needs_review=True,
        language="zh",
        summary="add endpoint",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "anthropic"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["code"].model.provider == "xai"
    assert roles["review"].model.provider == "anthropic"
    assert roles["review"].model.id == "claude-sonnet-5"


def test_review_falls_back_to_grok_without_other_keys():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_review=True,
        summary="add endpoint",
    )
    pipe = build_pipeline(task, "balanced", flags("xai"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["review"].model.provider == "xai"


def test_fast_skips_plan_and_review():
    task = TaskClass(intent="implement", complexity="standard", needs_plan=True, needs_review=True)
    pipe = build_pipeline(task, "fast", flags("xai"))
    roles = [s.role for s in pipe.stages]
    assert "plan" not in roles
    assert "review" not in roles
    assert "code" in roles


def test_trivial_skips_review():
    task = TaskClass(intent="fix", complexity="trivial", needs_review=True)
    pipe = build_pipeline(task, "balanced", flags("xai", "anthropic"))
    assert all(s.role != "review" for s in pipe.stages)


def test_ui_pipeline_includes_design():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        domains=["ui-design", "frontend"],
        needs_design=True,
        needs_plan=True,
        needs_review=True,
        summary="login page",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "google"))
    roles = {s.role: s for s in pipe.stages}
    assert "design" in roles
    # Gemini should win design when the UI strengths are requested
    assert roles["design"].model.provider in {"google", "xai"}


def test_only_openrouter_still_reaches_grok():
    spec = pick_model("code", "balanced", flags("openrouter"))
    assert spec.openrouter_id


def test_review_switches_vendor_when_coder_is_claude():
    task = TaskClass(
        intent="implement",
        complexity="hard",
        needs_plan=True,
        needs_review=True,
        summary="hard refactor",
    )
    pipe = build_pipeline(task, "quality", flags("anthropic", "deepseek"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["code"].model.provider != roles["review"].model.provider


def test_design_fallback_is_not_the_cheapest_model():
    spec = pick_model("design", "balanced", flags("anthropic", "deepseek"), prefer_strengths=("ui", "visual"))
    assert spec.id != "claude-haiku-4.5"
    assert spec.quality in {"standard", "frontier"}


def test_review_model_is_never_the_coder():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=True,
        needs_review=True,
        summary="add endpoint",
    )
    pipe = build_pipeline(task, "balanced", flags("xai", "anthropic", "deepseek"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["code"].model.id != roles["review"].model.id
    assert roles["code"].model.provider != roles["review"].model.provider


def test_review_differs_even_with_one_vendor():
    task = TaskClass(intent="implement", complexity="standard", needs_review=True, summary="x")
    pipe = build_pipeline(task, "balanced", flags("xai"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["code"].model.id != roles["review"].model.id


def test_kimi_and_qwen_cover_plan_code_review():
    task = TaskClass(
        intent="implement",
        complexity="standard",
        needs_plan=True,
        needs_review=True,
        summary="add endpoint",
    )
    pipe = build_pipeline(task, "balanced", flags("moonshot", "qwen"))
    roles = {s.role: s for s in pipe.stages}
    assert roles["plan"].model.id in {"kimi-k3", "qwen3.8-max"}
    assert roles["code"].model.id in {"kimi-k2.7-code", "qwen3-coder-plus", "qwen3.7-flash"}
    assert roles["review"].model.provider != roles["code"].model.provider
    assert roles["review"].model.id != roles["code"].model.id


def test_only_moonshot_still_routes():
    coder = pick_model("code", "balanced", flags("moonshot"))
    assert coder.provider == "moonshot"
    planner = pick_model("plan", "balanced", flags("moonshot"))
    assert planner.id == "kimi-k3"


def test_only_qwen_still_routes():
    coder = pick_model("code", "balanced", flags("qwen"))
    assert coder.provider == "qwen"
    planner = pick_model("plan", "balanced", flags("qwen"))
    assert planner.id == "qwen3.8-max"
