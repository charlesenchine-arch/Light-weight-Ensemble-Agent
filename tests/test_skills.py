from pathlib import Path

from agentflow.skills.categories import select_categories
from agentflow.skills.harvest import parse_harvest
from agentflow.skills.library import Skill, SkillLibrary, validate_name
from agentflow.tools import Toolbelt
from agentflow.types import TaskClass
from agentflow.workspace import Workspace


def test_validate_name():
    assert validate_name("Add_Router") == "add-router"
    assert validate_name("ab") == "ab"
    try:
        validate_name("x")
        raise AssertionError("expected failure")
    except ValueError:
        pass


def test_save_match_and_project_override(tmp_path: Path):
    lib = SkillLibrary(tmp_path, user_dir=tmp_path / "user-box")
    lib.save(
        Skill(
            name="add-router",
            description="Add a FastAPI APIRouter when adding HTTP endpoints",
            triggers=["endpoint", "新接口", "router"],
            domains=["backend"],
            body="1. Create routers/x.py\n2. include_router in main.py\n3. Add a test.",
            scope="user",
        )
    )
    hits = lib.match("给后台加一个新接口 endpoint", ["backend"], categories=["backend", "general"])
    assert hits
    assert hits[0].name == "add-router"
    assert hits[0].category == "general"

    lib.save(
        Skill(
            name="add-router",
            description="Project-specific router layout under src/api",
            body="Put routers in src/api/ and register in src/app.py",
            scope="project",
        )
    )
    found = lib.get("add-router")
    assert found is not None
    assert found.scope == "project"
    assert "src/api" in found.body


def test_save_skill_tool(tmp_path: Path):
    (tmp_path / "src").mkdir()
    lib = SkillLibrary(tmp_path, user_dir=tmp_path / "user-box")
    belt = Toolbelt(Workspace(tmp_path), library=lib)
    out = belt._save_skill(
        {
            "name": "pytest-layout",
            "description": "How tests are laid out in this repo. Triggers: 测试, pytest",
            "body": "Put tests next to src under tests/, name test_*.py, run pytest -q.",
            "triggers": ["pytest", "测试"],
            "scope": "user",
        }
    )
    assert "saved" in out
    assert lib.get("pytest-layout") is not None
    again = belt._save_skill(
        {
            "name": "pytest-layout",
            "description": "duplicate",
            "body": "should not overwrite " + "x" * 40,
        }
    )
    assert "already existed" in again


def test_parse_harvest_skips_existing_and_thin():
    raw = """
    {"skills": [
      {"name": "keep-me", "description": "A recurring deploy recipe", "body": "Step one then two then three, enough text.", "triggers": ["deploy"]},
      {"name": "keep-me", "description": "dup", "body": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
      {"name": "x", "description": "no", "body": "tiny"},
      {"name": "already", "description": "exists", "body": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}
    ]}
    """
    skills = parse_harvest(raw, {"already", "general/already"})
    assert [s.name for s in skills] == ["keep-me"]


def test_category_drawers_and_role_pick(tmp_path: Path):
    lib = SkillLibrary(tmp_path, user_dir=tmp_path / "user-box")
    lib.save(
        Skill(
            name="add-router",
            category="backend",
            description="Add a FastAPI router for new HTTP endpoints",
            triggers=["endpoint"],
            body="1. Create routers/x.py\n2. include_router in main.py\n3. Add a test.",
        )
    )
    lib.save(
        Skill(
            name="no-slop-ui",
            category="ui-design",
            description="Reject generic AI landing pages",
            triggers=["landing", "hero"],
            body="No purple gradients. Use the existing type scale and tokens.",
        )
    )
    stored = tmp_path / "user-box" / "backend" / "add-router" / "SKILL.md"
    assert stored.is_file()
    assert lib.get("add-router", category="backend") is not None
    backend_only = lib.match("endpoint router", ["backend"], categories=["backend"])
    assert backend_only and backend_only[0].name == "add-router"
    ui_only = lib.match("endpoint router", ["backend"], categories=["ui-design"])
    assert ui_only == []
    task = TaskClass(intent="implement", domains=["ui-design", "frontend"], summary="login ui")
    cats = select_categories(task, "design")
    assert "ui-design" in cats
    assert "backend" not in cats
