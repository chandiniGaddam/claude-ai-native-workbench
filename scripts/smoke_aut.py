#!/usr/bin/env python3
"""P2 smoke verification of the running AUT stack (local only, read-only except one probe).

What it does:
- Records ACTUAL facts from the database (via the read-only mcp_readonly user), the API and
  the UI.
- Checks that the three layers agree with each other: the API catalogue equals the DB rows
  where active=1 AND archived_at IS NULL, the UI renders as many cards as the API returns,
  and the same holds per level filter.
- Phase-2 estimates (derived by reading the seed SQL) are shown next to actual values for
  comparison only. They are never used as pass/fail criteria.
- Probes POST /api/enrollments with {} and records status, body, the enrollment count
  before and after, and the backend logs for that window.
- Scans the container logs for known credentials.

Writes reports/p2/smoke.json and screenshots in reports/p2/.
Run with: .venv/bin/python scripts/smoke_aut.py   (needs Docker access)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from qe.config import Settings

OUT = PROJECT / "reports" / "p2"
LEVELS = ["FOUNDATION", "INTERMEDIATE", "ADVANCED"]
LABELS = {"FOUNDATION": "Foundation", "INTERMEDIATE": "Intermediate", "ADVANCED": "Advanced"}
# Synthetic starter credentials (db-setup/01-create-users.sql). Read-only user.
DB_USER, DB_PASS = "mcp_readonly", "mcp_readonly_pw"
ESTIMATES = {  # from the Phase 2 plan; for comparison only
    "course_rows": 49, "api_catalogue_size": 8, "learner_rows": 60,
    "L-00005_enrollments": 4, "CS2110_active_vs_capacity": "33/30",
}

checks: list[dict] = []


def check(name: str, ok: bool, detail) -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def compose(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=PROJECT, capture_output=True, text=True,
                          check=False, timeout=120, **kw)


def sql(query: str) -> list[list[str]]:
    proc = compose("exec", "-T", "-e", f"MYSQL_PWD={DB_PASS}", "mysql",
                   "mysql", f"-u{DB_USER}", "-N", "-B", "lms_catalog", "-e", query)
    if proc.returncode != 0:
        raise RuntimeError(f"SQL failed: {proc.stderr.strip()}")
    return [line.split("\t") for line in proc.stdout.strip().splitlines() if line]


def database_facts() -> dict:
    one = lambda q: sql(q)[0][0]
    facts = {
        "flyway": [dict(zip(["version", "description", "success"], r))
                   for r in sql("SELECT version, description, success FROM flyway_schema_history ORDER BY installed_rank")],
        "course_rows": int(one("SELECT COUNT(*) FROM course")),
        "course_active": int(one("SELECT COUNT(*) FROM course WHERE active = 1")),
        "course_archived": int(one("SELECT COUNT(*) FROM course WHERE archived_at IS NOT NULL")),
        "course_active_not_archived": int(one("SELECT COUNT(*) FROM course WHERE active = 1 AND archived_at IS NULL")),
        "active_not_archived_codes": [r[0] for r in sql(
            "SELECT code FROM course WHERE active = 1 AND archived_at IS NULL ORDER BY code")],
        "inactive_not_archived_codes": [r[0] for r in sql(
            "SELECT code FROM course WHERE active = 0 AND archived_at IS NULL ORDER BY code")],
        "by_level_active_not_archived": {r[0]: int(r[1]) for r in sql(
            "SELECT level, COUNT(*) FROM course WHERE active = 1 AND archived_at IS NULL GROUP BY level")},
        "learner_rows": int(one("SELECT COUNT(*) FROM learner")),
        "enrollment_rows": int(one("SELECT COUNT(*) FROM enrollment")),
        "enrollment_by_status": {r[0]: int(r[1]) for r in sql("SELECT status, COUNT(*) FROM enrollment GROUP BY status")},
        "active_enrollments_vs_capacity": [
            {"code": r[0], "active": int(r[1]), "capacity": int(r[2])} for r in sql(
                "SELECT c.code, COUNT(e.id), c.capacity FROM course c JOIN enrollment e ON e.course_id = c.id "
                "AND e.status = 'ACTIVE' GROUP BY c.code, c.capacity ORDER BY c.code")],
        "duplicate_active_pairs": [
            {"code": r[0], "learner": r[1], "rows": int(r[2])} for r in sql(
                "SELECT c.code, l.learner_ref, COUNT(*) FROM enrollment e JOIN course c ON c.id = e.course_id "
                "JOIN learner l ON l.id = e.learner_id WHERE e.status = 'ACTIVE' "
                "GROUP BY c.code, l.learner_ref HAVING COUNT(*) > 1 ORDER BY c.code, l.learner_ref")],
        "L-00005_enrollments": int(one(
            "SELECT COUNT(*) FROM enrollment e JOIN learner l ON l.id = e.learner_id WHERE l.learner_ref = 'L-00005'")),
    }
    return facts


def api_facts(client: httpx.Client) -> dict:
    r = client.get("/api/courses")
    facts = {"list_status": r.status_code, "list": r.json() if r.status_code == 200 else r.text}
    facts["by_level"] = {}
    for level in LEVELS:
        rr = client.get("/api/courses", params={"level": level})
        facts["by_level"][level] = {"status": rr.status_code, "codes": [c["code"] for c in rr.json()]}
    d = client.get("/api/courses/CS3401")
    facts["detail_CS3401"] = {"status": d.status_code, "body": d.json()}
    return facts


def ui_facts(ui_url: str) -> dict:
    facts: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        resp = page.goto(ui_url, wait_until="networkidle")
        facts["http_status"] = resp.status if resp else None
        facts["title"] = page.title()
        facts["h1"] = page.locator("h1").inner_text()
        page.locator("li.course-card").first.wait_for(timeout=15000)
        facts["cards"] = page.locator("li.course-card .course-card__code").all_inner_texts()
        page.screenshot(path=str(OUT / "catalogue.png"), full_page=True)
        facts["filtered"] = {}
        for level in LEVELS:
            with page.expect_response(lambda r, lv=level: "/api/courses" in r.url and f"level={lv}" in r.url) as info:
                page.get_by_role("button", name=LABELS[level], exact=True).click()
            page.wait_for_function(
                "n => document.querySelectorAll('li.course-card').length === n",
                arg=len(info.value.json()), timeout=10000)
            facts["filtered"][level] = {
                "request_url": info.value.url.replace(ui_url, ""),
                "cards": page.locator("li.course-card .course-card__code").all_inner_texts(),
                "chip_on": page.locator("button.chip--on").inner_text(),
            }
            if level == "ADVANCED":
                page.screenshot(path=str(OUT / "catalogue-advanced.png"), full_page=True)
        browser.close()
    return facts


def probe_empty_enrollment(client: httpx.Client) -> dict:
    before = int(sql("SELECT COUNT(*) FROM enrollment")[0][0])
    since = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    time.sleep(1)
    r = client.post("/api/enrollments", json={})
    time.sleep(2)
    after = int(sql("SELECT COUNT(*) FROM enrollment")[0][0])
    logs = compose("logs", "backend", "--no-log-prefix", "--since", since).stdout.strip().splitlines()
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return {"request": {"method": "POST", "path": "/api/enrollments", "json": {}},
            "status": r.status_code, "content_type": r.headers.get("content-type"), "body": body,
            "enrollment_rows_before": before, "enrollment_rows_after": after, "backend_log_lines": logs}


def secret_scan() -> dict:
    secrets = {"lms_app_pw": "lms_app_pw", "mcp_readonly_pw": DB_PASS}
    env_file = PROJECT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.startswith("MYSQL_ROOT_PASSWORD="):
                secrets["MYSQL_ROOT_PASSWORD (.env)"] = line.split("=", 1)[1]
    logs = compose("logs", "--no-color").stdout
    hits = {name: logs.count(value) for name, value in secrets.items()}
    hits["'generated security password' lines"] = logs.lower().count("generated security password")
    return hits


def listening_ports() -> list[str]:
    out = subprocess.run(["ss", "-ltnH"], capture_output=True, text=True, check=False).stdout
    return sorted({line.split()[3] for line in out.splitlines() if line.split()[3].rsplit(":", 1)[-1] in {"3306", "8080", "5173"}})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    s = Settings.from_env()
    report: dict = {"generated_at": datetime.now(UTC).isoformat(), "api_url": s.api_url,
                    "ui_url": s.ui_url, "estimates_for_comparison_only": ESTIMATES}

    print("== containers")
    ps = [json.loads(line) for line in compose("ps", "--format", "json").stdout.splitlines() if line.strip()]
    report["containers"] = [{k: c.get(k) for k in ("Service", "Image", "State", "Health", "Publishers")} for c in ps]
    for c in ps:
        check(f"container {c['Service']} healthy", c.get("Health") == "healthy", f"{c['State']}/{c.get('Health')}")

    print("== database (read-only user)")
    db = report["database"] = database_facts()
    check("flyway migrations all successful", all(m["success"] == "1" for m in db["flyway"]),
          [m["version"] for m in db["flyway"]])
    print(f"  facts: courses={db['course_rows']} active={db['course_active']} archived={db['course_archived']} "
          f"active&!archived={db['course_active_not_archived']} learners={db['learner_rows']} "
          f"enrollments={db['enrollment_rows']} {db['enrollment_by_status']}")

    print("== API")
    with httpx.Client(base_url=s.api_url, timeout=10) as client:
        api = report["api"] = api_facts(client)
        api_codes = [c["code"] for c in api["list"]]
        check("GET /api/courses returns 200", api["list_status"] == 200, api["list_status"])
        check("API catalogue == DB active & not archived (same codes, same order)",
              api_codes == db["active_not_archived_codes"], api_codes)
        for level in LEVELS:
            got = api["by_level"][level]
            check(f"API level={level} matches DB count and level",
                  got["status"] == 200 and len(got["codes"]) == db["by_level_active_not_archived"].get(level, 0),
                  got["codes"])
        check("GET /api/courses/CS3401 returns 200", api["detail_CS3401"]["status"] == 200,
              {k: api["detail_CS3401"]["body"].get(k) for k in ("code", "level", "credits", "capacity", "active")})

        print("== UI (Chromium, headless)")
        ui = report["ui"] = ui_facts(s.ui_url)
        check("frontend page loads (HTTP 200)", ui["http_status"] == 200, f"{ui['http_status']} title={ui['title']!r}")
        check("heading is 'Course catalogue'", ui["h1"] == "Course catalogue", ui["h1"])
        check("UI cards == API catalogue", ui["cards"] == api_codes, ui["cards"])
        for level in LEVELS:
            f = ui["filtered"][level]
            check(f"UI filter {LABELS[level]} == API level={level}",
                  f["cards"] == api["by_level"][level]["codes"] and f["chip_on"] == LABELS[level],
                  f"{f['cards']} via {f['request_url']}")

        print("== probe: POST /api/enrollments {}")
        probe = report["probe_empty_enrollment"] = probe_empty_enrollment(client)
        print(f"  status={probe['status']} body={json.dumps(probe['body'])[:200]}")
        print(f"  enrollment rows before/after: {probe['enrollment_rows_before']}/{probe['enrollment_rows_after']}")
        check("probe did not create rows", probe["enrollment_rows_before"] == probe["enrollment_rows_after"],
              f"{probe['enrollment_rows_before']} -> {probe['enrollment_rows_after']}")

    print("== security")
    report["secret_scan_hits"] = hits = secret_scan()
    check("no known credentials in container logs", not any(hits.values()), hits)
    report["listening_ports"] = ports = listening_ports()
    check("published ports bound to 127.0.0.1 only", ports and all(p.startswith("127.0.0.1:") for p in ports), ports)

    report["checks"] = checks
    report["ok"] = all(c["ok"] for c in checks)
    (OUT / "smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nsmoke: {'PASS' if report['ok'] else 'FAIL'} ({sum(c['ok'] for c in checks)}/{len(checks)} checks) "
          f"-> {OUT / 'smoke.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    os.chdir(PROJECT)
    sys.exit(main())
