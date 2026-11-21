"""Bean Validation parsing and boundary values.

The last group reads the real AUT DTOs (read-only). They're contract tests: if the Java
constraints change, these fail and the API boundary tests must be revisited.
"""

import pytest

from qe.config import Settings
from qe.data.constraints import (
    length_boundaries,
    numeric_boundaries,
    parse_bean_constraints,
    parse_dto_file,
)

pytestmark = pytest.mark.unit

SNIPPET = """
public class Sample {
    @NotNull(message = "qty is required")
    @Min(value = 1, message = "qty must be at least 1")
    @Max(10)
    private Integer qty;

    @NotBlank
    @Size(min = 2, max = 5, message = "code must be 2-5, inclusive")
    private String code;

    @Email(message = "bad email") @Size(max = 120)
    private String email;

    @NotNull
    public String notAField() { return null; }

    private String plain;
}
"""


def test_parses_named_and_positional_annotation_arguments():
    c = parse_bean_constraints(SNIPPET)
    assert (c["qty"].min, c["qty"].max, c["qty"].not_null) == (1, 10, True)
    assert c["qty"].messages == {"NotNull": "qty is required", "Min": "qty must be at least 1"}


def test_parses_size_bounds_and_messages_containing_commas():
    code = parse_bean_constraints(SNIPPET)["code"]
    assert (code.size_min, code.size_max, code.not_blank) == (2, 5, True)
    assert code.messages["Size"] == "code must be 2-5, inclusive"


def test_multiple_annotations_on_one_line():
    email = parse_bean_constraints(SNIPPET)["email"]
    assert email.email and email.size_max == 120


def test_annotations_do_not_leak_past_a_method_to_the_next_field():
    plain = parse_bean_constraints(SNIPPET)["plain"]
    assert not (plain.not_null or plain.not_blank or plain.email)
    assert plain.min is plain.max is plain.size_max is None


def test_numeric_boundaries_are_inclusive_edges():
    b = numeric_boundaries(parse_bean_constraints(SNIPPET)["qty"])
    assert b.valid == (1, 10) and b.invalid == (0, 11)


def test_length_boundaries_respect_size_min_and_not_blank():
    b = length_boundaries(parse_bean_constraints(SNIPPET)["code"])
    assert [len(v) for v in b.valid] == [2, 5]
    assert b.invalid == ("", "   ", "xxxxxx")


def test_boundaries_require_complete_constraints():
    plain = parse_bean_constraints(SNIPPET)["plain"]
    with pytest.raises(ValueError):
        numeric_boundaries(plain)
    with pytest.raises(ValueError):
        length_boundaries(plain)


# --- contract tests against the real AUT source (read-only) ---------------------------

DTO_DIR = "backend/src/main/java/com/globallearning/lms/catalog/web/dto"


@pytest.fixture(scope="module")
def dto_dir():
    path = Settings.from_env().aut_dir / DTO_DIR
    if not path.is_dir():
        pytest.skip(f"AUT source not available at {path}")
    return path


def test_course_update_request_constraints_match_source(dto_dir):
    c = parse_dto_file(dto_dir / "CourseUpdateRequest.java")
    assert list(c) == ["title", "description", "credits", "capacity", "instructorEmail"]
    assert (c["credits"].min, c["credits"].max, c["credits"].not_null) == (5, 60, True)
    assert (c["capacity"].min, c["capacity"].max, c["capacity"].not_null) == (1, 500, True)
    assert (c["title"].not_blank, c["title"].size_max) == (True, 200)
    assert c["description"].size_max == 2000 and not c["description"].not_blank
    assert (c["instructorEmail"].email, c["instructorEmail"].size_max) == (True, 120)
    assert c["credits"].messages == {
        "NotNull": "credits is required",
        "Min": "credits must be at least 5",
        "Max": "credits must be 60 or fewer",
    }
    assert c["instructorEmail"].messages["Email"] == "must be a valid email"


def test_course_update_boundaries_derived_from_source(dto_dir):
    c = parse_dto_file(dto_dir / "CourseUpdateRequest.java")
    assert numeric_boundaries(c["credits"]).invalid == (4, 61)
    assert numeric_boundaries(c["capacity"]).invalid == (0, 501)
    title = length_boundaries(c["title"])
    assert [len(v) for v in title.valid] == [1, 200]
    assert [len(v) for v in title.invalid] == [0, 3, 201]


def test_archive_request_constraints_match_source(dto_dir):
    reason = parse_dto_file(dto_dir / "ArchiveRequest.java")["reason"]
    assert (reason.not_blank, reason.size_max) == (True, 500)
    assert reason.messages == {
        "NotBlank": "reason is required",
        "Size": "reason must be at most 500 characters",
    }


def test_enrollment_create_request_has_no_validation(dto_dir):
    """Documents Phase 1 finding: POST /api/enrollments bodies are not validated."""
    c = parse_dto_file(dto_dir / "EnrollmentCreateRequest.java")
    assert set(c) == {"courseCode", "learnerRef"}
    for fc in c.values():
        assert not (fc.not_null or fc.not_blank or fc.email), fc
        assert fc.size_max is None and fc.min is None
