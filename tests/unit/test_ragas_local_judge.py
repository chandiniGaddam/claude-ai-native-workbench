import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("openai")
pytest.importorskip("ragas")

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ragas_local_judge_eval.py"
SPEC = importlib.util.spec_from_file_location("ragas_local_judge_eval", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def test_score_with_retry_succeeds_after_one_retry():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("temporary")
        return SimpleNamespace(value=0.75)

    score, error = MOD.score_with_retry("faithfulness", flaky, 180.0)

    assert score == 0.75
    assert error is None
    assert len(calls) == 2


def test_score_with_retry_never_exceeds_one_retry():
    calls = []

    def fail():
        calls.append(1)
        raise RuntimeError("still unavailable")

    score, error = MOD.score_with_retry("answer_relevancy", fail, 180.0)

    assert score is None
    assert "RuntimeError" in error
    assert len(calls) == MOD.MAX_JUDGE_RETRIES + 1


def test_load_saved_judge_rows_keeps_latest_row(tmp_path):
    path = tmp_path / "scores.jsonl"
    path.write_text(
        '{"id":"RAG-01","faithfulness":0.1}\n'
        '{"id":"RAG-01","faithfulness":0.2}\n'
        '{"id":"RAG-02","faithfulness":null}\n',
        encoding="utf-8",
    )

    rows = MOD.load_saved_judge_rows(path)

    assert rows["RAG-01"]["faithfulness"] == 0.2
    assert rows["RAG-02"]["faithfulness"] is None


def test_completed_resume_filter_excludes_null_metrics():
    loaded = {
        "RAG-01": {"faithfulness": 0.5, "answer_relevancy": 0.6},
        "RAG-02": {"faithfulness": None, "answer_relevancy": None},
    }

    completed = {
        row_id: row
        for row_id, row in loaded.items()
        if row.get("faithfulness") is not None and row.get("answer_relevancy") is not None
    }

    assert set(completed) == {"RAG-01"}


def test_save_judge_progress_writes_jsonl_and_csv(tmp_path):
    jsonl = tmp_path / "scores.jsonl"
    csv_path = tmp_path / "scores.csv"
    fields = ["id", "faithfulness", "answer_relevancy"]
    rows = [{"id": "RAG-01", "faithfulness": 0.5, "answer_relevancy": 0.6}]

    MOD.save_judge_progress(jsonl, csv_path, fields, rows)

    assert json.loads(jsonl.read_text(encoding="utf-8").strip())["id"] == "RAG-01"
    with csv_path.open(encoding="utf-8", newline="") as fh:
        assert next(iter(csv.DictReader(fh)))["id"] == "RAG-01"


def test_default_judge_timeout_is_600_seconds():
    assert MOD.DEFAULT_JUDGE_TIMEOUT == 600.0
