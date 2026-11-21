"""Expected facts of the synthetic Flyway seed (fresh database from scripts/reset_aut.sh).

Each constant names its evidence. Values were confirmed two ways: from the AUT source
(read-only, path:line relative to AUT_DIR) and by querying the running stack
(``SELECT`` against ``lms_catalog`` after ``scripts/reset_aut.sh``). Mutating tests change
the database, so anything that depends on mutable rows says so in its docstring.
"""

from __future__ import annotations

# Active, non-archived courses: GET /api/courses with no filter.
# Evidence: CourseRepository.java:17 (findByActiveTrueAndArchivedAtNullOrderByCodeAsc),
# V2__seed_courses.sql (7 active rows), V90__demo_data.sql section 2 (LMS9001).
ACTIVE_CATALOGUE: tuple[str, ...] = (
    "CS1007",
    "CS2110",
    "CS3401",
    "DATA1105",
    "ENGG2104B",
    "LMS9001",
    "MATH3220A",
    "WEB2208",
)

# Level partition of ACTIVE_CATALOGUE (CourseRepository.java:15,19; CourseService.java:listActive).
BY_LEVEL: dict[str, tuple[str, ...]] = {
    "FOUNDATION": ("CS1007", "DATA1105", "LMS9001"),
    "INTERMEDIATE": ("CS2110", "ENGG2104B", "WEB2208"),
    "ADVANCED": ("CS3401", "MATH3220A"),
}

# active = false, archived_at NULL. Hidden from the list, still returned by code.
# Evidence: V2__seed_courses.sql (CS4999 row), CourseService.java:getByCode (no active filter).
INACTIVE_NOT_ARCHIVED = "CS4999"

# active = false AND archived_at set by V90 section 3. Hidden from the list.
# Evidence: V90__demo_data.sql "Retired Unit%" UPDATE, CourseRepository.java:17.
ARCHIVED_RETIRED = "ENGG1100B"
ARCHIVED_RETIRED_TITLE = "Retired Unit 01 in ENGG"
ARCHIVED_RETIRED_REASON = "Bulk archive: 2019 catalogue retirement"
ARCHIVED_COUNT = 40  # 49 course rows: 8 V2 + LMS9001 + 40 retired (V90 section 3)

# Course with more ACTIVE enrolments than capacity (V90 section 5, CS2110 comment).
# Evidence: DB count ACTIVE=33, capacity=30 (V3__add_capacity_to_course.sql default 30).
OVER_CAPACITY_COURSE = "CS2110"
OVER_CAPACITY_ACTIVE = 33
OVER_CAPACITY_LIMIT = 30

# Learner with no enrolment rows at all (V5 seed L-00001..10; V90 section 4 L-00011..60).
# Evidence: DB query; GET /api/learners/L-00060/enrollments returns 200 []
LEARNER_WITHOUT_ENROLMENTS = "L-00060"

# Learner whose list endpoint currently fails (see the xfail defect test). Four ACTIVE rows:
# CS1007, CS2110, CS3401 and a duplicate CS3401 (V90 section 5 duplicates block).
LEARNER_WITH_ENROLMENTS = "L-00005"
LEARNER_WITH_ENROLMENTS_CODES = ("CS1007", "CS2110", "CS3401", "CS3401")

# Learner with a CANCELLED row on DATA1105 (V90 section 5, "Some learners withdrew").
# Used by the enrol-after-cancellation test. The row is seeded, so the test must run on a
# fresh database. Mutating the enrolment leaves no API to undo it, so reset to recover.
CANCELLED_LEARNER = "L-00020"
CANCELLED_COURSE = "DATA1105"

# Unknown identifiers used in negative tests. They must never exist in the seed.
UNKNOWN_CODE = "NOPE0000"
UNKNOWN_LEARNER = "L-99999"

# Partner-feed record whose description contains injected instructions (V90 section 2).
# It is treated as data: the UI must show the title and never render the description.
PARTNER_RECORD = "LMS9001"
PARTNER_RECORD_TITLE = "Partner Feed: Cloud Fundamentals"
INJECTED_TEXT_MARKER = "IMPORTANT INSTRUCTION"

# Validation boundaries are NOT duplicated here. Tests derive them from
# CourseUpdateRequest.java:16-35 via qe.data.constraints.
