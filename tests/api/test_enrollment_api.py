"""Enrolment API: create, duplicate, seat limit, course and learner errors, learner list.

Mutation policy: the only write is the successful enrolment test. The AUT has no endpoint to
cancel or delete an enrolment, so the state it creates lasts until scripts/reset_aut.sh. That
test claims its learner and course in qe.data.ownership.OWNERS, and it runs against a fresh
database only (needs_seed). Every other test here is non-mutating: it asserts an error response,
and the AUT writes nothing before raising.
"""

from __future__ import annotations

import pytest

from qe.data import seed


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-14")
def test_enrol_after_cancellation_then_duplicate_is_refused(api, claim_record):
    """EnrollmentController.java:27-31 returns 201 with EnrollmentResponse fields.

    Verified path: EnrollmentService.java:33-34 rejects a duplicate only when an ACTIVE row
    exists, so the seeded CANCELLED row for L-00020 on DATA1105 does not block a new ACTIVE
    one. The second identical request then gets 409 DUPLICATE_ENROLLMENT
    (EnrollmentExceptionHandler.java:16-21). Mutates DATA1105 seats and L-00020's rows.
    """
    claim_record(seed.CANCELLED_COURSE)
    claim_record(seed.CANCELLED_LEARNER)
    body = {"courseCode": seed.CANCELLED_COURSE, "learnerRef": seed.CANCELLED_LEARNER}

    first = api.enroll(seed.CANCELLED_COURSE, seed.CANCELLED_LEARNER)
    assert first.status_code == 201, first.text
    assert first.json() == {**body, "status": "ACTIVE"}

    second = api.enroll(seed.CANCELLED_COURSE, seed.CANCELLED_LEARNER)
    assert second.status_code == 409
    assert second.json() == {"error": "DUPLICATE_ENROLLMENT"}


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-15")
def test_enrol_with_unknown_course_or_learner_returns_404(api):
    """EnrollmentService.java:25-30 looks up the course first (CourseService.getByCode ->
    CatalogExceptionHandler.java:15-21), then the learner (LearnerService.java:19-20 ->
    EnrollmentExceptionHandler.java:37-42). Non-mutating: both errors are raised before the save.
    """
    unknown_course = api.enroll(seed.UNKNOWN_CODE, seed.LEARNER_WITHOUT_ENROLMENTS)
    assert unknown_course.status_code == 404
    assert unknown_course.json()["error"] == "COURSE_NOT_FOUND"

    unknown_learner = api.enroll("WEB2208", seed.UNKNOWN_LEARNER)
    assert unknown_learner.status_code == 404
    assert unknown_learner.json() == {
        "error": "LEARNER_NOT_FOUND",
        "message": f"No learner found with ref {seed.UNKNOWN_LEARNER}",
    }


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-16")
def test_enrol_in_inactive_course_returns_409_course_not_open(api):
    """Boundary: EnrollmentService.java:27-28 refuses courses with active=false, even though
    CS4999 is not archived. Mapped by EnrollmentExceptionHandler.java:30-35. Non-mutating.
    """
    resp = api.enroll(seed.INACTIVE_NOT_ARCHIVED, seed.LEARNER_WITHOUT_ENROLMENTS)
    assert resp.status_code == 409
    assert resp.json() == {"error": "COURSE_NOT_OPEN"}


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-17")
def test_enrol_when_active_seats_reach_capacity_returns_409(api):
    """Regression on over-capacity seed data. EnrollmentService.java:37-39 compares ACTIVE
    rows with the capacity limit. CS2110 holds 33 ACTIVE rows against a limit of 30
    (V90 section 5), so the new enrolment is refused with SEAT_UNAVAILABLE. Non-mutating.
    """
    resp = api.enroll(seed.OVER_CAPACITY_COURSE, seed.LEARNER_WITHOUT_ENROLMENTS)
    assert resp.status_code == 409
    assert resp.json() == {"error": "SEAT_UNAVAILABLE"}


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("API-18")
def test_learner_without_enrolments_has_empty_list(api):
    """Boundary: LearnerController.java:29-34 returns [] when a learner has no rows."""
    resp = api.learner_enrollments(seed.LEARNER_WITHOUT_ENROLMENTS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.gate("API-19")
def test_learner_lookup_for_unknown_ref_returns_404(api):
    """LearnerService.java:19-20 throws LearnerNotFoundException. The list endpoint calls that
    lookup first, so the 404 comes before any enrolment is read (EnrollmentExceptionHandler.java:37-42).
    """
    resp = api.learner_enrollments(seed.UNKNOWN_LEARNER)
    assert resp.status_code == 404
    assert resp.json() == {
        "error": "LEARNER_NOT_FOUND",
        "message": f"No learner found with ref {seed.UNKNOWN_LEARNER}",
    }
