import json

import httpx
import pytest

from qe.api.client import CatalogClient, course_update_body
from qe.config import UnsafeTargetError
from qe.data import ownership

pytestmark = pytest.mark.unit


def make(handler):
    return CatalogClient("http://localhost:8080", transport=httpx.MockTransport(handler))


def test_rejects_remote_target():
    with pytest.raises(UnsafeTargetError):
        CatalogClient("https://example.com")


def test_list_courses_sends_only_given_params():
    seen = []
    c = make(lambda r: seen.append(r.url) or httpx.Response(200, json=[]))
    c.list_courses(level="ADVANCED")
    c.list_courses(q="data")
    c.list_courses()
    assert [str(u.query, "ascii") for u in seen] == ["level=ADVANCED", "q=data", ""]


def test_enroll_posts_expected_json():
    seen = []
    c = make(lambda r: seen.append(r) or httpx.Response(201, json={}))
    c.enroll("CS1007", "L-00001")
    assert seen[0].method == "POST" and seen[0].url.path == "/api/enrollments"
    assert json.loads(seen[0].content) == {"courseCode": "CS1007", "learnerRef": "L-00001"}


def test_enroll_with_none_serialises_null():
    seen = []
    c = make(lambda r: seen.append(r) or httpx.Response(404, json={}))
    c.enroll(None, None)
    assert json.loads(seen[0].content) == {"courseCode": None, "learnerRef": None}


@pytest.mark.parametrize(
    "call,method,path",
    [
        (lambda c: c.get_course("CS1007"), "GET", "/api/courses/CS1007"),
        (lambda c: c.update_course("CS1007", {}), "PUT", "/api/courses/CS1007"),
        (lambda c: c.deactivate_course("CS1007"), "POST", "/api/courses/CS1007/deactivate"),
        (lambda c: c.reactivate_course("CS1007"), "POST", "/api/courses/CS1007/reactivate"),
        (lambda c: c.archive_course("CS1007", "r"), "POST", "/api/courses/CS1007/archive"),
        (lambda c: c.learner_enrollments("L-00001"), "GET", "/api/learners/L-00001/enrollments"),
    ],
)
def test_routes_match_controllers(call, method, path):
    seen = []
    c = make(lambda r: seen.append(r) or httpx.Response(200, json={}))
    call(c)
    assert (seen[0].method, seen[0].url.path) == (method, path)


def test_archive_body():
    seen = []
    c = make(lambda r: seen.append(r) or httpx.Response(200, json={}))
    c.archive_course("X", "because")
    assert json.loads(seen[0].content) == {"reason": "because"}


def test_is_up_true_on_any_status_false_on_connect_error():
    assert make(lambda r: httpx.Response(500)).is_up() is True

    def boom(request):
        raise httpx.ConnectError("refused")

    assert make(boom).is_up() is False


def test_course_update_body_uses_only_accepted_fields_and_overrides():
    course = {"code": "A", "title": "T", "description": "D", "credits": 10, "capacity": 5,
              "instructorEmail": None, "active": True, "id": 1}
    body = course_update_body(course, credits=60)
    assert set(body) == {"title", "description", "credits", "capacity", "instructorEmail"}
    assert body["credits"] == 60 and body["title"] == "T"


def test_ownership_claim_conflict_and_release():
    reg: dict[str, str] = {}
    ownership.claim(reg, "CS1007", "t1")
    ownership.claim(reg, "CS1007", "t1")  # idempotent for the owner
    with pytest.raises(ownership.OwnershipError):
        ownership.claim(reg, "CS1007", "t2")
    ownership.release(reg, "CS1007", "t2")  # non-owner release is a no-op
    assert reg == {"CS1007": "t1"}
    ownership.release(reg, "CS1007", "t1")
    assert reg == {}
