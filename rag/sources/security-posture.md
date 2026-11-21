---
id: security-posture
title: Security configuration
evidence:
  - backend/src/main/java/com/globallearning/lms/catalog/config/SecurityConfig.java:20 | csrf.disable()
  - backend/src/main/java/com/globallearning/lms/catalog/config/SecurityConfig.java:22 | .requestMatchers("/api/courses/**").permitAll()
  - backend/src/main/java/com/globallearning/lms/catalog/config/SecurityConfig.java:23 | .anyRequest().permitAll()
  - backend/src/main/java/com/globallearning/lms/catalog/audit/CatalogAuditLogger.java:27 | action=COURSE_ARCHIVED
  - backend/src/main/java/com/globallearning/lms/catalog/service/CourseService.java:70 | auditLogger.recordCourseArchived("anonymous"
---
# Security configuration

Spring Security is configured to disable CSRF protection and to permit every request,
including the mutating endpoints (update, deactivate, reactivate, archive and enroll).
No authentication or role checks exist, so any caller can change or archive any course.

Audit log entries record the actor as the fixed string "anonymous"; archiving and
reactivating a course are logged, while update and deactivate are not.

There is no login feature and no payment feature in the catalogue source.
