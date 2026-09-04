from typer.testing import CliRunner

from agentflow.cli import app, rewrite_argv


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


def test_init_creates_templates_without_overwriting(tmp_path):
    runner = CliRunner()
    first = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert first.exit_code == 0
    assert (tmp_path / ".env.example").is_file()
    assert (tmp_path / "agentflow.yaml").is_file()

    config = tmp_path / "agentflow.yaml"
    config.write_text("mode: fast\n", encoding="utf-8")
    second = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert second.exit_code == 0
    assert config.read_text(encoding="utf-8") == "mode: fast\n"
    assert "kept existing" in second.output


def test_benchmark_json_is_machine_readable():
    import json

    runner = CliRunner()
    result = runner.invoke(app, ["benchmark", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["method"] == "catalog-estimate"
    assert payload["catalog_as_of"] == "2026-09-04"
    assert payload["pricing_sources"]["xai"].startswith("https://")
    assert payload["summary"]["savings_percent"] > 50


def test_models_json_is_auditable_and_hides_retired_aliases():
    import json

    runner = CliRunner()
    result = runner.invoke(app, ["models", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    ids = {model["id"] for model in payload["models"]}
    assert payload["catalog_as_of"] == "2026-09-04"
    assert "gemini-3.8-flash" in ids
    assert "grok-4-fast" not in ids
