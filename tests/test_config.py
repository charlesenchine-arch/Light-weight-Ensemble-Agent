from importlib.resources import files

import yaml

from agentflow.config import load_settings


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
