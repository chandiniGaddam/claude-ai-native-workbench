---
id: seed-data-quirks
title: Seed data and its known quirks
evidence:
  - backend/src/main/resources/db/migration/V2__seed_courses.sql:2 | 'CS1007'
  - backend/src/main/resources/db/migration/V2__seed_courses.sql:9 | 'CS4999'
  - backend/src/main/resources/db/demo/V90__demo_data.sql:82 | They were archived in one bulk job
  - backend/src/main/resources/db/demo/V90__demo_data.sql:156 | CS2110 has a capacity of 30. Thirty-three learners hold an ACTIVE place.
  - backend/src/main/resources/db/demo/V90__demo_data.sql:177 | CANCELLED, not deleted
  - backend/src/main/resources/db/demo/V90__demo_data.sql:195 | There is no unique constraint on the
  - backend/src/main/resources/db/demo/V90__demo_data.sql:197 | Two ACTIVE rows each for L-00001 and L-00002 on CS1007.
  - backend/src/main/resources/db/migration/V3__add_capacity_to_course.sql:2 | DEFAULT 30
---
# Seed data and its known quirks

Flyway seeds the database from two locations: the schema migrations and a demo-data script
(`V90__demo_data.sql`). Course V2 seeds include CS1007, CS2110, CS3401, ENGG2104B,
MATH3220A, DATA1105, WEB2208 and CS4999 (a retired course, seeded as inactive).

Capacity defaults to 30 (migration V3).

Documented quirks in the demo script:

- CS2110 has capacity 30 but 33 learners hold an ACTIVE place, so it is over capacity.
- Some duplicate ACTIVE enrollments exist, for example two each for L-00001 and L-00002 on
  CS1007. The enrollments table has no unique constraint to prevent them.
- A bulk-archived batch of old courses exists, hence the identical archive reason. They are
  not returned by the course list endpoint.
- Withdrawn enrollments are kept with status CANCELLED, not deleted.

The script comments state the API shows nine courses; the exact count returned by a
running system is not verified in this document.
