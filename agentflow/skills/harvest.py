from __future__ import annotations

import json
import re

from agentflow.skills.categories import normalize_category
from agentflow.skills.library import Skill, validate_name
from agentflow.types import ChatMessage

HARVEST_PROMPT = """You extract reusable SKILLS from a finished coding task for a local toolbox.
A skill is a repeatable procedure another agent can follow on a later, different task.

Save a skill only if:
- it is a multi-step recipe or a repo convention that will recur
- a future task could match it from the description/triggers alone

Do NOT save:
- this task's changelog or file list
- one-off patches
- generic advice ("write tests", "keep diffs small")

Reply with JSON only:
{"skills":[{"name":"kebab-case","category":"backend","description":"what + trigger phrases","triggers":["..."],"domains":["backend"],"body":"markdown steps"}]}
category must be one of: general, planning, backend, frontend, ui-design, mobile, testing, devops, data, docs, review, product.
Use an empty list if nothing is reusable.
"""


def parse_harvest(raw: str, existing: set[str]) -> list[Skill]:
    match = re.search(r"\{.*\}", raw or "", re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    items = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[Skill] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        try:
            name = validate_name(str(item.get("name") or ""))
        except ValueError:
            continue
        raw_domains = item.get("domains") or []
        if isinstance(raw_domains, str):
            raw_domains = [raw_domains]
        category = normalize_category(
            str(item.get("category") or (raw_domains[0] if raw_domains else "general"))
        )
        key = f"{category}/{name}"
        if name in existing or key in existing:
            continue
        description = str(item.get("description") or "").strip()
        body = str(item.get("body") or "").strip()
        if not description or not body or len(body) < 40:
            continue
        triggers = item.get("triggers") or []
        domains = item.get("domains") or []
        if isinstance(triggers, str):
            triggers = [triggers]
        if isinstance(domains, str):
            domains = [domains]
        out.append(
            Skill(
                name=name,
                category=category,
                description=description,
                triggers=[str(t) for t in triggers][:8],
                domains=[str(d) for d in domains][:6],
                body=body,
                scope="user",
            )
        )
        existing.add(key)
    return out


def harvest_messages(task: str, artifacts: dict[str, str], existing_names: list[str]) -> list[ChatMessage]:
    payload = {
        "task": task,
        "plan": (artifacts.get("plan") or "")[:4000],
        "code": (artifacts.get("code") or "")[:3000],
        "review": (artifacts.get("review") or "")[:2000],
        "existing_skills": existing_names,
    }
    return [
        ChatMessage(role="system", content=HARVEST_PROMPT),
        ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
    ]
