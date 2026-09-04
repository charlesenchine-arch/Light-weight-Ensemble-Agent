from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from agentflow.agent.loop import RoleOutcome, classify_task, run_role
from agentflow.config import Settings, require_any_provider
from agentflow.cost import BudgetExceeded, Ledger, conservative_input_tokens
from agentflow.policy import load_allow_roots
from agentflow.providers.factory import complete
from agentflow.router import build_pipeline, pick_model
from agentflow.skills.categories import select_categories
from agentflow.skills.harvest import harvest_messages, parse_harvest
from agentflow.skills.library import SkillLibrary, format_catalog
from agentflow.types import Pipeline, Role, Stage
from agentflow.workspace import Workspace

EventFn = Callable[[str, str], None]
AskFn = Callable[[str], str]


def is_pass(text: str) -> bool:
    token = (text or "").strip().lower()
    return token in {"pass", "ok", "okay", "y", "yes", "通过", "过", "lgtm", "done", "完成"}


@dataclass
class RunResult:
    pipeline: Pipeline
    artifacts: dict[str, str] = field(default_factory=dict)
    changed: list[str] = field(default_factory=list)
    ledger: Ledger = field(default_factory=Ledger)
    stopped: str | None = None
    skills_loaded: list[str] = field(default_factory=list)
    skills_saved: list[str] = field(default_factory=list)
    code_review_rounds: int = 0
    trial_rounds: int = 0
    trial_passed: bool | None = None
    backups: dict[str, str | None] = field(default_factory=dict)
    failed_stage: str | None = None
    failed_model: str | None = None
    error: str | None = None


def run_pipeline(
    task: str,
    settings: Settings,
    *,
    only: Role | None = None,
    emit: EventFn | None = None,
    ask_user: AskFn | None = None,
    skip_trial: bool = True,
    classify_as: str | None = None,
    followup: bool = False,
) -> RunResult:
    from agentflow.cancel import Cancelled
    from agentflow.cancel import clear as clear_cancel

    clear_cancel()
    require_any_provider()
    extra_roots = load_allow_roots(settings.workspace, settings.allow_paths)
    workspace = Workspace(settings.workspace, extra_roots=extra_roots)
    ledger = Ledger(cap_usd=settings.max_cost_usd)
    library = SkillLibrary(settings.workspace)
    library.ensure()

    seed = classify_as or task
    classification = classify_task(seed, settings, ledger, emit)
    if followup:
        from agentflow.composer import adjust_for_followup

        classification = adjust_for_followup(classification, seed)
    from agentflow.mentions import expand_at_mentions

    task = expand_at_mentions(task, settings.workspace)
    if not only:
        from agentflow.budget import fit_budget

        plan = fit_budget(
            classification,
            settings.max_cost_usd,
            preferred_mode=settings.mode,
        )
        settings.mode = plan.mode
        settings.skip_review = settings.skip_review or plan.skip_review
        settings.skip_design = settings.skip_design or plan.skip_design
        if not plan.harvest:
            settings.harvest_skills = False
        settings.max_code_review_rounds = min(settings.max_code_review_rounds, plan.max_review_rounds)
        if emit:
            emit(
                "info",
                f"budget → {plan.expected}  mode={plan.mode}  预估 ${plan.estimated_usd:.3f} / cap ${settings.max_cost_usd:.3f}",
            )
            for warning in plan.warnings:
                emit("warn", warning)
    pipeline = build_pipeline(
        classification,
        settings.mode,
        max_steps=settings.max_steps,
        skip_review=settings.skip_review or settings.mode == "fast",
        skip_design=settings.skip_design,
    )
    if not only and not pipeline.stages:
        model = pick_model("research", settings.mode)
        pipeline.stages = [
            Stage(
                role="research",
                model=model,
                reason="Read-only fallback — empty pipeline",
                max_steps=settings.steps_for("research"),
                tools="read",
            )
        ]
    if only:
        pipeline.stages = [s for s in pipeline.stages if s.role == only]
        if not pipeline.stages:
            model = pick_model(only, settings.mode)
            pipeline.stages = [
                Stage(
                    role=only,
                    model=model,
                    reason=f"forced --only {only}",
                    max_steps=settings.steps_for(only),
                    tools="all" if only in {"code", "fix"} else "read",
                )
            ]

    if emit:
        emit("pipeline", pipeline.model_dump_json())
        emit("info", "skill drawers " + ", ".join(select_categories(classification, "code")))

    result = RunResult(
        pipeline=pipeline,
        ledger=ledger,
    )
    artifacts: dict[str, str] = {}
    changed: list[str] = []

    def collect(outcome: RoleOutcome) -> None:
        for path in outcome.changed:
            if path not in changed:
                changed.append(path)
        for name in outcome.saved_skills:
            if name not in result.skills_saved:
                result.skills_saved.append(name)
        for rel, old in outcome.backups.items():
            if rel not in result.backups:
                result.backups[rel] = old

    def exec_stage(stage: Stage, label: str | None = None) -> RoleOutcome:
        if ledger.over_cap():
            result.stopped = f"cost cap ${settings.max_cost_usd:.2f}"
            return RoleOutcome(text=result.stopped, finished=False)
        title = label or f"{stage.role} → {stage.model.id} ({stage.model.provider}) · {stage.reason}"
        if emit:
            emit("stage", title)
        cats = select_categories(classification, stage.role)
        matched = library.match(
            task,
            list(classification.domains),
            categories=cats,
            limit=2,
        )
        for skill in matched:
            if skill.key not in result.skills_loaded:
                result.skills_loaded.append(skill.key)
        try:
            outcome = run_role(
                stage,
                task,
                classification,
                workspace,
                settings,
                ledger,
                artifacts,
                emit,
                library=library,
                skills=matched,
                catalog=format_catalog(library.all(), focus=cats, budget=1000),
            )
        except (Cancelled, KeyboardInterrupt):
            from agentflow.cancel import request as request_cancel

            request_cancel()
            result.stopped = "interrupted"
            result.failed_stage = stage.role
            result.failed_model = f"{stage.model.id} ({stage.model.provider})"
            outcome = RoleOutcome(text="已打断", finished=False)
        except BudgetExceeded as exc:
            result.stopped = f"cost cap ${settings.max_cost_usd:.2f}"
            if emit:
                emit("warn", f"预算保护停止 {stage.role}：{exc}")
            outcome = RoleOutcome(text=str(exc), finished=False)
        except Exception as exc:  # noqa: BLE001 — surface to the user, keep the REPL
            result.stopped = "error"
            result.error = f"{type(exc).__name__}: {exc}"
            result.failed_stage = stage.role
            result.failed_model = f"{stage.model.id} ({stage.model.provider})"
            if emit:
                emit("warn", f"卡在 {stage.role} · {stage.model.id} · {type(exc).__name__}")
            outcome = RoleOutcome(text=str(exc), finished=False)
        artifacts[stage.role] = outcome.text
        collect(outcome)
        if outcome.text == "已打断" and not result.stopped:
            result.stopped = "interrupted"
            result.failed_stage = result.failed_stage or stage.role
            result.failed_model = result.failed_model or f"{stage.model.id} ({stage.model.provider})"
        if not outcome.finished and not result.stopped:
            result.stopped = f"{stage.role} did not finish"
            result.failed_stage = stage.role
            result.failed_model = f"{stage.model.id} ({stage.model.provider})"
        if changed:
            artifacts["changed_files"] = "\n".join(changed)
        if emit:
            emit("cost", f"{ledger.total_usd:.4f}/{ledger.cap_usd:.4f}")
        return outcome

    if only:
        for stage in pipeline.stages:
            exec_stage(stage)
            if result.stopped:
                break
        result.artifacts = artifacts
        result.changed = changed
        return result

    by_role = {s.role: s for s in pipeline.stages}

    for role in ("research", "plan", "design"):
        stage = by_role.get(role)
        if stage:
            exec_stage(stage)
            if result.stopped:
                result.artifacts = artifacts
                result.changed = changed
                return result

    code_stage = by_role.get("code")
    fix_stage = by_role.get("fix")
    review_stage = by_role.get("review")

    if code_stage and review_stage:
        passed = False
        for rnd in range(1, settings.max_code_review_rounds + 1):
            result.code_review_rounds = rnd
            active_code_stage = code_stage if rnd == 1 or fix_stage is None else fix_stage
            exec_stage(
                active_code_stage,
                f"{active_code_stage.role} [{rnd}/{settings.max_code_review_rounds}] → {active_code_stage.model.id}",
            )
            if result.stopped:
                break
            if code_stage.model.id == review_stage.model.id:
                result.stopped = "code and review resolved to the same model"
                break
            review = exec_stage(
                review_stage,
                f"review [{rnd}/{settings.max_code_review_rounds}] → {review_stage.model.id}",
            )
            if result.stopped:
                break
            if review.blocking_issues <= 0:
                passed = True
                if emit:
                    emit("info", f"编程-审核循环通过（第 {rnd} 轮）")
                break
            if emit:
                emit("info", f"审核未过（{review.blocking_issues} blocking）→ 继续改")
        if not passed and not result.stopped:
            result.stopped = f"code-review loop exhausted ({settings.max_code_review_rounds} rounds)"
    elif code_stage:
        exec_stage(code_stage)

    if not result.stopped and settings.harvest_skills and changed:
        _harvest(task, artifacts, library, settings, ledger, result, emit)
    elif emit and not changed:
        emit("info", "skip harvest (no files changed)")

    if (
        not skip_trial
        and ask_user
        and code_stage
        and not result.stopped
        and settings.mode != "fast"
    ):
        _trial_loop(
            task,
            settings,
            code_stage,
            review_stage,
            exec_stage,
            artifacts,
            result,
            emit,
            ask_user,
        )

    result.artifacts = artifacts
    result.changed = changed
    return result


def _harvest(task, artifacts, library: SkillLibrary, settings, ledger, result: RunResult, emit) -> None:
    try:
        spec = pick_model("router", settings.mode)
        existing = [s.key for s in library.all()]
        messages = harvest_messages(task, artifacts, existing)
        allowed = ledger.affordable_output_tokens(
            spec,
            conservative_input_tokens(messages),
            1500,
        )
        if allowed < 256:
            if emit:
                emit("info", "skip harvest (budget reserved for useful model output)")
            return
        raw = complete(spec, messages, json_mode=True, max_tokens=allowed)
        ledger.record("harvest", spec.id, raw.provider, raw.usage)
        for skill in parse_harvest(raw.message.content, set(existing)):
            saved = library.save(skill, overwrite=False)
            if saved.key not in result.skills_saved:
                result.skills_saved.append(saved.key)
            if emit:
                emit("info", f"toolbox + {saved.key}")
    except Exception as exc:  # noqa: BLE001
        if emit:
            emit("warn", f"skill harvest skipped ({exc})")


def _trial_loop(
    task,
    settings,
    code_stage,
    review_stage,
    exec_stage,
    artifacts,
    result: RunResult,
    emit,
    ask_user: AskFn,
) -> None:
    for rnd in range(1, settings.max_trial_rounds + 1):
        result.trial_rounds = rnd
        prompt = (
            "请试用当前改动。\n"
            "输入 pass / 通过 表示验收通过。\n"
            "否则直接写下问题和期望，将进入「试用反馈 → 审核 → 编程」循环。"
        )
        if emit:
            emit("trial", f"试用轮次 {rnd}/{settings.max_trial_rounds}")
        feedback = ask_user(prompt)
        if is_pass(feedback):
            result.trial_passed = True
            if emit:
                emit("info", "用户试用通过")
            return
        artifacts["trial_feedback"] = feedback
        exec_stage(code_stage, f"trial-code [{rnd}] → {code_stage.model.id}")
        if result.stopped:
            return
        if review_stage:
            if code_stage.model.id == review_stage.model.id:
                result.stopped = "code and review resolved to the same model"
                return
            review = exec_stage(
                review_stage,
                f"trial-review [{rnd}] → {review_stage.model.id}",
            )
            if review.blocking_issues > 0 and emit:
                emit("info", f"试用后审核仍有 {review.blocking_issues} 个 blocking")
    result.trial_passed = False
    result.stopped = result.stopped or f"trial loop exhausted ({settings.max_trial_rounds} rounds)"
