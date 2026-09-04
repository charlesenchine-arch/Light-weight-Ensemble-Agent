"""Toolbox categories the agent can pick from.

Unknown kebab-case names are allowed; this list is the default map from
task/role → which drawers to open.
"""

from __future__ import annotations

from agentflow.types import Role, TaskClass

CATEGORIES: dict[str, str] = {
    "general": "Repo conventions and recipes that do not fit a narrower drawer",
    "planning": "How to break work down in this stack",
    "backend": "API, services, database, auth",
    "frontend": "Web UI implementation, components, state",
    "ui-design": "Visual/UX direction, tokens, layout",
    "mobile": "iOS/Android/RN",
    "testing": "Tests, fixtures, how to run them",
    "devops": "CI, Docker, deploy, scripts",
    "data": "ETL, analytics, schemas",
    "docs": "README, comments, changelog",
    "review": "What to check in this repo",
    "product": "Copy, UX copy, acceptance language",
}

ROLE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "plan": ("planning", "general"),
    "design": ("ui-design", "product", "frontend"),
    "code": ("general", "testing"),
    "fix": ("general", "testing"),
    "review": ("review", "testing"),
    "research": ("general", "docs"),
}

DOMAIN_CATEGORIES: dict[str, tuple[str, ...]] = {
    "backend": ("backend", "testing"),
    "frontend": ("frontend", "testing"),
    "ui-design": ("ui-design", "frontend"),
    "mobile": ("mobile", "testing"),
    "devops": ("devops",),
    "data": ("data",),
    "docs": ("docs",),
    "product": ("product", "ui-design"),
    "architecture": ("planning", "backend"),
}


def normalize_category(raw: str | None) -> str:
    slug = (raw or "general").strip().lower().replace("_", "-").replace(" ", "-")
    return slug or "general"


def select_categories(task: TaskClass, role: Role | str) -> list[str]:
    ordered: list[str] = []
    for item in ROLE_CATEGORIES.get(str(role), ("general",)):
        if item not in ordered:
            ordered.append(item)
    for domain in task.domains:
        for item in DOMAIN_CATEGORIES.get(domain, (domain,)):
            if item not in ordered:
                ordered.append(item)
    if "general" not in ordered:
        ordered.append("general")
    return ordered
