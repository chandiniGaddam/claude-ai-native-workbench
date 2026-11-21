#!/usr/bin/env python3
"""Run a Ragas evaluation. PAID: uses the Claude API for generation and judging.

It refuses to run unless QE_ALLOW_PAID_API=1 (set it only with the user's approval) and
ANTHROPIC_API_KEY is in the environment. Without approval it only does a dry run that
writes the Ragas input rows to reports/rag/ragas_rows.json, using the offline extractive
generator, and makes no network call.

Not implemented yet (needs approval and the separate .venv-eval): the actual
``ragas.evaluate`` call with the claude-sonnet-5-5 judge.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qe.rag.chunker import chunk_all
from qe.rag.evaluation import load_dataset, run_offline, to_ragas_rows
from qe.rag.pipeline import ExtractiveGenerator, RagPipeline
from qe.rag.retriever import Retriever
from qe.rag.sources import load_documents


def main() -> int:
    if os.environ.get("QE_ALLOW_PAID_API") == "1":
        print("QE_ALLOW_PAID_API=1: paid evaluation is not implemented in this phase.", file=sys.stderr)
        return 2
    pipe = RagPipeline(Retriever(chunk_all(load_documents())), ExtractiveGenerator())
    rows = to_ragas_rows(run_offline(load_dataset(), pipe))
    out = ROOT / "reports" / "rag"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ragas_rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"dry run: wrote {len(rows)} rows to {out / 'ragas_rows.json'} (no API call made)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
