"""Counterexample: correct ranks must not hide corrupted report columns."""
import pytest
import verify
import copy
import csv
import io
import json
from pathlib import Path


@pytest.mark.parametrize("field,value", [("top1_id", "wrong-id"),
                                        ("top1_title", "wrong-title"),
                                        ("top1_score", 0.123)])
def test_offline_audit_rejects_corrupted_top1_without_writing_artifacts(monkeypatch, field, value):
    original = verify.read

    def read(path):
        document = original(path)
        if path.name == "metrics.json":
            document[0][field] = value
        return document

    monkeypatch.setattr(verify, "read", read)
    with pytest.raises(AssertionError):
        verify.check(verify.HERE / "run-02")


def test_offline_audit_rejects_duplicate_case_replacing_missing_case(monkeypatch):
    original_read, original_text, original_open = verify.read, Path.read_text, Path.open
    out = verify.HERE / "run-02/retrieval"

    def duplicate(rows):
        return [copy.deepcopy(next(item for item in rows if item["case_id"] == "E03" and item["arm"] == row["arm"]))
                if row["case_id"] == "E01" else row for row in rows]

    metrics = duplicate(original_read(out / "metrics.json"))
    database = duplicate(original_read(out / "database-checks.json"))
    rankings = duplicate([json.loads(line) for line in original_text(out / "fixed-rankings.jsonl", encoding="utf-8").splitlines()])
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=list(metrics[0]))
    writer.writeheader()
    writer.writerows(metrics)

    def read(path):
        if path == out / "metrics.json":
            return copy.deepcopy(metrics)
        if path == out / "summary.json":
            return verify.summaries(metrics)
        if path == out / "database-checks.json":
            return copy.deepcopy(database)
        return original_read(path)

    def read_text(path, *args, **kwargs):
        if path == out / "fixed-rankings.jsonl":
            return "\n".join(json.dumps(row) for row in rankings)
        return original_text(path, *args, **kwargs)

    def open_file(path, *args, **kwargs):
        if path == out / "metrics.csv":
            return io.StringIO(csv_buffer.getvalue())
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(verify, "read", read)
    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(AssertionError):
        verify.check(verify.HERE / "run-02")
