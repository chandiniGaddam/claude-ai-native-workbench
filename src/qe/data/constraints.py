"""Derive validation constraints and boundary values from Jakarta Bean Validation DTOs.

The boundary values used by API tests come straight from the AUT's Java source (read-only),
so a change to e.g. ``@Min(5)`` on ``credits`` surfaces as a contract-test failure instead
of a silently stale hard-coded number.

Supported annotations: @NotNull, @NotBlank, @Min, @Max, @Size, @Email. Each is read from
the annotations directly above a ``private <Type> <name>;`` field declaration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_ANNOTATION = re.compile(r"@(?P<name>NotNull|NotBlank|Min|Max|Size|Email)\s*(?:\((?P<args>[^)]*)\))?")
_FIELD = re.compile(r"private\s+[\w<>, ?]+\s+(?P<name>\w+)\s*;")
_KV = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|-?\d+)')


@dataclass
class FieldConstraints:
    name: str
    not_null: bool = False
    not_blank: bool = False
    email: bool = False
    min: int | None = None
    max: int | None = None
    size_min: int | None = None
    size_max: int | None = None
    messages: dict[str, str] = field(default_factory=dict)


def _parse_args(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return {}
    raw = raw.strip()
    if re.fullmatch(r"-?\d+", raw):  # positional form: @Min(5)
        return {"value": raw}
    return {k: v.strip('"') for k, v in _KV.findall(raw)}


def parse_bean_constraints(java_source: str) -> dict[str, FieldConstraints]:
    """Return constraints per field name, in declaration order."""
    result: dict[str, FieldConstraints] = {}
    pending: list[tuple[str, dict[str, str]]] = []
    for line in java_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("@"):
            for m in _ANNOTATION.finditer(stripped):
                pending.append((m.group("name"), _parse_args(m.group("args"))))
            continue
        fm = _FIELD.search(stripped)
        if fm:
            fc = FieldConstraints(name=fm.group("name"))
            for ann, args in pending:
                if "message" in args:
                    fc.messages[ann] = args["message"]
                if ann == "NotNull":
                    fc.not_null = True
                elif ann == "NotBlank":
                    fc.not_blank = True
                elif ann == "Email":
                    fc.email = True
                elif ann == "Min":
                    fc.min = int(args["value"])
                elif ann == "Max":
                    fc.max = int(args["value"])
                elif ann == "Size":
                    fc.size_min = int(args["min"]) if "min" in args else None
                    fc.size_max = int(args["max"]) if "max" in args else None
            result[fc.name] = fc
            pending = []
        elif stripped and not stripped.startswith(("//", "*", "/*")):
            pending = []  # annotations only bind to the next field
    return result


def parse_dto_file(path: Path) -> dict[str, FieldConstraints]:
    return parse_bean_constraints(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Boundaries:
    valid: tuple
    invalid: tuple


def numeric_boundaries(fc: FieldConstraints) -> Boundaries:
    """Edges of an inclusive @Min/@Max range: valid {min, max}, invalid {min-1, max+1}."""
    if fc.min is None or fc.max is None:
        raise ValueError(f"field {fc.name!r} has no complete @Min/@Max range")
    return Boundaries(valid=(fc.min, fc.max), invalid=(fc.min - 1, fc.max + 1))


def length_boundaries(fc: FieldConstraints, char: str = "x") -> Boundaries:
    """String lengths at the @Size edge; @NotBlank adds "" (and whitespace) as invalid."""
    if fc.size_max is None:
        raise ValueError(f"field {fc.name!r} has no @Size(max=...)")
    lo = max(fc.size_min or 0, 1 if fc.not_blank else 0)
    invalid = [char * (fc.size_max + 1)]
    if fc.not_blank:
        invalid = ["", "   "] + invalid
    elif fc.size_min:
        invalid = [char * (fc.size_min - 1)] + invalid
    return Boundaries(valid=(char * lo, char * fc.size_max), invalid=tuple(invalid))
