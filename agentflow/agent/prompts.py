from __future__ import annotations

from agentflow.skills.library import Skill, format_skills_for_prompt
from agentflow.types import Role, Stage, TaskClass

ROUTER_PROMPT = """You classify software tasks for a multi-model coding agent.
Reply with a single JSON object, no markdown, matching:
{
  "intent": "implement|fix|refactor|review|design|research|plan|explain",
  "complexity": "trivial|standard|hard",
  "domains": ["backend","frontend","ui-design","mobile","devops","data","docs","product","architecture"],
  "needs_research": false,
  "needs_plan": true,
  "needs_design": false,
  "needs_review": true,
  "language": "zh",
  "summary": "one-line restatement"
}
Rules:
- needs_design=true if the work involves UI, visual polish, UX, branding, layout, or product copy.
- complexity=hard for architecture, concurrency, security, migrations, or large multi-module work.
- complexity=trivial for one-file typos, single-line fixes, or explain-only questions.
- Match the user's language in "language" (zh or en).
"""

ROLE_PROMPTS: dict[Role, str] = {
    "research": """You are the researcher / explainer.
If the user asked a question, answer it from the repo. If this is a research brief for a later coder, gather only facts they need.
Read the relevant files. Do not edit files. Do not invent APIs.
Call finish with a clear answer (for Q&A) or a short brief (for a later implementer).""",
    "plan": """You are the planner. A cheaper model will implement EXACTLY what you write,
so the plan must be executable, not advisory.
Read the relevant files. Do not edit. Include:
1. Goal and non-goals
2. Exact files to add/change (paths)
3. For each file: what to add/remove, key types/signatures, edge cases
4. Order of work (the coder will follow this sequence)
5. Commands to verify (test / typecheck / lint)
6. Risks and what not to invent
Do not leave architecture or API choices open. Call finish when the spec is complete.""",
    "design": """You are the product/UI designer working with a coding agent.
Cover non-code quality: visual hierarchy, typography, spacing, color, interaction,
empty/error states, accessibility, and copy. Reject generic AI-slop UI
(purple gradients, Inter-on-white, three feature cards).
If the repo already has a look, extend it rather than inventing a new brand.
Output:
- Direction (1 paragraph)
- Tokens (color, type, radius, spacing)
- Layout and component map
- Interaction and states
- What not to do
Do not write production code. Call finish with the spec.""",
    "code": """You are a cheap, fast implementer. A stronger model already planned this.
Do NOT re-plan, re-architect, or expand scope. Execute the plan/design spec in order.
If a review or user-trial note is present, fix only those points.
Match existing style. Keep diffs small. Do not commit unless asked.
Follow matched toolbox skills. Open other drawers with list_skills(category=...)
then read_skill when the catalog is relevant. save_skill must set a category
(backend/frontend/testing/…).
After edits, run the verification commands from the plan when practical.
Call finish with what changed and how to verify.""",
    "review": """You are the reviewer. You MUST be a different model than the implementer.
Look for what that implementer typically misses.
Check correctness, security, edge cases, design-spec fidelity, skill compliance, and simplicity.
If user-trial feedback is present, treat it as the acceptance test — blocking if unmet.
Use the git diff in the prompt first. Only open a file if the diff is not enough. Do not edit.
In finish():
- blocking_issues: integer count of must-fix problems (0 = pass, loop ends)
- summary: findings, most severe first
- followups: optional nits""",
    "fix": """You are fixing blocking review findings. Only change what the review
required. Re-read the files, patch them, call finish.""",
}


def language_line(lang: str) -> str:
    if lang.startswith("zh"):
        return "Respond in 中文 unless the repo comments/code should stay in English."
    return "Respond in English."


# Per-role artifact caps. Reviewers get a diff, not another copy of the repo.
_BUDGETS: dict[str, dict[str, int]] = {
    "plan": {"snapshot": 5000, "skill": 1800, "research": 2000},
    "design": {"snapshot": 4000, "skill": 1200, "plan": 2500},
    "code": {"snapshot": 4500, "skill": 1800, "plan": 3500, "design": 2000, "review": 2500},
    "fix": {"snapshot": 3000, "plan": 1500, "review": 2500},
    "review": {"snapshot": 2000, "plan": 1200, "code": 1200, "design": 800},
    "research": {"snapshot": 4000, "skill": 800},
}


def system_for(
    stage: Stage,
    task: TaskClass,
    workspace_snapshot: str,
    artifacts: dict[str, str],
    skills: list[Skill] | None = None,
    catalog: str = "",
) -> str:
    cap = _BUDGETS.get(stage.role, {})
    snap_n = cap.get("snapshot", 4000)
    parts = [
        ROLE_PROMPTS[stage.role],
        language_line(task.language),
        f"Role: {stage.role}  Model: {stage.model.id}  Why: {stage.reason}",
        f"Task intent={task.intent} complexity={task.complexity} domains={task.domains}",
        "Workspace:\n" + workspace_snapshot[:snap_n],
    ]
    if catalog and stage.role in {"plan", "code", "design", "review"}:
        parts.append(catalog[: cap.get("skill", 1200)])
    packed = format_skills_for_prompt(skills or [], budget=cap.get("skill", 1200))
    if packed and stage.role in {"plan", "code", "design"}:
        parts.append("Opened skills for this drawer:\n" + packed)
    if artifacts.get("research") and stage.role == "plan":
        parts.append("Research:\n" + artifacts["research"][: cap.get("research", 2000)])
    if artifacts.get("plan") and stage.role in {"code", "fix", "design", "review"}:
        parts.append("Plan:\n" + artifacts["plan"][: cap.get("plan", 2500)])
    if artifacts.get("design") and stage.role in {"code", "review"}:
        parts.append("Design:\n" + artifacts["design"][: cap.get("design", 1500)])
    if artifacts.get("changed_files") and stage.role == "review":
        parts.append("Files touched:\n" + artifacts["changed_files"][:1500])
    if artifacts.get("code") and stage.role == "review":
        parts.append("Implementer summary:\n" + artifacts["code"][: cap.get("code", 1200)])
    if artifacts.get("review") and stage.role in {"code", "fix"}:
        parts.append("Review to fix:\n" + artifacts["review"][: cap.get("review", 2500)])
    if artifacts.get("trial_feedback"):
        parts.append("User trial feedback:\n" + artifacts["trial_feedback"][:2000])
    return "\n\n".join(parts)
