#!/usr/bin/env python3
"""Verify rag/sources against the AUT, chunk them, and write rag/knowledge/index.json.

Offline only. Exits 1 if any evidence line doesn't match the AUT source.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qe.config import Settings
from qe.rag.chunker import chunk_all
from qe.rag.retriever import INDEX_PATH, save_chunks
from qe.rag.sources import load_documents, verify_evidence


def main() -> int:
    aut = Settings.from_env().aut_dir
    docs = load_documents()
    problems = [p for d in docs for p in verify_evidence(d, aut)]
    for p in problems:
        print("EVIDENCE MISMATCH", p)
    if problems:
        return 1
    chunks = chunk_all(docs)
    save_chunks(chunks)
    print(f"documents={len(docs)} chunks={len(chunks)} -> {INDEX_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
