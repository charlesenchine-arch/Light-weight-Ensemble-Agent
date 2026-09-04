import json

from agentflow.cost import Ledger
from agentflow.display import (
    cost_toolbar_html,
    render_cost_dock,
    render_cost_sidebar,
    render_costboard,
    role_totals,
)
from agentflow.session import load_session_ledger
from agentflow.types import Usage


def _ledger() -> Ledger:
    ledger = Ledger(cap_usd=3)
    ledger.record("plan", "kimi-k3", "moonshot", Usage(input_tokens=1000, output_tokens=500))
    ledger.record("code", "deepseek-v4-flash", "deepseek", Usage(input_tokens=8000, output_tokens=2000))
    ledger.record("review", "gemini-3.7-flash", "google", Usage(input_tokens=2000, output_tokens=400))
    return ledger


def test_dock_shows_process_bars():
    text = render_cost_dock(_ledger(), "cny")
    assert "规划" in text
    assert "编写" in text
    assert "审核" in text
    assert "¥" in text or "CNY" in text or "cny" in text.lower()


def test_sidebar_is_the_visible_chart():
    panel = render_cost_sidebar(_ledger(), "cny")
    assert panel is not None
    assert "花费" in str(panel.title) or panel.title is not None
    empty = render_cost_sidebar(Ledger(cap_usd=3), "cny")
    assert empty is not None


def test_empty_dock_still_has_totals():
    text = render_cost_dock(Ledger(cap_usd=3), "cny")
    assert "还没有花费" in text


def test_toolbar_html_has_spend():
    html = cost_toolbar_html(_ledger(), "cny")
    assert "¥" in html or "CNY" in html or "cny" in html.lower()
    assert "<" in html


def test_full_board_groups_processes():
    board = render_costboard(_ledger(), "cny", title="cost")
    labels = [r[0] for r in role_totals(_ledger())]
    assert labels[0] == "plan"
    assert "code" in labels
    assert "review" in labels
    assert board is not None


def test_explain_failure_429_and_interrupt():
    from agentflow.display import explain_failure

    text = explain_failure("Error code: 429", stage="design", model="gemini-3.7-flash (google)")
    assert "设计" in text
    assert "429" in text
    assert "/retry" in text
    assert "清空" in text
    stopped = explain_failure(stopped="interrupted")
    assert "Ctrl+C" in stopped
    assert "/retry" in stopped


def test_load_session_ledger(tmp_path):
    ledger = _ledger()
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "task": "demo",
                "cap_usd": 3,
                "cost_usd": ledger.total_usd,
                "events": [e.model_dump() for e in ledger.events],
            }
        ),
        encoding="utf-8",
    )
    loaded, payload = load_session_ledger(path)
    assert payload["task"] == "demo"
    assert loaded.total_usd == ledger.total_usd
    assert len(loaded.events) == 3
