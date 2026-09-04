from __future__ import annotations

import os
import subprocess
from pathlib import Path

from agentflow.policy import Policy

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".agentflow",
    ".next",
    ".turbo",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".woff",
    ".woff2",
    ".ttf",
    ".mp3",
    ".mp4",
    ".wasm",
}

TEXTISH = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".md",
    ".txt",
    ".css",
    ".scss",
    ".html",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".sql",
    ".sh",
    ".ps1",
    ".env.example",
}


class Workspace:
    def __init__(self, root: Path, extra_roots: list[Path] | None = None):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Workspace is not a directory: {self.root}")
        self.policy = Policy(self.root, extra_roots)

    def resolve(self, rel: str) -> Path:
        raw = Path(rel)
        path = (self.root / raw).resolve() if not raw.is_absolute() else raw.resolve()
        if not self.policy.allows_path(path):
            raise PermissionError(self.policy.check_path(rel).reason)
        return path

    def rel(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError:
            return str(resolved)

    def tree(self, max_entries: int = 80) -> str:
        lines: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS and not d.startswith("."))
            rel_dir = Path(dirpath).resolve().relative_to(self.root).as_posix()
            prefix = "" if rel_dir == "." else rel_dir + "/"
            for name in sorted(filenames):
                if name.startswith(".") and name not in {".env.example", ".gitignore"}:
                    continue
                suffix = Path(name).suffix.lower()
                if suffix in SKIP_SUFFIXES:
                    continue
                lines.append(prefix + name)
                if len(lines) >= max_entries:
                    lines.append("… (truncated)")
                    return "\n".join(lines)
        return "\n".join(lines) if lines else "(empty)"

    def snapshot(self, kind: str = "compact") -> str:
        git = self.root / ".git"
        vcs = "git repo" if git.exists() else "not a git repo"
        header = f"workspace: {self.root}\nos: {os.name}\nvcs: {vcs}\n"
        if kind == "review":
            return header + self.diff(max_chars=10_000)
        interesting = [
            "README.md",
            "readme.md",
            "AGENTS.md",
            "CLAUDE.md",
            "GEMINI.md",
            "LEA.md",
            ".cursorrules",
            ".github/copilot-instructions.md",
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "composer.json",
            "agentflow.yaml",
        ]
        chunks: list[str] = []
        cap = 500 if kind == "compact" else 2000
        instruction_names = {
            "AGENTS.md",
            "CLAUDE.md",
            "GEMINI.md",
            "LEA.md",
            ".cursorrules",
            ".github/copilot-instructions.md",
        }
        for name in interesting:
            path = self.root / name
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                limit = 2500 if name in instruction_names else cap
                if len(text) > limit:
                    text = text[:limit] + "\n… (truncated)"
                chunks.append(f"### {name}\n{text}")
        tree_n = 80 if kind == "compact" else 40
        return (
            header
            + f"## file tree\n{self.tree(tree_n)}\n\n"
            + ("\n\n".join(chunks) if chunks else "")
        )

    def diff(self, max_chars: int = 10_000) -> str:
        if not (self.root / ".git").exists():
            return "## diff\n(not a git repo — use read_file / git_status tools)\n"
        try:
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            patch = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "## diff\n(git unavailable)\n"
        body = (
            "## git status\n"
            + (status.stdout or "(clean)")
            + "\n## diffstat\n"
            + (diff.stdout or "")
            + "\n## patch\n"
            + (patch.stdout or "(no unstaged/uncommitted diff)")
        )
        if len(body) > max_chars:
            return body[:max_chars] + "\n… (diff truncated)"
        return body
