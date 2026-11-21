"""UI test fixtures (Playwright, Chromium). Two modes, kept separate:

* full-stack: ``needs_frontend`` + ``needs_backend``; talks to the real Vite dev server.
  Skipped (never passed) when the stack is down.
* route-mocked: ``page.route('**/api/courses*', ...)`` against the real frontend. It still
  needs the frontend (``needs_frontend``) but not the backend.

Screenshots go to reports/ (pytest.ini: --screenshot=only-on-failure; ``save_screenshot``
below is for explicit evidence shots).
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from qe.config import PROJECT_ROOT, Settings
from qe.pages.catalogue_page import CataloguePage

REPORTS = PROJECT_ROOT / "reports"


def _reachable(url: str) -> bool:
    try:
        httpx.get(url, timeout=3)
    except httpx.TransportError:
        return False
    return True


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(autouse=True)
def _require_stack(request, settings):
    if request.node.get_closest_marker("needs_frontend") and not _reachable(settings.ui_url):
        pytest.skip(f"frontend not reachable at {settings.ui_url} (BLOCKED: scripts/reset_aut.sh)")
    if request.node.get_closest_marker("needs_backend") and not _reachable(settings.api_url + "/api/courses"):
        pytest.skip(f"backend not reachable at {settings.api_url} (BLOCKED: scripts/reset_aut.sh)")


@pytest.fixture
def catalogue(page, settings) -> CataloguePage:
    return CataloguePage(page, settings.ui_url)


@pytest.fixture
def save_screenshot(page, request):
    def _save(label: str) -> Path:
        out = REPORTS / "screenshots"
        out.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in request.node.name)
        path = out / f"{safe}__{label}.png"
        page.screenshot(path=str(path), full_page=True)
        return path

    return _save
