import pytest

from qe.config import Settings
from qe.rag.sources import load_documents, parse_document, verify_evidence

pytestmark = pytest.mark.unit


def test_at_least_eight_documents_with_unique_ids():
    docs = load_documents()
    assert len(docs) >= 8
    assert len({d.id for d in docs}) == len(docs)


def test_every_evidence_line_exists_in_the_aut_and_contains_its_quote():
    aut = Settings.from_env().aut_dir
    problems = [p for d in load_documents() for p in verify_evidence(d, aut)]
    assert problems == []


def test_documents_make_no_login_or_payment_feature_claims():
    # CLAUDE.md: login/payment are unavailable; docs may only say they don't exist.
    for d in load_documents():
        for line in d.body.lower().splitlines():
            if "payment" in line or "login" in line:
                assert any(w in line for w in ("no ", "not ", "without")), (d.id, line)


def test_parse_rejects_missing_evidence():
    with pytest.raises(ValueError, match="evidence"):
        parse_document("---\nid: a\ntitle: t\n---\nbody")


def test_parse_rejects_missing_front_matter():
    with pytest.raises(ValueError, match="front matter"):
        parse_document("body only")


def test_verify_evidence_detects_wrong_quote(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\nbeta\n")
    doc = parse_document("---\nid: a\ntitle: t\nevidence:\n  - f.txt:2 | alpha\n  - f.txt:9 | x\n  - g.txt:1 | x\n---\nb")
    probs = verify_evidence(doc, tmp_path)
    assert len(probs) == 3
