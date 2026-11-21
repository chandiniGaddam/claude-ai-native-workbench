"""Load synthetic knowledge documents (rag/sources/*.md) and verify their evidence.

Front matter is a small YAML subset: ``id``, ``title`` and an ``evidence`` list whose items
are ``<path>:<line> | <quote>``. ``<path>`` is relative to AUT_DIR and ``<quote>`` must
occur on that line of that file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from qe.config import PROJECT_ROOT

SOURCES_DIR = PROJECT_ROOT / "rag" / "sources"
_EVIDENCE = re.compile(r"^(?P<path>[^|]+?):(?P<line>\d+)\s*\|\s*(?P<quote>.+)$")


@dataclass(frozen=True)
class Evidence:
    path: str
    line: int
    quote: str


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    body: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)


def parse_document(text: str, origin: str = "<string>") -> Document:
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        raise ValueError(f"{origin}: missing front matter")
    meta: dict[str, str] = {}
    evidence: list[Evidence] = []
    in_evidence = False
    for raw in m.group(1).splitlines():
        if raw.startswith("evidence:"):
            in_evidence = True
            continue
        if in_evidence and raw.lstrip().startswith("- "):
            em = _EVIDENCE.match(raw.lstrip()[2:].strip())
            if not em:
                raise ValueError(f"{origin}: bad evidence entry {raw!r}")
            evidence.append(Evidence(em["path"].strip(), int(em["line"]), em["quote"].strip()))
            continue
        in_evidence = False
        if ":" in raw:
            k, v = raw.split(":", 1)
            meta[k.strip()] = v.strip()
    for key in ("id", "title"):
        if not meta.get(key):
            raise ValueError(f"{origin}: missing {key}")
    if not evidence:
        raise ValueError(f"{origin}: a document needs at least one evidence entry")
    return Document(meta["id"], meta["title"], m.group(2).strip(), tuple(evidence))


def load_documents(directory: Path = SOURCES_DIR) -> list[Document]:
    docs = [parse_document(p.read_text(encoding="utf-8"), str(p)) for p in sorted(directory.glob("*.md"))]
    ids = [d.id for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate document ids")
    return docs


def verify_evidence(doc: Document, aut_dir: Path) -> list[str]:
    """Return problems: missing file, line out of range, or quote not on that line."""
    problems: list[str] = []
    for ev in doc.evidence:
        f = aut_dir / ev.path
        if not f.is_file():
            problems.append(f"{doc.id}: {ev.path} not found")
            continue
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        if not 1 <= ev.line <= len(lines):
            problems.append(f"{doc.id}: {ev.path}:{ev.line} out of range ({len(lines)} lines)")
        elif ev.quote not in lines[ev.line - 1]:
            problems.append(f"{doc.id}: {ev.path}:{ev.line} does not contain {ev.quote!r}")
    return problems
