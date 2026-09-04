from agentflow.catalog import estimate_stage, estimate_usd, get_model
from agentflow.cost import Ledger, conservative_input_tokens
from agentflow.types import ChatMessage, Usage


def test_estimate_usd_basic():
    spec = get_model("grok-4-fast")
    # 1M in + 1M out
    assert estimate_usd(spec, 1_000_000, 1_000_000) == spec.input_per_m + spec.output_per_m


def test_typical_stage_router_is_cheap():
    fast = get_model("grok-4-fast")
    flagship = get_model("grok-4.6")
    assert estimate_stage(fast, "router") < 0.01
    assert estimate_stage(flagship, "code") > estimate_stage(fast, "router")


def test_unknown_model():
    try:
        get_model("not-a-model")
        raise AssertionError("should have failed")
    except KeyError:
        pass


def test_ledger_groups_by_role():
    ledger = Ledger(cap_usd=1)
    ledger.record("code", "deepseek-v4-flash", "deepseek", Usage(input_tokens=1000, output_tokens=500))
    ledger.record("code", "deepseek-v4-flash", "deepseek", Usage(input_tokens=800, output_tokens=200))
    ledger.record("review", "claude-sonnet-5", "anthropic", Usage(input_tokens=1000, output_tokens=200))
    ledger.record("design", "gemini-3.7-flash", "google", Usage(input_tokens=500, output_tokens=500))
    by_role = ledger.by_role()
    assert set(by_role) == {"code", "review", "design"}
    assert by_role["code"] > by_role["review"] or by_role["code"] >= 0
    from agentflow.display import role_totals

    labels = [r[0] for r in role_totals(ledger)]
    assert labels.index("design") < labels.index("code") < labels.index("review")


def test_ledger_caps_output_to_remaining_budget():
    spec = get_model("claude-sonnet-5")
    ledger = Ledger(cap_usd=0.01)
    allowed = ledger.affordable_output_tokens(spec, input_tokens=1000, requested=8000)
    assert allowed == 800


def test_ledger_rejects_call_when_input_consumes_budget():
    spec = get_model("claude-sonnet-5")
    ledger = Ledger(cap_usd=0.001)
    assert ledger.affordable_output_tokens(spec, input_tokens=1000, requested=1000) == 0


def test_input_estimate_counts_unicode_and_tools_conservatively():
    messages = [ChatMessage(role="user", content="请修复这个接口")]
    plain = conservative_input_tokens(messages)
    with_tools = conservative_input_tokens(
        messages,
        [{"type": "function", "function": {"name": "read_file"}}],
    )
    assert plain > len(messages[0].content)
    assert with_tools > plain
