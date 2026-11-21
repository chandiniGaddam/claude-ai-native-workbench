---
id: frontend-catalogue-page
title: Frontend catalogue page
evidence:
  - frontend/src/App.jsx:39 | <h1>Course catalogue</h1>
  - frontend/src/App.jsx:16 | fetchCourses({ level })
  - frontend/src/api/catalog.js:1 | const BASE_URL = '/api/courses'
  - frontend/src/components/LevelFilter.jsx:5 | aria-label="Filter by level"
  - frontend/src/components/LevelFilter.jsx:11 | All levels
  - frontend/src/components/CourseList.jsx:5 | Loading the catalogue
  - frontend/src/components/CourseList.jsx:9 | Check that the API is running on port 8080.
  - frontend/src/components/CourseList.jsx:13 | No courses match this filter.
  - frontend/src/components/CourseCard.jsx:11 | course.credits} credits
  - frontend/src/constants.js:4 | FOUNDATION: "Foundation"
  - frontend/vite.config.js:11 | target: 'http://localhost:8080'
---
# Frontend catalogue page

The frontend is a single page titled "Course catalogue", built with React and Vite. It has
no routing and no login or payment screens.

A group of buttons labelled "Filter by level" offers "All levels", "Foundation",
"Intermediate" and "Advanced". Choosing a level reloads the list from `/api/courses` with
that level as a query parameter. The page itself has no keyword search box, although the
API client function accepts a keyword.

Each course is shown as a card with its code, a level label, its title and its credits.
The card always prints "<n> credits", even for a single credit.

The page has three non-list states: a loading message, an error message that mentions the
API on port 8080, and an empty-state message "No courses match this filter."

The Vite dev server proxies `/api` requests to `http://localhost:8080`.
