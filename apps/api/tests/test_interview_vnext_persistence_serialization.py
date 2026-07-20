"""V2-B-1:canonical text ↔ Pydantic serialization seam(plan §4.3/§4.5)。

守的性質:round-trip 恆等、canonical byte hash(Unicode/emoji 不經 ASCII escape)、
tampered text/hash/normalized identity 一律 PersistedDataCorruption(不修復、不容忍)。
無 DB、無 I/O——這層先綠,repository 才有資格接線。
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.reducers import ReductionResult, transition_session
from app.interview_vnext.domain.commands import TransitionSessionCommand
from app.interview_vnext.domain.session import InterviewSession, SessionStatus
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.checkpoint import OperationCheckpoint
from app.interview_vnext.observability.events import (
    ExecutionEventBody,
    ExecutionStatus,
    build_execution_event,
)
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1
from app.interview_vnext.persistence.errors import PersistedDataCorruption
from app.interview_vnext.persistence.serialization import (
    dump_model,
    load_artifact,
    load_checkpoint,
    load_event,
    load_state,
)


NOW = datetime(2026, 7, 17, 3, 0, tzinfo=UTC)


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-vnext-serialization:{name}")


def _state() -> InterviewState:
    session = InterviewSession(
        session_id=uid("session"),
        profile_id=uid("profile"),
        tenant_id=uid("tenant"),
        workflow_version="1.0.0",
        reference_snapshot_id="ref-snapshot-v1 🧪 中文",
        created_at=NOW,
        updated_at=NOW,
    )
    return InterviewState(session=session)


def _event(metadata: str = "{}"):
    taxonomy = INTERVIEW_VNEXT_EXECUTION_V1
    body = ExecutionEventBody(
        event_id=uid("event"),
        occurred_at=NOW,
        architecture_id="interview-vnext-evidence-workflow",
        workflow_version="1.0.0",
        taxonomy_id=taxonomy.taxonomy_id,
        taxonomy_version=taxonomy.version,
        taxonomy_hash=taxonomy.content_hash,
        run_id=uid("run"),
        session_id=uid("session"),
        event_type="workflow.run.started",
        stage="workflow.run",
        status=ExecutionStatus.OK,
        sequence=1,
        metadata_json=metadata,
    )
    return build_execution_event(body)


def _checkpoint() -> OperationCheckpoint:
    request = build_inline_artifact(
        artifact_id=uid("request-artifact"),
        kind="model.request",
        media_type="application/json",
        payload={"question": "最近一次上線,你做了什麼?🚀"},
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation"),
        created_at=NOW,
        contains_test_data=True,
    )
    return OperationCheckpoint(
        checkpoint_id=uid("checkpoint"),
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation"),
        operation_name="turn.interpret",
        operation_definition_hash=canonical_hash({"op": "turn.interpret"}),
        idempotency_key="turn-1:interpret",
        request_artifact=request.ref,
        state_before_hash=canonical_hash(_state()),
        created_at=NOW,
        updated_at=NOW,
    )


# ── round-trip 恆等 ────────────────────────────────────────────────────────────

def test_state_round_trip_preserves_model_and_hash():
    state = _state()
    text = dump_model(state)
    loaded = load_state(text, canonical_hash(state),
                        session_id=state.session.session_id, state_version=0)
    assert loaded == state
    assert dump_model(loaded) == text


def test_event_round_trip_preserves_model_and_hash():
    event = _event()
    text = dump_model(event)
    loaded = load_event(text, event.event_hash, event_id=event.event_id,
                        run_id=event.run_id, sequence=1)
    assert loaded == event


def test_checkpoint_round_trip_preserves_model():
    checkpoint = _checkpoint()
    text = dump_model(checkpoint)
    loaded = load_checkpoint(text, operation_id=checkpoint.operation_id, revision=0)
    assert loaded == checkpoint


def test_reduction_result_round_trip_carries_schema_discriminator():
    state = _state()
    result = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("activate"),
            expected_state_version=0,
            occurred_at=NOW,
            target_status=SessionStatus.ACTIVE,
        ),
    )
    assert result.schema_version == "reduction_result.v1"
    text = dump_model(result)
    assert '"schema_version":"reduction_result.v1"' in text
    assert ReductionResult.model_validate_json(text) == result


# ── Unicode / canonical byte hash ─────────────────────────────────────────────

def test_canonical_text_keeps_unicode_and_hash_covers_utf8_bytes():
    event = _event(metadata=canonical_json({"注記": "回歸測試 ✅", "emoji": "🧪"}))
    text = dump_model(event)
    assert "🧪" in text and "注記" in text            # ensure_ascii=False:不變 \uXXXX
    loaded = load_event(text, event.event_hash)
    assert loaded.metadata_json == event.metadata_json
    # hash 對 UTF-8 bytes:同 payload 不同 key 順序 → 同 canonical text/hash
    reordered = canonical_json({"emoji": "🧪", "注記": "回歸測試 ✅"})
    assert reordered == event.metadata_json


# ── tampered → corruption(不修復)──────────────────────────────────────────────

def test_tampered_text_is_corruption():
    state = _state()
    text = dump_model(state).replace("ref-snapshot-v1", "ref-snapshot-v999")
    with pytest.raises(PersistedDataCorruption):
        load_state(text, canonical_hash(state))


def test_tampered_hash_is_corruption():
    state = _state()
    with pytest.raises(PersistedDataCorruption):
        load_state(dump_model(state), "sha256:" + "0" * 64)


def test_non_canonical_text_is_corruption_even_when_semantically_equal():
    state = _state()
    pretty = dump_model(state).replace(",", ", ", 1)   # 語意同、byte 不同
    with pytest.raises(PersistedDataCorruption):
        load_state(pretty, canonical_hash(state))


def test_mismatched_normalized_identity_is_corruption():
    state = _state()
    text = dump_model(state)
    with pytest.raises(PersistedDataCorruption):
        load_state(text, canonical_hash(state), session_id=uid("another-session"))
    with pytest.raises(PersistedDataCorruption):
        load_state(text, canonical_hash(state), state_version=7)
    event = _event()
    with pytest.raises(PersistedDataCorruption):
        load_event(dump_model(event), event.event_hash, sequence=99)
    checkpoint = _checkpoint()
    with pytest.raises(PersistedDataCorruption):
        load_checkpoint(dump_model(checkpoint), revision=5)


def test_invalid_json_and_unknown_fields_are_corruption_with_chained_cause():
    with pytest.raises(PersistedDataCorruption) as excinfo:
        load_state("not-json{", "sha256:" + "0" * 64)
    assert excinfo.value.__cause__ is not None        # exception chaining 供 log
    state = _state()
    smuggled = dump_model(state).replace(
        '"schema_version":"interview_state.v2"',
        '"schema_version":"interview_state.v2","extra_field":1', 1)
    with pytest.raises(PersistedDataCorruption):      # strict:未知欄位不容忍
        load_state(smuggled, canonical_hash(state))


# ── artifact row hydration ────────────────────────────────────────────────────

class _Row:
    """§5.3 欄位形狀的 duck-typed row stub。"""

    def __init__(self, record, **overrides):
        self.artifact_id = record.ref.artifact_id
        self.record_schema_version = record.schema_version
        self.kind = record.ref.kind
        self.media_type = record.ref.media_type
        self.schema_id = record.ref.schema_id
        self.content_hash = record.ref.content_hash
        self.byte_size = record.ref.byte_size
        self.run_id = record.run_id
        self.session_id = record.session_id
        self.turn_id = record.turn_id
        self.operation_id = record.operation_id
        self.attempt_id = record.attempt_id
        self.created_at = record.created_at
        self.storage = record.storage.value
        self.inline_content = record.inline_content
        self.external_uri = record.external_uri
        self.retention_class = record.retention_class
        self.redaction_status = record.redaction_status.value
        self.contains_test_data = record.contains_test_data
        for key, value in overrides.items():
            setattr(self, key, value)


def _artifact_record():
    return build_inline_artifact(
        artifact_id=uid("artifact"),
        kind="context.packet",
        media_type="application/json",
        payload={"任務": "版本回歸 🧪"},
        run_id=uid("run"),
        session_id=uid("session"),
        created_at=NOW,
        contains_test_data=True,
    )


def test_artifact_row_round_trip():
    record = _artifact_record()
    assert load_artifact(_Row(record)) == record


def test_artifact_row_tampered_content_or_hash_is_corruption():
    record = _artifact_record()
    with pytest.raises(PersistedDataCorruption):
        load_artifact(_Row(record, inline_content='{"任務":"被改掉"}'))
    with pytest.raises(PersistedDataCorruption):
        load_artifact(_Row(record, content_hash="sha256:" + "f" * 64))
