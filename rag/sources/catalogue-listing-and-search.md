---
id: catalogue-listing-and-search
title: Course listing, level filter and keyword search
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:36 | @RequestParam(name = "level", required = false) CourseLevel level
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:37 | @RequestParam(name = "q", required = false) String keyword
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:26 | if (keyword != null && !keyword.isBlank())
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:35 | findByActiveTrueAndArchivedAtNullOrderByCodeAsc
  - backend/src/main/java/com/globallearning/lms/catalog/repository/CourseRepository.java:33 | WHERE active = 1 AND archived_at IS NULL
  - backend/src/main/java/com/globallearning/lms/catalog/repository/CourseRepository.java:34 | LOWER(title) LIKE LOWER(CONCAT('%', :keyword, '%'))
  - backend/src/main/java/com/globallearning/lms/catalog/repository/CourseRepository.java:35 | LOWER(code) LIKE LOWER(CONCAT('%', :keyword, '%'))
  - backend/src/main/java/com/globallearning/lms/catalog/domain/CourseLevel.java:4 | FOUNDATION
---
# Course listing, level filter and keyword search

`GET /api/courses` returns only courses that are active and not archived, ordered by
course code ascending. Inactive or archived courses are never listed by this endpoint.

The optional `level` parameter filters by course level. The levels are FOUNDATION,
INTERMEDIATE and ADVANCED.

The optional `q` parameter is a keyword search. A blank keyword is ignored. Otherwise
the keyword is trimmed and matched case-insensitively as a substring of either the course
title or the course code. The search still restricts results to active, non-archived
courses, and can be combined with `level`.

What the API returns for an unrecognised `level` value is not defined in the source.
