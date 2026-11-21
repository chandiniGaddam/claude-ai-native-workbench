"""Deterministic-test quality gate computed from a pytest JUnit XML report.

Gate tests are marked ``@pytest.mark.gate("API-01")``. The qe pytest plugin records the
ID as a JUnit property ``gate_id``, which requires ``junit_family = xunit1``.

Rules:
- A gate ID counts only if every test case carrying it passed. Parametrized expansions
  collapse to one ID, and skipped or xfailed cases never count.
- Any failure or error anywhere in the report fails the gate.
- At least ``min_passed`` distinct gate IDs must pass (default 8).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

GATE_PROPERTY = "gate_id"


@dataclass
class GateResult:
    passed_ids: set[str] = field(default_factory=set)
    failed_ids: set[str] = field(default_factory=set)
    skipped_ids: set[str] = field(default_factory=set)
    total_cases: int = 0
    failures: list[str] = field(default_factory=list)
    min_passed: int = 8

    @property
    def ok(self) -> bool:
        return not self.failures and len(self.passed_ids) >= self.min_passed

    def summary(self) -> str:
        lines = [
            f"gate: {'PASS' if self.ok else 'FAIL'}",
            f"  distinct gate IDs passed: {len(self.passed_ids)} (required >= {self.min_passed})",
            f"  passed IDs: {', '.join(sorted(self.passed_ids)) or '-'}",
        ]
        if self.skipped_ids:
            lines.append(f"  skipped (not counted): {', '.join(sorted(self.skipped_ids))}")
        if self.failures:
            lines.append(f"  failing test cases ({len(self.failures)}):")
            lines += [f"    - {f}" for f in self.failures]
        return "\n".join(lines)


def _status(case: ET.Element) -> str:
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def evaluate_junit(xml_text: str, min_passed: int = 8) -> GateResult:
    root = ET.fromstring(xml_text)
    result = GateResult(min_passed=min_passed)
    per_id: dict[str, list[str]] = {}
    for case in root.iter("testcase"):
        result.total_cases += 1
        status = _status(case)
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        if status == "failed":
            result.failures.append(name)
        gate_id = None
        for prop in case.iter("property"):
            if prop.get("name") == GATE_PROPERTY:
                gate_id = prop.get("value")
        if gate_id:
            per_id.setdefault(gate_id, []).append(status)
    for gate_id, statuses in per_id.items():
        if "failed" in statuses:
            result.failed_ids.add(gate_id)
        elif all(s == "passed" for s in statuses):
            result.passed_ids.add(gate_id)
        else:
            result.skipped_ids.add(gate_id)
    return result


def evaluate_junit_file(path: Path, min_passed: int = 8) -> GateResult:
    return evaluate_junit(Path(path).read_text(encoding="utf-8"), min_passed=min_passed)
