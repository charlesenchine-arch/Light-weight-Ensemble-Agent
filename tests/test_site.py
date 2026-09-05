from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentflow.site_data import build_site_data

ROOT = Path(__file__).resolve().parents[1]


def test_site_data_matches_the_reproducible_benchmark():
    data = build_site_data()
    assert data["catalog_as_of"] == "2026-09-04"
    assert data["summary"] == {
        "lea_usd": 0.2925,
        "baseline_usd": 0.6596,
        "savings_percent": 55.7,
    }
    assert len(data["scenarios"]) == 4
    assert data["default_baseline"] in {model["id"] for model in data["models"]}
    assert "equal model quality" in data["disclaimer"]


def test_committed_site_data_is_in_sync():
    committed = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    assert committed == build_site_data()


def test_site_has_conversion_and_methodology_content():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert 'id="cost-lab"' in html
    assert 'id="star-cta"' in html
    assert "data.json" not in html  # app.js owns data loading and error handling
    assert "catalog estimate" in html.lower()
    assert "github.com/charlesenchine-arch/Light-weight-Ensemble-Agent" in html
    assert "google-analytics" not in html.lower()


def test_site_javascript_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is not installed")
    result = subprocess.run(
        [node, "--check", str(ROOT / "site" / "app.js")],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
