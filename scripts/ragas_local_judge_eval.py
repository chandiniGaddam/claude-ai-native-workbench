#!/usr/bin/env python3
"""Ragas evaluation with a FREE local judge. No paid API is called.

Components (all local):
* Generator: Qwen2.5-7B-Instruct Q4_K_M served by llama.cpp on 127.0.0.1:8081 (qe.rag.local).
* Judge LLM: the same local endpoint, through ragas.llms.llm_factory(provider="openai")
  with base_url pointed at loopback. The OpenAI SDK is used only as a client; no key is sent
  to any remote host.
* Embeddings (AnswerRelevancy): all-MiniLM-L6-v2 from a local directory, CPU.

Usage (the llama.cpp server must already be running, see docs in reports/rag/):
    .venv-eval/bin/python -I scripts/ragas_local_judge_eval.py [--limit N] [--skip-generation]

Outputs (reports/rag/):
    local_answers.jsonl            generated answers and contexts (resumable)
    ragas_local_judge_scores.jsonl per-case judge scores, errors kept as null
    ragas_local_judge_scores.csv   same, flattened
    ragas_local_judge_summary.json means, abstention checks, low scorers

Nothing is fabricated: a judge call that fails leaves the metric null and records the error.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openai import OpenAI
from ragas.embeddings import HuggingFaceEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, Faithfulness

from qe.config import validate_local_url
from qe.rag.chunker import chunk_all
from qe.rag.evaluation import load_dataset, validate_dataset
from qe.rag.local import LocalChatGenerator
from qe.rag.pipeline import NOT_IN_KB, RagPipeline
from qe.rag.retriever import Retriever
from qe.rag.sources import load_documents

MODEL_LABEL = "qwen2.5-7b-instruct-q4_k_m"
JUDGE_URL = validate_local_url("http://127.0.0.1:8081/v1", {"127.0.0.1"})
EMBED_DIR = ROOT / ".tools" / "models" / "all-MiniLM-L6-v2"
REPORT_DIR = ROOT / "reports" / "rag"
K = 4
UNANSWERABLE = {"RAG-12", "RAG-13"}
INJECTION_MARKER = "BANANA"
MAX_JUDGE_RETRIES = 1
DEFAULT_JUDGE_TIMEOUT = 600.0


def generate_answers(cases, pipeline, path: Path, skip: bool) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["id"]] = row
    if skip:
        return done
    with path.open("a", encoding="utf-8") as fh:
        for case in cases:
            if case["id"] in done:
                continue
            t0 = time.time()
            ans = pipeline.ask(case["question"])
            row = {"id": case["id"], "response": ans.answer, "contexts": ans.contexts,
                   "generator": ans.generator, "seconds": round(time.time() - t0, 1)}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            done[case["id"]] = row
            print(f"generated {case['id']} in {row['seconds']}s", flush=True)
    return done


def score_with_retry(name: str, fn, timeout_seconds: float):
    """Call one judge metric, allowing at most one retry after a failure."""
    del timeout_seconds  # The OpenAI client owns transport timeout; this documents the per-call limit.
    last_error = None
    for attempt in range(MAX_JUDGE_RETRIES + 1):
        try:
            result = fn()
            return round(float(result.value), 4), None
        except Exception as exc:  # noqa: BLE001 - retries are bounded and errors are retained
            last_error = exc
    return None, f"{type(last_error).__name__}: {str(last_error)[:200]}"


def load_saved_judge_rows(path: Path) -> dict[str, dict]:
    """Load a resumable JSONL score file, keeping the latest row for each case."""
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if "id" in row:
                rows[row["id"]] = row
    return rows


def save_judge_progress(path: Path, csv_path: Path, fields: list[str], rows: list[dict]) -> None:
    """Persist completed judge rows after each case; no rows are guessed or fabricated."""
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-generation", action="store_true")
    ap.add_argument("--judge-timeout", type=float, default=DEFAULT_JUDGE_TIMEOUT,
                    help="Seconds for one local judge HTTP call (default: 600)")
    args = ap.parse_args()
    if args.judge_timeout <= 0:
        ap.error("--judge-timeout must be greater than zero")

    docs = load_documents()
    cases = load_dataset()
    problems = validate_dataset(cases, {d.id for d in docs})
    if problems:
        print("dataset INVALID:", problems)
        return 1
    if args.limit:
        cases = cases[: args.limit]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    retriever = Retriever(chunk_all(docs))
    generator = LocalChatGenerator(JUDGE_URL, MODEL_LABEL)
    pipeline = RagPipeline(retriever, generator, k=K)
    answers = generate_answers(cases, pipeline, REPORT_DIR / "local_answers.jsonl", args.skip_generation)

    client = OpenAI(base_url=JUDGE_URL, api_key="local-no-key", timeout=args.judge_timeout,
                    max_retries=0)
    judge = llm_factory(MODEL_LABEL, provider="openai", client=client)
    embeddings = HuggingFaceEmbeddings(model=str(EMBED_DIR), device="cpu")
    faith = Faithfulness(llm=judge)
    relevance = AnswerRelevancy(llm=judge, embeddings=embeddings)

    score_path = REPORT_DIR / "ragas_local_judge_scores.jsonl"
    csv_path = REPORT_DIR / "ragas_local_judge_scores.csv"
    fields = ["id", "category", "faithfulness", "answer_relevancy", "faithfulness_error",
              "answer_relevancy_error", "abstained", "followed_injection", "response", "reference", "question"]
    saved = {
        row_id: row
        for row_id, row in load_saved_judge_rows(score_path).items()
        if row.get("faithfulness") is not None and row.get("answer_relevancy") is not None
    }
    rows = [saved[c["id"]] for c in cases if c["id"] in saved]
    persisted_rows = list(saved.values())

    for case in cases:
        if case["id"] in saved:
            print(f"resumed {case['id']}", flush=True)
            continue
        a = answers[case["id"]]
        row = {"id": case["id"], "category": case["category"], "question": case["question"],
               "reference": case["reference"], "response": a["response"]}
        for name, fn in (
            ("faithfulness", lambda a=a, case=case: faith.score(user_input=case["question"], response=a["response"],
                                                 retrieved_contexts=a["contexts"])),
            ("answer_relevancy", lambda a=a, case=case: relevance.score(user_input=case["question"], response=a["response"])),
        ):
            t0 = time.time()
            row[name], row[name + "_error"] = score_with_retry(name, fn, args.judge_timeout)
            row[name + "_seconds"] = round(time.time() - t0, 1)
        if case["id"] in UNANSWERABLE:
            row["abstained"] = NOT_IN_KB.lower() in a["response"].lower()
        if case["category"] == "adversarial":
            row["followed_injection"] = INJECTION_MARKER in a["response"]
        rows.append(row)
        saved[case["id"]] = row
        persisted_rows.append(row)
        save_judge_progress(score_path, csv_path, fields, persisted_rows)
        print(f"judged {case['id']}: faith={row['faithfulness']} rel={row['answer_relevancy']}", flush=True)

    def mean(key, subset=rows):
        vals = [r[key] for r in subset if r.get(key) is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    low = {m: [{"id": r["id"], "score": r[m]} for r in sorted(
        [x for x in rows if x.get(m) is not None], key=lambda x: x[m])[:3]]
        for m in ("faithfulness", "answer_relevancy")}
    summary = {
        "generator": generator.name,
        "judge": f"local:{MODEL_LABEL} via ragas llm_factory(openai-compatible, 127.0.0.1)",
        "embeddings": "all-MiniLM-L6-v2 (local, CPU)",
        "judge_timeout_seconds": args.judge_timeout,
        "judge_max_retries": MAX_JUDGE_RETRIES,
        "cases": len(rows),
        "errors": {m: sum(1 for r in rows if r.get(m + "_error")) for m in ("faithfulness", "answer_relevancy")},
        "faithfulness_mean": mean("faithfulness"),
        "answer_relevancy_mean": mean("answer_relevancy"),
        "answerable_faithfulness_mean": mean("faithfulness", [r for r in rows if r["id"] not in UNANSWERABLE]),
        "unanswerable_abstention": {r["id"]: r["abstained"] for r in rows if r["id"] in UNANSWERABLE},
        "adversarial_injection_followed": {r["id"]: r["followed_injection"] for r in rows
                                          if r["category"] == "adversarial"},
        "lowest_3": low,
        "thresholds": "none documented for Ragas metrics (rag/eval/thresholds.json); not judged",
    }
    (REPORT_DIR / "ragas_local_judge_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    generator.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
