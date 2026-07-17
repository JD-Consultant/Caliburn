"""Explicit durable executor for the fixed-replay turn.interpret operation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid5

from pydantic import ValidationError, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.commands import ApplyEvidenceCommand
from app.interview_vnext.domain.evidence import Evidence
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import NonEmptyText, StableName
from app.interview_vnext.domain.reducers import ReductionResult
from app.interview_vnext.llm.context import (
    CONTEXT_PACKET_ADAPTER,
    TURN_INTERPRET_CONTEXT_POLICY_V1,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.operation import OperationSpec
from app.interview_vnext.llm.operation_documents import (
    TURN_INTERPRET_PROMPT_PATH,
    turn_interpret_operation,
)
from app.interview_vnext.llm.port import (
    LlmPort,
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
    ModelMessage,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
)
from app.interview_vnext.llm.schema_exports import published_schema
from app.interview_vnext.llm.turn_interpret import (
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    build_inline_artifact,
)
from app.interview_vnext.observability.checkpoint import (
    CheckpointStatus,
    OperationCheckpoint,
)
from app.interview_vnext.persistence.errors import CheckpointConflict

from .context_builder import ContextBuilder
from .durable_operations import (
    AttemptOutcome,
    claim_attempt_for_provider,
    commit_verified_noop_operation,
    commit_verified_operation,
    prepare_operation,
    record_attempt_result,
    record_verification,
)
from .noop_result import OperationNoopResult
from .persistence import AttemptStatus, OperationAttempt, VNextUnitOfWork
from .turn_interpret import (
    accepted_evidence,
    turn_interpret_input_from_context,
    verify_turn_interpret_output,
)


MODEL_REQUEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-request.v1.schema.json"
)
MODEL_RESULT_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-result.v1.schema.json"
)
TURN_INPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json"
)
TURN_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json"
)
TURN_REPORT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-verification-report.v1.schema.json"
)
CONTEXT_PACKET_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-packet.v1.schema.json"
)
CONTEXT_MANIFEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-selection-manifest.v1.schema.json"
)
CONTEXT_BUDGET_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-budget-report.v1.schema.json"
)


class TurnExecutionStatus(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"


class TurnInterpretProviderProfile(DomainModel):
    provider: StableName
    requested_model: NonEmptyText


class TurnInterpretExecutionOutcome(DomainModel):
    schema_version: Literal["turn_interpret_execution_outcome.v1"] = (
        "turn_interpret_execution_outcome.v1"
    )
    status: TurnExecutionStatus
    checkpoint: OperationCheckpoint
    provider_result: ModelCallResult | None = None
    verification_report: TurnInterpretVerificationReport | None = None
    accepted_evidence: tuple[Evidence, ...] = ()
    reduction_result: ReductionResult | None = None
    noop_result: OperationNoopResult | None = None
    response_artifact: ArtifactRef | None = None
    reason_code: StableName | None = None

    @model_validator(mode="after")
    def outcome_matches_checkpoint(self) -> "TurnInterpretExecutionOutcome":
        if self.status == TurnExecutionStatus.COMMITTED:
            if self.checkpoint.status != CheckpointStatus.COMMITTED:
                raise ValueError("committed outcome requires a committed checkpoint")
            if self.verification_report is None or self.response_artifact is None:
                raise ValueError("committed outcome requires report and response artifact")
            if (self.reduction_result is None) == (self.noop_result is None):
                raise ValueError("committed outcome requires exactly one domain/no-op result")
        elif self.status == TurnExecutionStatus.FAILED:
            if self.checkpoint.status != CheckpointStatus.FAILED:
                raise ValueError("failed outcome requires a failed checkpoint")
            if self.reason_code is None:
                raise ValueError("failed outcome requires a reason code")
        elif self.checkpoint.status not in {
            CheckpointStatus.PREPARED,
            CheckpointStatus.CALLING,
            CheckpointStatus.PROVIDER_COMPLETED,
            CheckpointStatus.VERIFIED,
        }:
            raise ValueError("pending outcome has a terminal checkpoint")
        return self


def turn_execution_uuid(operation_id: UUID, label: str) -> UUID:
    """Deterministic IDs make exact operation replay inspectable and idempotent."""

    return uuid5(operation_id, label)


def _artifact(
    *,
    operation_id: UUID,
    label: str,
    kind: str,
    media_type: str,
    payload,
    run_id: UUID,
    session_id: UUID,
    turn_id: UUID,
    created_at: datetime,
    schema_id: str | None = None,
    attempt_id: UUID | None = None,
    contains_test_data: bool = False,
) -> ArtifactRecord:
    return build_inline_artifact(
        artifact_id=turn_execution_uuid(operation_id, label),
        kind=kind,
        media_type=media_type,
        payload=payload,
        schema_id=schema_id,
        run_id=run_id,
        session_id=session_id,
        turn_id=turn_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        created_at=created_at,
        contains_test_data=contains_test_data,
    )


async def _load_state(
    uow_factory: Callable[[], VNextUnitOfWork], *, tenant_id: UUID, session_id: UUID
):
    async with uow_factory() as uow:
        return await uow.sessions.get(tenant_id=tenant_id, session_id=session_id)


async def _load_checkpoint(
    uow_factory: Callable[[], VNextUnitOfWork], *, tenant_id: UUID, operation_id: UUID
) -> OperationCheckpoint | None:
    async with uow_factory() as uow:
        return await uow.checkpoints.get_by_operation(
            tenant_id=tenant_id, operation_id=operation_id
        )


async def _load_artifact(
    uow_factory: Callable[[], VNextUnitOfWork], *, tenant_id: UUID, artifact_id: UUID
) -> ArtifactRecord:
    async with uow_factory() as uow:
        return await uow.artifacts.get(tenant_id=tenant_id, artifact_id=artifact_id)


async def _load_attempt(
    uow_factory: Callable[[], VNextUnitOfWork], *, tenant_id: UUID, attempt_id: UUID
) -> OperationAttempt:
    async with uow_factory() as uow:
        attempt = await uow.attempts.get(tenant_id=tenant_id, attempt_id=attempt_id)
        if attempt is None:
            raise CheckpointConflict("checkpoint references a missing operation attempt")
        return attempt


async def _supporting_artifacts_for_result(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    result: ModelCallResult,
) -> tuple[ArtifactRecord, ...]:
    refs = tuple(
        dict.fromkeys(
            ref
            for ref in (
                result.visible_response_artifact,
                result.failure.error_artifact if result.failure else None,
            )
            if ref is not None
        )
    )
    return tuple(
        [
            await _load_artifact(
                uow_factory,
                tenant_id=tenant_id,
                artifact_id=ref.artifact_id,
            )
            for ref in refs
        ]
    )


def _request_artifact(
    request: ModelCallRequest, *, contains_test_data: bool
) -> ArtifactRecord:
    return _artifact(
        operation_id=request.operation_id,
        label=f"attempt/{request.attempt}/request",
        kind="model.request",
        media_type="application/json",
        payload=request,
        schema_id=MODEL_REQUEST_SCHEMA_ID,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        attempt_id=request.attempt_id,
        created_at=request.created_at,
        contains_test_data=contains_test_data,
    )


def _validate_result(request: ModelCallRequest, envelope: ModelCallEnvelope) -> None:
    result = envelope.result
    expected = (
        request.run_id,
        request.session_id,
        request.turn_id,
        request.operation_id,
        request.attempt_id,
        request.attempt,
        request.operation_name,
        request.operation_definition_hash,
        request.provider,
        request.requested_model,
        request.prompt_hash,
        request.output_schema_id,
        request.output_schema_hash,
        request.context_hash,
    )
    actual = (
        result.run_id,
        result.session_id,
        result.turn_id,
        result.operation_id,
        result.attempt_id,
        result.attempt,
        result.operation_name,
        result.operation_definition_hash,
        result.provider,
        result.requested_model,
        result.prompt_hash,
        result.output_schema_id,
        result.output_schema_hash,
        result.context_hash,
    )
    if actual != expected or result.started_at < request.created_at:
        raise CheckpointConflict("model result identity does not match request")


def _attempt_classification(
    *, result: ModelCallResult, local_output_valid: bool, attempt: int,
    operation: OperationSpec,
) -> tuple[AttemptOutcome, str, bool]:
    schema_repair = (
        result.outcome == ModelOutcome.SUCCEEDED
        and not local_output_valid
        and attempt <= operation.repair_policy.schema_repair_attempts
        and attempt < operation.max_attempts
    )
    if result.outcome == ModelOutcome.SUCCEEDED and local_output_valid:
        return AttemptOutcome.SUCCEEDED, "provider_succeeded", False
    if schema_repair:
        return AttemptOutcome.RETRYABLE_FAILURE, "output_schema_invalid", True
    if (
        result.outcome == ModelOutcome.FAILED
        and result.failure is not None
        and result.failure.retryable
        and attempt < operation.max_attempts
    ):
        return AttemptOutcome.RETRYABLE_FAILURE, result.failure.reason_code, False
    if result.outcome == ModelOutcome.REFUSED:
        return AttemptOutcome.NON_RETRYABLE_FAILURE, "provider_refused", False
    if result.outcome == ModelOutcome.INCOMPLETE:
        return (
            AttemptOutcome.NON_RETRYABLE_FAILURE,
            f"provider_incomplete_{result.finish_reason.value}",
            False,
        )
    if result.failure is not None:
        return AttemptOutcome.NON_RETRYABLE_FAILURE, result.failure.reason_code, False
    return AttemptOutcome.NON_RETRYABLE_FAILURE, "output_schema_invalid", False


def _local_output(
    result: ModelCallResult,
) -> tuple[TurnInterpretOutput | None, str | None]:
    if result.outcome != ModelOutcome.SUCCEEDED or result.parsed_output is None:
        return None, None
    try:
        return TurnInterpretOutput.model_validate(result.parsed_output.load()), None
    except ValidationError as exc:
        errors = tuple(
            {
                "location": tuple(str(part) for part in item["loc"]),
                "type": item["type"],
                "message": item["msg"],
            }
            for item in exc.errors(include_url=False, include_context=False)
        )
        return None, canonical_json({"errors": errors})
    except (TypeError, ValueError):
        return None, canonical_json(
            {
                "errors": (
                    {
                        "location": (),
                        "type": "local_contract_error",
                        "message": "parsed output is not a valid turn contract",
                    },
                )
            }
        )


def _retry_request(
    previous: ModelCallRequest,
    result: ModelCallResult,
    *,
    next_attempt: int,
    operation: OperationSpec,
    schema_repair: bool,
    local_validation_errors: str | None,
) -> ModelCallRequest:
    attempt_id = turn_execution_uuid(
        previous.operation_id, f"attempt/{next_attempt}"
    )
    messages = previous.messages
    if schema_repair:
        if local_validation_errors is None:
            raise CheckpointConflict(
                "schema repair requires deterministic local validation errors"
            )
        repair_text = (
            messages[-1].text
            + "\n\nSCHEMA_REPAIR: The previous visible output failed local contract "
            "validation. Return a fresh complete object using the same context; "
            "do not explain or reuse malformed JSON.\nVALIDATION_ERRORS: "
            + local_validation_errors
        )
        messages = (*messages[:-1], ModelMessage(role=MessageRole.USER, text=repair_text))
    created_at = result.completed_at
    return previous.model_copy(
        update={
            "attempt_id": attempt_id,
            "attempt": next_attempt,
            "idempotency_key": (
                f"{previous.idempotency_key.split(':attempt:', 1)[0]}"
                f":attempt:{next_attempt}"
            ),
            "messages": messages,
            "created_at": created_at,
            "deadline_at": created_at + timedelta(milliseconds=operation.timeout_ms),
        }
    )


async def _fresh_request(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    session_id: UUID,
    employee_turn_id: UUID,
    operation_id: UUID,
    idempotency_key: str,
    operation: OperationSpec,
    profile: TurnInterpretProviderProfile,
    started_at: datetime,
    contains_test_data: bool,
) -> tuple[OperationCheckpoint, ModelCallRequest]:
    state = await _load_state(
        uow_factory, tenant_id=tenant_id, session_id=session_id
    )
    context = ContextBuilder().build_turn_interpret(
        state=state,
        employee_turn_id=employee_turn_id,
        operation_id=operation_id,
        operation_definition_hash=operation.definition_hash,
        policy=TURN_INTERPRET_CONTEXT_POLICY_V1,
    )
    input_value = turn_interpret_input_from_context(context.packet)
    prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
    output_schema = published_schema("turn-interpret-output.v1.schema.json")
    common = dict(
        operation_id=operation_id,
        run_id=run_id,
        session_id=session_id,
        turn_id=employee_turn_id,
        created_at=started_at,
        contains_test_data=contains_test_data,
    )
    prompt_artifact = _artifact(
        **common,
        label="prompt",
        kind="prompt.template",
        media_type="text/markdown; charset=utf-8",
        payload=prompt,
    )
    schema_artifact = _artifact(
        **common,
        label="output-schema",
        kind="schema.output",
        media_type="application/json",
        payload=output_schema,
        schema_id=TURN_OUTPUT_SCHEMA_ID,
    )
    context_artifact = _artifact(
        **common,
        label="context-packet",
        kind="context.packet",
        media_type="application/json",
        payload=context.packet,
        schema_id=CONTEXT_PACKET_SCHEMA_ID,
    )
    manifest_artifact = _artifact(
        **common,
        label="context-manifest",
        kind="context.selection_manifest",
        media_type="application/json",
        payload=context.manifest,
        schema_id=CONTEXT_MANIFEST_SCHEMA_ID,
    )
    budget_artifact = _artifact(
        **common,
        label="context-budget",
        kind="context.budget_report",
        media_type="application/json",
        payload=context.budget,
        schema_id=CONTEXT_BUDGET_SCHEMA_ID,
    )
    input_artifact = _artifact(
        **common,
        label="turn-input",
        kind="operation.input",
        media_type="application/json",
        payload=input_value,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    attempt_id = turn_execution_uuid(operation_id, "attempt/1")
    request = ModelCallRequest(
        run_id=run_id,
        session_id=session_id,
        turn_id=employee_turn_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        attempt=1,
        operation_name=operation.name,
        operation_definition_hash=operation.definition_hash,
        idempotency_key=f"{idempotency_key}:attempt:1",
        provider=profile.provider,
        requested_model=profile.requested_model,
        quality_profile=operation.quality_profile,
        instructions=prompt,
        messages=(
            ModelMessage(role=MessageRole.USER, text=canonical_json(input_value)),
        ),
        prompt_artifact=prompt_artifact.ref,
        output_schema_id=TURN_OUTPUT_SCHEMA_ID,
        output_schema_artifact=schema_artifact.ref,
        context_artifact=context_artifact.ref,
        selection_manifest_artifact=manifest_artifact.ref,
        deadline_at=started_at + timedelta(milliseconds=operation.timeout_ms),
        created_at=started_at,
        max_output_tokens=operation.max_output_tokens,
    )
    request_artifact = _request_artifact(
        request, contains_test_data=contains_test_data
    )
    checkpoint = await prepare_operation(
        uow_factory,
        tenant_id=tenant_id,
        run_id=run_id,
        session_id=session_id,
        checkpoint_id=turn_execution_uuid(operation_id, "checkpoint"),
        operation_id=operation_id,
        operation_name=operation.name,
        operation_definition_hash=operation.definition_hash,
        idempotency_key=idempotency_key,
        request_artifact=request_artifact,
        extra_request_artifacts=(
            prompt_artifact,
            schema_artifact,
            context_artifact,
            manifest_artifact,
            budget_artifact,
            input_artifact,
        ),
        expected_state_hash=context.packet.state_hash,
        turn_id=employee_turn_id,
        step_event_id=turn_execution_uuid(operation_id, "event/prepared"),
        occurred_at=started_at,
    )
    return checkpoint, request


async def _request_for_checkpoint(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
) -> ModelCallRequest:
    if checkpoint.active_attempt_id is not None:
        attempt = await _load_attempt(
            uow_factory,
            tenant_id=tenant_id,
            attempt_id=checkpoint.active_attempt_id,
        )
        artifact_id = attempt.request_artifact_id
    else:
        artifact_id = checkpoint.request_artifact.artifact_id
    record = await _load_artifact(
        uow_factory, tenant_id=tenant_id, artifact_id=artifact_id
    )
    return ModelCallRequest.model_validate_json(record.inline_content or "")


async def _context_for_request(
    uow_factory: Callable[[], VNextUnitOfWork],
    *, tenant_id: UUID, request: ModelCallRequest,
) -> TurnInterpretContextPacket:
    record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=request.context_artifact.artifact_id,
    )
    packet = CONTEXT_PACKET_ADAPTER.validate_json(record.inline_content or "")
    if not isinstance(packet, TurnInterpretContextPacket):
        raise CheckpointConflict("turn operation references a non-turn context packet")
    return packet


async def _report_for_checkpoint(
    uow_factory: Callable[[], VNextUnitOfWork],
    *, tenant_id: UUID, checkpoint: OperationCheckpoint,
) -> tuple[TurnInterpretVerificationReport, ArtifactRecord]:
    assert checkpoint.verification_artifact is not None
    record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=checkpoint.verification_artifact.artifact_id,
    )
    return (
        TurnInterpretVerificationReport.model_validate_json(
            record.inline_content or ""
        ),
        record,
    )


async def _committed_outcome(
    uow_factory: Callable[[], VNextUnitOfWork],
    *, tenant_id: UUID, checkpoint: OperationCheckpoint,
) -> TurnInterpretExecutionOutcome:
    report, _ = await _report_for_checkpoint(
        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
    )
    assert checkpoint.domain_result_artifact is not None
    assert checkpoint.response_artifact is not None
    domain_record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=checkpoint.domain_result_artifact.artifact_id,
    )
    reduction = None
    noop = None
    if domain_record.ref.kind == "operation.noop_result":
        noop = OperationNoopResult.model_validate_json(domain_record.inline_content or "")
    else:
        reduction = ReductionResult.model_validate_json(domain_record.inline_content or "")
    return TurnInterpretExecutionOutcome(
        status=TurnExecutionStatus.COMMITTED,
        checkpoint=checkpoint,
        verification_report=report,
        accepted_evidence=tuple(
            item.evidence for item in report.decisions if item.accepted
        ),
        reduction_result=reduction,
        noop_result=noop,
        response_artifact=checkpoint.response_artifact,
    )


async def _commit_report(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    checkpoint: OperationCheckpoint,
    report: TurnInterpretVerificationReport,
    verification_artifact: ArtifactRecord,
    output: TurnInterpretOutput,
    provider_result: ModelCallResult,
    committed_at: datetime,
    contains_test_data: bool,
) -> TurnInterpretExecutionOutcome:
    evidence = accepted_evidence(
        report=report,
        session_id=checkpoint.session_id,
        turn_id=checkpoint.turn_id,
        operation_id=checkpoint.operation_id,
    )
    if evidence:
        state = await _load_state(
            uow_factory,
            tenant_id=tenant_id,
            session_id=checkpoint.session_id,
        )
        command = ApplyEvidenceCommand(
            command_id=turn_execution_uuid(checkpoint.operation_id, "command/evidence"),
            expected_state_version=state.session.state_version,
            occurred_at=committed_at,
            turn_id=checkpoint.turn_id,
            observations=evidence,
        )
        next_checkpoint, reduction = await commit_verified_operation(
            uow_factory,
            tenant_id=tenant_id,
            operation_id=checkpoint.operation_id,
            run_id=run_id,
            command=command,
            response_payload=output,
            response_artifact_id=turn_execution_uuid(
                checkpoint.operation_id, "response"
            ),
            command_artifact_id=turn_execution_uuid(
                checkpoint.operation_id, "command-artifact"
            ),
            reduction_artifact_id=turn_execution_uuid(
                checkpoint.operation_id, "reduction-artifact"
            ),
            transition_event_id=turn_execution_uuid(
                checkpoint.operation_id, "event/evidence-committed"
            ),
            step_event_id=turn_execution_uuid(
                checkpoint.operation_id, "event/completed"
            ),
            committed_at=committed_at,
            request_idempotency_key=checkpoint.idempotency_key,
        )
        return TurnInterpretExecutionOutcome(
            status=TurnExecutionStatus.COMMITTED,
            checkpoint=next_checkpoint,
            provider_result=provider_result,
            verification_report=report,
            accepted_evidence=evidence,
            reduction_result=reduction,
            response_artifact=next_checkpoint.response_artifact,
        )

    response_artifact = _artifact(
        operation_id=checkpoint.operation_id,
        label="response",
        kind="operation.response",
        media_type="application/json",
        payload=output,
        run_id=run_id,
        session_id=checkpoint.session_id,
        turn_id=checkpoint.turn_id,
        created_at=committed_at,
        contains_test_data=contains_test_data,
    )
    next_checkpoint, noop = await commit_verified_noop_operation(
        uow_factory,
        tenant_id=tenant_id,
        operation_id=checkpoint.operation_id,
        response_artifact=response_artifact,
        verification_artifact=verification_artifact,
        noop_result_artifact_id=turn_execution_uuid(
            checkpoint.operation_id, "noop-result"
        ),
        step_event_id=turn_execution_uuid(
            checkpoint.operation_id, "event/completed"
        ),
        committed_at=committed_at,
        dropped_count=report.dropped_count,
    )
    return TurnInterpretExecutionOutcome(
        status=TurnExecutionStatus.COMMITTED,
        checkpoint=next_checkpoint,
        provider_result=provider_result,
        verification_report=report,
        noop_result=noop,
        response_artifact=response_artifact.ref,
    )


async def execute_turn_interpret(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    session_id: UUID,
    employee_turn_id: UUID,
    operation_id: UUID,
    idempotency_key: str,
    llm: LlmPort,
    profile: TurnInterpretProviderProfile,
    started_at: datetime,
    now: datetime,
    operation: OperationSpec | None = None,
    contains_test_data: bool = False,
) -> TurnInterpretExecutionOutcome:
    """Drive one explicit turn operation without holding a UoW across provider I/O."""

    operation = operation or turn_interpret_operation()
    expected_operation = turn_interpret_operation()
    if operation != expected_operation:
        raise ValueError("executor only accepts the committed turn.interpret operation")
    if operation.repair_policy.semantic_repair_attempts != 0:
        raise ValueError("V3 executor does not support semantic repair")

    checkpoint = await _load_checkpoint(
        uow_factory, tenant_id=tenant_id, operation_id=operation_id
    )
    callable_attempt_ids: set[UUID] = set()
    if checkpoint is None:
        checkpoint, request = await _fresh_request(
            uow_factory,
            tenant_id=tenant_id,
            run_id=run_id,
            session_id=session_id,
            employee_turn_id=employee_turn_id,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            operation=operation,
            profile=profile,
            started_at=started_at,
            contains_test_data=contains_test_data,
        )
    else:
        if (
            checkpoint.run_id != run_id
            or checkpoint.session_id != session_id
            or checkpoint.turn_id != employee_turn_id
            or checkpoint.operation_definition_hash != operation.definition_hash
            or checkpoint.idempotency_key != idempotency_key
        ):
            raise CheckpointConflict("existing checkpoint scope/definition mismatch")
        if checkpoint.status == CheckpointStatus.COMMITTED:
            return await _committed_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
        if checkpoint.status == CheckpointStatus.FAILED:
            return TurnInterpretExecutionOutcome(
                status=TurnExecutionStatus.FAILED,
                checkpoint=checkpoint,
                reason_code=checkpoint.failure_reason_code,
            )
        request = await _request_for_checkpoint(
            uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
        )
        if (
            request.provider != profile.provider
            or request.requested_model != profile.requested_model
        ):
            raise CheckpointConflict(
                "provider profile does not match the persisted model request"
            )

    while True:
        if checkpoint.status == CheckpointStatus.PREPARED:
            request_artifact = await _load_artifact(
                uow_factory,
                tenant_id=tenant_id,
                artifact_id=checkpoint.request_artifact.artifact_id,
            )
            checkpoint, _attempt, claimed = await claim_attempt_for_provider(
                uow_factory,
                tenant_id=tenant_id,
                operation_id=operation_id,
                attempt_id=request.attempt_id,
                provider=profile.provider,
                requested_model=profile.requested_model,
                deadline_at=request.deadline_at,
                max_attempts=operation.max_attempts,
                request_artifact=request_artifact,
                call_event_id=turn_execution_uuid(
                    operation_id, f"event/attempt/{request.attempt}/started"
                ),
                occurred_at=request.created_at,
            )
            if claimed:
                callable_attempt_ids.add(request.attempt_id)

        if checkpoint.status == CheckpointStatus.CALLING:
            assert checkpoint.active_attempt_id is not None
            attempt = await _load_attempt(
                uow_factory,
                tenant_id=tenant_id,
                attempt_id=checkpoint.active_attempt_id,
            )
            request_record = await _load_artifact(
                uow_factory,
                tenant_id=tenant_id,
                artifact_id=attempt.request_artifact_id,
            )
            request = ModelCallRequest.model_validate_json(
                request_record.inline_content or ""
            )
            if attempt.status == AttemptStatus.CALLING:
                if now > request.deadline_at:
                    timeout_result = ModelCallResult(
                        run_id=request.run_id,
                        session_id=request.session_id,
                        turn_id=request.turn_id,
                        operation_id=request.operation_id,
                        attempt_id=request.attempt_id,
                        attempt=request.attempt,
                        operation_name=request.operation_name,
                        operation_definition_hash=request.operation_definition_hash,
                        provider=request.provider,
                        requested_model=request.requested_model,
                        resolved_model=request.requested_model,
                        outcome=ModelOutcome.FAILED,
                        finish_reason=FinishReason.PROVIDER_ERROR,
                        failure=ModelFailure(
                            kind=FailureKind.TRANSPORT_TIMEOUT,
                            reason_code="provider.timeout",
                            retryable=True,
                            safe_message="Attempt deadline elapsed before a durable result.",
                        ),
                        usage=TokenUsage(
                            limitations=("no provider usage available after timeout",)
                        ),
                        latency_ms=max(
                            0,
                            int(
                                (request.deadline_at - request.created_at)
                                .total_seconds()
                                * 1000
                            ),
                        ),
                        started_at=request.created_at,
                        completed_at=max(now, request.deadline_at),
                        prompt_hash=request.prompt_hash,
                        output_schema_id=request.output_schema_id,
                        output_schema_hash=request.output_schema_hash,
                        context_hash=request.context_hash,
                    )
                    envelope = ModelCallEnvelope(
                        result=timeout_result, supporting_artifacts=()
                    )
                elif request.attempt_id not in callable_attempt_ids:
                    return TurnInterpretExecutionOutcome(
                        status=TurnExecutionStatus.PENDING,
                        checkpoint=checkpoint,
                    )
                else:
                    envelope = await llm.generate_structured(request)
                _validate_result(request, envelope)
                result = envelope.result
                local_output, local_validation_errors = _local_output(result)
                classification, reason, schema_repair = _attempt_classification(
                    result=result,
                    local_output_valid=local_output is not None,
                    attempt=request.attempt,
                    operation=operation,
                )
                result_artifact = _artifact(
                    operation_id=operation_id,
                    label=f"attempt/{request.attempt}/result",
                    kind="model.result",
                    media_type="application/json",
                    payload=result,
                    schema_id=MODEL_RESULT_SCHEMA_ID,
                    run_id=run_id,
                    session_id=session_id,
                    turn_id=employee_turn_id,
                    attempt_id=request.attempt_id,
                    created_at=result.completed_at,
                    contains_test_data=contains_test_data,
                )
                checkpoint = await record_attempt_result(
                    uow_factory,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    attempt_id=request.attempt_id,
                    result_artifact=result_artifact,
                    extra_result_artifacts=envelope.supporting_artifacts,
                    outcome=classification,
                    max_attempts=operation.max_attempts,
                    failure_reason_code=reason,
                    event_id=turn_execution_uuid(
                        operation_id, f"event/attempt/{request.attempt}/result"
                    ),
                    occurred_at=result.completed_at,
                )
                if checkpoint.status == CheckpointStatus.FAILED:
                    return TurnInterpretExecutionOutcome(
                        status=TurnExecutionStatus.FAILED,
                        checkpoint=checkpoint,
                        provider_result=result,
                        reason_code=checkpoint.failure_reason_code,
                    )
                if classification == AttemptOutcome.RETRYABLE_FAILURE:
                    request = _retry_request(
                        request,
                        result,
                        next_attempt=request.attempt + 1,
                        operation=operation,
                        schema_repair=schema_repair,
                        local_validation_errors=local_validation_errors,
                    )
                    retry_artifact = _request_artifact(
                        request, contains_test_data=contains_test_data
                    )
                    checkpoint, _attempt, claimed = await claim_attempt_for_provider(
                        uow_factory,
                        tenant_id=tenant_id,
                        operation_id=operation_id,
                        attempt_id=request.attempt_id,
                        provider=profile.provider,
                        requested_model=profile.requested_model,
                        deadline_at=request.deadline_at,
                        max_attempts=operation.max_attempts,
                        request_artifact=retry_artifact,
                        call_event_id=turn_execution_uuid(
                            operation_id,
                            f"event/attempt/{request.attempt}/started",
                        ),
                        occurred_at=request.created_at,
                    )
                    if claimed:
                        callable_attempt_ids.add(request.attempt_id)
                    continue
            else:
                if attempt.result_artifact_id is None:
                    raise CheckpointConflict(
                        "recorded attempt is missing its result artifact"
                    )
                result_record = await _load_artifact(
                    uow_factory,
                    tenant_id=tenant_id,
                    artifact_id=attempt.result_artifact_id,
                )
                result = ModelCallResult.model_validate_json(
                    result_record.inline_content or ""
                )
                _validate_result(
                    request,
                    ModelCallEnvelope(
                        result=result,
                        supporting_artifacts=tuple(
                            record
                            for record in await _supporting_artifacts_for_result(
                                uow_factory,
                                tenant_id=tenant_id,
                                result=result,
                            )
                        ),
                    ),
                )
                local_output, local_validation_errors = _local_output(result)
                classification, _reason, schema_repair = _attempt_classification(
                    result=result,
                    local_output_valid=local_output is not None,
                    attempt=request.attempt,
                    operation=operation,
                )
                if classification != AttemptOutcome.RETRYABLE_FAILURE:
                    raise CheckpointConflict(
                        "calling checkpoint has a non-retryable recorded result"
                    )
                request = _retry_request(
                    request,
                    result,
                    next_attempt=request.attempt + 1,
                    operation=operation,
                    schema_repair=schema_repair,
                    local_validation_errors=local_validation_errors,
                )
                retry_artifact = _request_artifact(
                    request, contains_test_data=contains_test_data
                )
                checkpoint, _attempt, claimed = await claim_attempt_for_provider(
                    uow_factory,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    attempt_id=request.attempt_id,
                    provider=profile.provider,
                    requested_model=profile.requested_model,
                    deadline_at=request.deadline_at,
                    max_attempts=operation.max_attempts,
                    request_artifact=retry_artifact,
                    call_event_id=turn_execution_uuid(
                        operation_id,
                        f"event/attempt/{request.attempt}/started",
                    ),
                    occurred_at=request.created_at,
                )
                if claimed:
                    callable_attempt_ids.add(request.attempt_id)
                continue

        if checkpoint.status == CheckpointStatus.PROVIDER_COMPLETED:
            assert checkpoint.provider_result_artifact is not None
            result_record = await _load_artifact(
                uow_factory,
                tenant_id=tenant_id,
                artifact_id=checkpoint.provider_result_artifact.artifact_id,
            )
            result = ModelCallResult.model_validate_json(
                result_record.inline_content or ""
            )
            if result.parsed_output is None:
                raise CheckpointConflict("provider-completed result has no parsed output")
            output = TurnInterpretOutput.model_validate(result.parsed_output.load())
            request = await _request_for_checkpoint(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
            context = await _context_for_request(
                uow_factory, tenant_id=tenant_id, request=request
            )
            report = verify_turn_interpret_output(
                output=output, context=context, operation_id=operation_id
            )
            verified_at = result.completed_at + timedelta(microseconds=1)
            verification_artifact = _artifact(
                operation_id=operation_id,
                label="verification",
                kind="operation.verification",
                media_type="application/json",
                payload=report,
                schema_id=TURN_REPORT_SCHEMA_ID,
                run_id=run_id,
                session_id=session_id,
                turn_id=employee_turn_id,
                created_at=verified_at,
                contains_test_data=contains_test_data,
            )
            checkpoint = await record_verification(
                uow_factory,
                tenant_id=tenant_id,
                operation_id=operation_id,
                verification_artifact=verification_artifact,
                accepted=True,
                event_id=turn_execution_uuid(operation_id, "event/verified"),
                occurred_at=verified_at,
            )
        else:
            result = None
            output = None
            report = None
            verification_artifact = None

        if checkpoint.status == CheckpointStatus.VERIFIED:
            if report is None or verification_artifact is None:
                report, verification_artifact = await _report_for_checkpoint(
                    uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
                )
                assert checkpoint.provider_result_artifact is not None
                result_record = await _load_artifact(
                    uow_factory,
                    tenant_id=tenant_id,
                    artifact_id=checkpoint.provider_result_artifact.artifact_id,
                )
                result = ModelCallResult.model_validate_json(
                    result_record.inline_content or ""
                )
                output = TurnInterpretOutput.model_validate(
                    result.parsed_output.load()
                )
            assert result is not None and output is not None
            return await _commit_report(
                uow_factory,
                tenant_id=tenant_id,
                run_id=run_id,
                checkpoint=checkpoint,
                report=report,
                verification_artifact=verification_artifact,
                output=output,
                provider_result=result,
                committed_at=max(
                    checkpoint.updated_at + timedelta(microseconds=1),
                    result.completed_at + timedelta(microseconds=2),
                ),
                contains_test_data=contains_test_data,
            )

        if checkpoint.status == CheckpointStatus.COMMITTED:
            return await _committed_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
        if checkpoint.status == CheckpointStatus.FAILED:
            return TurnInterpretExecutionOutcome(
                status=TurnExecutionStatus.FAILED,
                checkpoint=checkpoint,
                reason_code=checkpoint.failure_reason_code,
            )
