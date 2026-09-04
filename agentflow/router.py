"""Pick a model for each role from what the user actually has keys for.

Order inside each list is preference. Native provider first; OpenRouter is a
last-resort transport for the same model id.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from agentflow.catalog import MODELS, estimate_stage
from agentflow.config import available_providers
from agentflow.types import Mode, ModelSpec, Pipeline, ProviderName, Role, Stage, TaskClass

# Preferred model ids per (role, mode). Cross-vendor review is applied later.
PREFERENCES: dict[Role, dict[Mode, list[str]]] = {
    "router": {
        "budget": ["grok-4-fast", "gpt-5.6-luna", "qwen3.7-flash", "deepseek-v4-flash", "claude-haiku-4.5"],
        "fast": ["grok-4-fast", "gpt-5.6-luna", "qwen3.7-flash", "deepseek-v4-flash"],
        "balanced": ["grok-4-fast", "gpt-5.6-luna", "claude-haiku-4.5", "qwen3.7-flash"],
        "quality": ["grok-4-fast", "grok-4.6", "claude-sonnet-5"],
    },
    "research": {
        "budget": ["grok-4-fast", "deepseek-v4-flash", "gpt-5.6-luna", "qwen3.7-flash"],
        "fast": ["grok-4-fast", "gpt-5.6-luna"],
        "balanced": ["grok-4-fast", "grok-4.3", "gpt-5.6-terra", "kimi-k3"],
        "quality": ["grok-4.6", "claude-sonnet-5", "kimi-k3", "qwen3.8-max"],
    },
    # Planning is short and high-leverage — spend here.
    "plan": {
        "budget": ["claude-sonnet-5", "grok-4.3", "deepseek-v4-pro", "qwen3.8-max"],
        "fast": ["grok-4.3", "claude-sonnet-5", "grok-build-0.1"],
        "balanced": ["grok-4.6", "claude-sonnet-5", "claude-opus-5", "gpt-5.6-terra", "kimi-k3", "qwen3.8-max"],
        "quality": ["grok-4.6", "claude-opus-5", "gpt-5.6-sol", "claude-sonnet-5", "kimi-k3", "qwen3.8-max"],
    },
    "design": {
        "budget": ["gemini-3.7-flash", "gemini-3.6-flash", "qwen3.7-flash", "grok-4-fast"],
        "fast": ["gemini-3.7-flash", "gemini-3.6-flash", "grok-4-fast"],
        "balanced": ["gemini-3.7-flash", "grok-4.6", "gemini-3.6-flash", "qwen3.8-max"],
        "quality": ["grok-4.6", "gemini-3.7-flash", "claude-sonnet-5"],
    },
    # Coding burns most tokens — keep it on flash/budget models.
    # The planner already made the expensive decisions.
    "code": {
        "budget": ["deepseek-v4-flash", "qwen3.7-flash", "gemini-3.7-flash", "grok-code-fast-1", "kimi-k2.7-code"],
        "fast": ["deepseek-v4-flash", "qwen3.7-flash", "gemini-3.7-flash", "kimi-k2.7-code-highspeed", "grok-code-fast-1"],
        "balanced": [
            "deepseek-v4-flash",
            "gemini-3.7-flash",
            "qwen3-coder-plus",
            "kimi-k2.7-code",
            "grok-code-fast-1",
            "deepseek-v4-pro",
        ],
        "quality": [
            "gemini-3.7-flash",
            "deepseek-v4-pro",
            "qwen3-coder-plus",
            "kimi-k2.7-code",
            "grok-build-0.1",
            "grok-code-fast-1",
        ],
    },
    "review": {
        "budget": ["grok-4-fast", "claude-haiku-4.5", "deepseek-v4-flash", "qwen3.7-flash"],
        "fast": ["grok-4-fast", "claude-haiku-4.5"],
        "balanced": [
            "claude-sonnet-5",
            "gpt-5.6-terra",
            "grok-4.6",
            "gemini-3.7-flash",
            "kimi-k3",
            "qwen3.8-max",
        ],
        "quality": ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol", "grok-4.6", "kimi-k3", "qwen3.8-max"],
    },
    "fix": {
        "budget": ["deepseek-v4-flash", "qwen3.7-flash", "gemini-3.7-flash", "grok-code-fast-1", "kimi-k2.7-code"],
        "fast": ["deepseek-v4-flash", "qwen3.7-flash", "gemini-3.7-flash", "kimi-k2.7-code-highspeed", "grok-code-fast-1"],
        "balanced": [
            "deepseek-v4-flash",
            "gemini-3.7-flash",
            "qwen3-coder-plus",
            "kimi-k2.7-code",
            "grok-code-fast-1",
            "deepseek-v4-pro",
        ],
        "quality": [
            "gemini-3.7-flash",
            "deepseek-v4-pro",
            "qwen3-coder-plus",
            "kimi-k2.7-code",
            "grok-build-0.1",
            "grok-code-fast-1",
        ],
    },
}

KEYWORD_DESIGN = re.compile(
    r"设计|ui|ux|css|layout|visual|界面|样式|美观|frontend|前端|landing|hero|theme",
    re.I,
)
KEYWORD_FIX = re.compile(r"修|bug|error|报错|fail|fix|crash|回滚", re.I)
KEYWORD_REVIEW = re.compile(r"review|审查|评审|code review", re.I)
KEYWORD_REFACTOR = re.compile(r"重构|refactor", re.I)
KEYWORD_RESEARCH = re.compile(r"调研|research|怎么做|对比|why|为何", re.I)
KEYWORD_PLAN = re.compile(r"方案|架构|plan|design doc|设计文档", re.I)
KEYWORD_HARD = re.compile(
    r"架构|分布式|并发|安全|迁移|编译器|kernel|multi-agent|性能|大规模",
    re.I,
)
KEYWORD_EXPLAIN = re.compile(
    r"解释|说明一下|是什么|什么是|干什么|做什么的|怎么理解|讲讲|"
    r"what is|what does|how does|explain |why is|why does",
    re.I,
)
KEYWORD_HOW_TO = re.compile(
    r"怎么(做|弄|改|实现|写)|如何(实现|做|写)|how (do i|to |can i )",
    re.I,
)
KEYWORD_EDIT = re.compile(
    r"请?(实现|加上|做成|开发|创建一个|写一个|改成|改一下|修一下)|"
    r"implement |add a |add the |build a |create |write ",
    re.I,
)


def looks_like_question(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if KEYWORD_EDIT.search(stripped) or KEYWORD_HOW_TO.search(stripped):
        return False
    if KEYWORD_EXPLAIN.search(stripped):
        return True
    return stripped.endswith(("?", "？")) and len(stripped) < 80


class NoModelAvailable(RuntimeError):
    pass


def heuristic_classify(task: str) -> TaskClass:
    text = task.strip()
    implementish = bool(KEYWORD_EDIT.search(text) or KEYWORD_HOW_TO.search(text))
    if KEYWORD_REVIEW.search(text) and not KEYWORD_FIX.search(text) and not implementish:
        intent_v = "review"
    elif KEYWORD_REFACTOR.search(text):
        intent_v = "refactor"
    elif KEYWORD_FIX.search(text):
        intent_v = "fix"
    elif KEYWORD_PLAN.search(text) and not KEYWORD_DESIGN.search(text) and not implementish:
        intent_v = "plan"
    elif KEYWORD_RESEARCH.search(text) and not implementish:
        intent_v = "research"
    elif looks_like_question(text):
        intent_v = "explain"
    elif KEYWORD_DESIGN.search(text) and not implementish and len(text) < 80:
        intent_v = "design"
    else:
        intent_v = "implement"

    domains: list[str] = []
    if KEYWORD_DESIGN.search(text):
        domains.append("ui-design")
        domains.append("frontend")
    if re.search(r"api|backend|服务端|数据库|sql|支付|oauth|auth", text, re.I):
        domains.append("backend")
    if re.search(r"deploy|ci|docker|k8s|devops", text, re.I):
        domains.append("devops")
    if re.search(r"文档|readme|docs", text, re.I):
        domains.append("docs")
    if re.search(r"架构|architecture", text, re.I):
        domains.append("architecture")

    complexity = "hard" if KEYWORD_HARD.search(text) or len(text) > 800 else "standard"
    if len(text) < 40 and intent_v in {"explain", "fix"}:
        complexity = "trivial"

    if intent_v == "explain" and len(text) < 80:
        complexity = "trivial"

    needs_design = "ui-design" in domains or intent_v == "design"
    needs_plan = intent_v in {"implement", "refactor", "plan"} and complexity != "trivial"
    needs_review = intent_v in {"implement", "fix", "refactor", "review"} and complexity != "trivial"
    if intent_v == "explain":
        needs_design = False
        needs_plan = False
        needs_review = False
    language = "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"

    return TaskClass(
        intent=intent_v,  # type: ignore[arg-type]
        complexity=complexity,  # type: ignore[arg-type]
        domains=domains,  # type: ignore[arg-type]
        needs_research=bool(KEYWORD_RESEARCH.search(text)),
        needs_plan=needs_plan,
        needs_design=needs_design,
        needs_review=needs_review,
        language=language,
        summary=text[:240],
    )


def parse_classification(raw: str, fallback: TaskClass) -> TaskClass:
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return fallback
    try:
        data = json.loads(match.group(0))
        return TaskClass.model_validate(data)
    except Exception:
        return fallback


def _reachable(spec: ModelSpec, available: dict[ProviderName, bool]) -> bool:
    from agentflow.retry import is_healthy

    native = bool(available.get(spec.provider) and is_healthy(spec.provider))
    if native:
        return True
    if available.get("openrouter") and spec.openrouter_id and is_healthy("openrouter"):
        return True
    return False


def _quality_rank(spec: ModelSpec, role: Role, mode: Mode) -> int:
    rank = {"budget": 1, "standard": 2, "frontier": 3}[spec.quality]
    # Router + implementers: cheaper is better. Plan/review still prefer capability.
    if role in {"router", "code", "fix"}:
        return 4 - rank
    cap = {"budget": 1, "fast": 2, "balanced": 2, "quality": 3}[mode]
    return min(rank, cap)


def pick_model(
    role: Role,
    mode: Mode,
    available: dict[ProviderName, bool] | None = None,
    *,
    avoid_provider: ProviderName | None = None,
    avoid_model: str | None = None,
    prefer_strengths: Iterable[str] = (),
    pins: dict[str, str] | None = None,
) -> ModelSpec:
    flags = available if available is not None else available_providers()
    if pins is None:
        from agentflow.picks import get_pins

        pins = get_pins()
    wanted = list(prefer_strengths)
    preferred_ids = list(PREFERENCES[role][mode])
    pin_role = "code" if role == "fix" and "fix" not in pins else role
    pinned_id = pins.get(pin_role) or pins.get(role)
    if pinned_id and pinned_id in MODELS:
        spec = MODELS[pinned_id]
        if _reachable(spec, flags) and spec.id != avoid_model:
            return spec

    def list_rank(spec: ModelSpec) -> int:
        try:
            return len(preferred_ids) - preferred_ids.index(spec.id)
        except ValueError:
            return 0

    def score(spec: ModelSpec) -> tuple[int, int, int, int, int, int]:
        in_pref = 1 if spec.id in preferred_ids else 0
        role_fit = 1 if role in spec.roles else 0
        strength_hits = sum(1 for item in wanted if item in spec.strengths)
        native = 1 if flags.get(spec.provider) else 0
        return (
            in_pref,
            role_fit,
            strength_hits,
            native,
            _quality_rank(spec, role, mode),
            list_rank(spec),
        )

    reachable = [spec for spec in MODELS.values() if _reachable(spec, flags)]
    if not reachable:
        raise NoModelAvailable(
            "No reachable model. Set XAI_API_KEY (recommended) or another provider key."
        )

    def ok(spec: ModelSpec, *, check_provider: bool, check_model: bool) -> bool:
        if check_model and avoid_model and spec.id == avoid_model:
            return False
        if check_provider and avoid_provider and spec.provider == avoid_provider:
            return False
        return True

    pool = [s for s in reachable if ok(s, check_provider=True, check_model=True)]
    if not pool:
        pool = [s for s in reachable if ok(s, check_provider=False, check_model=True)]
    if not pool:
        pool = list(reachable)
    pool.sort(key=score, reverse=True)
    return pool[0]


def transport_for(spec: ModelSpec, available: dict[ProviderName, bool]) -> ProviderName:
    if available.get(spec.provider):
        return spec.provider
    if available.get("openrouter") and spec.openrouter_id:
        return "openrouter"
    raise NoModelAvailable(f"No transport for {spec.id}")


def build_pipeline(
    task: TaskClass,
    mode: Mode,
    available: dict[ProviderName, bool] | None = None,
    max_steps: dict[str, int] | None = None,
    skip_review: bool = False,
    skip_design: bool = False,
) -> Pipeline:
    flags = available if available is not None else available_providers()
    steps = max_steps or {}
    notes: list[str] = []
    stages: list[Stage] = []

    def add(role: Role, tools: str, reason: str, **pick_kw) -> Stage:
        model = pick_model(role, mode, flags, **pick_kw)
        stage = Stage(
            role=role,
            model=model,
            reason=reason,
            max_steps=int(steps.get(role, 12)),
            tools=tools,  # type: ignore[arg-type]
        )
        stages.append(stage)
        return stage

    if task.needs_research and mode != "fast":
        add("research", "read", "Lookup before changing code")
    if task.intent in {"explain", "research"} and not any(s.role == "research" for s in stages):
        add("research", "read", "Read-only Q&A — do not edit files")

    plan_needed = task.needs_plan and mode != "fast" and task.complexity != "trivial"
    if mode == "quality" and task.intent in {"implement", "refactor", "plan", "design"}:
        plan_needed = True
    if task.intent == "plan":
        plan_needed = True
    if plan_needed:
        # Spend on planning, not on coding. Opus only for hard tasks.
        plan_mode: Mode = mode
        if (task.complexity == "hard" or "architecture" in task.domains) and mode != "budget":
            plan_mode = "quality"
            reason = "Frontier planner (hard/architecture) — coder stays cheap"
        else:
            reason = "High-end planner; cheap model will execute this spec"
        model = pick_model("plan", plan_mode, flags)
        stages.append(
            Stage(
                role="plan",
                model=model,
                reason=reason,
                max_steps=int(steps.get("plan", 10)),
                tools="read",
            )
        )
        notes.append("Plan uses a high-end model; code uses a flash/budget model.")

    design_needed = task.needs_design or "ui-design" in task.domains or "product" in task.domains
    if task.intent == "design":
        design_needed = True
    if skip_design:
        design_needed = False
        notes.append("BUDGET: skipped design stage.")
    if design_needed and not (mode == "budget" and "ui-design" not in task.domains):
        prefer = ("ui", "visual", "frontend") if "ui-design" in task.domains else ("visual",)
        add(
            "design",
            "read",
            "UI/product pass before implementation",
            prefer_strengths=prefer,
        )

    code_needed = task.intent in {"implement", "fix", "refactor", "design"}
    coder: Stage | None = None
    if code_needed:
        prefer: tuple[str, ...] = ("bulk-code", "unit-economics", "agentic-coding")
        reason = "Cheap implementer executing the plan"
        if "ui-design" in task.domains or "frontend" in task.domains:
            prefer = ("frontend", "ui", "visual", "bulk-code")
            reason = "Cheap UI implementer (Gemini Flash / DS Flash)"
        model = pick_model("code", mode, flags, prefer_strengths=prefer)
        coder = Stage(
            role="code",
            model=model,
            reason=reason,
            max_steps=int(steps.get("code", 32)),
            tools="all",
        )
        stages.append(coder)

    review_needed = task.needs_review and mode not in {"fast"}
    if skip_review and task.intent != "review":
        review_needed = False
        notes.append("BUDGET: skipped review model — check the diff yourself.")
    elif mode == "budget" and task.complexity != "hard":
        review_needed = False
        notes.append("Skipped review (budget mode, non-hard).")
    if task.complexity == "trivial":
        review_needed = False
    if task.intent in {"explain", "research", "plan"} and task.intent != "review":
        review_needed = False
    if task.intent == "review":
        review_needed = True
        code_needed = False

    if review_needed:
        avoid = coder.model.provider if coder else None
        avoid_id = coder.model.id if coder else None
        add(
            "review",
            "read",
            "Reviewer must be a different model than the coder",
            avoid_provider=avoid,
            avoid_model=avoid_id,
            prefer_strengths=("review", "repo-reasoning"),
        )
        reviewer = stages[-1]
        if coder and reviewer.model.id == coder.model.id:
            notes.append("WARNING: review and code share a model — add another API key.")
        elif coder and reviewer.model.provider == coder.model.provider:
            notes.append(
                f"Review {reviewer.model.id} ≠ coder {coder.model.id} (same vendor, no other key)."
            )
        elif coder:
            notes.append(
                f"Reviewer {reviewer.model.id} is a different vendor than coder {coder.model.id}."
            )

    notes.append("Workflow: 需求 → 规划 → 编程↔审核 → 通过（人类试用默认关闭，策略放行）")

    if coder and review_needed and mode in {"balanced", "quality"}:
        # Fix stage is conditional at runtime; include it so cost estimates cover a possible loop.
        add("fix", "all", "Apply review findings if any")

    estimated = round(sum(estimate_stage(s.model, s.role) for s in stages), 4)
    return Pipeline(
        classification=task,
        mode=mode,
        stages=stages,
        estimated_usd=estimated,
        notes=notes,
    )
