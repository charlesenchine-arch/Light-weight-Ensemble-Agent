"""Local skill toolbox.

Two layers, both on this machine:

- User toolbox: ``~/.agentflow/toolbox/skills/<category>/<name>/SKILL.md``
- Project toolbox: ``<workspace>/.agentflow/skills/<category>/<name>/SKILL.md``

Matched skills are injected into plan/code prompts. New reusable procedures
are written back during coding (save_skill) or after a passing review (harvest).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agentflow.skills.categories import CATEGORIES, normalize_category

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "with",
    "on",
    "是",
    "的",
    "和",
    "一个",
    "一下",
}


class Skill(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    triggers: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    body: str = ""
    path: str = ""
    scope: str = "user"  # user | project
    created: str = ""

    @property
    def key(self) -> str:
        return f"{self.category}/{self.name}"


def validate_name(name: str) -> str:
    slug = (name or "").strip().lower().replace("_", "-").replace(" ", "-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not NAME_RE.match(slug) or not (2 <= len(slug) <= 64):
        raise ValueError(
            f"Invalid skill name {name!r}. Use lowercase letters, digits, hyphens; 2-64 chars."
        )
    return slug


def user_toolbox_dir() -> Path:
    return Path.home() / ".agentflow" / "toolbox" / "skills"


def project_skills_dir(workspace: Path) -> Path:
    return Path(workspace) / ".agentflow" / "skills"


def _parse_skill(path: Path, scope: str, category_hint: str = "general") -> Skill | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            if not isinstance(meta, dict):
                meta = {}
    name = str(meta.get("name") or path.parent.name)
    try:
        name = validate_name(name)
    except ValueError:
        return None
    triggers = meta.get("triggers") or []
    if isinstance(triggers, str):
        triggers = [triggers]
    domains = meta.get("domains") or []
    if isinstance(domains, str):
        domains = [domains]
    category = normalize_category(str(meta.get("category") or category_hint or "general"))
    return Skill(
        name=name,
        description=str(meta.get("description") or ""),
        category=category,
        triggers=[str(t) for t in triggers],
        domains=[str(d) for d in domains],
        body=body,
        path=str(path),
        scope=scope,
        created=str(meta.get("created") or ""),
    )


def _tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text.lower())
    return [t for t in raw if t not in STOPWORDS and len(t) > 1]


def render_skill_md(skill: Skill) -> str:
    meta = {
        "name": skill.name,
        "category": normalize_category(skill.category),
        "description": skill.description,
        "triggers": skill.triggers,
        "domains": skill.domains,
        "created": skill.created or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{front}\n---\n\n{skill.body.strip()}\n"


class SkillLibrary:
    def __init__(self, workspace: Path, user_dir: Path | None = None):
        self.workspace = Path(workspace).resolve()
        self.user_dir = Path(user_dir) if user_dir else user_toolbox_dir()
        self.project_dir = project_skills_dir(self.workspace)

    def ensure(self) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        readme = self.user_dir.parent / "README.md"
        if not readme.is_file():
            readme.write_text(
                "# Agent-flow toolbox\n\n"
                "Skills live in `skills/<category>/<name>/SKILL.md`.\n"
                "The agent opens drawers by category (backend, frontend, testing, …)\n"
                "instead of loading every skill into the prompt.\n",
                encoding="utf-8",
            )

    def _scan(self, root: Path, scope: str) -> list[Skill]:
        if not root.is_dir():
            return []
        found: list[Skill] = []
        for path in sorted(root.rglob("SKILL.md")):
            rel = path.relative_to(root)
            if len(rel.parts) not in {2, 3}:
                continue
            hint = rel.parts[0] if len(rel.parts) == 3 else "general"
            skill = _parse_skill(path, scope, category_hint=hint)
            if skill:
                found.append(skill)
        return found

    def all(self) -> list[Skill]:
        # Project skills override user skills with the same category/name.
        by_key: dict[str, Skill] = {}
        for skill in self._scan(self.user_dir, "user"):
            by_key[skill.key] = skill
        for skill in self._scan(self.project_dir, "project"):
            by_key[skill.key] = skill
        return list(by_key.values())

    def categories(self) -> dict[str, int]:
        counts: dict[str, int] = {name: 0 for name in CATEGORIES}
        for skill in self.all():
            counts[skill.category] = counts.get(skill.category, 0) + 1
        return {k: v for k, v in sorted(counts.items()) if v or k in CATEGORIES}

    def in_category(self, category: str) -> list[Skill]:
        slug = normalize_category(category)
        return [s for s in self.all() if s.category == slug]

    def get(self, name: str, category: str | None = None) -> Skill | None:
        try:
            slug = validate_name(name)
        except ValueError:
            return None
        hits = [s for s in self.all() if s.name == slug]
        if category:
            want = normalize_category(category)
            hits = [s for s in hits if s.category == want]
        return hits[0] if hits else None

    def match(
        self,
        query: str,
        domains: list[str] | None = None,
        *,
        categories: list[str] | None = None,
        limit: int = 4,
    ) -> list[Skill]:
        tokens = set(_tokenize(query))
        want_domains = {d.lower() for d in (domains or [])}
        want_cats = {normalize_category(c) for c in (categories or [])}
        scored: list[tuple[int, Skill]] = []
        for skill in self.all():
            if want_cats and skill.category not in want_cats:
                continue
            hay = " ".join(
                [
                    skill.name,
                    skill.category,
                    skill.description,
                    " ".join(skill.triggers),
                    " ".join(skill.domains),
                ]
            ).lower()
            hits = sum(1 for t in tokens if t in hay or t in skill.body.lower())
            domain_hits = len(want_domains.intersection({d.lower() for d in skill.domains}))
            score = hits + domain_hits * 2
            if any(tr.lower() in query.lower() for tr in skill.triggers if tr):
                score += 3
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda item: (-item[0], item[1].key))
        return [skill for _, skill in scored[:limit]]

    def save(self, skill: Skill, *, overwrite: bool = False) -> Skill:
        skill.name = validate_name(skill.name)
        skill.category = normalize_category(skill.category)
        if not skill.description.strip():
            raise ValueError("Skill description is required")
        if not skill.body.strip():
            raise ValueError("Skill body is required")
        self.ensure()
        target_root = self.project_dir if skill.scope == "project" else self.user_dir
        folder = target_root / skill.category / skill.name
        path = folder / "SKILL.md"
        if path.exists() and not overwrite:
            existing = _parse_skill(path, skill.scope, category_hint=skill.category)
            if existing:
                return existing
        folder.mkdir(parents=True, exist_ok=True)
        if not skill.created:
            skill.created = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path.write_text(render_skill_md(skill), encoding="utf-8")
        skill.path = str(path)
        return skill


def format_skills_for_prompt(skills: list[Skill], budget: int = 1800) -> str:
    if not skills:
        return ""
    chunks: list[str] = []
    used = 0
    for skill in skills:
        block = (
            f"### skill:{skill.key} ({skill.scope})\n"
            f"{skill.description}\n\n{skill.body.strip()}"
        )
        if used + len(block) > budget:
            break
        chunks.append(block)
        used += len(block)
    return "\n\n".join(chunks)


def format_catalog(skills: list[Skill], *, focus: list[str] | None = None, budget: int = 1200) -> str:
    if not skills:
        return "Toolbox is empty. New reusable recipes go in category drawers via save_skill."
    focus_set = {normalize_category(c) for c in (focus or [])}
    grouped: dict[str, list[Skill]] = {}
    for skill in skills:
        grouped.setdefault(skill.category, []).append(skill)
    lines = [
        "Toolbox drawers (open with list_skills(category=...) then read_skill):",
    ]
    # Focused categories first, then the rest as names-only.
    ordered_cats = [c for c in focus or [] if c in grouped]
    ordered_cats += sorted(c for c in grouped if c not in ordered_cats)
    used = 0
    for cat in ordered_cats:
        items = grouped[cat]
        label = CATEGORIES.get(cat, "")
        header = f"[{cat}] {label}".strip()
        if focus_set and cat in focus_set:
            block_lines = [header]
            for skill in items:
                block_lines.append(f"  - {skill.name}: {skill.description[:70]}")
            block = "\n".join(block_lines)
        else:
            names = ", ".join(s.name for s in items[:8])
            extra = f" +{len(items)-8}" if len(items) > 8 else ""
            block = f"{header}: {names}{extra}"
        if used + len(block) > budget:
            lines.append("… catalog truncated; use list_skill_categories")
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)
