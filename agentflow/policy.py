"""Broad auto-allow boundary so a human does not have to approve every step.

Allow:
  - file ops inside the project workspace
  - file ops inside paths the human added to the allowlist
  - local computer / toolchain commands that do not touch files outside those roots

Deny:
  - any path outside workspace + allowlist
  - destructive system commands
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DANGEROUS = re.compile(
    r"""
    (rm\s+-rf\s+[\\/])|
    (format-volume)|
    (shutdown)|
    (mkfs)|
    (reg\s+delete)|
    (remove-item\s+.*-recurse\s+.*(windows|system32|program\s*files))|
    (del\s+/s\s+/q\s+[c-z]:\\)|
    (bcdedit)|
    (diskpart)|
    (stop-computer)|
    (restart-computer)
    """,
    re.I | re.X,
)

# Absolute or parent-escaping path tokens in a shell string.
PATH_TOKEN = re.compile(
    r"""(?x)
    (?P<p>
        (?:
            (?<![A-Za-z])[A-Za-z]:[\\/]
            | \\\\\w
            | (?<=[\s'"=(])/(?!/)
            | ~[\\/]
            | (?:\.\.[\\/])+
        )
        [^\s'"]*
    )
    """
)

ALLOWLIST_NAME = "allow-paths.txt"


@dataclass
class Decision:
    ok: bool
    reason: str

    def __bool__(self) -> bool:
        return self.ok


def user_allowlist_file() -> Path:
    return Path.home() / ".agentflow" / "allow-paths.txt"


def project_allowlist_file(workspace: Path) -> Path:
    return Path(workspace) / ".agentflow" / ALLOWLIST_NAME


def _read_list(path: Path) -> list[Path]:
    if not path.is_file():
        return []
    roots: list[Path] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        roots.append(Path(raw).expanduser())
    return roots


def load_allow_roots(workspace: Path, extra: list[str] | None = None) -> list[Path]:
    roots: list[Path] = []
    roots.extend(_read_list(user_allowlist_file()))
    roots.extend(_read_list(project_allowlist_file(workspace)))
    for item in extra or []:
        roots.append(Path(item).expanduser())
    resolved: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            path = root.resolve()
        except OSError:
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return resolved


def add_allow_path(path: Path, *, user: bool, workspace: Path) -> Path:
    target = user_allowlist_file() if user else project_allowlist_file(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.expanduser().resolve()
    existing = {str(p) for p in _read_list(target)}
    if str(resolved) not in existing:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(str(resolved) + "\n")
    return target


def remove_allow_path(path: Path, *, user: bool, workspace: Path) -> Path:
    target = user_allowlist_file() if user else project_allowlist_file(workspace)
    if not target.is_file():
        return target
    resolved = str(path.expanduser().resolve())
    lines = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            try:
                if str(Path(stripped).expanduser().resolve()) == resolved:
                    continue
            except OSError:
                pass
        lines.append(line)
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target


class Policy:
    def __init__(self, workspace: Path, extra_roots: list[Path] | None = None):
        self.workspace = Path(workspace).resolve()
        self.roots = [self.workspace]
        for root in extra_roots or []:
            resolved = Path(root).resolve()
            if resolved not in self.roots:
                self.roots.append(resolved)

    def allows_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        for root in self.roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def check_path(self, rel: str) -> Decision:
        raw = Path(rel)
        path = (self.workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
        if self.allows_path(path):
            return Decision(True, "inside allow roots")
        return Decision(
            False,
            f"Path outside project (and not on the allowlist): {path}\n"
            f"Add it with: agentflow allow add \"{path}\"",
        )

    def extract_paths(self, command: str) -> list[Path]:
        found: list[Path] = []
        for match in PATH_TOKEN.finditer(command or ""):
            token = match.group("p")
            if not token:
                continue
            token = token.replace("~", str(Path.home()))
            raw = Path(token)
            path = raw.resolve() if raw.is_absolute() else (self.workspace / raw).resolve()
            found.append(path)
        return found

    def allow_shell(self, command: str) -> Decision:
        text = (command or "").strip()
        if not text:
            return Decision(False, "Empty command")
        if DANGEROUS.search(text):
            return Decision(False, "Blocked dangerous system command")
        outside = [p for p in self.extract_paths(text) if not self.allows_path(p)]
        if outside:
            shown = ", ".join(str(p) for p in outside[:4])
            return Decision(
                False,
                f"Command touches paths outside the project: {shown}\n"
                f"Add a root with: agentflow allow add <path>",
            )
        return Decision(True, "computer/project command auto-allowed")
