from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import time
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from agentflow.workspace import IGNORE_DIRS, SKIP_SUFFIXES, Workspace

if TYPE_CHECKING:
    from agentflow.config import MCPServerSettings
    from agentflow.types import Role

MAX_READ = 24_000
MAX_GREP_HITS = 40
MAX_SHELL_CHARS = 8_000



ToolFn = Callable[[dict[str, Any]], str]


def _clip(text: str, limit: int = MAX_SHELL_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… truncated ({len(text)} chars)"


def openai_tools(names: list[str]) -> list[dict[str, Any]]:
    specs = {item["function"]["name"]: item for item in TOOL_SCHEMAS}
    return [specs[name] for name in names if name in specs]


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders under a workspace-relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory. Default '.'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file. Optional 1-based line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "description": "1-based start line"},
                    "limit": {"type": "integer", "description": "Max lines to return"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a UTF-8 text file inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exactly one occurrence of old_string with new_string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Regex search over text files in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "Subdirectory or file to search"},
                    "glob": {"type": "string", "description": "Optional filename glob, e.g. *.py"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "Find files by glob pattern relative to the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "e.g. src/**/*.ts"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a command in the workspace. Windows uses PowerShell, otherwise bash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status and a short diffstat for the workspace.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skill_categories",
            "description": "List toolbox drawers/categories and how many skills each has.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List toolbox skills. Pass category to open one drawer (backend, frontend, testing, …).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Drawer name. Omit to list all.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "Read a toolbox skill by name (and optional category if names collide).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_skill",
            "description": (
                "Save a reusable procedure to the local toolbox so later tasks can reuse it. "
                "Only for repeatable recipes, not this task's changelog."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "kebab-case, 2-64 chars"},
                    "description": {
                        "type": "string",
                        "description": "What it does and when to trigger it",
                    },
                    "body": {"type": "string", "description": "Markdown steps"},
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "category": {
                        "type": "string",
                        "description": "Drawer: general|planning|backend|frontend|ui-design|testing|devops|docs|review|product",
                    },
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["user", "project"],
                        "description": "user = this machine toolbox (default); project = this repo",
                    },
                },
                "required": ["name", "description", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call when the role's work is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "blocking_issues": {
                        "type": "integer",
                        "description": "For reviewers: number of must-fix issues",
                    },
                    "followups": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["summary"],
            },
        },
    },
]


class Toolbelt:
    def __init__(
        self,
        workspace: Workspace,
        shell_policy: str = "allow",
        library=None,
        *,
        mcp_servers: dict[str, "MCPServerSettings"] | None = None,
        role: "Role" = "code",
    ):
        self.ws = workspace
        self.shell_policy = shell_policy
        self.library = library
        self.mcp = None
        if mcp_servers:
            from agentflow.mcp_client import MCPToolRegistry

            self.mcp = MCPToolRegistry(workspace, mcp_servers, role)
        self.changed: list[str] = []
        self.saved_skills: list[str] = []
        self.backups: dict[str, str | None] = {}
        self._handlers: dict[str, ToolFn] = {
            "list_dir": self._list_dir,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "grep": self._grep,
            "glob_files": self._glob,
            "run_shell": self._shell,
            "git_status": self._git_status,
            "list_skill_categories": self._list_skill_categories,
            "list_skills": self._list_skills,
            "read_skill": self._read_skill,
            "save_skill": self._save_skill,
            "finish": self._finish,
        }

    def names(self, level: str) -> list[str]:
        read = [
            "list_dir",
            "read_file",
            "grep",
            "glob_files",
            "git_status",
            "list_skill_categories",
            "list_skills",
            "read_skill",
            "finish",
        ]
        if level == "none":
            return ["finish"]
        if level == "read":
            return read
        return read + ["write_file", "edit_file", "run_shell", "save_skill"]

    def schemas(self, level: str) -> list[dict[str, Any]]:
        schemas = openai_tools(self.names(level))
        if level != "none" and self.mcp is not None:
            schemas.extend(self.mcp.schemas())
        return schemas

    @property
    def mcp_warnings(self) -> list[str]:
        if self.mcp is None:
            return []
        return list(self.mcp.warnings)

    def run(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """Return (result, is_finish)."""
        if name == "finish":
            return self._finish(arguments), True
        handler = self._handlers.get(name)
        if handler is None and self.mcp is not None and self.mcp.handles(name):
            handler = partial(self.mcp.call, name)
        if not handler:
            return f"Unknown tool: {name}", False
        try:
            return handler(arguments), False
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            from agentflow.cancel import Cancelled

            if isinstance(exc, Cancelled):
                raise
            return f"ERROR: {type(exc).__name__}: {exc}", False

    def _list_dir(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args.get("path") or ".")
        if not path.exists():
            return f"Not found: {args.get('path')}"
        if path.is_file():
            return self.ws.rel(path)
        entries = []
        for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in IGNORE_DIRS:
                continue
            mark = "/" if child.is_dir() else ""
            entries.append(child.name + mark)
        return "\n".join(entries) or "(empty)"

    def _read_file(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args["path"])
        if not path.is_file():
            return f"Not a file: {args['path']}"
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        offset = max(int(args.get("offset") or 1), 1)
        limit = int(args.get("limit") or 0)
        sliced = lines[offset - 1 :]
        if limit > 0:
            sliced = sliced[:limit]
        numbered = [f"{i + offset}|{line}" for i, line in enumerate(sliced)]
        body = "\n".join(numbered)
        return _clip(body, MAX_READ)

    def _backup(self, path: Path) -> None:
        rel = self.ws.rel(path)
        if rel in self.backups:
            return
        if path.is_file():
            try:
                self.backups[rel] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self.backups[rel] = None
        else:
            self.backups[rel] = None

    def _write_file(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args["path"])
        self._backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.get("content") or "", encoding="utf-8")
        rel = self.ws.rel(path)
        if rel not in self.changed:
            self.changed.append(rel)
        return f"Wrote {rel} ({len(args.get('content') or '')} chars)"

    def _edit_file(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args["path"])
        if not path.is_file():
            return f"Not a file: {args['path']}"
        self._backup(path)
        text = path.read_text(encoding="utf-8")
        old, new = args.get("old_string") or "", args.get("new_string") or ""
        count = text.count(old)
        if count == 0:
            return "old_string not found"
        if count > 1:
            return f"old_string found {count} times; make it unique"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        rel = self.ws.rel(path)
        if rel not in self.changed:
            self.changed.append(rel)
        return f"Edited {rel}"

    def _grep(self, args: dict[str, Any]) -> str:
        pattern = re.compile(args["pattern"])
        target = self.ws.resolve(args.get("path") or ".")
        glob = args.get("glob")
        hits: list[str] = []
        files: list[Path] = []
        if target.is_file():
            files = [target]
        else:
            for dirpath, dirnames, filenames in os.walk(target):
                dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
                for name in filenames:
                    path = Path(dirpath) / name
                    if path.suffix.lower() in SKIP_SUFFIXES:
                        continue
                    if glob and not (
                        fnmatch.fnmatch(path.name, glob) or fnmatch.fnmatch(path.as_posix(), glob)
                    ):
                        continue
                    files.append(path)
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = self.ws.rel(path)
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{rel}:{i}:{line[:240]}")
                    if len(hits) >= MAX_GREP_HITS:
                        hits.append("… more matches truncated")
                        return "\n".join(hits)
        return "\n".join(hits) or "No matches"

    def _glob(self, args: dict[str, Any]) -> str:
        pattern = args["pattern"]
        matches: list[str] = []
        for path in sorted(self.ws.root.glob(pattern)):
            if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            rel = self.ws.rel(path)
            if any(part in IGNORE_DIRS for part in Path(rel).parts):
                continue
            matches.append(rel)
        if len(matches) > 200:
            return "\n".join(matches[:200]) + f"\n… {len(matches) - 200} more"
        return "\n".join(matches) or "No files"

    def _run_argv(self, argv: list[str], timeout: int = 60) -> str:
        from agentflow.cancel import check as cancel_check

        try:
            popen = subprocess.Popen(
                argv,
                cwd=self.ws.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            return f"ERROR: command not found: {argv[0]}"
        deadline = time.monotonic() + timeout
        while True:
            try:
                stdout, stderr = popen.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                try:
                    cancel_check()
                except Exception:
                    popen.terminate()
                    try:
                        popen.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        popen.kill()
                        popen.communicate()
                    raise
                if time.monotonic() >= deadline:
                    popen.terminate()
                    try:
                        popen.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        popen.kill()
                        popen.communicate()
                    return f"ERROR: timed out: {' '.join(argv)}"
        parts = [f"exit {popen.returncode}"]
        if stdout.strip():
            parts.append(stdout)
        if stderr.strip():
            parts.append("stderr:\n" + stderr)
        return _clip("\n".join(parts))

    def _shell(self, args: dict[str, Any]) -> str:
        if self.shell_policy == "deny":
            return "Shell is disabled (shell_policy=deny)"
        command = (args.get("command") or "").strip()
        if not command:
            return "Empty command"
        decision = self.ws.policy.allow_shell(command)
        if not decision.ok:
            return f"Blocked: {decision.reason}"
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            cmd = ["bash", "-lc", command]
        output = self._run_argv(cmd, timeout=120)
        if output.startswith("exit "):
            first, *rest = output.split("\n", 1)
            if rest and rest[0].strip():
                return _clip(first + "\nstdout:\n" + rest[0])
        return _clip(output)

    def _git_status(self, args: dict[str, Any]) -> str:
        # Two git argv calls (PowerShell 5.1 cannot take POSIX command chaining).
        status = self._run_argv(["git", "status", "--short"], timeout=20)
        diff = self._run_argv(["git", "diff", "--stat"], timeout=20)
        return "status:\n" + status + "\n\ndiffstat:\n" + diff

    def _list_skill_categories(self, args: dict[str, Any]) -> str:
        if self.library is None:
            return "No skill library attached"
        from agentflow.skills.categories import CATEGORIES

        counts = self.library.categories()
        lines = []
        for name, count in counts.items():
            label = CATEGORIES.get(name, "")
            lines.append(f"{name}\t{count}\t{label}")
        return "\n".join(lines) or "No categories"

    def _list_skills(self, args: dict[str, Any]) -> str:
        if self.library is None:
            return "No skill library attached"
        category = str(args.get("category") or "").strip()
        skills = self.library.in_category(category) if category else self.library.all()
        if not skills:
            return f"No skills in drawer {category or '(all)'}"
        lines = [f"{s.key} [{s.scope}] — {s.description}" for s in skills]
        return "\n".join(lines)

    def _read_skill(self, args: dict[str, Any]) -> str:
        if self.library is None:
            return "No skill library attached"
        skill = self.library.get(str(args.get("name") or ""), category=args.get("category") or None)
        if not skill:
            return "Skill not found"
        return f"# {skill.key}\n{skill.description}\n\n{skill.body}"

    def _save_skill(self, args: dict[str, Any]) -> str:
        if self.library is None:
            return "No skill library attached"
        from agentflow.skills.library import Skill

        skill = Skill(
            name=str(args.get("name") or ""),
            category=str(args.get("category") or "general"),
            description=str(args.get("description") or ""),
            body=str(args.get("body") or ""),
            triggers=[str(t) for t in (args.get("triggers") or [])],
            domains=[str(d) for d in (args.get("domains") or [])],
            scope=str(args.get("scope") or "user"),
        )
        before = self.library.get(skill.name, category=skill.category)
        saved = self.library.save(skill, overwrite=False)
        if saved.key not in self.saved_skills:
            self.saved_skills.append(saved.key)
        status = "already existed" if before else "saved"
        return f"{status}: {saved.key} → {saved.path}"

    def _finish(self, args: dict[str, Any]) -> str:
        return json.dumps(args, ensure_ascii=False)


def restore_backups(root: Path, backups: dict[str, str | None]) -> list[str]:
    """Revert write/edit from a turn. None means the file did not exist before."""
    notes: list[str] = []
    base = Path(root).resolve()
    for rel, old in backups.items():
        path = (base / rel).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            notes.append(f"skip {rel} (outside workspace)")
            continue
        if old is None:
            if path.is_file():
                path.unlink()
                notes.append(f"removed {rel}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(old, encoding="utf-8")
        notes.append(f"restored {rel}")
    return notes
