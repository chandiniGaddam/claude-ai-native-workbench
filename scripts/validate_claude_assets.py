#!/usr/bin/env python3
"""Validate .claude/skills/*/SKILL.md and .claude/agents/*.md.

Checks front matter, naming, and that every subagent is restricted (an explicit ``tools``
allowlist, none of the mutating or delegating tools). Exit 0 when valid, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
KNOWN_TOOLS = {"Read", "Grep", "Glob", "Write", "Edit", "MultiEdit", "Bash", "WebFetch", "WebSearch", "Agent"}
FORBIDDEN_FOR_AGENTS = {"Bash", "Write", "Edit", "MultiEdit", "Agent", "WebFetch", "WebSearch"}


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        raise ValueError("missing --- front matter ---")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            raise ValueError(f"bad front matter line: {line!r}")
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def _tools(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def validate_skill(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{path}: {exc}"]
    if meta.get("name") != path.parent.name:
        errs.append(f"{path}: name {meta.get('name')!r} must equal directory {path.parent.name!r}")
    if not NAME.match(meta.get("name", "")):
        errs.append(f"{path}: invalid name")
    if len(meta.get("description", "")) < 40:
        errs.append(f"{path}: description missing or too short")
    for t in _tools(meta.get("allowed-tools", "")):
        if t not in KNOWN_TOOLS:
            errs.append(f"{path}: unknown tool {t!r}")
    if "Bash" in _tools(meta.get("allowed-tools", "")):
        errs.append(f"{path}: skills must not allow Bash")
    if len(body.strip()) < 100:
        errs.append(f"{path}: body too short")
    return errs


def validate_agent(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{path}: {exc}"]
    if meta.get("name") != path.stem:
        errs.append(f"{path}: name {meta.get('name')!r} must equal file stem {path.stem!r}")
    if len(meta.get("description", "")) < 40:
        errs.append(f"{path}: description missing or too short")
    if "tools" not in meta:
        errs.append(f"{path}: restricted agents need an explicit tools allowlist")
    tools = _tools(meta.get("tools", ""))
    for t in tools:
        if t not in KNOWN_TOOLS:
            errs.append(f"{path}: unknown tool {t!r}")
        if t in FORBIDDEN_FOR_AGENTS:
            errs.append(f"{path}: tool {t!r} is not allowed for a restricted agent")
    if not tools:
        errs.append(f"{path}: empty tools list")
    if len(body.strip()) < 100:
        errs.append(f"{path}: body too short")
    return errs


def validate_all(root: Path = ROOT) -> tuple[int, int, list[str]]:
    skills = sorted((root / ".claude" / "skills").glob("*/SKILL.md"))
    agents = sorted((root / ".claude" / "agents").glob("*.md"))
    errs: list[str] = []
    for s in skills:
        errs += validate_skill(s)
    for a in agents:
        errs += validate_agent(a)
    return len(skills), len(agents), errs


def main() -> int:
    n_skills, n_agents, errs = validate_all()
    for e in errs:
        print("ERROR", e)
    print(f"skills={n_skills} agents={n_agents} errors={len(errs)}")
    return 1 if errs or n_skills != 3 or n_agents != 3 else 0


if __name__ == "__main__":
    sys.exit(main())
