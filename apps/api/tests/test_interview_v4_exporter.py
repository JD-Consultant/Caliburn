import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from evals.interview_v4.exporter import export_session_case, find_direct_identifiers
from evals.interview_v4.loader import load_case


def test_direct_identifier_scan_does_not_treat_opaque_sha_as_phone():
    digest_with_phone_like_digits = (
        "sha256:b921631966aed97e01e50d2b342dced09f1a15c3e6302846dd19f94aa4e0c8d9"
    )
    assert find_direct_identifiers({"source_fingerprint": digest_with_phone_like_digits}) == []
    assert find_direct_identifiers({"text": "請聯絡 0912-345-678"}) == [
        {"kind": "PHONE", "path": "text"}
    ]


class ReadOnlyRepo:
    def __init__(self, session_id):
        self.calls = []
        self.session = SimpleNamespace(
            id=session_id,
            phase="deep",
            focus={"owner": "王經理"},
            counters={},
            human_touched=[],
            ledger_state={},
        )
        self.turns = [
            SimpleNamespace(seq=1, role="consultant", text="請說明工作"),
            SimpleNamespace(
                seq=2,
                role="employee",
                text="請寄 test@example.com，電話 0912-345-678，系統 https://internal.example/a",
            ),
        ]

    async def get(self, session_id):
        self.calls.append("get")
        return self.session if session_id == self.session.id else None

    async def list_turns(self, session_id):
        self.calls.append("list_turns")
        return self.turns

    async def list_review_events(self, session_id):
        self.calls.append("list_review_events")
        return []

    async def list_llm_calls(self, session_id):
        self.calls.append("list_llm_calls")
        return []


@pytest.mark.asyncio
async def test_exporter_is_read_only_redacts_and_requires_manual_review(tmp_path):
    session_id = uuid4()
    repo = ReadOnlyRepo(session_id)
    destination = await export_session_case(
        repo=repo,
        session_id=session_id,
        initial_document={"job_summary": "王經理負責；帳號 owner@example.com"},
        reference_snapshot={"ref_codes": [], "content_hash": "snapshot-1"},
        output_root=tmp_path,
        case_id="REAL-EXPORT-001",
        source_hash_salt="test-only-secret-salt",
        role_family="operations",
        risk_tags=["E-QUAL"],
        observed_document={"job_summary": "王經理目前的匯出草稿"},
        replacements={"王經理": "[主管_A]"},
    )
    assert repo.calls == ["get", "list_turns", "list_review_events", "list_llm_calls"]
    bundle = load_case(destination)
    assert bundle.manifest.privacy.status.value == "redaction_pending_review"
    assert bundle.manifest.privacy.manual_review_required is True
    all_text = "\n".join(turn.text for turn in bundle.transcript)
    assert "test@example.com" not in all_text
    assert "0912-345-678" not in all_text
    assert "https://internal.example/a" not in all_text
    assert not find_direct_identifiers(json.loads(
        (destination / "source_audit.json").read_text(encoding="utf-8")
    ))
    audit = json.loads((destination / "source_audit.json").read_text(encoding="utf-8"))
    assert audit["source_fingerprint"].startswith("sha256:")
    assert audit["fixture_provenance"] == {
        "initial_document": "provided",
        "initial_state": "unavailable",
        "reference_snapshot": "provided",
    }
    initial_state = json.loads((destination / "initial_state.json").read_text(encoding="utf-8"))
    assert initial_state["available"] is False
    assert initial_state["fixture"] == "initial_state"
    observed_state = json.loads(
        (destination / "observed_session_state.json").read_text(encoding="utf-8")
    )
    assert observed_state["focus"]["owner"] == "[主管_A]"
    observed_document = json.loads(
        (destination / "observed_document.json").read_text(encoding="utf-8")
    )
    assert observed_document["job_summary"] == "[主管_A]目前的匯出草稿"
    assert str(session_id) not in (destination / "source_audit.json").read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        await export_session_case(
            repo=repo,
            session_id=session_id,
            initial_document={},
            reference_snapshot={},
            output_root=tmp_path,
            case_id="REAL-EXPORT-001",
            source_hash_salt="test-only-secret-salt",
            role_family="operations",
            risk_tags=["E-QUAL"],
        )


@pytest.mark.asyncio
async def test_exporter_marks_missing_historical_fixtures_without_fabricating_start_state(tmp_path):
    session_id = uuid4()
    destination = await export_session_case(
        repo=ReadOnlyRepo(session_id),
        session_id=session_id,
        initial_document=None,
        initial_state=None,
        reference_snapshot=None,
        observed_document={"job_summary": "export-time only"},
        output_root=tmp_path,
        case_id="REAL-EXPORT-MISSING-001",
        source_hash_salt="test-only-secret-salt",
        role_family="operations",
        risk_tags=["missing-initial-fixtures"],
    )

    bundle = load_case(destination)
    assert bundle.manifest.replay.ready is False
    assert bundle.initial_document["available"] is False
    assert bundle.initial_state["available"] is False
    assert bundle.reference_snapshot["available"] is False
    assert any(
        "must not be reconstructed" in item
        for item in bundle.manifest.replay.limitations
    )


@pytest.mark.asyncio
async def test_owner_confirmed_test_data_is_synthetic_but_not_falsely_replay_ready(tmp_path):
    session_id = uuid4()
    destination = await export_session_case(
        repo=ReadOnlyRepo(session_id),
        session_id=session_id,
        initial_document=None,
        initial_state=None,
        reference_snapshot=None,
        observed_document={},
        output_root=tmp_path,
        case_id="TEST-SESSION-001",
        source_hash_salt="test-only-secret-salt",
        role_family="test-role",
        risk_tags=["missing-initial-fixtures"],
        test_data=True,
    )

    bundle = load_case(destination)
    assert bundle.manifest.privacy.status.value == "synthetic"
    assert bundle.manifest.privacy.manual_review_required is False
    assert bundle.manifest.source_type.value == "migrated_provisional"
    assert bundle.manifest.replay.ready is False
