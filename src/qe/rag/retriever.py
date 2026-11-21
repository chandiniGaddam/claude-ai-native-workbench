"""Deterministic offline BM25 retrieval (rank-bm25). No network, no embeddings."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from qe.config import PROJECT_ROOT
from qe.rag.chunker import Chunk

INDEX_PATH = PROJECT_ROOT / "rag" / "knowledge" / "index.json"
_STOP = frozenset(["a", "an", "the", "of", "to", "in", "is", "are", "be", "it", "its", "for", "on", "and", "or", "by", "with", "as", "at", "this", "that", "what", "which", "how", "does", "do"])
_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Retriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("cannot build a retriever from zero chunks")
        self.chunks = chunks
        # The heading and doc id are indexed with the text so title words are searchable.
        self._bm25 = BM25Okapi([tokenize(f"{c.doc_id} {c.heading} {c.text}") for c in chunks])

    def search(self, query: str, k: int = 4) -> list[Hit]:
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        # stable tie-break on chunk order keeps results deterministic
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
        return [Hit(self.chunks[i], float(scores[i])) for i in order if scores[i] > 0]

    def search_docs(self, query: str, k: int = 4) -> list[str]:
        """Distinct document ids in rank order, from the top-k chunks."""
        seen: list[str] = []
        for h in self.search(query, k):
            if h.chunk.doc_id not in seen:
                seen.append(h.chunk.doc_id)
        return seen


def save_chunks(chunks: list[Chunk], path: Path = INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(c) for c in chunks], indent=1), encoding="utf-8")


def load_chunks(path: Path = INDEX_PATH) -> list[Chunk]:
    return [Chunk(**d) for d in json.loads(path.read_text(encoding="utf-8"))]
