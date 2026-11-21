"""Catalogue API: listing, filtering, lookup, validation and archive/inactive behaviour.

Expected values come from the AUT source (path:line relative to AUT_DIR) and from the seed
facts in qe.data.seed. Every test here is read-only except the PUT tests, which claim the
course they change and restore it in a finalizer (fixture ``restore_course``).
"""

from __future__ import annotations

import pytest

from qe.api.client import course_update_body
from qe.data import seed
from qe.data.constraints import length_boundaries, numeric_boundaries, parse_dto_file

DTO_DIR = "backend/src/main/java/com/globallearning/lms/catalog/web/dto"
UPDATE_DTO = "CourseUpdateRequest.java"


@pytest.fixture(scope="module")
def update_dto_constraints():
    from qe.config import Settings

    path = Settings.from_env().aut_dir / DTO_DIR / UPDATE_DTO
    if not path.is_file():
        pytest.skip(f"AUT source not available at {path} (BLOCKED)")
    return parse_dto_file(path)


def _codes(resp) -> list[str]:
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:200]}"
    return [c["code"] for c in resp.json()]


# --- listing and filters -------------------------------------------------------------------


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-01")
def test_list_returns_only_active_unarchived_courses(api):
    """CourseController.java:34-41 -> CourseService.java:listActive -> CourseRepository.java:17.

    Expected codes are the 8 rows with active=1 and archived_at NULL (qe.data.seed).
    CS4999 (inactive) and the 40 archived retired units must not appear.
    """
    codes = _codes(api.list_courses())
    assert codes == list(seed.ACTIVE_CATALOGUE)
    assert seed.INACTIVE_NOT_ARCHIVED not in codes
    assert seed.ARCHIVED_RETIRED not in codes


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-02")
def test_level_filter_returns_only_matching_level(api):
    """CourseController.java:36 binds ?level to CourseLevel; CourseRepository.java:19 filters it."""
    assert _codes(api.list_courses(level="ADVANCED")) == list(seed.BY_LEVEL["ADVANCED"])


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-03")
def test_level_filters_partition_the_default_list(api):
    """Boundary: the three levels are disjoint and together equal the unfiltered list."""
    by_level = {lvl: _codes(api.list_courses(level=lvl)) for lvl in seed.BY_LEVEL}
    assert by_level == {lvl: list(codes) for lvl, codes in seed.BY_LEVEL.items()}
    combined = [code for lvl in seed.BY_LEVEL for code in by_level[lvl]]
    assert len(combined) == len(set(combined))
    assert sorted(combined) == sorted(_codes(api.list_courses()))


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-04")
def test_keyword_search_is_case_insensitive_and_matches_title_or_code(api):
    """CourseRepository.java:29-39 LOWER(title)/LOWER(code) LIKE %keyword%.

    CourseService.java:listActive trims the keyword, and a blank one is ignored.
    """
    assert _codes(api.list_courses(q="LINEAR")) == ["MATH3220A"]  # title match
    assert _codes(api.list_courses(q="cs2110")) == ["CS2110"]  # code match, lower case
    assert _codes(api.list_courses(q="   ")) == list(seed.ACTIVE_CATALOGUE)  # blank = no filter


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-05")
def test_keyword_and_level_combine_with_and(api):
    """CourseRepository.java:41-52 adds 'AND level = :level' to the keyword query."""
    assert _codes(api.list_courses(q="data", level="FOUNDATION")) == ["DATA1105"]
    assert _codes(api.list_courses(q="data", level="ADVANCED")) == []


# --- lookup by code ------------------------------------------------------------------------


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-06")
def test_get_course_by_code_is_case_insensitive_and_returns_detail(api):
    """CourseController.java:44-47; CourseService.java:getByCode uses findByCodeIgnoreCase
    (CourseRepository.java:21). Response fields: CourseResponse.java (mapper: CourseMapper.java:22-35).
    """
    resp = api.get_course("cs2110")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "CS2110"
    assert body["title"] == "Object Oriented Design"
    assert body["level"] == "INTERMEDIATE"
    assert body["credits"] == 15
    assert body["capacity"] == seed.OVER_CAPACITY_LIMIT
    assert body["faculty"] == "CS"
    assert body["active"] is True
    assert body["archivedAt"] is None


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.gate("API-07")
def test_get_unknown_course_returns_404(api):
    """CatalogExceptionHandler.java:15-21 maps CourseNotFoundException to 404 COURSE_NOT_FOUND."""
    resp = api.get_course(seed.UNKNOWN_CODE)
    assert resp.status_code == 404
    assert resp.json() == {
        "error": "COURSE_NOT_FOUND",
        "message": f"No course found with code {seed.UNKNOWN_CODE}",
    }


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-08")
def test_inactive_course_is_hidden_from_list_but_returned_by_code(api):
    """Boundary: CS4999 has active=false and no archive date. The list filters on active,
    but CourseService.java:getByCode does not, so the detail endpoint still answers 200.
    """
    resp = api.get_course(seed.INACTIVE_NOT_ARCHIVED)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is False
    assert body["archivedAt"] is None
    assert seed.INACTIVE_NOT_ARCHIVED not in _codes(api.list_courses())


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-09")
def test_archived_course_detail_exposes_archive_metadata(api):
    """V6__add_course_archive.sql adds archived_at/archive_reason; V90 section 3 sets them for
    ENGG1100B. The detail response returns them (CourseResponse archivedAt/archiveReason).
    """
    resp = api.get_course(seed.ARCHIVED_RETIRED)
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == seed.ARCHIVED_RETIRED_TITLE
    assert body["active"] is False
    assert body["archivedAt"] is not None
    assert body["archiveReason"] == seed.ARCHIVED_RETIRED_REASON


# --- invalid input -------------------------------------------------------------------------


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.gate("API-10")
def test_unknown_level_value_is_rejected_with_400(api):
    """A level outside CourseLevel fails binding (MethodArgumentTypeMismatchException). No
    handler in CatalogExceptionHandler maps it, so Spring's default 400 'Bad Request' applies.
    Observed against the running stack (backend log: MethodArgumentTypeMismatchException).
    """
    resp = api.list_courses(level="EXPERT")
    assert resp.status_code == 400
    assert resp.json()["error"] == "Bad Request"


# --- update (PUT) boundaries and validation ------------------------------------------------


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-11")
def test_update_credits_boundaries_follow_the_dto_constraints(api, restore_course, update_dto_constraints):
    """CourseUpdateRequest.java:23-25: @NotNull, @Min(5), @Max(60) on credits.
    Boundaries are derived from the source, not hard-coded. Valid edges are accepted (200)
    and invalid edges are rejected (400, VALIDATION_FAILED). Mutates MATH3220A and restores it.
    """
    code = "MATH3220A"
    original = restore_course(code)
    credits = update_dto_constraints["credits"]
    edges = numeric_boundaries(credits)
    assert credits.messages["Min"] == "credits must be at least 5"
    assert credits.messages["Max"] == "credits must be 60 or fewer"

    for bad, message_key in ((edges.invalid[0], "Min"), (edges.invalid[1], "Max")):
        resp = api.update_course(code, course_update_body(original, credits=bad))
        assert resp.status_code == 400, f"credits={bad}: {resp.status_code}"
        assert resp.json() == {
            "error": "VALIDATION_FAILED",
            "fields": {"credits": credits.messages[message_key]},
        }

    for good in edges.valid:
        resp = api.update_course(code, course_update_body(original, credits=good))
        assert resp.status_code == 200, f"credits={good}: {resp.status_code} {resp.text[:200]}"
        assert resp.json()["credits"] == good


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-12")
def test_update_rejects_several_invalid_fields_at_once(api, update_dto_constraints):
    """All field errors come back together (CatalogExceptionHandler.java:23-32).

    Uses CS3401 and sends only invalid values, so nothing is written. Title and capacity
    bounds come from the DTO source.
    """
    title = length_boundaries(update_dto_constraints["title"])
    capacity = numeric_boundaries(update_dto_constraints["capacity"])
    resp = api.update_course(
        "CS3401",
        {
            "title": title.invalid[0],  # "" -> @NotBlank
            "description": None,
            "credits": 20,
            "capacity": capacity.invalid[0],  # 0 -> @Min(1)
            "instructorEmail": "not-an-email",  # -> @Email
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "VALIDATION_FAILED"
    assert body["fields"] == {
        "title": update_dto_constraints["title"].messages["NotBlank"],
        "capacity": update_dto_constraints["capacity"].messages["Min"],
        "instructorEmail": "must be a valid email",
    }
    assert api.get_course("CS3401").json()["title"] == "Distributed Systems"


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-13")
def test_update_archived_course_is_refused_and_unchanged(api):
    """CourseService.java:49-51 throws CourseArchivedException; CatalogExceptionHandler.java:50-56
    maps it to 409 COURSE_ARCHIVED. The write happens after the check, so nothing changes.
    """
    before = api.get_course(seed.ARCHIVED_RETIRED).json()
    resp = api.update_course(
        seed.ARCHIVED_RETIRED,
        course_update_body(before, title="Edited while archived"),
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "COURSE_ARCHIVED"
    assert api.get_course(seed.ARCHIVED_RETIRED).json()["title"] == seed.ARCHIVED_RETIRED_TITLE


# --- characterization and known defects (never counted toward the gate) -------------------


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.characterization
@pytest.mark.xfail(
    strict=True,
    reason="DEFECT (CONFIRMED): GET /api/learners/{ref}/enrollments answers 500 "
    "LazyInitializationException for any learner with enrolments. Enrollment.java:24-29 uses "
    "LAZY associations, LearnerController.java:137-143 has no transaction, and "
    "application.yml:19 sets open-in-view=false, so EnrollmentMapper.java:11 cannot load the course.",
)
def test_learner_enrollment_list_returns_rows_for_enrolled_learner(api):
    """Expected behaviour: 200 with four ACTIVE rows (qe.data.seed.LEARNER_WITH_ENROLMENTS)."""
    resp = api.learner_enrollments(seed.LEARNER_WITH_ENROLMENTS)
    assert resp.status_code == 200
    rows = resp.json()
    assert sorted(r["courseCode"] for r in rows) == sorted(seed.LEARNER_WITH_ENROLMENTS_CODES)
    assert {r["status"] for r in rows} == {"ACTIVE"}
