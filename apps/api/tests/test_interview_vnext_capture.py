from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.observability.artifacts import (
    ArtifactConflict,
    InMemoryArtifactStore,
    build_inline_artifact,
)
from app.interview_vnext.observability.capture import CaptureConflict, CaptureRecorder
from app.interview_vnext.observability.checkpoint import (
    CheckpointStatus,
    CheckpointTransitionError,
    OperationCheckpoint,
    mark_calling,
    mark_committed,
    mark_failed,
    mark_provider_completed,
    mark_verified,
    start_next_attempt,
)
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    ExecutionStatus,
    ExecutionTaxonomy,
    validate_event_chain,
)
from app.interview_vnext.observability.outbox import (
    InMemoryOutbox,
    OutboxLeaseConflict,
    OutboxStatus,
)
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1


NOW = datetime(2026, 7, 16, 2, 0, tzinfo=UTC)


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-vnext-capture:{name}")


def taxonomy(*, extra_stage: str | None = None) -> ExecutionTaxonomy:
    if extra_stage is None:
        return INTERVIEW_VNEXT_EXECUTION_V1
    return ExecutionTaxonomy(
        taxonomy_id=INTERVIEW_VNEXT_EXECUTION_V1.taxonomy_id,
        version="1.1.0",
        event_types=INTERVIEW_VNEXT_EXECUTION_V1.event_types,
        stages=tuple(sorted({*INTERVIEW_VNEXT_EXECUTION_V1.stages, extra_stage})),
    )


def artifact(name: str, *, payload=None, at=NOW):
    return build_inline_artifact(
        artifact_id=uid(f"artifact:{name}"),
        kind=name,
        media_type="application/json",
        payload=payload if payload is not None else {"name": name},
        schema_id=f"{name}.v1",
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation"),
        created_at=at,
        contains_test_data=True,
    )


def test_inline_artifact_is_canonical_hash_verified_and_immutable_by_id():
    store = InMemoryArtifactStore()
    first = artifact("context.packet", payload={"b": 2, "a": 1})
    duplicate = artifact("context.packet", payload={"a": 1, "b": 2})

    assert first.inline_content == '{"a":1,"b":2}'
    assert store.put(first) == first
    assert store.put(duplicate) == first
    assert store.get(first.ref.artifact_id).ref.content_hash == first.ref.content_hash

    changed = artifact("context.packet", payload={"a": 999})
    with pytest.raises(ArtifactConflict):
        store.put(changed)
    with pytest.raises(ValidationError, match="content hash mismatch"):
        type(first).model_validate(
            {**first.model_dump(), "inline_content": '{"a":999}', "ref": first.ref}
        )


def test_capture_builds_and_validates_artifact_backed_hash_chain_and_manifest():
    artifacts = InMemoryArtifactStore()
    prompt = artifacts.put(artifact("prompt.template"))
    response = artifacts.put(artifact("model.visible_response", at=NOW + timedelta(seconds=1)))
    outbox = InMemoryOutbox()
    capture = CaptureRecorder(taxonomy=taxonomy(), artifacts=artifacts, outbox=outbox)

    started = capture.record(
        event_id=uid("event:started"),
        occurred_at=NOW,
        architecture_id="interview-vnext-evidence-workflow",
        workflow_version="1.0.0",
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation"),
        attempt_id=uid("attempt"),
        attempt=1,
        event_type="model.call.started",
        stage="turn.interpret",
        status=ExecutionStatus.OK,
        input_artifacts=(prompt.ref,),
        metadata={"provider": "fake"},
    )
    completed = capture.record(
        event_id=uid("event:completed"),
        occurred_at=NOW + timedelta(seconds=1),
        architecture_id="interview-vnext-evidence-workflow",
        workflow_version="1.0.0",
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation"),
        attempt_id=uid("attempt"),
        attempt=1,
        event_type="model.call.completed",
        stage="turn.interpret",
        status=ExecutionStatus.OK,
        input_artifacts=(prompt.ref,),
        output_artifacts=(response.ref,),
        metadata={"outcome": "succeeded"},
    )
    manifest = capture.build_manifest(
        run_id=uid("run"),
        completed_at=NOW + timedelta(seconds=2),
        root_artifacts=(response.ref,),
    )

    assert started.sequence == 1
    assert completed.sequence == 2
    assert completed.previous_event_hash == started.event_hash
    assert manifest.event_count == 2
    assert manifest.last_event_hash == completed.event_hash
    assert len(outbox.all()) == 2
    validate_event_chain(
        capture.events(uid("run")),
        taxonomy=taxonomy(),
        artifact_store=artifacts,
        manifest=manifest,
    )

    tampered_values = dict(completed.__dict__)
    tampered_values["event_hash"] = canonical_hash({"tampered": True})
    tampered = ExecutionEvent.model_construct(**tampered_values)
    with pytest.raises(ValidationError, match="event hash mismatch"):
        validate_event_chain(
            (started, tampered), taxonomy=taxonomy(), artifact_store=artifacts
        )


def test_capture_event_id_is_idempotent_but_not_rewritable():
    artifacts = InMemoryArtifactStore()
    outbox = InMemoryOutbox()
    capture = CaptureRecorder(taxonomy=taxonomy(), artifacts=artifacts, outbox=outbox)
    values = dict(
        event_id=uid("event:run-start"),
        occurred_at=NOW,
        architecture_id="interview-vnext-evidence-workflow",
        workflow_version="1.0.0",
        run_id=uid("run"),
        session_id=uid("session"),
        event_type="workflow.run.started",
        stage="workflow.run",
        status=ExecutionStatus.OK,
    )

    first = capture.record(**values)
    assert capture.record(**values) == first
    assert len(outbox.all()) == 1
    with pytest.raises(CaptureConflict):
        capture.record(**{**values, "status": ExecutionStatus.FAILED})


def test_rejected_event_leaves_no_half_run_or_outbox_record():
    artifacts = InMemoryArtifactStore()
    outbox = InMemoryOutbox()
    capture = CaptureRecorder(taxonomy=taxonomy(), artifacts=artifacts, outbox=outbox)

    with pytest.raises(ValidationError, match="attempt requires operation_id"):
        capture.record(
            event_id=uid("event:invalid-attempt"),
            occurred_at=NOW,
            architecture_id="interview-vnext-evidence-workflow",
            workflow_version="1.0.0",
            run_id=uid("run:invalid"),
            session_id=uid("session"),
            attempt_id=uid("attempt:invalid"),
            attempt=1,
            event_type="model.call.started",
            stage="turn.interpret",
            status=ExecutionStatus.OK,
        )

    assert capture.events(uid("run:invalid")) == ()
    assert outbox.all() == ()


def test_open_stage_string_gains_meaning_through_taxonomy_not_envelope_change():
    expanded = taxonomy(extra_stage="evidence.reconcile")
    expanded.validate_names(event_type="model.call.started", stage="evidence.reconcile")
    with pytest.raises(ValueError, match="not registered"):
        taxonomy().validate_names(event_type="model.call.started", stage="evidence.reconcile")

    schema = ExecutionEvent.model_json_schema()
    stage_schema = schema["properties"]["stage"]
    assert "enum" not in stage_schema


def test_outbox_retries_after_exporter_failure_without_duplicate_event():
    artifacts = InMemoryArtifactStore()
    outbox = InMemoryOutbox()
    capture = CaptureRecorder(taxonomy=taxonomy(), artifacts=artifacts, outbox=outbox)
    event = capture.record(
        event_id=uid("event:outbox"),
        occurred_at=NOW,
        architecture_id="interview-vnext-evidence-workflow",
        workflow_version="1.0.0",
        run_id=uid("run"),
        session_id=uid("session"),
        event_type="workflow.run.started",
        stage="workflow.run",
        status=ExecutionStatus.OK,
    )

    assert outbox.enqueue(event, occurred_at=NOW).message_id == event.event_id
    leased = outbox.lease(
        worker_id="capture-exporter-1",
        now=NOW,
        lease_for=timedelta(seconds=30),
    )[0]
    assert leased.delivery_attempts == 1
    failed = outbox.mark_failed(
        event.event_id,
        worker_id="capture-exporter-1",
        occurred_at=NOW + timedelta(seconds=1),
        error_code="sink.unavailable",
        retry_at=NOW + timedelta(seconds=5),
    )
    assert failed.status == OutboxStatus.RETRY_WAIT
    assert outbox.lease(
        worker_id="capture-exporter-2",
        now=NOW + timedelta(seconds=4),
        lease_for=timedelta(seconds=30),
    ) == ()

    retried = outbox.lease(
        worker_id="capture-exporter-2",
        now=NOW + timedelta(seconds=5),
        lease_for=timedelta(seconds=30),
    )[0]
    assert retried.delivery_attempts == 2
    delivered = outbox.mark_delivered(
        event.event_id,
        worker_id="capture-exporter-2",
        occurred_at=NOW + timedelta(seconds=6),
    )
    assert delivered.status == OutboxStatus.DELIVERED
    assert outbox.mark_delivered(
        event.event_id,
        worker_id="another-worker",
        occurred_at=NOW + timedelta(seconds=7),
    ) == delivered
    with pytest.raises(OutboxLeaseConflict):
        outbox.mark_failed(
            event.event_id,
            worker_id="capture-exporter-1",
            occurred_at=NOW + timedelta(seconds=8),
            error_code="late.failure",
        )


def test_checkpoint_recovery_reuses_provider_result_and_committed_outcome():
    request_artifact = artifact("model.request").ref
    result_artifact = artifact("model.result").ref
    evidence_artifact = artifact("model.provider_execution_evidence").ref
    conformance_artifact = artifact("model.provider_conformance").ref
    verification_artifact = artifact("verification.result").ref
    domain_result_artifact = artifact("domain.reducer_result").ref
    response_artifact = artifact("consultant.response").ref
    checkpoint = OperationCheckpoint(
        checkpoint_id=uid("checkpoint"),
        run_id=uid("run"),
        session_id=uid("session"),
        turn_id=uid("turn"),
        operation_id=uid("operation"),
        operation_name="turn.interpret",
        operation_definition_hash=canonical_hash({"operation": "turn.interpret"}),
        idempotency_key="turn-7:turn.interpret",
        request_artifact=request_artifact,
        state_before_hash=canonical_hash({"state": 7}),
        created_at=NOW,
        updated_at=NOW,
    )

    calling = mark_calling(
        checkpoint,
        attempt_id=uid("attempt"),
        attempt=1,
        occurred_at=NOW + timedelta(seconds=1),
    )
    provider_completed = mark_provider_completed(
        calling,
        result_artifact=result_artifact,
        execution_evidence_artifact=evidence_artifact,
        conformance_artifact=conformance_artifact,
        occurred_at=NOW + timedelta(seconds=2),
    )
    assert mark_provider_completed(
        provider_completed,
        result_artifact=result_artifact,
        execution_evidence_artifact=evidence_artifact,
        conformance_artifact=conformance_artifact,
        occurred_at=NOW + timedelta(seconds=99),
    ) == provider_completed
    verified = mark_verified(
        provider_completed,
        verification_artifact=verification_artifact,
        occurred_at=NOW + timedelta(seconds=3),
    )
    committed = mark_committed(
        verified,
        domain_result_artifact=domain_result_artifact,
        response_artifact=response_artifact,
        state_after_hash=canonical_hash({"state": 8}),
        occurred_at=NOW + timedelta(seconds=4),
    )

    assert committed.status == CheckpointStatus.COMMITTED
    assert committed.revision == 4
    assert committed.provider_result_artifact == result_artifact
    assert mark_committed(
        committed,
        domain_result_artifact=domain_result_artifact,
        response_artifact=response_artifact,
        state_after_hash=committed.state_after_hash,
        occurred_at=NOW + timedelta(seconds=100),
    ) == committed
    with pytest.raises(CheckpointTransitionError, match="terminal"):
        mark_failed(
            committed,
            failure_artifact=artifact("failure.result").ref,
            reason_code="late.failure",
            occurred_at=NOW + timedelta(seconds=5),
        )


def test_checkpoint_rejects_skipped_transition_and_allows_explicit_terminal_failure():
    checkpoint = OperationCheckpoint(
        checkpoint_id=uid("checkpoint:failure"),
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation:failure"),
        operation_name="episode.code",
        operation_definition_hash=canonical_hash({"operation": "episode.code"}),
        idempotency_key="episode-3:episode.code",
        request_artifact=artifact("model.request.failure").ref,
        state_before_hash=canonical_hash({"state": 10}),
        created_at=NOW,
        updated_at=NOW,
    )
    with pytest.raises(CheckpointTransitionError, match="requires verified"):
        mark_committed(
            checkpoint,
            domain_result_artifact=artifact("domain.result.failure").ref,
            response_artifact=artifact("response.failure").ref,
            state_after_hash=canonical_hash({"state": 11}),
            occurred_at=NOW + timedelta(seconds=1),
        )

    calling = mark_calling(
        checkpoint,
        attempt_id=uid("attempt:failure"),
        attempt=1,
        occurred_at=NOW + timedelta(seconds=1),
    )
    failed = mark_failed(
        calling,
        failure_artifact=artifact("provider.timeout").ref,
        reason_code="provider.timeout",
        occurred_at=NOW + timedelta(seconds=2),
    )
    assert failed.status == CheckpointStatus.FAILED
    assert failed.state_after_hash is None


def test_checkpoint_persists_failed_attempt_before_retrying_same_operation():
    checkpoint = OperationCheckpoint(
        checkpoint_id=uid("checkpoint:retry"),
        run_id=uid("run"),
        session_id=uid("session"),
        operation_id=uid("operation:retry"),
        operation_name="turn.interpret",
        operation_definition_hash=canonical_hash({"operation": "turn.interpret"}),
        idempotency_key="turn-8:turn.interpret",
        request_artifact=artifact("model.request.retry").ref,
        state_before_hash=canonical_hash({"state": 12}),
        created_at=NOW,
        updated_at=NOW,
    )
    first = mark_calling(
        checkpoint,
        attempt_id=uid("attempt:retry:1"),
        attempt=1,
        occurred_at=NOW + timedelta(seconds=1),
    )
    first_failure = artifact("attempt.result.timeout").ref
    second = start_next_attempt(
        first,
        previous_attempt_result=first_failure,
        attempt_id=uid("attempt:retry:2"),
        attempt=2,
        occurred_at=NOW + timedelta(seconds=2),
    )
    final_result = artifact("attempt.result.success").ref
    completed = mark_provider_completed(
        second,
        result_artifact=final_result,
        execution_evidence_artifact=artifact("attempt.evidence.success").ref,
        conformance_artifact=artifact("attempt.conformance.success").ref,
        occurred_at=NOW + timedelta(seconds=3),
    )

    assert second.status == CheckpointStatus.CALLING
    assert second.operation_id == first.operation_id
    assert second.active_attempt == 2
    assert second.attempt_result_artifacts == (first_failure,)
    assert start_next_attempt(
        second,
        previous_attempt_result=first_failure,
        attempt_id=uid("attempt:retry:2"),
        attempt=2,
        occurred_at=NOW + timedelta(seconds=99),
    ) == second
    assert completed.attempt_result_artifacts == (first_failure, final_result)
    assert completed.provider_result_artifact == final_result
    with pytest.raises(CheckpointTransitionError, match="increment by one"):
        start_next_attempt(
            second,
            previous_attempt_result=artifact("attempt.result.other").ref,
            attempt_id=uid("attempt:retry:4"),
            attempt=4,
            occurred_at=NOW + timedelta(seconds=4),
        )
