from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELEASE = "v0.3.0"
EXPECTED_SHA256 = "3cbb85b6e7545c2129c30c681ea69e28b75a25591366438658a370fd779fd7c9"


def test_installers_pin_the_same_release_and_checksum():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert f'LEA_RELEASE="{EXPECTED_RELEASE}"' in shell
    assert f'$LeaRelease = "{EXPECTED_RELEASE}"' in powershell
    assert EXPECTED_SHA256 in shell.lower()
    assert EXPECTED_SHA256 in powershell.lower()
    assert re.fullmatch(r"[0-9a-f]{64}", EXPECTED_SHA256)
    assert "uv tool install" in shell
    assert '"tool", "install"' in powershell
    assert "sudo" not in shell.lower()
    assert "Start-Process" not in powershell


def test_native_installer_dry_run_is_side_effect_free():
    env = os.environ.copy()
    env["LEA_INSTALL_DRY_RUN"] = "1"
    env["LEA_WITH_MCP"] = "1"
    if os.name == "nt":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "install.ps1"),
        ]
    else:
        command = ["sh", str(ROOT / "install.sh")]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "installer dry run" in result.stdout.lower()
    assert EXPECTED_RELEASE in result.stdout
    assert EXPECTED_SHA256 in result.stdout.lower()
    assert "mcp>=2.1,<3" in result.stdout
