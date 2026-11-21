---
id: api-endpoints
title: Catalogue REST endpoints
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:23 | @RequestMapping("/api/courses")
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:34 | @GetMapping
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:44 | @GetMapping("/{code}")
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:49 | @PutMapping("/{code}")
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:58 | @PostMapping("/{code}/deactivate")
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:63 | @PostMapping("/{code}/reactivate")
  - backend/src/main/java/com/globallearning/lms/catalog/web/CourseController.java:68 | @PostMapping("/{code}/archive")
  - backend/src/main/java/com/globallearning/lms/catalog/web/EnrollmentController.java:27 | @PostMapping
  - backend/src/main/java/com/globallearning/lms/catalog/web/LearnerController.java:29 | @GetMapping("/{learnerRef}/enrollments")
---
# Catalogue REST endpoints

The backend exposes three controllers. All paths are under `/api`.

- `GET /api/courses` lists courses. Optional query parameters are `level` and `q`.
- `GET /api/courses/{code}` returns one course by code.
- `PUT /api/courses/{code}` updates a course.
- `POST /api/courses/{code}/deactivate` deactivates a course.
- `POST /api/courses/{code}/reactivate` reactivates a course.
- `POST /api/courses/{code}/archive` archives a course; the body carries a `reason`.
- `POST /api/enrollments` creates an enrollment and returns 201 on success.
- `GET /api/learners/{learnerRef}/enrollments` lists a learner's enrollments.

The source defines no DELETE endpoint, no login endpoint and no payment endpoint.
