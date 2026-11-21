#!/usr/bin/env python3
"""Offline Ragas evaluation: no LLM judge, no network, no paid API.

Run with the separate evaluation environment, isolated from the working directory:
    .venv-eval/bin/python -I scripts/ragas_offline_eval.py

What it does
1. Validates rag/eval/dataset.jsonl against the knowledge base.
2. Retrieves with BM25 (qe.rag.retriever) and answers with the offline ExtractiveGenerator.
3. Computes the Ragas metrics that need no LLM (collections BleuScore, RougeScore,
   CHRFScore, NonLLMStringSimilarity), comparing each response with its reference.
4. Computes retrieval metrics (hit@k, full recall@k, MRR) and compares them with the floors
   in rag/eval/thresholds.json.
5. Writes reports/rag/ragas_offline_scores.csv, ragas_offline_scores.jsonl and
   ragas_offline_summary.json.

Not computed here: Faithfulness, AnswerRelevancy, ContextRecall, ContextPrecision, and any
other metric that needs a judge LLM. Those are paid (Claude judge) and need explicit approval.
No metric threshold is invented. rag/eval/thresholds.json defines none for Ragas metrics.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ragas.metrics.collections import BleuScore, CHRFScore, NonLLMStringSimilarity, RougeScore  # noqa: E402

from qe.rag.chunker import chunk_all  # noqa: E402
from qe.rag.evaluation import load_dataset, retrieval_report, validate_dataset  # noqa: E402
from qe.rag.pipeline import ExtractiveGenerator, RagPipeline  # noqa: E402
from qe.rag.retriever import Retriever  # noqa: E402
from qe.rag.sources import load_documents  # noqa: E402

REPORT_DIR = ROOT / "reports" / "rag"
THRESHOLDS = ROOT / "rag" / "eval" / "thresholds.json"
K = 4
METRICS = {
    "bleu": BleuScore(),
    "rouge_l_f": RougeScore(rouge_type="rougeL", mode="fmeasure"),
    "chrf": CHRFScore(),
    "levenshtein_similarity": NonLLMStringSimilarity(),
}


def main() -> int:
    docs = load_documents()
    known = {d.id for d in docs}
    cases = load_dataset()
    problems = validate_dataset(cases, known)
    if problems:
        print("dataset: INVALID")
        for p in problems:
            print("  -", p)
        return 1
    print(f"dataset: {len(cases)} cases valid against {len(known)} knowledge documents")

    chunks = chunk_all(docs)
    retriever = Retriever(chunks)
    pipeline = RagPipeline(retriever, ExtractiveGenerator(), k=K)
    retr = retrieval_report(cases, retriever, k=K)

    rows = []
    for case in cases:
        ans = pipeline.ask(case["question"])
        scores = {}
        for name, metric in METRICS.items():
            scores[name] = round(float(metric.score(response=ans.answer, reference=case["reference"]).value), 4)
        retrieved_docs = retriever.search_docs(case["question"], K)
        want = set(case["reference_doc_ids"])
        ranks = [i for i, d in enumerate(retrieved_docs, 1) if d in want]
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "reference": case["reference"],
                "response": ans.answer,
                "retrieved_doc_ids": retrieved_docs,
                "reference_doc_ids": case["reference_doc_ids"],
                "hit_at_k": bool(ranks) if want else None,
                "first_relevant_rank": ranks[0] if ranks else None,
                **scores,
            }
        )

    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))["retrieval"]
    retrieval_checks = {
        "hit_at_k": {"value": round(retr.hit_at_k, 4), "floor": thresholds["min_hit_at_k"],
                     "passed": retr.hit_at_k >= thresholds["min_hit_at_k"]},
        "mrr": {"value": round(retr.mrr, 4), "floor": thresholds["min_mrr"],
                "passed": retr.mrr >= thresholds["min_mrr"]},
    }

    metric_names = list(METRICS)
    summary = {
        "generator": pipeline.generator.name,
        "k": K,
        "cases": len(rows),
        "answerable_cases": retr.answerable,
        "retrieval": {"hit_at_k": retr.hit_at_k, "full_recall_at_k": retr.full_recall_at_k,
                      "mrr": retr.mrr, "misses": retr.misses, "vs_thresholds": retrieval_checks},
        "ragas_metric_means": {m: round(statistics.fmean(r[m] for r in rows), 4) for m in metric_names},
        "ragas_metric_thresholds": "none documented in rag/eval/thresholds.json (not invented)",
        "lowest_3_by_metric": {
            m: [{"id": r["id"], "score": r[m]} for r in sorted(rows, key=lambda r: r[m])[:3]]
            for m in metric_names
        },
        "means_by_category": {
            cat: {m: round(statistics.fmean(r[m] for r in rows if r["category"] == cat), 4) for m in metric_names}
            for cat in sorted({r["category"] for r in rows})
        },
        "not_computed": ["faithfulness", "answer_relevancy", "context_precision", "context_recall",
                         "noise_sensitivity"],
        "not_computed_reason": "need a judge LLM (paid Claude API; approval required)",
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "ragas_offline_scores.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    fields = ["id", "category", "hit_at_k", "first_relevant_rank", *metric_names,
              "retrieved_doc_ids", "reference_doc_ids", "question", "response", "reference"]
    with (REPORT_DIR / "ragas_offline_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, "retrieved_doc_ids": ",".join(r["retrieved_doc_ids"]),
                             "reference_doc_ids": ",".join(r["reference_doc_ids"])})
    (REPORT_DIR / "ragas_offline_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"generator: {summary['generator']}  k={K}")
    for name, check in retrieval_checks.items():
        verdict = "PASS" if check["passed"] else "FAIL"
        print(f"retrieval {name}: {check['value']} vs floor {check['floor']} -> {verdict}")
    print("ragas (non-LLM) means:", summary["ragas_metric_means"])
    print("reports:", REPORT_DIR / "ragas_offline_scores.csv", REPORT_DIR / "ragas_offline_scores.jsonl",
          REPORT_DIR / "ragas_offline_summary.json", sep="\n  ")
    return 0 if all(c["passed"] for c in retrieval_checks.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
