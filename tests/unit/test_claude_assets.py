import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("validate_claude_assets", ROOT / "scripts/validate_claude_assets.py")
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


def test_repository_assets_are_valid():
    n_skills, n_agents, errs = v.validate_all(ROOT)
    assert (n_skills, n_agents) == (3, 3)
    assert errs == []


def test_agent_with_write_tool_is_rejected(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("---\nname: bad\ndescription: " + "x" * 50 + "\ntools: Read, Write\n---\n" + "y" * 120)
    assert any("not allowed" in e for e in v.validate_agent(p))


def test_agent_without_tools_is_rejected(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("---\nname: bad\ndescription: " + "x" * 50 + "\n---\n" + "y" * 120)
    assert any("explicit tools" in e for e in v.validate_agent(p))


def test_skill_name_must_match_directory(tmp_path):
    d = tmp_path / "right-name"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: other\ndescription: " + "x" * 50 + "\n---\n" + "y" * 120)
    assert any("must equal directory" in e for e in v.validate_skill(d / "SKILL.md"))


def test_missing_front_matter(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("no front matter")
    assert v.validate_agent(p)
