---
id: error-responses
title: Error codes and HTTP statuses
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:18 | COURSE_NOT_FOUND
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:20 | HttpStatus.NOT_FOUND
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:26 | VALIDATION_FAILED
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:31 | ResponseEntity.badRequest()
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:37 | COURSE_ALREADY_ARCHIVED
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:45 | COURSE_ALREADY_ACTIVE
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:53 | COURSE_ARCHIVED
  - backend/src/main/java/com/globallearning/lms/catalog/web/CatalogExceptionHandler.java:55 | HttpStatus.CONFLICT
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentExceptionHandler.java:19 | DUPLICATE_ENROLLMENT
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentExceptionHandler.java:26 | SEAT_UNAVAILABLE
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentExceptionHandler.java:33 | COURSE_NOT_OPEN
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentExceptionHandler.java:40 | LEARNER_NOT_FOUND
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentExceptionHandler.java:42 | status(404)
---
# Error codes and HTTP statuses

Errors are JSON objects with an `error` code.

| Error code | HTTP status | Extra fields |
|---|---|---|
| COURSE_NOT_FOUND | 404 | message |
| LEARNER_NOT_FOUND | 404 | message |
| VALIDATION_FAILED | 400 | `fields` map of field name to message |
| COURSE_ALREADY_ARCHIVED | 409 | message |
| COURSE_ALREADY_ACTIVE | 409 | message |
| COURSE_ARCHIVED | 409 | message |
| DUPLICATE_ENROLLMENT | 409 | none |
| SEAT_UNAVAILABLE | 409 | none |
| COURSE_NOT_OPEN | 409 | none |

The source has no handlers for other exception types, so the behaviour for requests such
as an unsupported HTTP method or a malformed JSON body is not defined in the source.
