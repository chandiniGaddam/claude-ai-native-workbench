"""Fixtures for API tests. They need the AUT backend (scripts/reset_aut.sh).

Tests marked needs_backend are SKIPPED when the backend isn't reachable. A skip is never
counted by the gate, so an absent stack can't produce a false pass.
"""

from __future__ import annotations

import pytest

from qe.api.client import CatalogClient
from qe.config import Settings
from qe.data import ownership


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session")
def api(settings):
    client = CatalogClient(settings.api_url)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def _require_backend(request, api):
    if request.node.get_closest_marker("needs_backend") and not api.is_up():
        pytest.skip(f"backend not reachable at {api.base_url} (BLOCKED: start with scripts/reset_aut.sh)")


@pytest.fixture
def claim_record(request):
    """Claim a course/learner for this test; released (and state restore left to the caller)."""
    claimed: list[str] = []

    def _claim(record: str) -> None:
        ownership.claim(ownership.OWNERS, record, request.node.nodeid)
        claimed.append(record)

    yield _claim
    for r in claimed:
        ownership.release(ownership.OWNERS, r, request.node.nodeid)


@pytest.fixture
def restore_course(api, claim_record, request):
    """Snapshot a course before mutation and PUT the original fields back afterwards.

    Restores title/description/credits/capacity/instructorEmail only. It can't undo
    archive (no unarchive endpoint exists), so tests that archive must use a course
    reserved for archive tests.
    """
    from qe.api.client import course_update_body

    saved: list[tuple[str, dict, bool]] = []

    def _snapshot(code: str) -> dict:
        claim_record(code)
        resp = api.get_course(code)
        assert resp.status_code == 200, f"cannot snapshot {code}: {resp.status_code}"
        data = resp.json()
        saved.append((code, data, bool(data.get("active"))))
        return data

    yield _snapshot
    for code, data, was_active in reversed(saved):
        api.update_course(code, course_update_body(data))
        if was_active:
            api.reactivate_course(code)  # 409 COURSE_ALREADY_ACTIVE when already active is fine
        else:
            api.deactivate_course(code)
