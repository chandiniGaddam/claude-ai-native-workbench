"""httpx client for the course catalogue backend.

Endpoints are the ones declared in the AUT controllers (read-only source):
  CourseController.java:34,44,49,58,63,68  EnrollmentController.java:27  LearnerController.java:29
The client returns raw ``httpx.Response`` objects so tests assert on status codes and bodies
themselves; it never retries and never hides errors.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from qe.config import allowed_hosts, validate_local_url

DEFAULT_TIMEOUT = 10.0


class CatalogClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        hosts: frozenset[str] | None = None,
    ) -> None:
        self.base_url = validate_local_url(base_url, hosts or allowed_hosts())
        self._http = httpx.Client(base_url=self.base_url, transport=transport, timeout=timeout)

    # -- lifecycle -----------------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def is_up(self) -> bool:
        """True if GET /api/courses answers at all (any HTTP status). False on connect errors."""
        try:
            self._http.get("/api/courses")
        except httpx.TransportError:
            return False
        return True

    # -- courses -------------------------------------------------------------------
    def list_courses(self, level: str | None = None, q: str | None = None) -> httpx.Response:
        params = {k: v for k, v in (("level", level), ("q", q)) if v is not None}
        return self._http.get("/api/courses", params=params)

    def get_course(self, code: str) -> httpx.Response:
        return self._http.get(f"/api/courses/{code}")

    def update_course(self, code: str, body: dict[str, Any]) -> httpx.Response:
        return self._http.put(f"/api/courses/{code}", json=body)

    def deactivate_course(self, code: str) -> httpx.Response:
        return self._http.post(f"/api/courses/{code}/deactivate")

    def reactivate_course(self, code: str) -> httpx.Response:
        return self._http.post(f"/api/courses/{code}/reactivate")

    def archive_course(self, code: str, reason: str) -> httpx.Response:
        return self._http.post(f"/api/courses/{code}/archive", json={"reason": reason})

    # -- enrollments / learners ----------------------------------------------------
    def enroll(self, course_code: str | None, learner_ref: str | None) -> httpx.Response:
        return self._http.post(
            "/api/enrollments", json={"courseCode": course_code, "learnerRef": learner_ref}
        )

    def enroll_raw(self, body: dict[str, Any]) -> httpx.Response:
        return self._http.post("/api/enrollments", json=body)

    def learner_enrollments(self, learner_ref: str) -> httpx.Response:
        return self._http.get(f"/api/learners/{learner_ref}/enrollments")

    def raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Escape hatch for negative tests (bad paths, odd content types)."""
        return self._http.request(method, path, **kwargs)


def course_update_body(course: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """A valid PUT body built from a GET /api/courses/{code} response, with overrides applied.

    Uses only the fields CourseUpdateRequest.java:16-35 accepts.
    """
    body = {
        "title": course.get("title"),
        "description": course.get("description"),
        "credits": course.get("credits"),
        "capacity": course.get("capacity"),
        "instructorEmail": course.get("instructorEmail"),
    }
    body.update(overrides)
    return body
