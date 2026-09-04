from agentflow.benchmark import BenchmarkCase, benchmark_summary, run_catalog_benchmark


def test_catalog_benchmark_is_deterministic_and_cheaper():
    rows = run_catalog_benchmark()
    assert len(rows) == 4
    assert all(row.lea_usd < row.baseline_usd for row in rows)
    assert all(row.providers >= 2 for row in rows if "review" in row.roles)
    assert benchmark_summary(rows)["savings_percent"] > 50


def test_catalog_benchmark_ignores_user_pins(monkeypatch):
    monkeypatch.setattr("agentflow.picks.get_pins", lambda: {"code": "grok-4.6"})
    cases = (BenchmarkCase("One", "Add pagination to the users API"),)
    row = run_catalog_benchmark(cases=cases)[0]
    assert "deepseek-v4-flash" in row.route


def test_documented_totals_match_current_catalog():
    from pathlib import Path

    summary = benchmark_summary(run_catalog_benchmark())
    readme = Path("README.md").read_text(encoding="utf-8")
    assert f"${summary['lea_usd']:.4f}" in readme
    assert f"${summary['baseline_usd']:.4f}" in readme
    assert f"{summary['savings_percent']:.1f}%" in readme
