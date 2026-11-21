---
id: enrollment-rules
title: Enrollment business rules and their order
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:26 | courseService.getByCode(courseCode)
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:27 | if (!course.isActive())
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:30 | learnerService.getByRef(learnerRef)
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:33 | findByCourseAndLearnerAndStatus(course, learner, EnrollmentStatus.ACTIVE)
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:37 | countByCourseAndStatus(course, EnrollmentStatus.ACTIVE)
  - backend/src/main/java/com/globallearning/lms/catalog/service/EnrollmentService.java:38 | activeSeats >= course.getCapacity()
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentController.java:31 | ResponseEntity.status(201)
---
# Enrollment business rules and their order

`POST /api/enrollments` takes a course code and a learner reference. The service applies
these checks in this order:

1. The course must exist (lookup by code, ignoring case). Otherwise COURSE_NOT_FOUND.
2. The course must be active. Otherwise COURSE_NOT_OPEN.
3. The learner must exist. Otherwise LEARNER_NOT_FOUND.
4. The learner must not already hold an ACTIVE enrollment in that course. Otherwise
   DUPLICATE_ENROLLMENT.
5. The number of ACTIVE enrollments must be below the course capacity. When it is
   greater than or equal to the capacity the result is SEAT_UNAVAILABLE.

On success a new ACTIVE enrollment is saved and the controller responds with HTTP 201.
Only ACTIVE enrollments count toward capacity and duplicate detection.

Because the course is looked up before the learner, a request with both an unknown
course and an unknown learner reports the course as not found.
