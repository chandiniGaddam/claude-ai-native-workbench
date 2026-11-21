"""Evaluation dataset I/O, offline retrieval metrics, and Ragas sample export.

Nothing here calls any API. ``to_ragas_rows`` only builds the data a Ragas run would need;
running Ragas uses the paid Claude judge and needs the user's approval (scripts/run_ragas.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from qe.config import PROJECT_ROOT
from qe.rag.pipeline import RagAnswer, RagPipeline
from qe.rag.retriever import Retriever

DATASET_PATH = PROJECT_ROOT / "rag" / "eval" / "dataset.jsonl"
CATEGORIES = {"factual", "multi_doc", "unanswerable", "adversarial"}
REQUIRED = ("id", "category", "question", "reference", "reference_doc_ids")


def load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_dataset(cases: list[dict], known_doc_ids: set[str]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id", "<no id>")
        for key in REQUIRED:
            if key not in c:
                problems.append(f"{cid}: missing {key}")
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("category") not in CATEGORIES:
            problems.append(f"{cid}: bad category {c.get('category')!r}")
        ids = c.get("reference_doc_ids", [])
        for d in ids:
            if d not in known_doc_ids:
                problems.append(f"{cid}: unknown doc id {d!r}")
        if c.get("category") == "unanswerable" and ids:
            problems.append(f"{cid}: unanswerable cases must have no reference_doc_ids")
        if c.get("category") != "unanswerable" and not ids:
            problems.append(f"{cid}: answerable cases need reference_doc_ids")
        if not str(c.get("question", "")).strip() or not str(c.get("reference", "")).strip():
            problems.append(f"{cid}: empty question or reference")
    return problems


@dataclass(frozen=True)
class RetrievalReport:
    answerable: int
    hit_at_k: float  # share of cases where >=1 reference doc is in the retrieved docs
    full_recall_at_k: float  # share where ALL reference docs are retrieved
    mrr: float  # mean reciprocal rank of the first reference doc
    misses: list[str]  # case ids with no reference doc retrieved


def retrieval_report(cases: list[dict], retriever: Retriever, k: int = 4) -> RetrievalReport:
    ans = [c for c in cases if c["reference_doc_ids"]]
    hit = full = 0
    rr = 0.0
    misses: list[str] = []
    for c in ans:
        got = retriever.search_docs(c["question"], k)
        want = set(c["reference_doc_ids"])
        ranks = [i for i, d in enumerate(got, 1) if d in want]
        if ranks:
            hit += 1
            rr += 1 / ranks[0]
        else:
            misses.append(c["id"])
        if want <= set(got):
            full += 1
    n = len(ans) or 1
    return RetrievalReport(len(ans), hit / n, full / n, rr / n, misses)


def run_offline(cases: list[dict], pipeline: RagPipeline) -> list[tuple[dict, RagAnswer]]:
    return [(c, pipeline.ask(c["question"])) for c in cases]


def to_ragas_rows(results: list[tuple[dict, RagAnswer]]) -> list[dict]:
    """Rows in the Ragas single-turn sample shape (user_input/response/retrieved_contexts/reference)."""
    return [
        {
            "user_input": c["question"],
            "response": a.answer,
            "retrieved_contexts": a.contexts,
            "reference": c["reference"],
        }
        for c, a in results
    ]
