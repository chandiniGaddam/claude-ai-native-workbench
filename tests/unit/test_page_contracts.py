"""Contract tests: page-object selectors must still exist in the AUT's JSX source.

These read AUT files only (read-only). They don't run a browser or the AUT.
"""

import pytest

from qe.config import Settings
from qe.pages import catalogue_page as cp

pytestmark = pytest.mark.unit
SRC = Settings.from_env().aut_dir / "frontend" / "src"


def read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def test_heading_text():
    assert "<h1>Course catalogue</h1>" in read("App.jsx")


def test_filter_group_role_and_label():
    t = read("components/LevelFilter.jsx")
    assert 'role="group"' in t and 'aria-label="Filter by level"' in t
    assert cp.ALL_LEVELS_LABEL in t
    assert "chip chip--on" in t


def test_level_labels_match_constants():
    t = read("constants.js")
    for key, label in cp.LEVEL_LABELS.items():
        assert f'{key}: "{label}"' in t


def test_card_classes():
    t = read("components/CourseCard.jsx")
    for cls in ("course-card", "course-card__code", "course-card__level", "course-card__title", "course-card__credits"):
        assert f'"{cls}"' in t


def test_state_and_empty_text():
    t = read("components/CourseList.jsx")
    assert 'className="state"' in t
    assert cp.EMPTY_STATE_TEXT in t
    assert "Loading the catalogue" in t
