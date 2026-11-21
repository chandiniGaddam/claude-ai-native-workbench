---
id: course-lifecycle
title: Updating, deactivating, reactivating and archiving courses
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:50 | if (course.getArchivedAt() != null)
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:51 | throw new CourseArchivedException(code)
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:65 | throw new CourseAlreadyArchivedException(code)
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:67 | course.setArchivedAt(Instant.now())
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:74 | TODO(platform-team)
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:79 | course.setActive(false)
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:86 | if (course.isActive())
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:87 | throw new CourseAlreadyActiveException(code)
---
# Updating, deactivating, reactivating and archiving courses

- **Update** replaces title, description, credits, capacity and instructor email. An
  archived course can't be updated (COURSE_ARCHIVED).
- **Archive** records the archive time and the supplied reason. Archiving a course that
  is already archived fails with COURSE_ALREADY_ARCHIVED. No endpoint or service method
  un-archives a course.
- **Deactivate** sets the course inactive. The service performs no checks: it doesn't
  refuse deactivation for already-inactive, archived or enrolled courses. A TODO comment
  says that, once an enrolment service exists, the catalogue should refuse to deactivate a
  course with open enrolments, which means that rule is not implemented.
- **Reactivate** sets the course active. If it is already active the call fails with
  COURSE_ALREADY_ACTIVE. Reactivation doesn't check whether the course is archived.

All course lookups by code are case-insensitive.
