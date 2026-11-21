# Claude AI-Native Quality Engineering Workbench

A Python QA automation framework for the **course catalogue application** in the
[`git-demo`](https://github.com/sharmaanku/git-demo) starter repository. It is built with
pytest, Playwright (Chromium), httpx, a BM25 RAG pipeline evaluated with Ragas, Claude
Skills, restricted subagents, an MCP integration and GitHub Actions.

> **Status: Phase P2 (AUT running in Docker, smoke-verified).** The framework core and its unit tests are in place.
> API, UI and security suites, the RAG pipeline, MCP verification and CI follow in later
> phases (see [Roadmap](#roadmap)).

## Application Under Test

| | |
|---|---|
| Source (local, **read-only**) | `../git-demo/starter_code` (`AUT_DIR`) |
| Source (CI) | pinned `D4 - Starter Code.zip` from public repo `sharmaanku/git-demo` at commit `3e3eb67`, SHA-256 verified in CI. Its source is byte-identical to the local copy |
| Backend | Spring Boot 3.5.4, Java 21, MySQL 8.4, Flyway seed. REST on `:8080` (`/api/courses`, `/api/enrollments`, `/api/learners`) |
| Frontend | React 18 + Vite 5, catalogue page with a level filter, on `:5173` |

The starter repository is never modified. The AUT is built and run only from copies
(Docker build contexts), and a Claude Code hook blocks writes to it (see [Safety](#safety)).

### Unavailable functionality

| Feature | Status | Evidence |
|---|---|---|
| Login | **Not implemented** | `payment-login-java-project.zip` → `LoginService.login()` throws `UnsupportedOperationException("Login functionality is not implemented yet.")`. The catalogue frontend has no login UI, although its README says it does. |
| Payment | **Not found** | No payment classes, endpoints or UI exist in either project. |

There are no tests for these features, placeholder or otherwise.

## Setup

Everything is project-local: uv, Python and the browsers live in `.tools/` (git-ignored).

| Tool | Version |
|---|---|
| Python (uv-managed) | 3.12.16 |
| uv | 0.13.9 |
| Docker / Compose | 29.1.3 / 2.40.3 |
| Chromium (Playwright build 1255) | 159.0.8154.6 |

```bash
cd /home/labuser/Downloads/claude-ai-native-workbench
export UV_CACHE_DIR=$PWD/.tools/uv-cache UV_PYTHON_INSTALL_DIR=$PWD/.tools/python
export PLAYWRIGHT_BROWSERS_PATH=$PWD/.tools/ms-playwright

.tools/bin/uv venv --python 3.12 .venv
.tools/bin/uv pip sync --python .venv/bin/python requirements.lock
.venv/bin/playwright install chromium
```

Dependency files:

- `requirements.txt` lists the direct test and framework dependencies, pinned exactly.
- `requirements.lock` is the full transitive lock (52 packages), generated with
  `uv pip compile requirements.txt --python 3.12 -o requirements.lock`.
- `requirements-eval.txt` holds Ragas and the Claude judge adapter. Install them into a
  separate `.venv-eval` only when you need to run an evaluation. **Evaluations make paid
  Claude API calls and need approval first.**

## Running the AUT (Docker Compose)

```bash
scripts/reset_aut.sh          # fresh copy, fresh DB, build, start, wait until healthy
.venv/bin/python scripts/smoke_aut.py   # smoke verification -> reports/p2/smoke.json
scripts/reset_aut.sh --down   # stop and delete the data volume
```

These need Docker access (membership of the `docker` group).

- `scripts/snapshot_aut.py` copies the starter source (77 files, without `node_modules/`,
  `target/` or logs) into `.aut/starter_code/` and verifies every file by SHA-256. Compose
  builds **only** from that copy.
- `mysql` (8.4) initialises a fresh volume with the copied `db-setup/01-create-users.sql`,
  mounted read-only. The backend's Flyway then applies V1–V6 and V90 (demo data).
- `backend` is built with Maven on Temurin 21 and runs as a non-root user.
  `SPRING_DATASOURCE_URL` points it at the `mysql` service, and one logger is silenced so the
  Spring-generated default password is never logged. Both are runtime overrides;
  `application.yml` is unchanged.
- `frontend` runs `npm ci`, then `vite` (dev server). It shares the backend's network
  namespace so the unchanged `vite.config.js` proxy (`localhost:8080`) works.
- Ports are bound to **127.0.0.1 only**: 3306 (MySQL), 8080 (API), 5173 (UI).
- `.env` (git-ignored, mode 600) holds a random MySQL root password. It's generated on
  first reset and never printed.

### Verified seed facts (P2, actual database counts)

| Fact | Actual |
|---|---|
| Flyway migrations | 1, 2, 3, 4, 5, 6, 90, all successful |
| `course` rows | 49 (8 active and not archived; 40 archived; `CS4999` inactive, not archived) |
| `GET /api/courses` | 8: CS1007, CS2110, CS3401, DATA1105, ENGG2104B, LMS9001, MATH3220A, WEB2208 (the V90 comment's "nine" is wrong) |
| By level | FOUNDATION 3, INTERMEDIATE 3, ADVANCED 2 |
| `learner` rows | 60 |
| `enrollment` rows | 79 (71 ACTIVE, 8 CANCELLED) |
| ACTIVE vs capacity | CS1007 14/30, **CS2110 33/30**, CS3401 9/30, WEB2208 15/30 |
| Duplicate ACTIVE pairs | CS1007/L-00001 ×2, CS1007/L-00002 ×2, CS3401/L-00005 ×2 |
| `POST /api/enrollments {}` | **404** `{"error":"COURSE_NOT_FOUND","message":"No course found with code null"}`. No row created, nothing logged |

## Post-P2 components (built while Docker access was unavailable)

Docker needed `sudo`, so P2 was postponed and these were built and tested **without the AUT running**.
Nothing below has been executed against the live backend or frontend.

| Component | Where | Verified by |
|---|---|---|
| 3 Claude Skills | `.claude/skills/{cite-aut-evidence,write-api-test,author-rag-case}` | `scripts/validate_claude_assets.py` (structure only) |
| 3 restricted subagents (read-only tools) | `.claude/agents/{aut-source-reader,test-reviewer,rag-auditor}.md` | same validator |
| API client + fixtures | `src/qe/api/client.py`, `src/qe/data/ownership.py`, `tests/api/conftest.py` | unit tests with `httpx.MockTransport` |
| Playwright architecture | `src/qe/pages/catalogue_page.py`, `tests/ui/conftest.py` | selector contract tests against AUT JSX; page-object logic in Chromium on a DOM stub |
| Synthetic knowledge docs (10) | `rag/sources/*.md` | every `path:line | quote` checked against the AUT source |
| RAG pipeline | `src/qe/rag/` (BM25 retrieval, extractive + Claude generators) | unit tests; Claude path tested only with a fake client |
| Ragas eval dataset (15 cases) | `rag/eval/dataset.jsonl`, `thresholds.json` | schema validation, offline retrieval metrics |

No API tests exist yet and no Ragas run was made (paid; needs approval).

## Running tests

```bash
.venv/bin/python -m pytest -m unit      # framework unit tests, no AUT needed
.venv/bin/ruff check src scripts tests
python3 scripts/check_gate.py reports/junit.xml   # deterministic-test gate
```

Every run writes `reports/junit.xml` and `reports/html/report.html`. UI runs also write
screenshots and traces to `reports/playwright/` when a test fails.

### What the unit tests cover

| Module | What is verified |
|---|---|
| `qe.guard` + `scripts/guard_readonly.py` | Writes into the starter repo are blocked: file tools, `..` traversal, symlinks, redirects, `rm`/`mv`/`sed -i`/`cp` destinations, mutating `git`, build tools. Read-only commands are allowed. The hook exits 2 and fails closed. |
| `qe.config` | Targets must be loopback hosts. Remote hosts, `localhost.example.com`, `localhost@host` userinfo tricks and non-HTTP schemes are rejected. Compose service names need explicit opt-in. |
| `qe.data.constraints` | Bean Validation annotations are parsed from Java DTOs, and boundary values are derived from them. Contract tests against the real AUT DTOs: credits 5–60, capacity 1–500, title ≤ 200, archive reason ≤ 500, and `EnrollmentCreateRequest` has no validation. |
| `qe.gate` + `qe.pytest_plugin` | Only distinct, fully passed `@pytest.mark.gate("ID")` tests count. Skipped and xfail tests count as zero, and any failure fails the gate. Checked end to end with a real inner pytest run. |

## Quality gate

`scripts/check_gate.py` passes only when **at least 8 distinct matrix IDs** marked
`@pytest.mark.gate(...)` passed **and** there are no failures or errors anywhere in the
report. Skipped, xfailed, unit and characterization tests never count.

## Safety

- **Read-only AUT.** `.claude/settings.json` denies `Edit(//home/labuser/Downloads/git-demo/**)`,
  which also covers Write and NotebookEdit. A `PreToolUse` hook
  (`scripts/guard_readonly.py`) checks every Edit/Write/MultiEdit/NotebookEdit/Bash call and
  blocks writes into the starter repo with exit code 2. It isn't a sandbox: it can't see
  writes made from inside an arbitrary program.
- **Local targets only.** `qe.config` refuses any non-loopback URL.
- **No pushes.** `git push` and `git remote add` are denied in Claude Code. The repository
  has no remote.
- **No paid API calls** without explicit approval. No secrets in the repo (`.env` is
  git-ignored and unreadable to Claude).
- **No payment data** of any kind. Test data is the synthetic Flyway seed.

## Layout

```
src/qe/            framework package (config, guard, gate, pytest plugin, data, api, pages, rag)
tests/unit/        framework unit tests
tests/{api,ui,security}/   AUT suites (later phases)
scripts/           guard_readonly.py (hook), check_gate.py (gate CLI)
rag/{knowledge,eval}/      RAG index and evaluation dataset (later phases)
.claude/           settings.json (deny rules + hook); skills/ and agents/ (later phases)
.github/workflows/ CI (later phase; local only until a remote is provided)
reports/           generated output (git-ignored)
```

## Roadmap

| Phase | Scope | State |
|---|---|---|
| P0 | Docker, uv, Python 3.12, images | ✅ done |
| P1 | Project setup, guard, gate, unit tests | ✅ done |
| P2 | Start the AUT with Docker Compose (from copies), confirm the seed-derived expectations | ✅ done |
| P3 | API + security suites | next |
| P4 | Playwright UI suite (full-stack + route-mocked), screenshots | |
| P5 | MCP verification (read-only MySQL MCP server) | |
| P6 | RAG pipeline (BM25 + Claude) and evaluation dataset | |
| P7 | Ragas evaluation run (**paid, needs approval**) | |
| P8 | Claude Skills and restricted subagents | |
| P9 | GitHub Actions workflow (local; push after a remote is provided) | |
| P10 | Final documentation and evidence report | |
