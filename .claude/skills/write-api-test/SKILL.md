---
name: write-api-test
description: Write a pytest + httpx API test for the course catalogue backend using the qe.api client and the ownership registry. Use when adding a test under tests/api/.
allowed-tools: Read, Grep, Glob, Write, Edit
---

# Write an API test

Only for files under `tests/api/` and `src/qe/` in this workbench. Never write into the AUT.

## Rules

1. Use `qe.api.client.CatalogClient` (fixture `api`). Don't build raw URLs or call hosts directly.
   Targets are loopback only (`qe.config`).
2. Mark the test `@pytest.mark.api` plus `@pytest.mark.needs_backend`. Add
   `@pytest.mark.needs_seed` if it depends on seed rows.
3. A deterministic test that counts toward the gate carries `@pytest.mark.gate("API-NN")`
   with a unique matrix ID. Characterization tests never carry `gate`.
4. Expected values must come from AUT source (use the `cite-aut-evidence` skill) or from
   `qe.data.constraints`. Put the `path:line` in the test docstring. If behaviour is
   undefined, observe it first and mark the test `characterization`.
5. A test that mutates a course or learner must claim it in `qe.data.ownership.OWNERS`
   (one owning test per record) and restore state in a finalizer (fixture `restore_course`).
6. No login, payment or placeholder tests. No pytest-xdist.
7. Never state a test passed unless you ran it. If the stack is down, report BLOCKED.

## Template

```python
@pytest.mark.api
@pytest.mark.needs_backend
@pytest.mark.gate("API-01")
def test_get_unknown_course_returns_404(api):
    """CatalogExceptionHandler.java:18-20 maps CourseNotFoundException to 404 COURSE_NOT_FOUND."""
    resp = api.get_course("NOPE0000")
    assert resp.status_code == 404
    assert resp.json()["error"] == "COURSE_NOT_FOUND"
```
