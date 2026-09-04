from importlib.resources import files

import yaml

from agentflow.config import available_providers, load_settings


def test_packaged_defaults_are_available(tmp_path):
    defaults = files("agentflow").joinpath("defaults.yaml")
    assert defaults.is_file()

    settings = load_settings(tmp_path)
    assert settings.mode == "balanced"
    assert settings.max_cost_usd == 3.0
    assert settings.max_steps["code"] == 20


def test_repository_example_matches_packaged_defaults():
    packaged = yaml.safe_load(
        files("agentflow").joinpath("defaults.yaml").read_text(encoding="utf-8")
    )
    root = yaml.safe_load(
        files("agentflow").joinpath("../agentflow.yaml").read_text(encoding="utf-8")
    )
    assert root == packaged


def test_repository_env_example_matches_packaged_template():
    packaged = files("agentflow").joinpath("env.example").read_text(encoding="utf-8")
    root = files("agentflow").joinpath("../.env.example").read_text(encoding="utf-8")
    assert "XAI_API_KEY=" in packaged
    assert set(line for line in root.splitlines() if line and not line.startswith("#")) == set(
        line for line in packaged.splitlines() if line and not line.startswith("#")
    )


def test_ollama_model_enables_local_provider(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3-coder:30b")
    assert available_providers()["ollama"] is True
