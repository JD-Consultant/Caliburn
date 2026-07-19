"""Durable operation use cases — prepare / attempt / verify / commit / fail (§7.4–§7.8).

每個函式恰一個短 transaction;provider network call 只發生在 ``start_attempt``
commit 之後、``record_attempt_result`` 之前,絕不在 UoW 內。checkpoint 寫入順序
永遠是:hydrate → pure transition(observability.checkpoint 的函式)→ canonical
serialize → revision CAS;不直接 patch JSON columns。

V2-B 邊界:outcome 分類(succeeded / retryable / non-retryable)由呼叫端提供
——typed ``ModelCallResult`` 的正規化屬 provider adapter(V6)與 workflow(V3),
本層只保存 canonical result artifact 並依分類推進 checkpoint。關鍵不變量:
attempt row 與 checkpoint 轉換同一 transaction,因此「calling + result_recorded」
的 durable 組合**只可能**來自 retryable 結果(non-retryable/succeeded 會在同
transaction 轉 failed/provider_completed)。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Callable
from uuid import UUID

from app.interview_vnext.domain.commands import CommandBase
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.reducers import ReductionResult
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    build_inline_artifact,
)
from app.interview_vnext.observability.checkpoint import (
    CheckpointStatus,
    OperationCheckpoint,
    mark_calling,
    mark_committed,
    mark_failed,
    mark_provider_completed,
    mark_verified,
    start_next_attempt,
)
from app.interview_vnext.observability.events import ExecutionStatus
from app.interview_vnext.persistence.errors import (
    CheckpointConflict,
    PersistedDataCorruption,
    StateVersionConflict,
)

from .durable_commands import DurableCommandOutcome, _commit_command_core
from .noop_result import OPERATION_NOOP_RESULT_SCHEMA_ID, OperationNoopResult
from .persistence import (
    AttemptStatus,
    ExecutionEventDraft,
    OperationAttempt,
    VNextUnitOfWork,
)


class AttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    NON_RETRYABLE_FAILURE = "non_retryable_failure"


async def _require_checkpoint(uow: VNextUnitOfWork, *, tenant_id: UUID,
                              operation_id: UUID) -> OperationCheckpoint:
    checkpoint = await uow.checkpoints.get_by_operation(
        tenant_id=tenant_id, operation_id=operation_id)
    if checkpoint is None:
        raise CheckpointConflict("operation checkpoint does not exist",
                                 tenant_id=tenant_id, operation_id=operation_id)
    return checkpoint


async def _cas_or_conflict(uow: VNextUnitOfWork, *, tenant_id: UUID,
                           expected_revision: int,
                           checkpoint: OperationCheckpoint) -> None:
    updated = await uow.checkpoints.save_cas(
        tenant_id=tenant_id, expected_revision=expected_revision,
        checkpoint=checkpoint)
    if not updated:
        await uow.rollback()
        raise CheckpointConflict(
            "checkpoint revision moved; reload and re-decide",
            operation_id=checkpoint.operation_id,
            expected_revision=expected_revision)


async def prepare_operation(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    session_id: UUID,
    checkpoint_id: UUID,
    operation_id: UUID,
    operation_name: str,
    operation_definition_hash: str,
    idempotency_key: str,
    request_artifact: ArtifactRecord,
    extra_request_artifacts: tuple[ArtifactRecord, ...] = (),
    expected_state_hash: str | None = None,
    turn_id: UUID | None = None,
    stage: str = "turn.interpret",
    step_event_id: UUID,
    occurred_at: datetime,
) -> OperationCheckpoint:
    """§7.4:load state → request artifacts → idempotency 查重 → prepared
    checkpoint → ``workflow.step.started``。到此為止才允許啟動 attempt。"""
    async with uow_factory() as uow:
        state = await uow.sessions.get(tenant_id=tenant_id, session_id=session_id)
        state_before_hash = canonical_hash(state)
        if expected_state_hash is not None and state_before_hash != expected_state_hash:
            raise CheckpointConflict(
                "session state moved while context/request artifacts were built",
                operation_id=operation_id,
                session_id=session_id,
            )

        existing = await uow.checkpoints.get_by_idempotency(
            tenant_id=tenant_id, session_id=session_id,
            operation_name=operation_name, idempotency_key=idempotency_key)
        if existing is not None:
            same = (existing.operation_id == operation_id
                    and existing.operation_definition_hash == operation_definition_hash
                    and existing.request_artifact == request_artifact.ref
                    and existing.state_before_hash == state_before_hash)
            if same:
                return existing
            raise CheckpointConflict(
                "idempotency key already used with a different request/definition/state",
                operation_id=operation_id, idempotency_key=idempotency_key)

        for record in (request_artifact, *extra_request_artifacts):
            await uow.artifacts.put(tenant_id=tenant_id, record=record)
        checkpoint = OperationCheckpoint(
            checkpoint_id=checkpoint_id, run_id=run_id, session_id=session_id,
            turn_id=turn_id, operation_id=operation_id,
            operation_name=operation_name,
            operation_definition_hash=operation_definition_hash,
            idempotency_key=idempotency_key,
            request_artifact=request_artifact.ref,
            state_before_hash=state_before_hash,
            created_at=occurred_at, updated_at=occurred_at)
        await uow.checkpoints.create(tenant_id=tenant_id, checkpoint=checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=run_id,
            draft=ExecutionEventDraft(
                event_id=step_event_id, occurred_at=occurred_at,
                session_id=session_id, turn_id=turn_id,
                operation_id=operation_id,
                event_type="workflow.step.started", stage=stage,
                status=ExecutionStatus.OK,
                input_artifacts=(request_artifact.ref,),
                state_before_hash=state_before_hash))
        await uow.commit()
        return checkpoint


async def _start_attempt(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    attempt_id: UUID,
    provider: str,
    requested_model: str,
    deadline_at: datetime,
    max_attempts: int,
    request_artifact: ArtifactRecord | None = None,
    stage: str = "turn.interpret",
    call_event_id: UUID,
    occurred_at: datetime,
) -> tuple[OperationCheckpoint, OperationAttempt, bool]:
    """§7.5:短 transaction 記 calling attempt;commit 後呼叫端才打 provider。
    attempt 1 只能由 prepared 建立;retry 必須已保存前一 attempt result。"""
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(uow, tenant_id=tenant_id,
                                               operation_id=operation_id)
        if (checkpoint.status == CheckpointStatus.CALLING
                and checkpoint.active_attempt_id == attempt_id):
            attempt = await uow.attempts.get(tenant_id=tenant_id,
                                             attempt_id=attempt_id)
            if attempt is None:
                raise PersistedDataCorruption(
                    "checkpoint references a missing attempt row",
                    operation_id=operation_id, attempt_id=attempt_id)
            if (
                request_artifact is not None
                and attempt.request_artifact_id != request_artifact.ref.artifact_id
            ):
                raise CheckpointConflict(
                    "attempt already uses a different request artifact",
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                )
            return checkpoint, attempt, False   # crash-after-commit 冪等重入

        if checkpoint.status == CheckpointStatus.PREPARED:
            attempt_number = 1
            next_checkpoint = mark_calling(
                checkpoint, attempt_id=attempt_id, attempt=1,
                occurred_at=occurred_at)
        elif checkpoint.status == CheckpointStatus.CALLING:
            assert checkpoint.active_attempt_id is not None
            previous = await uow.attempts.get(
                tenant_id=tenant_id, attempt_id=checkpoint.active_attempt_id)
            if previous is None:
                raise PersistedDataCorruption(
                    "checkpoint references a missing attempt row",
                    operation_id=operation_id,
                    attempt_id=checkpoint.active_attempt_id)
            if previous.status != AttemptStatus.RESULT_RECORDED:
                raise CheckpointConflict(
                    "retry requires the previous attempt result to be recorded",
                    operation_id=operation_id,
                    attempt_id=checkpoint.active_attempt_id)
            assert previous.result_artifact_id is not None
            previous_result = await uow.artifacts.get(
                tenant_id=tenant_id, artifact_id=previous.result_artifact_id)
            attempt_number = previous.attempt + 1
            if attempt_number > max_attempts:
                raise CheckpointConflict(
                    "operation attempt budget is exhausted",
                    operation_id=operation_id, attempt=attempt_number,
                    max_attempts=max_attempts)
            next_checkpoint = start_next_attempt(
                checkpoint, previous_attempt_result=previous_result.ref,
                attempt_id=attempt_id, attempt=attempt_number,
                occurred_at=occurred_at)
        else:
            raise CheckpointConflict(
                f"cannot start an attempt from status {checkpoint.status.value}",
                operation_id=operation_id)

        if request_artifact is not None:
            if (
                request_artifact.run_id != checkpoint.run_id
                or request_artifact.session_id != checkpoint.session_id
                or request_artifact.turn_id != checkpoint.turn_id
                or request_artifact.operation_id != operation_id
                or request_artifact.attempt_id != attempt_id
            ):
                raise CheckpointConflict(
                    "attempt request artifact scope does not match attempt",
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                )
            stored_request = await uow.artifacts.put(
                tenant_id=tenant_id, record=request_artifact
            )
            request_artifact_id = stored_request.ref.artifact_id
        else:
            request_artifact_id = checkpoint.request_artifact.artifact_id

        attempt = OperationAttempt(
            attempt_id=attempt_id, run_id=checkpoint.run_id,
            session_id=checkpoint.session_id, operation_id=operation_id,
            attempt=attempt_number,
            request_artifact_id=request_artifact_id,
            provider=provider, requested_model=requested_model,
            deadline_at=deadline_at, started_at=occurred_at,
            updated_at=occurred_at)
        await uow.attempts.start(tenant_id=tenant_id, attempt=attempt)
        await _cas_or_conflict(uow, tenant_id=tenant_id,
                               expected_revision=checkpoint.revision,
                               checkpoint=next_checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=call_event_id, occurred_at=occurred_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, attempt_id=attempt_id,
                attempt=attempt_number, event_type="model.call.started",
                stage=stage, status=ExecutionStatus.OK))
        await uow.commit()
        return next_checkpoint, attempt, True


async def start_attempt(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    attempt_id: UUID,
    provider: str,
    requested_model: str,
    deadline_at: datetime,
    max_attempts: int,
    request_artifact: ArtifactRecord | None = None,
    stage: str = "turn.interpret",
    call_event_id: UUID,
    occurred_at: datetime,
) -> tuple[OperationCheckpoint, OperationAttempt]:
    """Backward-compatible durable start without granting provider-call authority."""

    checkpoint, attempt, _claimed = await _start_attempt(
        uow_factory,
        tenant_id=tenant_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        provider=provider,
        requested_model=requested_model,
        deadline_at=deadline_at,
        max_attempts=max_attempts,
        request_artifact=request_artifact,
        stage=stage,
        call_event_id=call_event_id,
        occurred_at=occurred_at,
    )
    return checkpoint, attempt


async def claim_attempt_for_provider(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    attempt_id: UUID,
    provider: str,
    requested_model: str,
    deadline_at: datetime,
    max_attempts: int,
    request_artifact: ArtifactRecord | None = None,
    stage: str = "turn.interpret",
    call_event_id: UUID,
    occurred_at: datetime,
) -> tuple[OperationCheckpoint, OperationAttempt, bool]:
    """Start an attempt and tell the caller if this transaction won the call claim.

    Only a ``True`` claimant may perform provider I/O. An idempotent replay of an
    already-calling attempt returns ``False`` even when it used the same attempt ID.
    """

    try:
        return await _start_attempt(
            uow_factory,
            tenant_id=tenant_id,
            operation_id=operation_id,
            attempt_id=attempt_id,
            provider=provider,
            requested_model=requested_model,
            deadline_at=deadline_at,
            max_attempts=max_attempts,
            request_artifact=request_artifact,
            stage=stage,
            call_event_id=call_event_id,
            occurred_at=occurred_at,
        )
    except CheckpointConflict:
        # A same-ID claimant can lose the INSERT/CAS before the winner commits.
        # The failed UoW is gone; classify the race only from a fresh transaction.
        async with uow_factory() as uow:
            checkpoint = await _require_checkpoint(
                uow, tenant_id=tenant_id, operation_id=operation_id
            )
            attempt = await uow.attempts.get(
                tenant_id=tenant_id, attempt_id=attempt_id
            )
            expected_request_artifact_id = (
                request_artifact.ref.artifact_id
                if request_artifact is not None
                else checkpoint.request_artifact.artifact_id
            )
            if (
                checkpoint.status == CheckpointStatus.CALLING
                and checkpoint.active_attempt_id == attempt_id
                and attempt is not None
                and attempt.operation_id == operation_id
                and attempt.attempt == checkpoint.active_attempt
                and attempt.status == AttemptStatus.CALLING
                and attempt.request_artifact_id == expected_request_artifact_id
                and attempt.provider == provider
                and attempt.requested_model == requested_model
                and attempt.deadline_at == deadline_at
            ):
                return checkpoint, attempt, False
        raise


async def record_attempt_result(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    attempt_id: UUID,
    result_artifact: ArtifactRecord,
    execution_evidence_artifact: ArtifactRecord,
    conformance_artifact: ArtifactRecord,
    extra_result_artifacts: tuple[ArtifactRecord, ...] = (),
    outcome: AttemptOutcome,
    wire_succeeded: bool,
    conformance_eligible: bool,
    max_attempts: int,
    failure_reason_code: str = "provider_failure",
    stage: str = "turn.interpret",
    result_event_id: UUID,
    conformance_event_id: UUID,
    occurred_at: datetime,
) -> OperationCheckpoint:
    """§7.3/§7.6:provider 返回後的單一 transaction。

    wire result、normalized execution evidence 與 conformance report 一起保存,
    再依 classification 推進 checkpoint:succeeded(wire 成功+conformance 合格+
    local schema 有效)→ provider_completed;retryable 且還有額度 → checkpoint
    保留 calling(三個 artifact 只在 events/artifacts,不留 checkpoint 指標);
    non-retryable/額度耗盡 → failed。wire 成功但 conformance 不合格時,failure
    authority 是 conformance report,attempt 由 wire result 終結(§7.4)。兩個
    event(model.call.* 與 provider.conformance.completed)同一 transaction。"""
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(uow, tenant_id=tenant_id,
                                               operation_id=operation_id)
        attempt = await uow.attempts.get(tenant_id=tenant_id, attempt_id=attempt_id)
        if attempt is None or attempt.operation_id != operation_id:
            raise CheckpointConflict("attempt does not belong to this operation",
                                     operation_id=operation_id,
                                     attempt_id=attempt_id)
        provider_records = (
            result_artifact,
            execution_evidence_artifact,
            conformance_artifact,
            *extra_result_artifacts,
        )
        for record in provider_records:
            if (
                record.run_id != checkpoint.run_id
                or record.session_id != checkpoint.session_id
                or record.turn_id != checkpoint.turn_id
                or record.operation_id != operation_id
                or record.attempt_id != attempt_id
            ):
                raise CheckpointConflict(
                    "attempt result artifact scope does not match attempt",
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                    artifact_id=record.ref.artifact_id,
                )
        stored_supporting = tuple(
            [
                await uow.artifacts.put(tenant_id=tenant_id, record=record)
                for record in extra_result_artifacts
            ]
        )
        stored = await uow.artifacts.put(tenant_id=tenant_id, record=result_artifact)
        stored_evidence = await uow.artifacts.put(
            tenant_id=tenant_id, record=execution_evidence_artifact
        )
        stored_conformance = await uow.artifacts.put(
            tenant_id=tenant_id, record=conformance_artifact
        )
        recorded = attempt.model_copy(update={
            "status": AttemptStatus.RESULT_RECORDED,
            "result_artifact_id": stored.ref.artifact_id,
            "completed_at": occurred_at, "updated_at": occurred_at})
        recorded = OperationAttempt.model_validate(recorded.model_dump())
        await uow.attempts.record_result(tenant_id=tenant_id, attempt=recorded)

        exhausted = attempt.attempt >= max_attempts
        conformance_failure = wire_succeeded and not conformance_eligible
        if outcome == AttemptOutcome.SUCCEEDED:
            next_checkpoint = mark_provider_completed(
                checkpoint, result_artifact=stored.ref,
                execution_evidence_artifact=stored_evidence.ref,
                conformance_artifact=stored_conformance.ref,
                occurred_at=occurred_at)
            event_type, event_status = "model.call.completed", ExecutionStatus.OK
        elif outcome == AttemptOutcome.NON_RETRYABLE_FAILURE or exhausted:
            failure_ref = (
                stored_conformance.ref if conformance_failure else stored.ref
            )
            next_checkpoint = mark_failed(
                checkpoint, failure_artifact=failure_ref,
                reason_code=failure_reason_code, occurred_at=occurred_at,
                attempt_result_artifact=stored.ref,
                execution_evidence_artifact=stored_evidence.ref,
                conformance_artifact=stored_conformance.ref)
            event_type, event_status = "model.call.failed", ExecutionStatus.FAILED
        else:
            next_checkpoint = None       # retryable、額度未盡:checkpoint 保留 calling
            event_type, event_status = "model.call.failed", ExecutionStatus.FAILED

        if next_checkpoint is not None:
            await _cas_or_conflict(uow, tenant_id=tenant_id,
                                   expected_revision=checkpoint.revision,
                                   checkpoint=next_checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=result_event_id, occurred_at=occurred_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, attempt_id=attempt_id,
                attempt=attempt.attempt, event_type=event_type, stage=stage,
                status=event_status,
                output_artifacts=tuple(
                    item.ref for item in stored_supporting
                ) + (stored.ref, stored_evidence.ref)))
        if wire_succeeded:
            conformance_status = (
                ExecutionStatus.OK if conformance_eligible else ExecutionStatus.FAILED
            )
        else:
            conformance_status = ExecutionStatus.SKIPPED
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=conformance_event_id, occurred_at=occurred_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, attempt_id=attempt_id,
                attempt=attempt.attempt,
                event_type="provider.conformance.completed", stage=stage,
                status=conformance_status,
                input_artifacts=(stored_evidence.ref,),
                output_artifacts=(stored_conformance.ref,)))
        await uow.commit()
        return next_checkpoint if next_checkpoint is not None else checkpoint


async def record_verification(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    verification_artifact: ArtifactRecord,
    accepted: bool,
    rejection_reason_code: str = "verification_rejected",
    stage: str = "turn.interpret",
    event_id: UUID,
    occurred_at: datetime,
) -> OperationCheckpoint:
    """§7.7:schema valid ≠ semantic valid。rejected → failed,不執行 reducer。"""
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(uow, tenant_id=tenant_id,
                                               operation_id=operation_id)
        stored = await uow.artifacts.put(tenant_id=tenant_id,
                                         record=verification_artifact)
        if accepted:
            next_checkpoint = mark_verified(
                checkpoint, verification_artifact=stored.ref,
                occurred_at=occurred_at)
            event_status = ExecutionStatus.OK
        else:
            next_checkpoint = mark_failed(
                checkpoint, failure_artifact=stored.ref,
                reason_code=rejection_reason_code, occurred_at=occurred_at)
            event_status = ExecutionStatus.FAILED
        await _cas_or_conflict(uow, tenant_id=tenant_id,
                               expected_revision=checkpoint.revision,
                               checkpoint=next_checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=event_id, occurred_at=occurred_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, event_type="verification.completed",
                stage=stage, status=event_status,
                output_artifacts=(stored.ref,)))
        await uow.commit()
        return next_checkpoint


async def commit_verified_operation(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    run_id: UUID,
    command: CommandBase,
    response_payload: Any,
    response_artifact_id: UUID,
    command_artifact_id: UUID,
    reduction_artifact_id: UUID,
    transition_event_id: UUID,
    step_event_id: UUID,
    committed_at: datetime,
    stage: str = "turn.interpret",
    request_idempotency_key: str | None = None,
) -> tuple[OperationCheckpoint, ReductionResult]:
    """§7.8:session、command、checkpoint、event、outbox 同生共死。
    committed 後重呼叫回既有 domain result/response,不重跑 reducer。
    state 已 stale(state_before_hash 不符)→ conflict,不把舊 proposal 硬套新 state。"""
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(uow, tenant_id=tenant_id,
                                               operation_id=operation_id)
        if checkpoint.status == CheckpointStatus.COMMITTED:
            assert checkpoint.domain_result_artifact is not None
            stored = await uow.artifacts.get(
                tenant_id=tenant_id,
                artifact_id=checkpoint.domain_result_artifact.artifact_id)
            result = ReductionResult.model_validate_json(stored.inline_content or "")
            return checkpoint, result
        if checkpoint.status != CheckpointStatus.VERIFIED:
            raise CheckpointConflict(
                f"commit requires a verified checkpoint, got {checkpoint.status.value}",
                operation_id=operation_id)

        state = await uow.sessions.get(tenant_id=tenant_id,
                                       session_id=checkpoint.session_id)
        if canonical_hash(state) != checkpoint.state_before_hash:
            raise CheckpointConflict(
                "session state moved since prepare; re-prepare the operation",
                operation_id=operation_id, session_id=checkpoint.session_id)

        core = await _commit_command_core(
            uow, tenant_id=tenant_id, session_id=checkpoint.session_id,
            run_id=run_id, command=command, stage=stage,
            event_id=transition_event_id,
            command_artifact_id=command_artifact_id,
            reduction_artifact_id=reduction_artifact_id,
            committed_at=committed_at,
            request_idempotency_key=request_idempotency_key)
        if core is None:
            raise StateVersionConflict(
                "session state moved during verified-operation commit",
                operation_id=operation_id, session_id=checkpoint.session_id)
        if isinstance(core, DurableCommandOutcome):
            # command 已由別的路徑 commit(duplicate race)→ 沿用既有 reduction
            result = core.result
            stored_reduction = await uow.artifacts.get(
                tenant_id=tenant_id,
                artifact_id=core.record.reduction_artifact_id)
            reduction_ref = stored_reduction.ref
        else:
            result, _record, _command_ref, reduction_ref = core

        response = await uow.artifacts.put(
            tenant_id=tenant_id,
            record=build_inline_artifact(
                artifact_id=response_artifact_id, kind="operation.response",
                media_type="application/json", payload=response_payload,
                run_id=run_id, session_id=checkpoint.session_id,
                operation_id=operation_id, created_at=committed_at))
        next_checkpoint = mark_committed(
            checkpoint, domain_result_artifact=reduction_ref,
            response_artifact=response.ref, state_after_hash=result.state_hash,
            occurred_at=committed_at)
        await _cas_or_conflict(uow, tenant_id=tenant_id,
                               expected_revision=checkpoint.revision,
                               checkpoint=next_checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=run_id,
            draft=ExecutionEventDraft(
                event_id=step_event_id, occurred_at=committed_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, event_type="workflow.step.completed",
                stage=stage, status=ExecutionStatus.OK,
                output_artifacts=(reduction_ref, response.ref),
                state_before_hash=checkpoint.state_before_hash,
                state_after_hash=result.state_hash))
        await uow.commit()
        return next_checkpoint, result


def _require_operation_artifact_scope(
    record: ArtifactRecord,
    *,
    checkpoint: OperationCheckpoint,
    role: str,
) -> None:
    if (
        record.run_id != checkpoint.run_id
        or record.session_id != checkpoint.session_id
        or record.turn_id != checkpoint.turn_id
        or record.operation_id != checkpoint.operation_id
        or record.attempt_id is not None
    ):
        raise CheckpointConflict(
            f"{role} artifact scope does not match operation checkpoint",
            operation_id=checkpoint.operation_id,
            artifact_id=record.ref.artifact_id,
        )


def _build_noop_artifact(
    *,
    checkpoint: OperationCheckpoint,
    verification_artifact: ArtifactRecord,
    response_artifact: ArtifactRecord,
    noop_result_artifact_id: UUID,
    step_event_id: UUID,
    reason_code: str,
    dropped_count: int,
    committed_at: datetime,
) -> tuple[OperationNoopResult, ArtifactRecord]:
    result = OperationNoopResult(
        operation_id=checkpoint.operation_id,
        completion_event_id=step_event_id,
        reason_code=reason_code,
        state_before_hash=checkpoint.state_before_hash,
        state_after_hash=checkpoint.state_before_hash,
        dropped_count=dropped_count,
        verification_artifact=verification_artifact.ref,
    )
    artifact = build_inline_artifact(
        artifact_id=noop_result_artifact_id,
        kind="operation.noop_result",
        media_type="application/json",
        payload=result,
        schema_id=OPERATION_NOOP_RESULT_SCHEMA_ID,
        run_id=checkpoint.run_id,
        session_id=checkpoint.session_id,
        turn_id=checkpoint.turn_id,
        operation_id=checkpoint.operation_id,
        created_at=committed_at,
        contains_test_data=(
            verification_artifact.contains_test_data
            or response_artifact.contains_test_data
        ),
    )
    return result, artifact


async def _replay_committed_noop(
    uow: VNextUnitOfWork,
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
    verification_artifact: ArtifactRecord,
    response_artifact: ArtifactRecord,
    noop_result_artifact_id: UUID,
    step_event_id: UUID,
    reason_code: str,
    dropped_count: int,
    committed_at: datetime,
) -> tuple[OperationCheckpoint, OperationNoopResult]:
    assert checkpoint.status == CheckpointStatus.COMMITTED
    assert checkpoint.verification_artifact is not None
    assert checkpoint.domain_result_artifact is not None
    assert checkpoint.response_artifact is not None

    expected_result, expected_noop = _build_noop_artifact(
        checkpoint=checkpoint,
        verification_artifact=verification_artifact,
        response_artifact=response_artifact,
        noop_result_artifact_id=noop_result_artifact_id,
        step_event_id=step_event_id,
        reason_code=reason_code,
        dropped_count=dropped_count,
        committed_at=committed_at,
    )
    if (
        checkpoint.verification_artifact != verification_artifact.ref
        or checkpoint.domain_result_artifact != expected_noop.ref
        or checkpoint.response_artifact != response_artifact.ref
        or checkpoint.state_after_hash != checkpoint.state_before_hash
    ):
        raise CheckpointConflict(
            "committed checkpoint has a different no-op outcome",
            operation_id=checkpoint.operation_id,
        )

    stored_verification, stored_noop, stored_response = await uow.artifacts.get_many(
        tenant_id=tenant_id,
        refs=(
            checkpoint.verification_artifact,
            checkpoint.domain_result_artifact,
            checkpoint.response_artifact,
        ),
    )
    if (
        stored_verification != verification_artifact
        or stored_noop != expected_noop
        or stored_response != response_artifact
    ):
        raise CheckpointConflict(
            "committed no-op artifacts differ from the replay request",
            operation_id=checkpoint.operation_id,
        )
    persisted_result = OperationNoopResult.model_validate_json(
        stored_noop.inline_content or ""
    )
    if persisted_result != expected_result:
        raise CheckpointConflict(
            "committed no-op result differs from the replay request",
            operation_id=checkpoint.operation_id,
        )
    return checkpoint, persisted_result


async def commit_verified_noop_operation(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    response_artifact: ArtifactRecord,
    verification_artifact: ArtifactRecord,
    noop_result_artifact_id: UUID,
    step_event_id: UUID,
    committed_at: datetime,
    dropped_count: int,
    reason_code: str = "no_domain_mutation",
    stage: str = "turn.interpret",
) -> tuple[OperationCheckpoint, OperationNoopResult]:
    """Commit a successful verified operation without a command or state write.

    The typed no-op outcome, response, checkpoint transition, completion event and
    outbox message are atomic. Exact replay is idempotent; any changed artifact or
    semantic input is an explicit checkpoint conflict.
    """
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(
            uow, tenant_id=tenant_id, operation_id=operation_id
        )
        _require_operation_artifact_scope(
            verification_artifact, checkpoint=checkpoint, role="verification"
        )
        _require_operation_artifact_scope(
            response_artifact, checkpoint=checkpoint, role="response"
        )
        if response_artifact.ref.kind != "operation.response":
            raise CheckpointConflict(
                "response artifact has an unexpected kind",
                operation_id=operation_id,
                artifact_id=response_artifact.ref.artifact_id,
            )
        if response_artifact.ref.media_type != "application/json":
            raise CheckpointConflict(
                "response artifact must be application/json",
                operation_id=operation_id,
                artifact_id=response_artifact.ref.artifact_id,
            )
        if response_artifact.created_at != committed_at:
            raise CheckpointConflict(
                "response artifact timestamp must equal committed_at",
                operation_id=operation_id,
                artifact_id=response_artifact.ref.artifact_id,
            )
        if noop_result_artifact_id in {
            verification_artifact.ref.artifact_id,
            response_artifact.ref.artifact_id,
        }:
            raise CheckpointConflict(
                "no-op result artifact ID must be distinct",
                operation_id=operation_id,
                artifact_id=noop_result_artifact_id,
            )

        if checkpoint.status == CheckpointStatus.COMMITTED:
            return await _replay_committed_noop(
                uow,
                tenant_id=tenant_id,
                checkpoint=checkpoint,
                verification_artifact=verification_artifact,
                response_artifact=response_artifact,
                noop_result_artifact_id=noop_result_artifact_id,
                step_event_id=step_event_id,
                reason_code=reason_code,
                dropped_count=dropped_count,
                committed_at=committed_at,
            )
        if checkpoint.status != CheckpointStatus.VERIFIED:
            raise CheckpointConflict(
                f"no-op commit requires a verified checkpoint, got {checkpoint.status.value}",
                operation_id=operation_id,
            )
        if checkpoint.verification_artifact != verification_artifact.ref:
            raise CheckpointConflict(
                "verification artifact does not match the verified checkpoint",
                operation_id=operation_id,
                artifact_id=verification_artifact.ref.artifact_id,
            )

        # Match the command path lock order: run -> state/artifacts -> event.
        await uow.runs.lock(tenant_id=tenant_id, run_id=checkpoint.run_id)
        checkpoint = await _require_checkpoint(
            uow, tenant_id=tenant_id, operation_id=operation_id
        )
        if checkpoint.status == CheckpointStatus.COMMITTED:
            return await _replay_committed_noop(
                uow,
                tenant_id=tenant_id,
                checkpoint=checkpoint,
                verification_artifact=verification_artifact,
                response_artifact=response_artifact,
                noop_result_artifact_id=noop_result_artifact_id,
                step_event_id=step_event_id,
                reason_code=reason_code,
                dropped_count=dropped_count,
                committed_at=committed_at,
            )
        if (
            checkpoint.status != CheckpointStatus.VERIFIED
            or checkpoint.verification_artifact != verification_artifact.ref
        ):
            raise CheckpointConflict(
                "checkpoint moved before no-op commit",
                operation_id=operation_id,
            )

        state = await uow.sessions.get(
            tenant_id=tenant_id, session_id=checkpoint.session_id
        )
        if canonical_hash(state) != checkpoint.state_before_hash:
            raise CheckpointConflict(
                "session state moved since prepare; re-prepare the operation",
                operation_id=operation_id,
                session_id=checkpoint.session_id,
            )

        result, noop_artifact = _build_noop_artifact(
            checkpoint=checkpoint,
            verification_artifact=verification_artifact,
            response_artifact=response_artifact,
            noop_result_artifact_id=noop_result_artifact_id,
            step_event_id=step_event_id,
            reason_code=reason_code,
            dropped_count=dropped_count,
            committed_at=committed_at,
        )
        await uow.artifacts.put(tenant_id=tenant_id, record=verification_artifact)
        stored_noop = await uow.artifacts.put(
            tenant_id=tenant_id, record=noop_artifact
        )
        stored_response = await uow.artifacts.put(
            tenant_id=tenant_id, record=response_artifact
        )
        next_checkpoint = mark_committed(
            checkpoint,
            domain_result_artifact=stored_noop.ref,
            response_artifact=stored_response.ref,
            state_after_hash=checkpoint.state_before_hash,
            occurred_at=committed_at,
        )
        await _cas_or_conflict(
            uow,
            tenant_id=tenant_id,
            expected_revision=checkpoint.revision,
            checkpoint=next_checkpoint,
        )
        await uow.capture.append_event(
            tenant_id=tenant_id,
            run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=step_event_id,
                occurred_at=committed_at,
                session_id=checkpoint.session_id,
                turn_id=checkpoint.turn_id,
                operation_id=operation_id,
                event_type="workflow.step.completed",
                stage=stage,
                status=ExecutionStatus.OK,
                input_artifacts=(verification_artifact.ref,),
                output_artifacts=(stored_noop.ref, stored_response.ref),
                state_before_hash=checkpoint.state_before_hash,
                state_after_hash=checkpoint.state_before_hash,
                metadata_json=canonical_json(
                    {
                        "accepted_count": 0,
                        "dropped_count": dropped_count,
                        "reason": reason_code,
                    }
                ),
            ),
        )
        await uow.commit()
        return next_checkpoint, result


async def fail_operation(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
    failure_artifact: ArtifactRecord,
    reason_code: str,
    stage: str = "turn.interpret",
    event_id: UUID,
    occurred_at: datetime,
) -> OperationCheckpoint:
    """終局失敗;committed 不可改寫、prepared 必須先有 attempt(contract 由
    checkpoint transition 函式把關)。同 artifact/reason 重呼叫冪等。"""
    async with uow_factory() as uow:
        checkpoint = await _require_checkpoint(uow, tenant_id=tenant_id,
                                               operation_id=operation_id)
        stored = await uow.artifacts.put(tenant_id=tenant_id, record=failure_artifact)
        next_checkpoint = mark_failed(
            checkpoint, failure_artifact=stored.ref, reason_code=reason_code,
            occurred_at=occurred_at)
        if next_checkpoint == checkpoint:      # already failed with same outcome
            return checkpoint
        await _cas_or_conflict(uow, tenant_id=tenant_id,
                               expected_revision=checkpoint.revision,
                               checkpoint=next_checkpoint)
        await uow.capture.append_event(
            tenant_id=tenant_id, run_id=checkpoint.run_id,
            draft=ExecutionEventDraft(
                event_id=event_id, occurred_at=occurred_at,
                session_id=checkpoint.session_id, turn_id=checkpoint.turn_id,
                operation_id=operation_id, event_type="workflow.step.failed",
                stage=stage, status=ExecutionStatus.FAILED,
                output_artifacts=(stored.ref,)))
        await uow.commit()
        return next_checkpoint
