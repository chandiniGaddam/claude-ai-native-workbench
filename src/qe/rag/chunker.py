"""Split documents into retrievable chunks: one chunk per markdown block (paragraph, list,
or table) under the document title and nearest heading. Deterministic, no model needed."""

from __future__ import annotations

import re
from dataclasses import dataclass

from qe.rag.sources import Document


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<doc id>#<n>"
    doc_id: str
    heading: str
    text: str


def chunk_document(doc: Document, min_chars: int = 40) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading = doc.title
    for block in re.split(r"\n\s*\n", doc.body):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            first, _, rest = block.partition("\n")
            heading = first.lstrip("# ").strip() or heading
            block = rest.strip()
            if not block:
                continue
        if len(block) < min_chars and chunks and chunks[-1].heading == heading:
            prev = chunks[-1]
            chunks[-1] = Chunk(prev.chunk_id, prev.doc_id, prev.heading, prev.text + "\n" + block)
            continue
        chunks.append(Chunk(f"{doc.id}#{len(chunks)}", doc.id, heading, block))
    return chunks


def chunk_all(docs: list[Document]) -> list[Chunk]:
    return [c for d in docs for c in chunk_document(d)]
