"""Expand @path mentions the way Claude Code / Grok do in the prompt."""

from __future__ import annotations

import re
from pathlib import Path

AT_PATH = re.compile(
    r"(?<![\w.])@((?:[\w.-]+[\\/])+[\w.-]+|[\w.-]+\.[A-Za-z0-9]+)"
)
CLIP = 3_500


def expand_at_mentions(text: str, workspace: Path, *, clip: int = CLIP) -> str:
    """Inline @src/app.py (and similar) file contents so the agent can see them."""
    if not text or "@" not in text:
        return text
    root = Path(workspace).resolve()
    chunks: list[str] = []
    seen: set[str] = set()
    for match in AT_PATH.finditer(text):
        rel = match.group(1).replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            chunks.append(f"### @{rel}\n(path outside workspace)")
            continue
        if not path.is_file():
            chunks.append(f"### @{rel}\n(file not found)")
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if len(body) > clip:
            body = body[:clip] + "\n… truncated"
        chunks.append(f"### @{rel}\n{body}")
    if not chunks:
        return text
    return text.rstrip() + "\n\nAttached files:\n" + "\n\n".join(chunks)
