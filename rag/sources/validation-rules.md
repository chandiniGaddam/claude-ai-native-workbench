---
id: validation-rules
title: Request validation rules
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:16 | @NotBlank(message = "title is required")
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:17 | @Size(max = 200
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:20 | @Size(max = 2000
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:24 | @Min(value = 5
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:25 | @Max(value = 60
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:29 | @Min(value = 1
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:30 | @Max(value = 500
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:33 | @Email(message = "must be a valid email")
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/CourseUpdateRequest.java:34 | @Size(max = 120
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/ArchiveRequest.java:8 | @NotBlank(message = "reason is required")
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/ArchiveRequest.java:9 | @Size(max = 500
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/EnrollmentCreateRequest.java:4 | private String courseCode;
  - backend/src/main/java/com/globallearning/lms/catalog/web/dto/EnrollmentCreateRequest.java:5 | private String learnerRef;
---
# Request validation rules

**Course update (PUT)**

| Field | Rule |
|---|---|
| title | required, not blank, at most 200 characters |
| description | optional, at most 2000 characters |
| credits | required, 5 to 60 inclusive |
| capacity | required, 1 to 500 inclusive |
| instructorEmail | optional, must be a valid email, at most 120 characters |

**Archive**: `reason` is required, not blank, at most 500 characters.

**Enrollment create**: the request has two plain string fields, `courseCode` and
`learnerRef`, with no validation annotations. An empty or missing body therefore reaches
the service with null values instead of being rejected by validation.

Validation failures on the annotated requests are reported by the error handler
(see the error-responses document).
