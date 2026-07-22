"""Explicit durable executor for the fixed-replay turn.interpret operation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid5

from pydantic import ValidationError, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.commands import ApplyTurnInterpretationCommand
from app.interview_vnext.domain.evidence import Evidence
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import NonEmptyText, StableName
from app.interview_vnext.domain.interpretation import (
    TurnInsufficiencyCode,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.reducers import ReductionResult
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.conformance import (
    ConformanceMismatch,
    ConformancePolicy,
    ConformanceReport,
    evaluate_conformance,
    resolve_conformance_policy,
)
from app.interview_vnext.llm.context import (
    CONTEXT_PACKET_ADAPTER,
    TURN_INTERPRET_CONTEXT_POLICY_V2,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
    define_provider_execution_evidence,
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
    ResolvedModelCall,
)
from app.interview_vnext.llm.portable_schema import (
    SchemaProjectionMismatch,
    SchemaProjectionPolicy,
    SchemaProjectionReport,
    project_portable_strict_output_schema,
    resolve_schema_projection_policy,
)
from app.interview_vnext.llm.schema_ids import (
    CONFORMANCE_SCHEMA_ID,
    EXECUTION_EVIDENCE_SCHEMA_ID,
    MODEL_REQUEST_SCHEMA_ID,
    MODEL_RESULT_SCHEMA_ID,
    PROVIDER_BINDING_SCHEMA_ID,
    SCHEMA_PROJECTION_SCHEMA_ID,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
)
from app.interview_vnext.llm.schema_exports import SCHEMA_EXPORTS, published_schema
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
from app.interview_vnext.persistence.errors import (
    ArtifactNotFound,
    CheckpointConflict,
    PersistedDataCorruption,
    StateContextStale,
)

from .context_builder import ContextBuilder
from .durable_operations import (
    AttemptOutcome,
    claim_attempt_for_provider,
    commit_verified_operation,
    fail_operation,
    prepare_operation,
    record_attempt_result,
    record_verification,
)
from .noop_result import OperationNoopResult
from .persistence import AttemptStatus, OperationAttempt, VNextUnitOfWork
from .provider_gate import (
    RESULT_ARTIFACT_KIND,
    ValidatedProviderGate,
    validate_provider_gate_artifacts,
)
from .turn_interpret import (
    accepted_evidence,
    turn_interpret_input_from_context,
    turn_interpret_projection,
    verify_turn_interpret_output,
)


# A concurrent state advance is a clean, terminal, deterministic failure — never
# a rebase and never confused with persisted corruption (plan §13.2, §13.4).
STATE_CONTEXT_STALE = "state_context_stale"


def _merged_insufficiency_codes(report) -> tuple[TurnInsufficiencyCode, ...]:
    order = {code: index for index, code in enumerate(TurnInsufficiencyCode)}
    merged = set(report.model_insufficiency_codes) | set(
        report.system_insufficiency_codes
    )
    return tuple(sorted(merged, key=order.__getitem__))


# 共用 LLM contract schema IDs 收斂在 llm/schema_ids.py(R3-C1 §6.1.1);
# 這裡只留 operation-specific IDs。provider config artifact 刻意無 schema ID
# (§5.2:generic provider-config schema 不存在,以 content hash 對 binding)。
TURN_INPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-input.v2.schema.json"
)
TURN_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json"
)
TURN_REPORT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-verification-report.v2.schema.json"
)
CONTEXT_PACKET_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-packet.v2.schema.json"
)
CONTEXT_MANIFEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-selection-manifest.v2.schema.json"
)
CONTEXT_BUDGET_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-budget-report.v2.schema.json"
)
QUESTION_FRAME_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-frame.v1.schema.json"
)
INTERPRETATION_RECORD_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpretation-record.v1.schema.json"
)
TURN_COMMAND_SCHEMA_ID = (
    "https://caliburn.local/schemas/apply-turn-interpretation-command.v1.schema.json"
)
REDUCTION_RESULT_SCHEMA_ID = (
    "https://caliburn.local/schemas/reduction-result.v2.schema.json"
)
TURN_EXECUTION_OUTCOME_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-execution-outcome.v2.schema.json"
)

FRAME_ARTIFACT_KIND = "interview.question_frame_snapshot.v1"
CONTEXT_ARTIFACT_KIND = "interview.context_packet.v2"
CONTEXT_MANIFEST_ARTIFACT_KIND = "interview.context_selection_manifest.v2"
CONTEXT_BUDGET_ARTIFACT_KIND = "interview.context_budget_report.v2"
TURN_INPUT_ARTIFACT_KIND = "interview.turn_interpret_input.v2"
TURN_OUTPUT_ARTIFACT_KIND = "interview.turn_interpret_output.v2"
TURN_REPORT_ARTIFACT_KIND = "interview.turn_interpret_verification_report.v2"
INTERPRETATION_RECORD_ARTIFACT_KIND = "interview.turn_interpretation_record.v1"
TURN_COMMAND_ARTIFACT_KIND = "interview.apply_turn_interpretation_command.v1"
REDUCTION_ARTIFACT_KIND = "interview.reduction_result.v2"
TURN_OUTCOME_ARTIFACT_KIND = "interview.turn_interpret_execution_outcome.v2"


class TurnExecutionStatus(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"


def _resolve_projection_policy(binding: ProviderBinding) -> SchemaProjectionPolicy:
    """Resolve via the shared exact authority(R3-C1 §6.2;不再維護第二份邏輯)。"""

    try:
        return resolve_schema_projection_policy(binding.schema_projection_policy)
    except SchemaProjectionMismatch as exc:
        raise CheckpointConflict(str(exc)) from exc


def _resolve_conformance_policy(binding: ProviderBinding) -> ConformancePolicy:
    """Resolve via the shared exact authority(R3-C2 §6.3;不再維護第二份邏輯)。"""

    try:
        return resolve_conformance_policy(binding.conformance_policy)
    except ConformanceMismatch as exc:
        raise CheckpointConflict(str(exc)) from exc


def _project_turn_output_schema(
    policy: SchemaProjectionPolicy,
) -> tuple[dict, SchemaProjectionReport]:
    """Project the turn output schema and account for every removed constraint.

    The projected schema is byte-identical to the published portable schema (so
    the eval schema catalog and operation output contract still resolve), while
    the report documents the real projection from the raw Pydantic model.
    """

    schema_id, title, _factory = SCHEMA_EXPORTS["turn-interpret-output.v2.schema.json"]
    source = {
        **TurnInterpretOutput.model_json_schema(),
        "$id": schema_id,
        "title": title,
    }
    projected = project_portable_strict_output_schema(
        source, source_schema_id=schema_id, target_profile=policy.target_profile
    )
    return projected.schema, projected.report


class TurnInterpretExecutionOutcome(DomainModel):
    schema_version: Literal["turn_interpret_execution_outcome.v2"] = (
        "turn_interpret_execution_outcome.v2"
    )
    status: TurnExecutionStatus
    checkpoint: OperationCheckpoint
    context_packet_ref: ArtifactRef | None = None
    input_ref: ArtifactRef | None = None
    provider_result_ref: ArtifactRef | None = None
    verification_report_ref: ArtifactRef | None = None
    interpretation_record_ref: ArtifactRef | None = None
    domain_command_ref: ArtifactRef | None = None
    reduction_result_ref: ArtifactRef | None = None
    turn_output_ref: ArtifactRef | None = None
    failure_ref: ArtifactRef | None = None
    provider_result: ModelCallResult | None = None
    verification_report: TurnInterpretVerificationReport | None = None
    interpretation: TurnInterpretationRecord | None = None
    accepted_evidence: tuple[Evidence, ...] = ()
    reduction_result: ReductionResult | None = None
    # Always null on this path: a zero-evidence turn commits a receipt, so the
    # interpreter never produces a generic no-op result any more (plan §13.3).
    noop_result: OperationNoopResult | None = None
    response_artifact: ArtifactRef | None = None
    reason_code: StableName | None = None

    @model_validator(mode="after")
    def outcome_matches_checkpoint(self) -> "TurnInterpretExecutionOutcome":
        payload_refs = (
            (self.provider_result, self.provider_result_ref, "provider result"),
            (
                self.verification_report,
                self.verification_report_ref,
                "verification report",
            ),
            (
                self.interpretation,
                self.interpretation_record_ref,
                "interpretation record",
            ),
            (self.reduction_result, self.reduction_result_ref, "reduction result"),
        )
        for payload, ref, label in payload_refs:
            if payload is not None and ref is not None:
                if canonical_hash(payload) != ref.content_hash:
                    raise ValueError(f"{label} payload does not match its artifact ref")
        if (
            self.provider_result_ref is not None
            and self.checkpoint.provider_result_artifact is not None
            and self.provider_result_ref != self.checkpoint.provider_result_artifact
        ):
            raise ValueError("provider result ref does not match checkpoint")
        if (
            self.verification_report_ref is not None
            and self.checkpoint.verification_artifact is not None
            and self.verification_report_ref != self.checkpoint.verification_artifact
        ):
            raise ValueError("verification report ref does not match checkpoint")
        if (
            self.reduction_result_ref is not None
            and self.checkpoint.domain_result_artifact is not None
            and self.reduction_result_ref != self.checkpoint.domain_result_artifact
        ):
            raise ValueError("reduction ref does not match checkpoint")
        if (
            self.turn_output_ref is not None
            and self.checkpoint.response_artifact is not None
            and self.turn_output_ref != self.checkpoint.response_artifact
        ):
            raise ValueError("turn output ref does not match checkpoint")
        if self.response_artifact is not None and (
            self.turn_output_ref is None or self.response_artifact != self.turn_output_ref
        ):
            raise ValueError("legacy response ref must equal turn output ref")
        if self.status == TurnExecutionStatus.COMMITTED:
            if self.checkpoint.status != CheckpointStatus.COMMITTED:
                raise ValueError("committed outcome requires a committed checkpoint")
            if self.verification_report is None or self.response_artifact is None:
                raise ValueError("committed outcome requires report and response artifact")
            if self.reduction_result is None or self.interpretation is None:
                raise ValueError("committed outcome requires a reduction and a receipt")
            if any(
                ref is None
                for ref in (
                    self.context_packet_ref,
                    self.input_ref,
                    self.provider_result_ref,
                    self.verification_report_ref,
                    self.interpretation_record_ref,
                    self.domain_command_ref,
                    self.reduction_result_ref,
                    self.turn_output_ref,
                )
            ):
                raise ValueError("committed outcome requires the full artifact closure")
            if self.noop_result is not None:
                raise ValueError("turn interpretation never commits a no-op result")
            if self.reason_code is not None or self.failure_ref is not None:
                raise ValueError("committed outcome cannot carry failure fields")
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


async def _load_exact_artifact(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    ref: ArtifactRef,
) -> ArtifactRecord:
    """§5.6:checkpoint/request 有 ref 時必須載入該 exact ref 並比較完整 ArtifactRef。

    ref 指向的 row 不存在同樣是 persisted-gate corruption(fail closed),不是
    可重試的 not-found。
    """

    try:
        record = await _load_artifact(
            uow_factory, tenant_id=tenant_id, artifact_id=ref.artifact_id
        )
    except ArtifactNotFound as exc:
        raise PersistedDataCorruption(
            "persisted gate artifact reference points at a missing row",
            artifact_id=ref.artifact_id,
        ) from exc
    if record.ref != ref:
        raise PersistedDataCorruption(
            "persisted artifact does not match its recorded reference",
            artifact_id=ref.artifact_id,
        )
    return record


def _require_turn_artifact(
    record: ArtifactRecord,
    *,
    checkpoint: OperationCheckpoint,
    kind: str,
    schema_id: str | None,
) -> None:
    if (
        record.run_id != checkpoint.run_id
        or record.session_id != checkpoint.session_id
        or record.turn_id != checkpoint.turn_id
        or record.operation_id != checkpoint.operation_id
        or record.attempt_id is not None
        or record.ref.kind != kind
        or record.ref.schema_id != schema_id
    ):
        raise PersistedDataCorruption(
            "turn artifact scope, kind, or schema does not match the operation",
            operation_id=checkpoint.operation_id,
            artifact_id=record.ref.artifact_id,
            artifact_kind=record.ref.kind,
        )


async def _load_turn_artifact(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
    artifact_id: UUID,
    kind: str,
    schema_id: str | None,
    ref: ArtifactRef | None = None,
) -> ArtifactRecord:
    try:
        record = await _load_artifact(
            uow_factory, tenant_id=tenant_id, artifact_id=artifact_id
        )
    except ArtifactNotFound as exc:
        raise PersistedDataCorruption(
            "turn artifact reference points at a missing row",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        ) from exc
    if ref is not None and record.ref != ref:
        raise PersistedDataCorruption(
            "turn artifact does not match its authoritative ref",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        )
    _require_turn_artifact(
        record, checkpoint=checkpoint, kind=kind, schema_id=schema_id
    )
    return record


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


def _attempt_classification(
    *, result: ModelCallResult, conformance_eligible: bool,
    local_output_valid: bool, attempt: int, operation: OperationSpec,
) -> tuple[AttemptOutcome, str, bool]:
    """§7.4 gate precedence: wire failure → conformance → local schema.

    Returns (outcome, reason_code, is_schema_repair). Conformance is only
    consulted for a wire-succeeded result; a wire-succeeded but ineligible attempt
    is a non-retryable conformance failure whose authority is the conformance
    report (recorded by ``record_attempt_result``).
    """

    # wire failure takes precedence over any conformance/local judgement
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
    if result.outcome == ModelOutcome.FAILED and result.failure is not None:
        return AttemptOutcome.NON_RETRYABLE_FAILURE, result.failure.reason_code, False
    if result.outcome == ModelOutcome.FAILED:
        return AttemptOutcome.NON_RETRYABLE_FAILURE, "output_schema_invalid", False

    # wire succeeded: conformance gate before the local schema gate
    if not conformance_eligible:
        return AttemptOutcome.NON_RETRYABLE_FAILURE, "provider.conformance_failed", False
    if local_output_valid:
        return AttemptOutcome.SUCCEEDED, "provider_succeeded", False
    schema_repair = (
        attempt <= operation.repair_policy.schema_repair_attempts
        and attempt < operation.max_attempts
    )
    if schema_repair:
        return AttemptOutcome.RETRYABLE_FAILURE, "output_schema_invalid", True
    return AttemptOutcome.NON_RETRYABLE_FAILURE, "output_schema_invalid", False


def _evidence_artifact(
    evidence: ProviderExecutionEvidence,
    *,
    request: ModelCallRequest,
    created_at: datetime,
    contains_test_data: bool,
) -> ArtifactRecord:
    return build_inline_artifact(
        artifact_id=uuid5(request.attempt_id, "provider-execution-evidence"),
        kind="model.provider_execution_evidence",
        media_type="application/json",
        payload=evidence,
        schema_id=EXECUTION_EVIDENCE_SCHEMA_ID,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=created_at,
        contains_test_data=contains_test_data,
    )


def _conformance_artifact(
    report: ConformanceReport,
    *,
    request: ModelCallRequest,
    created_at: datetime,
    contains_test_data: bool,
) -> ArtifactRecord:
    return build_inline_artifact(
        artifact_id=uuid5(request.attempt_id, "provider-conformance"),
        kind="model.provider_conformance",
        media_type="application/json",
        payload=report,
        schema_id=CONFORMANCE_SCHEMA_ID,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=created_at,
        contains_test_data=contains_test_data,
    )


def _timeout_envelope(
    request: ModelCallRequest, *, binding: ProviderBinding, now: datetime
) -> ModelCallEnvelope:
    """Synthesize a locally-produced deadline timeout with unknown evidence (§7.1)."""

    timeout_result = ModelCallResult(
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        attempt=request.attempt,
        operation_name=request.operation_name,
        operation_definition_hash=request.operation_definition_hash,
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        resolved_model=binding.requested_model,
        outcome=ModelOutcome.FAILED,
        finish_reason=FinishReason.PROVIDER_ERROR,
        failure=ModelFailure(
            kind=FailureKind.TRANSPORT_TIMEOUT,
            reason_code="provider.timeout",
            retryable=True,
            safe_message="Attempt deadline elapsed before a durable result.",
        ),
        usage=TokenUsage(limitations=("no provider usage available after timeout",)),
        latency_ms=max(
            0,
            int((request.deadline_at - request.created_at).total_seconds() * 1000),
        ),
        started_at=request.created_at,
        completed_at=max(now, request.deadline_at),
        prompt_hash=request.prompt_hash,
        output_schema_id=request.output_schema_id,
        output_schema_hash=request.output_schema_hash,
        context_hash=request.context_hash,
    )
    evidence = define_provider_execution_evidence(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        gateway_resolved_model=None,
        upstream_provider=None,
        upstream_model=None,
        upstream_endpoint=None,
        route_strategy=None,
        upstream_attempt_count=None,
        transformation_status=TransformationStatus.UNKNOWN,
        pipeline_stages=(),
        cache_status=CacheStatus.UNKNOWN,
        provider_request_id=None,
        generation_id=None,
        usage=TokenUsage(limitations=("no provider usage available after timeout",)),
        cost_decimal=None,
        limitations=(
            "cost unavailable after transport timeout",
            "route metadata unavailable after transport timeout",
        ),
        raw_routing_artifact=None,
    )
    return ModelCallEnvelope(
        result=timeout_result,
        execution_evidence=evidence,
        supporting_artifacts=(),
    )


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
    binding: ProviderBinding,
    provider_config: object,
    started_at: datetime,
    contains_test_data: bool,
) -> tuple[OperationCheckpoint, ModelCallRequest]:
    projection_policy = _resolve_projection_policy(binding)
    _resolve_conformance_policy(binding)
    state = await _load_state(
        uow_factory, tenant_id=tenant_id, session_id=session_id
    )
    context = ContextBuilder().build_turn_interpret(
        state=state,
        employee_turn_id=employee_turn_id,
        operation_id=operation_id,
        operation_definition_hash=operation.definition_hash,
        policy=TURN_INTERPRET_CONTEXT_POLICY_V2,
    )
    input_value = turn_interpret_input_from_context(context.packet)
    prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
    output_schema, projection_report = _project_turn_output_schema(projection_policy)
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
        kind=CONTEXT_ARTIFACT_KIND,
        media_type="application/json",
        payload=context.packet,
        schema_id=CONTEXT_PACKET_SCHEMA_ID,
    )
    manifest_artifact = _artifact(
        **common,
        label="context-manifest",
        kind=CONTEXT_MANIFEST_ARTIFACT_KIND,
        media_type="application/json",
        payload=context.manifest,
        schema_id=CONTEXT_MANIFEST_SCHEMA_ID,
    )
    budget_artifact = _artifact(
        **common,
        label="context-budget",
        kind=CONTEXT_BUDGET_ARTIFACT_KIND,
        media_type="application/json",
        payload=context.budget,
        schema_id=CONTEXT_BUDGET_SCHEMA_ID,
    )
    input_artifact = _artifact(
        **common,
        label="turn-input",
        kind=TURN_INPUT_ARTIFACT_KIND,
        media_type="application/json",
        payload=input_value,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    # The frame exactly as the model was allowed to read it. Persisted separately
    # so an audit can prove which question a contextual answer resolved without
    # re-deriving it from current state (plan §13.1).
    frame_artifact = None
    if context.packet.question_frame is not None:
        frame_artifact = _artifact(
            **common,
            label="question-frame-snapshot",
            kind=FRAME_ARTIFACT_KIND,
            media_type="application/json",
            payload=context.packet.question_frame.frame,
            schema_id=QUESTION_FRAME_SCHEMA_ID,
        )
        if frame_artifact.ref.content_hash != canonical_hash(
            context.packet.question_frame.frame
        ):
            raise CheckpointConflict("question frame snapshot hash mismatch")
    binding_artifact = _artifact(
        **common,
        label="provider-binding",
        kind="model.provider_binding",
        media_type="application/json",
        payload=binding,
        schema_id=PROVIDER_BINDING_SCHEMA_ID,
    )
    if binding_artifact.ref.content_hash != canonical_hash(binding):
        raise CheckpointConflict("binding artifact content hash mismatch")
    config_artifact = _artifact(
        **common,
        label="provider-config",
        kind="provider.config",
        media_type="application/json",
        payload=provider_config,
    )
    if config_artifact.ref.content_hash != binding.provider_config_hash:
        raise CheckpointConflict(
            "provider config artifact hash does not match the binding config hash"
        )
    projection_artifact = _artifact(
        **common,
        label="schema-projection",
        kind="model.schema_projection",
        media_type="application/json",
        payload=projection_report,
        schema_id=SCHEMA_PROJECTION_SCHEMA_ID,
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
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        requested_model=binding.requested_model,
        instructions=prompt,
        messages=(
            ModelMessage(role=MessageRole.USER, text=canonical_json(input_value)),
        ),
        prompt_artifact=prompt_artifact.ref,
        output_schema_id=TURN_OUTPUT_SCHEMA_ID,
        output_schema_artifact=schema_artifact.ref,
        context_artifact=context_artifact.ref,
        selection_manifest_artifact=manifest_artifact.ref,
        binding_artifact=binding_artifact.ref,
        provider_config_artifact=config_artifact.ref,
        schema_projection_artifact=projection_artifact.ref,
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
            binding_artifact,
            config_artifact,
            projection_artifact,
        )
        + ((frame_artifact,) if frame_artifact is not None else ()),
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
    try:
        record = await _load_artifact(
            uow_factory, tenant_id=tenant_id, artifact_id=artifact_id
        )
    except ArtifactNotFound as exc:
        raise PersistedDataCorruption(
            "operation request artifact is missing",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        ) from exc
    if checkpoint.active_attempt_id is None and record.ref != checkpoint.request_artifact:
        raise PersistedDataCorruption(
            "prepared request does not match checkpoint ref",
            operation_id=checkpoint.operation_id,
        )
    if (
        record.ref.kind != "model.request"
        or record.ref.schema_id != MODEL_REQUEST_SCHEMA_ID
        or record.run_id != checkpoint.run_id
        or record.session_id != checkpoint.session_id
        or record.turn_id != checkpoint.turn_id
        or record.operation_id != checkpoint.operation_id
    ):
        raise PersistedDataCorruption(
            "operation request scope, kind, or schema is invalid",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        )
    try:
        request = ModelCallRequest.model_validate_json(record.inline_content or "")
    except ValidationError as exc:
        raise PersistedDataCorruption(
            "operation request artifact failed typed validation",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        ) from exc
    if (
        request.run_id != checkpoint.run_id
        or request.session_id != checkpoint.session_id
        or request.turn_id != checkpoint.turn_id
        or request.operation_id != checkpoint.operation_id
        or record.attempt_id != request.attempt_id
    ):
        raise PersistedDataCorruption(
            "operation request payload does not match checkpoint scope",
            operation_id=checkpoint.operation_id,
            artifact_id=artifact_id,
        )
    return request


async def _resolved_call_for_request(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    request: ModelCallRequest,
) -> ResolvedModelCall:
    """Reconstruct the resolved call from the request's immutable artifact refs.

    fresh-process recovery reads the binding and schema projection back from the
    persisted request; it never re-resolves a binding from current deployment
    config (ADR 0036 §3). R3-C2(§6.6):每個 ref 都以完整 ``ArtifactRef`` exact
    比較載入,provider config artifact 必須存在且 content hash 等於 binding
    (payload 不進 ``ResolvedModelCall``;adapter 用自己的 config hash 做第二道
    preflight)。ResolvedModelCall's own validators re-check every hash。
    """

    binding_record = await _load_exact_artifact(
        uow_factory, tenant_id=tenant_id, ref=request.binding_artifact
    )
    projection_record = await _load_exact_artifact(
        uow_factory, tenant_id=tenant_id, ref=request.schema_projection_artifact
    )
    config_record = await _load_exact_artifact(
        uow_factory, tenant_id=tenant_id, ref=request.provider_config_artifact
    )
    try:
        binding = ProviderBinding.model_validate_json(
            binding_record.inline_content or ""
        )
        projection = SchemaProjectionReport.model_validate_json(
            projection_record.inline_content or ""
        )
    except ValidationError as exc:
        raise PersistedDataCorruption(
            "persisted binding/projection artifact failed typed validation",
            operation_id=request.operation_id,
        ) from exc
    if config_record.ref.content_hash != binding.provider_config_hash:
        raise PersistedDataCorruption(
            "persisted provider config artifact does not match the binding config hash",
            operation_id=request.operation_id,
        )
    return ResolvedModelCall(
        request=request, binding=binding, schema_projection=projection
    )


async def _load_and_validate_provider_gate(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    request: ModelCallRequest,
    result_ref: ArtifactRef | None = None,
    evidence_ref: ArtifactRef | None = None,
    conformance_ref: ArtifactRef | None = None,
    result_artifact_id: UUID | None = None,
    require_eligible: bool | None,
) -> tuple[ProviderBinding, ValidatedProviderGate]:
    """§5.6:單一 recovery loader,所有 fresh-process 分支共用。

    先以 exact refs 載回 binding/config/projection 並重驗(``ResolvedModelCall``
    validators),再依 checkpoint refs 或 deterministic attempt IDs 載入
    result/evidence/conformance,交給共用 ``validate_provider_gate_artifacts()``。
    """

    resolved = await _resolved_call_for_request(
        uow_factory, tenant_id=tenant_id, request=request
    )
    binding = resolved.binding

    async def load_gate_artifact(artifact_id: UUID) -> ArtifactRecord:
        try:
            return await _load_artifact(
                uow_factory, tenant_id=tenant_id, artifact_id=artifact_id
            )
        except ArtifactNotFound as exc:
            raise PersistedDataCorruption(
                "persisted gate artifact is missing", artifact_id=artifact_id
            ) from exc

    if result_ref is not None:
        result_record = await _load_exact_artifact(
            uow_factory, tenant_id=tenant_id, ref=result_ref
        )
    else:
        assert result_artifact_id is not None
        result_record = await load_gate_artifact(result_artifact_id)
    if evidence_ref is not None:
        evidence_record = await _load_exact_artifact(
            uow_factory, tenant_id=tenant_id, ref=evidence_ref
        )
    else:
        evidence_record = await load_gate_artifact(
            uuid5(request.attempt_id, "provider-execution-evidence")
        )
    if conformance_ref is not None:
        conformance_record = await _load_exact_artifact(
            uow_factory, tenant_id=tenant_id, ref=conformance_ref
        )
    else:
        conformance_record = await load_gate_artifact(
            uuid5(request.attempt_id, "provider-conformance")
        )
    gate = validate_provider_gate_artifacts(
        request=request,
        binding=binding,
        result_artifact=result_record,
        evidence_artifact=evidence_record,
        conformance_artifact=conformance_record,
        require_eligible=require_eligible,
    )
    return binding, gate


async def _revalidate_failed_checkpoint(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
    request: ModelCallRequest,
) -> None:
    """§5.6 failed 行:重驗 provider gate 與 failure authority 後才可回 failed。"""

    assert checkpoint.failure_artifact is not None  # checkpoint model 保證
    await _load_exact_artifact(
        uow_factory, tenant_id=tenant_id, ref=checkpoint.failure_artifact
    )
    evidence_ref = checkpoint.provider_execution_evidence_artifact
    conformance_ref = checkpoint.provider_conformance_artifact
    if evidence_ref is None and conformance_ref is None:
        # pre-provider/coordinator failure:不得宣稱任何 provider 成果。
        if checkpoint.provider_result_artifact is not None:
            raise PersistedDataCorruption(
                "failed checkpoint without a provider gate cannot carry a provider result",
                operation_id=checkpoint.operation_id,
            )
        return
    result_ref = (
        checkpoint.attempt_result_artifacts[-1]
        if checkpoint.attempt_result_artifacts
        else None
    )
    if result_ref is None:
        raise PersistedDataCorruption(
            "failed provider attempt is missing its terminating result artifact",
            operation_id=checkpoint.operation_id,
        )
    # failure authority 決定 gate 的 eligibility 要求。Conformance authority
    # 必須 ineligible；result authority 可能是 wire failure，也可能是
    # wire-success + eligible 後才發現的 local output-schema failure，因此先
    # 驗完整 gate、再依 typed result + persisted reason 分流。
    if checkpoint.failure_artifact == conformance_ref:
        require_eligible = False
    elif checkpoint.failure_artifact == result_ref:
        require_eligible = None
    else:
        require_eligible = True
    _, gate = await _load_and_validate_provider_gate(
        uow_factory,
        tenant_id=tenant_id,
        request=request,
        result_ref=result_ref,
        evidence_ref=evidence_ref,
        conformance_ref=conformance_ref,
        require_eligible=require_eligible,
    )
    if checkpoint.failure_artifact == conformance_ref and (
        gate.result.outcome != ModelOutcome.SUCCEEDED
    ):
        raise PersistedDataCorruption(
            "conformance failure authority requires a wire-succeeded result",
            operation_id=checkpoint.operation_id,
        )
    if checkpoint.failure_artifact == result_ref and (
        gate.result.outcome == ModelOutcome.SUCCEEDED
    ):
        if (
            not gate.conformance.eligible
            or checkpoint.failure_reason_code != "output_schema_invalid"
        ):
            raise PersistedDataCorruption(
                "succeeded result authority requires an eligible gate and a "
                "local output-schema failure",
                operation_id=checkpoint.operation_id,
            )
    elif checkpoint.failure_artifact == result_ref and gate.conformance.eligible:
        raise PersistedDataCorruption(
            "wire failure authority requires an ineligible conformance report",
            operation_id=checkpoint.operation_id,
        )


async def _context_for_request(
    uow_factory: Callable[[], VNextUnitOfWork],
    *, tenant_id: UUID, request: ModelCallRequest, checkpoint: OperationCheckpoint,
) -> TurnInterpretContextPacket:
    record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=request.context_artifact.artifact_id,
        kind=CONTEXT_ARTIFACT_KIND,
        schema_id=CONTEXT_PACKET_SCHEMA_ID,
        ref=request.context_artifact,
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
    record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=checkpoint.verification_artifact.artifact_id,
        kind=TURN_REPORT_ARTIFACT_KIND,
        schema_id=TURN_REPORT_SCHEMA_ID,
        ref=checkpoint.verification_artifact,
    )
    return (
        TurnInterpretVerificationReport.model_validate_json(
            record.inline_content or ""
        ),
        record,
    )


async def _failed_outcome(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
) -> TurnInterpretExecutionOutcome:
    """Reconstruct only the artifacts that existed before a terminal failure."""

    request = await _request_for_checkpoint(
        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
    )
    await _context_for_request(
        uow_factory,
        tenant_id=tenant_id,
        request=request,
        checkpoint=checkpoint,
    )
    input_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=turn_execution_uuid(checkpoint.operation_id, "turn-input"),
        kind=TURN_INPUT_ARTIFACT_KIND,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    await _revalidate_failed_checkpoint(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        request=request,
    )
    provider_result = None
    provider_result_ref = checkpoint.provider_result_artifact
    if provider_result_ref is None and checkpoint.provider_execution_evidence_artifact:
        provider_result_ref = checkpoint.attempt_result_artifacts[-1]
    if provider_result_ref is not None:
        provider_record = await _load_exact_artifact(
            uow_factory, tenant_id=tenant_id, ref=provider_result_ref
        )
        try:
            provider_result = ModelCallResult.model_validate_json(
                provider_record.inline_content or ""
            )
        except ValidationError as exc:
            raise PersistedDataCorruption(
                "failed provider result failed typed validation",
                operation_id=checkpoint.operation_id,
            ) from exc
    report = None
    report_ref = checkpoint.verification_artifact
    if report_ref is not None:
        report, _ = await _report_for_checkpoint(
            uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
        )
    return TurnInterpretExecutionOutcome(
        status=TurnExecutionStatus.FAILED,
        checkpoint=checkpoint,
        context_packet_ref=request.context_artifact,
        input_ref=input_record.ref,
        provider_result_ref=provider_result_ref,
        verification_report_ref=report_ref,
        failure_ref=checkpoint.failure_artifact,
        provider_result=provider_result,
        verification_report=report,
        reason_code=checkpoint.failure_reason_code,
    )


async def _committed_outcome(
    uow_factory: Callable[[], VNextUnitOfWork],
    *, tenant_id: UUID, checkpoint: OperationCheckpoint,
) -> TurnInterpretExecutionOutcome:
    request = await _request_for_checkpoint(
        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
    )
    await _context_for_request(
        uow_factory,
        tenant_id=tenant_id,
        request=request,
        checkpoint=checkpoint,
    )
    input_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=turn_execution_uuid(checkpoint.operation_id, "turn-input"),
        kind=TURN_INPUT_ARTIFACT_KIND,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    assert checkpoint.provider_result_artifact is not None
    _, provider_gate = await _load_and_validate_provider_gate(
        uow_factory,
        tenant_id=tenant_id,
        request=request,
        result_ref=checkpoint.provider_result_artifact,
        evidence_ref=checkpoint.provider_execution_evidence_artifact,
        conformance_ref=checkpoint.provider_conformance_artifact,
        require_eligible=True,
    )
    report, _ = await _report_for_checkpoint(
        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
    )
    assert checkpoint.domain_result_artifact is not None
    assert checkpoint.response_artifact is not None
    # §5.6 committed 行:committed artifacts 也以 exact ref 載回。
    output_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=checkpoint.response_artifact.artifact_id,
        kind=TURN_OUTPUT_ARTIFACT_KIND,
        schema_id=TURN_OUTPUT_SCHEMA_ID,
        ref=checkpoint.response_artifact,
    )
    domain_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=checkpoint.domain_result_artifact.artifact_id,
        kind=REDUCTION_ARTIFACT_KIND,
        schema_id=REDUCTION_RESULT_SCHEMA_ID,
        ref=checkpoint.domain_result_artifact,
    )
    # A committed turn always holds a reduction: the no-op branch is gone, so a
    # no-op artifact here means the row predates R5-BC (plan §13.3).
    if domain_record.ref.kind == "operation.noop_result":
        raise PersistedDataCorruption(
            "committed turn interpretation references a legacy no-op result",
            operation_id=checkpoint.operation_id,
        )
    reduction = ReductionResult.model_validate_json(domain_record.inline_content or "")
    record = next(
        (
            item
            for item in reduction.state.turn_interpretations
            if item.operation_id == checkpoint.operation_id
        ),
        None,
    )
    if record is None:
        raise PersistedDataCorruption(
            "committed reduction has no receipt for the operation",
            operation_id=checkpoint.operation_id,
        )
    receipt_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=turn_execution_uuid(
            checkpoint.operation_id, "interpretation-record"
        ),
        kind=INTERPRETATION_RECORD_ARTIFACT_KIND,
        schema_id=INTERPRETATION_RECORD_SCHEMA_ID,
    )
    command_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=turn_execution_uuid(checkpoint.operation_id, "command-artifact"),
        kind=TURN_COMMAND_ARTIFACT_KIND,
        schema_id=TURN_COMMAND_SCHEMA_ID,
    )
    try:
        stored_receipt = TurnInterpretationRecord.model_validate_json(
            receipt_record.inline_content or ""
        )
        stored_command = ApplyTurnInterpretationCommand.model_validate_json(
            command_record.inline_content or ""
        )
        TurnInterpretOutput.model_validate_json(output_record.inline_content or "")
    except ValidationError as exc:
        raise PersistedDataCorruption(
            "committed turn closure failed typed validation",
            operation_id=checkpoint.operation_id,
        ) from exc
    if stored_receipt != record or stored_command.record != record:
        raise PersistedDataCorruption(
            "committed receipt, command, and reduction disagree",
            operation_id=checkpoint.operation_id,
        )
    return TurnInterpretExecutionOutcome(
        status=TurnExecutionStatus.COMMITTED,
        checkpoint=checkpoint,
        context_packet_ref=request.context_artifact,
        input_ref=input_record.ref,
        provider_result_ref=checkpoint.provider_result_artifact,
        verification_report_ref=checkpoint.verification_artifact,
        interpretation_record_ref=receipt_record.ref,
        domain_command_ref=command_record.ref,
        reduction_result_ref=domain_record.ref,
        turn_output_ref=output_record.ref,
        provider_result=provider_gate.result,
        verification_report=report,
        interpretation=record,
        accepted_evidence=tuple(
            item.evidence for item in report.decisions if item.accepted
        )
        + tuple(
            evidence
            for item in report.binding_decisions
            if item.accepted
            for evidence in item.materialized_evidence
        ),
        reduction_result=reduction,
        response_artifact=output_record.ref,
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
    request: ModelCallRequest,
    context: TurnInterpretContextPacket,
    committed_at: datetime,
    contains_test_data: bool,
) -> TurnInterpretExecutionOutcome:
    """Commit the receipt — with or without evidence — against the context snapshot.

    The expected version and hash come from the context the model actually saw,
    never from a freshly loaded state: if the session moved on while the provider
    was answering, this must fail closed rather than rebase a stale answer onto
    new state (plan §13.2).
    """

    evidence = accepted_evidence(
        report=report,
        session_id=checkpoint.session_id,
        turn_id=checkpoint.turn_id,
        operation_id=checkpoint.operation_id,
    )
    async def stale_outcome() -> TurnInterpretExecutionOutcome:
        state = await _load_state(
            uow_factory,
            tenant_id=tenant_id,
            session_id=checkpoint.session_id,
        )
        actual_hash = canonical_hash(state)
        failure_artifact = _artifact(
            operation_id=checkpoint.operation_id,
            label="state-context-stale",
            kind="operation.local_failure",
            media_type="application/json",
            payload={
                "reason_code": STATE_CONTEXT_STALE,
                "expected_state_version": context.state_version,
                "actual_state_version": state.session.state_version,
                "expected_state_hash": context.state_hash,
                "actual_state_hash": actual_hash,
            },
            run_id=run_id,
            session_id=checkpoint.session_id,
            turn_id=checkpoint.turn_id,
            created_at=committed_at,
            contains_test_data=contains_test_data,
        )
        next_checkpoint = await fail_operation(
            uow_factory,
            tenant_id=tenant_id,
            operation_id=checkpoint.operation_id,
            reason_code=STATE_CONTEXT_STALE,
            failure_artifact=failure_artifact,
            event_id=turn_execution_uuid(
                checkpoint.operation_id, "event/state-context-stale"
            ),
            occurred_at=committed_at,
        )
        return TurnInterpretExecutionOutcome(
            status=TurnExecutionStatus.FAILED,
            checkpoint=next_checkpoint,
            context_packet_ref=request.context_artifact,
            input_ref=input_record.ref,
            provider_result_ref=next_checkpoint.provider_result_artifact,
            verification_report_ref=verification_artifact.ref,
            failure_ref=next_checkpoint.failure_artifact,
            provider_result=provider_result,
            verification_report=report,
            reason_code=STATE_CONTEXT_STALE,
        )

    frame = context.question_frame.frame if context.question_frame is not None else None
    insufficiency_codes = _merged_insufficiency_codes(report)
    record = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(checkpoint.operation_id),
        session_id=checkpoint.session_id,
        employee_turn_id=checkpoint.turn_id,
        operation_id=checkpoint.operation_id,
        question_frame_id=frame.question_frame_id if frame is not None else None,
        question_frame_definition_hash=(
            frame.definition.definition_hash if frame is not None else None
        ),
        context_packet_hash=report.context_packet_hash,
        output_hash=report.output_hash,
        verification_report_hash=canonical_hash(report),
        accepted_evidence_ids=tuple(item.evidence_id for item in evidence),
        dialogue_act=report.dialogue_act,
        episode_signal=report.episode_signal,
        insufficiency_codes=insufficiency_codes,
        applied_at=committed_at,
    )
    command = ApplyTurnInterpretationCommand(
        command_id=turn_execution_uuid(
            checkpoint.operation_id, "command/interpretation"
        ),
        expected_state_version=context.state_version,
        occurred_at=committed_at,
        record=record,
        observations=evidence,
    )
    receipt_artifact = _artifact(
        operation_id=checkpoint.operation_id,
        label="interpretation-record",
        kind=INTERPRETATION_RECORD_ARTIFACT_KIND,
        media_type="application/json",
        payload=record,
        schema_id=INTERPRETATION_RECORD_SCHEMA_ID,
        run_id=run_id,
        session_id=checkpoint.session_id,
        turn_id=checkpoint.turn_id,
        created_at=committed_at,
        contains_test_data=contains_test_data,
    )
    input_record = await _load_turn_artifact(
        uow_factory,
        tenant_id=tenant_id,
        checkpoint=checkpoint,
        artifact_id=turn_execution_uuid(checkpoint.operation_id, "turn-input"),
        kind=TURN_INPUT_ARTIFACT_KIND,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    try:
        next_checkpoint, reduction, closure = await commit_verified_operation(
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
                checkpoint.operation_id, "event/interpretation-committed"
            ),
            step_event_id=turn_execution_uuid(
                checkpoint.operation_id, "event/completed"
            ),
            committed_at=committed_at,
            request_idempotency_key=checkpoint.idempotency_key,
            expected_state_hash=context.state_hash,
            additional_domain_artifacts=(receipt_artifact,),
            response_artifact_kind=TURN_OUTPUT_ARTIFACT_KIND,
            response_schema_id=TURN_OUTPUT_SCHEMA_ID,
            contains_test_data=contains_test_data,
        )
    except StateContextStale:
        return await stale_outcome()
    return TurnInterpretExecutionOutcome(
        status=TurnExecutionStatus.COMMITTED,
        checkpoint=next_checkpoint,
        context_packet_ref=request.context_artifact,
        input_ref=input_record.ref,
        provider_result_ref=next_checkpoint.provider_result_artifact,
        verification_report_ref=verification_artifact.ref,
        interpretation_record_ref=closure.additional_domain_refs[0],
        domain_command_ref=closure.command_ref,
        reduction_result_ref=closure.reduction_ref,
        turn_output_ref=closure.response_ref,
        provider_result=provider_result,
        verification_report=report,
        interpretation=record,
        accepted_evidence=evidence,
        reduction_result=reduction,
        response_artifact=closure.response_ref,
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
    binding: ProviderBinding,
    provider_config: object,
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
    if binding.operation_name != operation.name:
        raise ValueError("binding operation does not match the turn operation")
    conformance_policy = _resolve_conformance_policy(binding)

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
            binding=binding,
            provider_config=provider_config,
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
        request = await _request_for_checkpoint(
            uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
        )
        # fresh-process recovery uses the binding persisted in the request, not the
        # binding the caller happens to pass now (ADR 0036 §3).
        if (
            request.binding_id != binding.binding_id
            or request.binding_hash != binding.binding_hash
        ):
            raise CheckpointConflict(
                "provider binding does not match the persisted model request"
            )
        # §5.6:every fresh-process terminal path 先重驗 persisted provider gate,
        # 再回 idempotent outcome;不得以 refs 存在即視為正確。
        if checkpoint.status == CheckpointStatus.COMMITTED:
            return await _committed_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
        if checkpoint.status == CheckpointStatus.FAILED:
            return await _failed_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
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
                provider=binding.gateway_provider,
                requested_model=binding.requested_model,
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
                    envelope = _timeout_envelope(request, binding=binding, now=now)
                elif request.attempt_id not in callable_attempt_ids:
                    return TurnInterpretExecutionOutcome(
                        status=TurnExecutionStatus.PENDING,
                        checkpoint=checkpoint,
                    )
                else:
                    resolved_call = await _resolved_call_for_request(
                        uow_factory, tenant_id=tenant_id, request=request
                    )
                    envelope = await llm.generate_structured(resolved_call)
                # identity/gateway/conformance 驗證統一由 record_attempt_result
                # 內的 provider gate 執行(§6.5:單一 authority,不前後各做一次)。
                result = envelope.result
                conformance = evaluate_conformance(
                    policy=conformance_policy,
                    binding=binding,
                    evidence=envelope.execution_evidence,
                    wire_outcome=result.outcome,
                )
                wire_succeeded = result.outcome == ModelOutcome.SUCCEEDED
                local_output, local_validation_errors = (
                    _local_output(result)
                    if wire_succeeded and conformance.eligible
                    else (None, None)
                )
                classification, reason, schema_repair = _attempt_classification(
                    result=result,
                    conformance_eligible=conformance.eligible,
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
                evidence_artifact = _evidence_artifact(
                    envelope.execution_evidence,
                    request=request,
                    created_at=result.completed_at,
                    contains_test_data=contains_test_data,
                )
                conformance_artifact = _conformance_artifact(
                    conformance,
                    request=request,
                    created_at=result.completed_at,
                    contains_test_data=contains_test_data,
                )
                checkpoint = await record_attempt_result(
                    uow_factory,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    attempt_id=request.attempt_id,
                    result_artifact=result_artifact,
                    execution_evidence_artifact=evidence_artifact,
                    conformance_artifact=conformance_artifact,
                    extra_result_artifacts=envelope.supporting_artifacts,
                    outcome=classification,
                    max_attempts=operation.max_attempts,
                    failure_reason_code=reason,
                    result_event_id=turn_execution_uuid(
                        operation_id, f"event/attempt/{request.attempt}/result"
                    ),
                    conformance_event_id=turn_execution_uuid(
                        operation_id, f"event/attempt/{request.attempt}/conformance"
                    ),
                    occurred_at=result.completed_at,
                )
                if checkpoint.status == CheckpointStatus.FAILED:
                    return await _failed_outcome(
                        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
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
                        provider=binding.gateway_provider,
                        requested_model=binding.requested_model,
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
                # §5.6 calling+result_recorded:重驗 prior result/evidence/
                # conformance(deterministic attempt IDs)後才可建 next attempt。
                _, recorded_gate = await _load_and_validate_provider_gate(
                    uow_factory,
                    tenant_id=tenant_id,
                    request=request,
                    result_artifact_id=attempt.result_artifact_id,
                    require_eligible=None,
                )
                result = recorded_gate.result
                recorded_conformance = recorded_gate.conformance
                wire_succeeded = result.outcome == ModelOutcome.SUCCEEDED
                local_output, local_validation_errors = (
                    _local_output(result)
                    if wire_succeeded and recorded_conformance.eligible
                    else (None, None)
                )
                classification, _reason, schema_repair = _attempt_classification(
                    result=result,
                    conformance_eligible=recorded_conformance.eligible,
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
                    provider=binding.gateway_provider,
                    requested_model=binding.requested_model,
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
            request = await _request_for_checkpoint(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
            # §5.6 provider_completed 行:載入 exact 三件 artifact、重驗 eligible
            # 後才跑 local verifier。
            _, completed_gate = await _load_and_validate_provider_gate(
                uow_factory,
                tenant_id=tenant_id,
                request=request,
                result_ref=checkpoint.provider_result_artifact,
                evidence_ref=checkpoint.provider_execution_evidence_artifact,
                conformance_ref=checkpoint.provider_conformance_artifact,
                require_eligible=True,
            )
            result = completed_gate.result
            if result.parsed_output is None:
                raise CheckpointConflict("provider-completed result has no parsed output")
            output = TurnInterpretOutput.model_validate(result.parsed_output.load())
            context = await _context_for_request(
                uow_factory,
                tenant_id=tenant_id,
                request=request,
                checkpoint=checkpoint,
            )
            report = verify_turn_interpret_output(
                output=output, context=context, operation_id=operation_id
            )
            verified_at = result.completed_at + timedelta(microseconds=1)
            verification_artifact = _artifact(
                operation_id=operation_id,
                label="verification",
                kind=TURN_REPORT_ARTIFACT_KIND,
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
            context = None

        if checkpoint.status == CheckpointStatus.VERIFIED:
            if report is None or verification_artifact is None:
                # §5.6 verified 行:fresh-process 先重驗 provider gate,再載入
                # verification report,才可 commit。
                request = await _request_for_checkpoint(
                    uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
                )
                assert checkpoint.provider_result_artifact is not None
                _, verified_gate = await _load_and_validate_provider_gate(
                    uow_factory,
                    tenant_id=tenant_id,
                    request=request,
                    result_ref=checkpoint.provider_result_artifact,
                    evidence_ref=checkpoint.provider_execution_evidence_artifact,
                    conformance_ref=checkpoint.provider_conformance_artifact,
                    require_eligible=True,
                )
                result = verified_gate.result
                report, verification_artifact = await _report_for_checkpoint(
                    uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
                )
                output = TurnInterpretOutput.model_validate(
                    result.parsed_output.load()
                )
            assert result is not None and output is not None
            if context is None:
                request = await _request_for_checkpoint(
                    uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
                )
                context = await _context_for_request(
                    uow_factory,
                    tenant_id=tenant_id,
                    request=request,
                    checkpoint=checkpoint,
                )
            return await _commit_report(
                uow_factory,
                tenant_id=tenant_id,
                run_id=run_id,
                checkpoint=checkpoint,
                report=report,
                verification_artifact=verification_artifact,
                output=output,
                provider_result=result,
                request=request,
                context=context,
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
            return await _failed_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
