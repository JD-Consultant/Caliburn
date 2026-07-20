import json
from pathlib import Path

import pytest

from evals.interview_v4.contracts import EvalCaseManifest, SCHEMA_MODELS
from evals.interview_v4.graders import grade_case_integrity
from evals.interview_v4.loader import CaseIntegrityError, load_case
from evals.interview_v4.write_schemas import write_schemas


ROOT = Path(__file__).parents[1] / "evals" / "interview_v4"
LEGACY_CASE = ROOT / "cases" / "development" / "JD-golden-001"


def test_committed_schemas_match_pydantic_contracts(tmp_path):
    generated = write_schemas(tmp_path)
    assert {path.name for path in generated} == set(SCHEMA_MODELS)
    for path in generated:
        committed = ROOT / "schemas" / path.name
        assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
            committed.read_text(encoding="utf-8")
        )


def test_legacy_case_is_valid_but_explicitly_provisional():
    bundle = load_case(LEGACY_CASE)
    assert bundle.manifest.case_id == "JD-golden-001"
    assert bundle.manifest.replay.ready is False
    assert bundle.manifest.annotation.status.value == "draft"
    assert len(bundle.transcript) == 14
    labels = {item.label_id for item in bundle.gold.required_evidence}
    assert {"ev_completion_rule", "ev_sampling_exception"} <= labels
    assert bundle.gold.required_projection_claims == []
    assert grade_case_integrity(LEGACY_CASE).passed is True


def test_manifest_rejects_parent_path():
    raw = json.loads((LEGACY_CASE / "case.json").read_text(encoding="utf-8"))
    raw["transcript"] = "../secret.jsonl"
    with pytest.raises(ValueError, match="relative file path"):
        EvalCaseManifest.model_validate(raw)


def test_loader_rejects_gold_quote_from_consultant_turn(tmp_path):
    target = tmp_path / "case"
    target.mkdir()
    for source in LEGACY_CASE.iterdir():
        if source.is_file():
            (target / source.name).write_bytes(source.read_bytes())
    gold = json.loads((target / "gold.json").read_text(encoding="utf-8"))
    gold["required_evidence"][0]["source"] = {
        "turn_seq": 1,
        "quote": "你好，我是 AI 訪談顧問"
    }
    (target / "gold.json").write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CaseIntegrityError, match="non-employee turn"):
        load_case(target)
