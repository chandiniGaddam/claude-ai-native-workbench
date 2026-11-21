"""pytest plugin for the workbench (enabled via ``-p qe.pytest_plugin`` in pytest.ini).

- Validates ``@pytest.mark.gate("<MATRIX-ID>")`` markers and records the ID as the JUnit
  property ``gate_id``, which scripts/check_gate.py consumes.
- Points Playwright at the project-local browser cache (.tools/ms-playwright) unless
  PLAYWRIGHT_BROWSERS_PATH is already set.
"""

from __future__ import annotations

import os
import re

import pytest

from qe.config import PROJECT_ROOT
from qe.gate import GATE_PROPERTY

GATE_ID = re.compile(r"[A-Z]{2,5}-\d{2}")


def pytest_configure(config: pytest.Config) -> None:
    browsers = PROJECT_ROOT / ".tools" / "ms-playwright"
    if browsers.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("gate")
        if marker is None:
            continue
        if len(marker.args) != 1 or not GATE_ID.fullmatch(str(marker.args[0])):
            raise pytest.UsageError(
                f"{item.nodeid}: @pytest.mark.gate needs exactly one matrix ID like 'API-01', got {marker.args!r}"
            )
        item.user_properties.append((GATE_PROPERTY, marker.args[0]))
