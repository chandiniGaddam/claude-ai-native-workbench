import json
from types import SimpleNamespace

import pytest

from qe.rag import pipeline as P
from qe.rag.chunker import chunk_all, chunk_document
from qe.rag.evaluation import (
    DATASET_PATH,
    load_dataset,
    retrieval_report,
    run_offline,
    to_ragas_rows,
    validate_dataset,
)
from qe.rag.retriever import Retriever, load_chunks, save_chunks, tokenize
from qe.rag.sources import load_documents, parse_document

pytestmark = pytest.mark.unit
THRESHOLDS = json.loads((DATASET_PATH.parent / "thresholds.json").read_text())["retrieval"]


@pytest.fixture(scope="module")
def docs():
    return load_documents()


@pytest.fixture(scope="module")
def retriever(docs):
    return Retriever(chunk_all(docs))


def test_chunking_is_deterministic_and_ids_unique(docs):
    a, b = chunk_all(docs), chunk_all(docs)
    assert a == b
    assert len({c.chunk_id for c in a}) == len(a)
    assert all(c.text.strip() for c in a)


def test_short_block_merges_into_previous():
    d = parse_document("---\nid: x\ntitle: T\nevidence:\n  - f:1 | q\n---\nA long enough first paragraph for chunking.\n\nshort")
    assert len(chunk_document(d)) == 1


def test_tokenize_drops_stopwords_and_lowercases():
    assert tokenize("What IS the Capacity?") == ["capacity"]


def test_search_is_deterministic_and_ranked(retriever):
    q = "HTTP status for duplicate enrollment"
    assert retriever.search(q) == retriever.search(q)
    scores = [h.score for h in retriever.search(q, 6)]
    assert scores == sorted(scores, reverse=True)


def test_search_empty_and_nonsense_queries(retriever):
    assert retriever.search("") == []
    assert retriever.search("zzzqqq xylophone") == []


def test_empty_retriever_rejected():
    with pytest.raises(ValueError):
        Retriever([])


def test_index_roundtrip(tmp_path, docs):
    chunks = chunk_all(docs)
    save_chunks(chunks, tmp_path / "i.json")
    assert load_chunks(tmp_path / "i.json") == chunks


def test_dataset_valid_and_large_enough(docs):
    cases = load_dataset()
    assert len(cases) >= 10
    assert validate_dataset(cases, {d.id for d in docs}) == []
    assert {"factual", "multi_doc", "unanswerable", "adversarial"} <= {c["category"] for c in cases}


def test_validate_dataset_catches_problems():
    bad = [
        {"id": "A", "category": "nope", "question": "q", "reference": "r", "reference_doc_ids": ["ghost"]},
        {"id": "A", "category": "unanswerable", "question": "q", "reference": "r", "reference_doc_ids": ["x"]},
        {"id": "B", "category": "factual", "question": "", "reference": "r", "reference_doc_ids": []},
    ]
    text = "\n".join(validate_dataset(bad, {"x"}))
    for needle in ("bad category", "unknown doc id", "duplicate id", "unanswerable cases must have no", "answerable cases need", "empty question"):
        assert needle in text


def test_offline_retrieval_meets_floors(retriever):
    rep = retrieval_report(load_dataset(), retriever, THRESHOLDS["k"])
    assert rep.answerable >= 10
    assert rep.hit_at_k >= THRESHOLDS["min_hit_at_k"], rep.misses
    assert rep.mrr >= THRESHOLDS["min_mrr"]


def test_extractive_pipeline_and_ragas_rows(retriever):
    pipe = P.RagPipeline(retriever, P.ExtractiveGenerator())
    out = run_offline(load_dataset()[:3], pipe)
    rows = to_ragas_rows(out)
    assert set(rows[0]) == {"user_input", "response", "retrieved_contexts", "reference"}
    assert all(r["retrieved_contexts"] for r in rows)


def test_extractive_says_not_in_kb_without_hits(retriever):
    pipe = P.RagPipeline(retriever, P.ExtractiveGenerator())
    assert pipe.ask("zzzqqq").answer == P.NOT_IN_KB


# -- paid-API guard: all offline, using a fake client --------------------------------
def test_claude_generator_refuses_without_flag():
    with pytest.raises(P.PaidApiNotAllowed):
        P.ClaudeGenerator(client=object(), env={})


def test_claude_generator_refuses_without_key():
    with pytest.raises(P.PaidApiNotAllowed):
        P.ClaudeGenerator(env={"QE_ALLOW_PAID_API": "1"})


def test_claude_generator_prompt_fences_context_and_uses_expected_model(retriever):
    calls = []

    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                calls.append(kw)
                return SimpleNamespace(content=[SimpleNamespace(text=" answer [x] ")])

    gen = P.ClaudeGenerator(client=Fake, env={"QE_ALLOW_PAID_API": "1"})
    ans = P.RagPipeline(retriever, gen).ask("What is the credits range for course update?")
    kw = calls[0]
    assert ans.answer == "answer [x]"
    assert kw["model"] == "claude-opus-5-5"
    assert "untrusted" in kw["system"] and "<context>" in kw["messages"][0]["content"]


def test_claude_generator_skips_call_when_no_hits(retriever):
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise AssertionError("must not be called")

    gen = P.ClaudeGenerator(client=Boom, env={"QE_ALLOW_PAID_API": "1"})
    assert P.RagPipeline(retriever, gen).ask("zzzqqq").answer == P.NOT_IN_KB
