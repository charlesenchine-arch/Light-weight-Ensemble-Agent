from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table
from rich.text import Text

from agentflow import __version__, theme
from agentflow.config import available_providers, load_settings
from agentflow.policy import (
    add_allow_path,
    load_allow_roots,
    project_allowlist_file,
    remove_allow_path,
    user_allowlist_file,
)
from agentflow.router import build_pipeline, heuristic_classify, pick_model
from agentflow.skills.library import SkillLibrary, user_toolbox_dir
from agentflow.types import Mode, Role

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
    help="LEA — Light-weight Ensemble Agent",
)

COMMANDS = {
    "version",
    "init",
    "models",
    "use",
    "route",
    "doctor",
    "cost",
    "run",
    "plan",
    "design",
    "review",
    "ask",
    "skills",
    "allow",
}
skills_app = typer.Typer(help="本机 toolbox skills")
allow_app = typer.Typer(help="项目外路径白名单")
app.add_typer(skills_app, name="skills")
app.add_typer(allow_app, name="allow")
theme.load_skin_from_prefs()
console = theme.styled_console()

MODES = ("budget", "fast", "balanced", "quality")


def _settings(workspace: Optional[Path], mode: Optional[str], max_cost: Optional[float]):
    parsed_mode: Mode | None = mode if mode in MODES else None  # type: ignore[assignment]
    return load_settings(
        workspace=workspace.resolve() if workspace else Path.cwd(),
        mode=parsed_mode,
        max_cost_usd=max_cost,
    )


def _print_keys() -> None:
    flags = available_providers()
    skin = theme.current()
    table = theme.themed_table("keys")
    table.add_column("Provider")
    table.add_column("Status")
    for name, ok in flags.items():
        table.add_row(
            name,
            f"[bold {skin.ok}]ready[/]" if ok else f"[{skin.muted} italic]missing[/]",
        )
    console.print(table)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    mode: str = typer.Option("balanced", "--mode", "-m"),
) -> None:
    """LEA — Light-weight Ensemble Agent. 无参数进入对话，有子命令则执行。"""
    if ctx.invoked_subcommand is not None:
        return
    from agentflow.repl import start_repl

    start_repl(workspace=workspace, mode=mode if mode in MODES else "balanced")


@app.command()
def version() -> None:
    """Print version."""
    skin = theme.current()
    console.print(f"[bold {skin.accent}]LEA[/] [{skin.muted}]{__version__}[/]  [italic {skin.text}]Light-weight Ensemble Agent[/]")


@app.command("init")
def init_cmd(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Create safe starter configuration in a project without overwriting files."""
    from importlib.resources import files

    root = (workspace or Path.cwd()).resolve()
    if not root.is_dir():
        console.print(theme.err_line(f"workspace does not exist: {root}"))
        raise typer.Exit(1)

    templates = {
        ".env.example": files("agentflow").joinpath("env.example"),
        "agentflow.yaml": files("agentflow").joinpath("defaults.yaml"),
    }
    created: list[str] = []
    kept: list[str] = []
    for name, resource in templates.items():
        target = root / name
        if target.exists():
            kept.append(name)
            continue
        target.write_text(resource.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(name)

    if created:
        console.print(theme.ok_line("created  " + ", ".join(created)))
    if kept:
        console.print(theme.dim_line("kept existing  " + ", ".join(kept)))
    console.print(theme.dim_line("next: copy .env.example to .env, add one API key, then run lea"))


def _print_vendor_models() -> None:
    from agentflow.catalog import MODELS, PIN_ROLES, PROVIDER_LABEL, PROVIDER_ORDER
    from agentflow.picks import get_pins, set_last_index

    flags = available_providers()
    pins = get_pins()
    reverse = {mid: [r for r, m in pins.items() if m == mid] for mid in MODELS}
    listed: list[str] = []
    n = 1
    skin = theme.current()
    for provider in PROVIDER_ORDER:
        specs = [m for m in MODELS.values() if m.provider == provider]
        if not specs:
            continue
        key_ok = flags.get(provider)
        status = f"[{skin.ok}]key ready[/]" if key_ok else f"[{skin.muted} italic]no key[/]"
        console.print(f"\n[bold {skin.accent}]{PROVIDER_LABEL.get(provider, provider)}[/]  {status}")
        table = theme.themed_table("")
        table.add_column("#", justify="right")
        table.add_column("Model")
        table.add_column("In / Out")
        table.add_column("Tier")
        table.add_column("Roles")
        table.add_column("Pinned")
        for spec in specs:
            listed.append(spec.id)
            used = reverse.get(spec.id) or []
            pin = ", ".join(used) if used else ""
            table.add_row(
                str(n),
                spec.id,
                f"${spec.input_per_m:.2f} / ${spec.output_per_m:.2f}",
                spec.quality,
                ", ".join(spec.roles[:3]),
                f"[bold {skin.accent}]{pin}[/]" if pin else f"[{skin.muted}]—[/]",
            )
            n += 1
        console.print(table)
    set_last_index(listed)
    if pins:
        console.print(theme.dim_line("pins  " + "  ·  ".join(f"{r}={m}" for r, m in pins.items())))
    console.print(theme.dim_line(f"pick  lea use <{'|'.join(PIN_ROLES)}> <model-or-#>"))


@app.command()
def models(
    list_only: bool = typer.Option(False, "--list", help="只打印目录，不进入选择界面"),
) -> None:
    """默认模型列表。TTY 下进入换供应商/换模型界面。"""
    if list_only or not sys.stdin.isatty():
        _print_vendor_models()
        _print_keys()
        return
    from agentflow.model_desk import open_desk

    open_desk()


@app.command()
def use(
    role: str = typer.Argument(..., help="plan | design | code | review"),
    model: str = typer.Argument(..., help="model id or number from `lea models`"),
) -> None:
    """Pin a vendor model to a pipeline role."""
    from agentflow.catalog import PIN_ROLES
    from agentflow.picks import clear_pin, resolve_listed, set_pin

    role = role.strip().lower()
    if model.strip().lower() in {"-", "clear", "auto"}:
        if role not in PIN_ROLES:
            console.print(theme.err_line(f"role must be {', '.join(PIN_ROLES)}"))
            raise typer.Exit(1)
        clear_pin(role)
        console.print(theme.ok_line(f"{role} → auto"))
        return
    try:
        model_id = resolve_listed(model)
        spec = set_pin(role, model_id)
    except (KeyError, ValueError) as exc:
        console.print(theme.err_line(str(exc)))
        raise typer.Exit(1)
    flags = available_providers()
    reachable = flags.get(spec.provider) or flags.get("openrouter")
    note = "" if reachable else "  (no API key for this vendor yet)"
    console.print(theme.ok_line(f"{role} → {spec.id}  [{spec.provider}]{note}"))


@app.command("route")
def route_cmd(
    task: str = typer.Argument(..., help="What you want done"),
    mode: str = typer.Option("balanced", "--mode", "-m", help="budget|fast|balanced|quality"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Show which models would run, without calling any API."""
    settings = _settings(workspace, mode, None)
    _preview_route(task, settings)


def _preview_route(task: str, settings) -> None:
    """Render the real budget-fitted route without making provider calls."""
    from agentflow.budget import fit_budget

    classification = heuristic_classify(task)
    plan = fit_budget(
        classification,
        settings.max_cost_usd,
        preferred_mode=settings.mode,
    )
    pipeline = build_pipeline(
        classification,
        plan.mode,
        max_steps=settings.max_steps,
        skip_review=settings.skip_review or plan.skip_review,
        skip_design=settings.skip_design or plan.skip_design,
    )
    _render_pipeline(pipeline)
    console.print(
        f"\n[dim]Heuristic classify (no API). Estimated typical cost ≈ "
        f"${pipeline.estimated_usd:.3f} / cap ${settings.max_cost_usd:.3f}[/dim]"
    )
    for warning in plan.warnings:
        console.print(theme.warn_line(warning))


def _render_pipeline(pipeline) -> None:
    table = theme.themed_table(f"pipeline  ·  {pipeline.mode}")
    table.add_column("Role")
    table.add_column("Model")
    table.add_column("Provider")
    table.add_column("Why")
    table.add_column("Est.")
    from agentflow.catalog import estimate_stage

    for stage in pipeline.stages:
        glyph = theme.STAGE_GLYPH.get(stage.role, "·")
        table.add_row(
            f"{glyph} {stage.role}",
            stage.model.id,
            stage.model.provider,
            stage.reason,
            f"{estimate_stage(stage.model, stage.role):.3f}",
        )
    console.print(table)
    cls = pipeline.classification
    skin = theme.current()
    console.print(
        theme.panel(
            f"[{skin.muted} italic]intent[/] {cls.intent}   "
            f"[{skin.muted} italic]complexity[/] {cls.complexity}   "
            f"[{skin.muted} italic]domains[/] {cls.domains}\n"
            f"[{skin.text}]{cls.summary}[/]",
            title="task",
        )
    )
    for note in pipeline.notes:
        console.print(theme.warn_line(note) if "风险" in note or "WARNING" in note or "BUDGET" in note else theme.dim_line(note))


@app.command()
def doctor(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Check keys, router, and auto-allow roots."""
    settings = _settings(workspace, None, None)
    _print_keys()
    flags = available_providers()
    if not any(flags.values()):
        console.print("[red]No keys. Copy .env.example to .env and set XAI_API_KEY.[/red]")
        raise typer.Exit(1)
    spec = pick_model("router", "balanced", flags)
    console.print(theme.ok_line(f"router  {spec.id}  via {spec.provider}"))
    extra = load_allow_roots(settings.workspace, settings.allow_paths)
    console.print(theme.dim_line(f"workspace  {settings.workspace}"))
    for extra_root in extra:
        console.print(theme.dim_line(str(extra_root)))
    console.print(theme.dim_line(f"allowlist  user {user_allowlist_file()}"))
    console.print(theme.dim_line(f"allowlist  project {project_allowlist_file(settings.workspace)}"))


@app.command()
def cost(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """打开最近一次运行的花费图（规划/设计/编写/审核）。"""
    from agentflow.display import show_costboard
    from agentflow.money import load_prefs, normalize_currency
    from agentflow.session import latest_session_file, load_session_ledger

    settings = _settings(workspace, None, None)
    path = latest_session_file(settings.workspace)
    if path is None:
        console.print(theme.err_line("还没有花费记录。先跑一次任务。对话里花费图在右上角。"))
        raise typer.Exit(1)
    ledger, payload = load_session_ledger(path)
    prefs = load_prefs()
    try:
        cur = normalize_currency(prefs.get("currency") or settings.currency or "cny")
    except ValueError:
        cur = "cny"
    title = "cost"
    task = (payload.get("task") or "").strip().splitlines()
    if task:
        title = "cost  ·  " + task[0][:40]
    show_costboard(console, ledger, cur, title=title, pause=False)
    console.print(theme.dim_line(str(path)))


@app.command()
def run(
    task: str = typer.Argument(..., help="What you want done"),
    mode: str = typer.Option("balanced", "--mode", "-m"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost", help="USD cap for this run"),
    only: Optional[str] = typer.Option(None, "--only", help="Run a single role: plan|design|code|review"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Classify and route, do not call implementers"),
    trial: bool = typer.Option(False, "--trial", help="Opt into the human trial loop"),
    no_trial: bool = typer.Option(False, "--no-trial", help="Force-skip trial even if human_trial is true"),
    budget: Optional[str] = typer.Option(None, "--budget", "-b", help="e.g. 0.5usd / 10cny"),
    currency: Optional[str] = typer.Option(None, "--currency", help="usd|cny|eur|gbp|jpy|hkd"),
    classify_as: Optional[str] = typer.Option(None, hidden=True),
    followup: bool = typer.Option(False, hidden=True),
    show_cost: bool = typer.Option(True, hidden=True),
) -> None:
    """需求 → 规划 → 编程↔审核 → 通过。人类试用默认关闭，由项目边界策略放行。"""
    from agentflow.agent.pipeline import run_pipeline
    from agentflow.display import print_costboard
    from agentflow.money import fmt, load_prefs, normalize_currency, parse_money, save_prefs, to_usd
    from agentflow.session import save_session

    settings = _settings(workspace, mode, max_cost)
    prefs = load_prefs()
    try:
        cur = normalize_currency(currency or settings.currency or prefs.get("currency") or "cny")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    settings.currency = cur
    prefs["currency"] = cur
    save_prefs(prefs)
    if budget:
        parsed = parse_money(budget, cur)
        if not parsed:
            console.print("[red]预算格式：0.5 / 0.5usd / 10cny[/red]")
            raise typer.Exit(1)
        amount, bcur = parsed
        settings.max_cost_usd = to_usd(amount, bcur)
        settings.currency = bcur
        cur = bcur
        prefs["currency"] = cur
        save_prefs(prefs)
    if dry_run:
        _preview_route(classify_as or task, settings)
        return

    console.print(
        theme.panel(
            f"[{theme.current().muted} italic]workspace[/]  {settings.workspace}\n"
            f"[{theme.current().muted} italic]mode[/]       {settings.mode}    "
            f"[{theme.current().muted} italic]cap[/]  {fmt(settings.max_cost_usd, cur)}    "
            f"[{theme.current().muted} italic]fx[/]  {cur.upper()}",
            title="run",
        )
    )

    def emit(kind: str, payload: str) -> None:
        if kind == "token":
            console.print(payload, end="", highlight=False, markup=False)
            return
        if kind == "pipeline":
            return
        if kind == "tool":
            console.print(theme.tool_line(payload))
            return
        if kind == "stage":
            console.print()
            console.print(theme.stage_line(payload))
            return
        if kind == "step":
            console.print(theme.dim_line(payload))
            return
        if kind == "warn":
            console.print(theme.warn_line(payload))
            return
        if kind == "info":
            console.print(theme.info_line(payload))
            return
        if kind == "router":
            console.print(theme.dim_line(payload))
        if kind == "trial":
            console.print(theme.warn_line(payload))
        if kind == "cost":
            spent_s, cap_s = payload.split("/")
            console.print(theme.dim_line(f"spend {fmt(float(spent_s), cur)} / {fmt(float(cap_s), cur)}"))

    def ask_user(prompt: str) -> str:
        console.print(theme.panel(prompt, title="trial"))
        return typer.prompt("试用结果", default="pass")

    role: Role | None = only if only in {"research", "plan", "design", "code", "review", "fix"} else None  # type: ignore[assignment]
    want_trial = trial or (settings.human_trial and not no_trial)
    skip_trial = bool(not want_trial or only or not sys.stdin.isatty())
    try:
        result = run_pipeline(
            task,
            settings,
            only=role,
            emit=emit,
            ask_user=None if skip_trial else ask_user,
            skip_trial=skip_trial,
            classify_as=classify_as,
            followup=followup,
        )
    except KeyboardInterrupt:
        from agentflow.cancel import request as request_cancel

        request_cancel()
        console.print(theme.warn_line("已打断  ·  Ctrl+C 只停这一轮，对话还在"))
        raise
    _render_pipeline(result.pipeline)
    if show_cost:
        print_costboard(console, result.ledger, cur, title="cost")
    if result.skills_loaded or result.skills_saved:
        console.print(
            theme.dim_line(
                f"skills  {', '.join(result.skills_loaded) or '—'}  ·  saved {', '.join(result.skills_saved) or '—'}"
            )
        )
    if result.changed:
        console.print(theme.panel("\n".join(result.changed), title="files"))
        try:
            from agentflow.workspace import Workspace as _WS

            diff_text = _WS(settings.workspace).diff(max_chars=4000)
            if diff_text and "no unstaged/uncommitted" not in diff_text.lower():
                console.print(theme.panel(Text(diff_text[:4000]), title="diff"))
        except Exception:
            pass
    final = result.artifacts.get("fix") or result.artifacts.get("code") or result.artifacts.get("review")
    if not final:
        final = next(reversed(list(result.artifacts.values())), "")
    if final:
        console.print(theme.panel(Text(final[:4000]), title="summary"))
    path = save_session(settings.workspace, result, classify_as or task)
    console.print(theme.dim_line(f"session {path}"))
    if result.stopped:
        from agentflow.display import explain_failure

        console.print(
            theme.panel(
                explain_failure(
                    result.error,
                    stage=result.failed_stage,
                    model=result.failed_model,
                    stopped=result.stopped,
                    changed=result.changed,
                ),
                title="这一轮没跑完",
            )
        )
        console.print(theme.dim_line("输入框已清空。直接打下一步，或 /retry 重发刚才那句。"))
    return result


def _render_cost(result, currency: str = "usd") -> None:
    from agentflow.display import print_costboard

    print_costboard(console, result.ledger, currency)


@app.command()
def plan(
    task: str = typer.Argument(...),
    mode: str = typer.Option("balanced", "--mode", "-m"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Plan only — no file writes."""
    run(task=task, mode=mode, workspace=workspace, max_cost=None, only="plan", dry_run=False)


@app.command()
def design(
    task: str = typer.Argument(...),
    mode: str = typer.Option("balanced", "--mode", "-m"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Design spec only (UI / product / copy)."""
    run(task=task, mode=mode, workspace=workspace, max_cost=None, only="design", dry_run=False)


@app.command()
def review(
    task: str = typer.Argument("Review the current git diff for bugs, design drift, and risk."),
    mode: str = typer.Option("balanced", "--mode", "-m"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Review the workspace / current diff."""
    run(task=task, mode=mode, workspace=workspace, max_cost=None, only="review", dry_run=False)


@app.command()
def ask(
    question: str = typer.Argument(...),
    mode: str = typer.Option("fast", "--mode", "-m"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """Single-role Q&A over the repo (read-only)."""
    run(
        task=question,
        mode=mode,
        workspace=workspace,
        max_cost=None,
        only="research",
        dry_run=False,
        no_trial=True,
    )


@skills_app.command("list")
def skills_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="只看一个分类抽屉"),
) -> None:
    """列出本机 toolbox 里的 skills。"""
    root = workspace.resolve() if workspace else Path.cwd()
    lib = SkillLibrary(root)
    skills = lib.in_category(category) if category else lib.all()
    if not skills:
        console.print("[dim]toolbox 为空[/dim]")
        console.print(f"用户库: {user_toolbox_dir()}")
        return
    table = Table(title="Toolbox skills" + (f" · {category}" if category else ""))
    table.add_column("Category")
    table.add_column("Name")
    table.add_column("Scope")
    table.add_column("Description")
    for skill in skills:
        table.add_row(skill.category, skill.name, skill.scope, skill.description[:80])
    console.print(table)


@skills_app.command("cats")
def skills_cats(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """列出 toolbox 分类抽屉。"""
    from agentflow.skills.categories import CATEGORIES

    root = workspace.resolve() if workspace else Path.cwd()
    counts = SkillLibrary(root).categories()
    table = Table(title="Toolbox drawers")
    table.add_column("Category")
    table.add_column("Count")
    table.add_column("For")
    for name, count in counts.items():
        table.add_row(name, str(count), CATEGORIES.get(name, ""))
    console.print(table)


@skills_app.command("show")
def skills_show(
    name: str,
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """打印一个 skill 的全文。"""
    root = workspace.resolve() if workspace else Path.cwd()
    skill = SkillLibrary(root).get(name)
    if not skill:
        console.print(f"[red]not found: {name}[/red]")
        raise typer.Exit(1)
    console.print(theme.panel(f"{skill.description}\n\n{skill.body}", title=f"{skill.name} ({skill.scope})"))


@skills_app.command("path")
def skills_path(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """显示本机 / 项目 skill 目录。"""
    root = workspace.resolve() if workspace else Path.cwd()
    lib = SkillLibrary(root)
    console.print(f"user    {lib.user_dir}")
    console.print(f"project {lib.project_dir}")


@allow_app.command("list")
def allow_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
) -> None:
    """列出自动放行的根目录。"""
    settings = _settings(workspace, None, None)
    console.print(f"workspace {settings.workspace}")
    extras = load_allow_roots(settings.workspace, settings.allow_paths)
    if not extras:
        console.print("[dim]no extra allowlisted roots[/dim]")
        return
    for root in extras:
        console.print(str(root))


@allow_app.command("add")
def allow_add(
    path: Path,
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    user: bool = typer.Option(False, "--user", help="Write to the machine-wide allowlist"),
) -> None:
    """把项目外的目录加入白名单。之后该目录内的文件指令会自动放行。"""
    settings = _settings(workspace, None, None)
    target = add_allow_path(path, user=user, workspace=settings.workspace)
    console.print(f"[green]allowed {path.resolve()}[/green]\n[dim]wrote {target}[/dim]")


@allow_app.command("remove")
def allow_remove(
    path: Path,
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    user: bool = typer.Option(False, "--user"),
) -> None:
    """从白名单去掉一个路径。"""
    settings = _settings(workspace, None, None)
    target = remove_allow_path(path, user=user, workspace=settings.workspace)
    console.print(f"removed {path.resolve()}\n[dim]{target}[/dim]")


def rewrite_argv(argv: list[str]) -> list[str]:
    """`lea fix the login page` → `lea run 'fix the login page'`."""
    if len(argv) < 2:
        return argv
    first = argv[1]
    if first in COMMANDS or first.startswith("-"):
        return argv
    return [argv[0], "run", " ".join(argv[1:])]


def main() -> None:
    sys.argv = rewrite_argv(sys.argv)
    app()


if __name__ == "__main__":
    main()
