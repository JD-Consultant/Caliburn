"""Explicit durable executor for ``question.select/1.0.0``.

The operation remains application-owned: deterministic agenda/context before
the provider call, local semantic verification afterwards, and an atomic plan
of existing domain commands. This is deliberately not a generic agent runner.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import StableName
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.conformance import evaluate_conformance
from app.interview_vnext.llm.context import (
    QUESTION_SELECT_CONTEXT_POLICY_V1,
    QuestionSelectContextPacket,
)
from app.interview_vnext.llm.operation import OperationSpec
from app.interview_vnext.llm.operation_documents import (
    QUESTION_SELECT_PROMPT_PATH,
    question_select_operation,
)
from app.interview_vnext.llm.port import (
    LlmPort,
    MessageRole,
    ModelCallRequest,
    ModelMessage,
)
from app.interview_vnext.llm.portable_schema import (
    SchemaProjectionReport,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.question_select import (
    QuestionSelectOutput,
    QuestionSelectVerificationReport,
)
from app.interview_vnext.llm.result import ModelCallResult, ModelOutcome
from app.interview_vnext.llm.schema_exports import SCHEMA_EXPORTS
from app.interview_vnext.llm.schema_ids import (
    MODEL_RESULT_SCHEMA_ID,
    PROVIDER_BINDING_SCHEMA_ID,
    SCHEMA_PROJECTION_SCHEMA_ID,
)
from app.interview_vnext.observability.artifacts import ArtifactRef
from app.interview_vnext.observability.checkpoint import (
    CheckpointStatus,
    OperationCheckpoint,
)
from app.interview_vnext.persistence.errors import (
    CheckpointConflict,
    StateContextStale,
)
from app.job_authoring.contracts import JobStateDigest

from .agenda import build_question_agenda
from .context_builder import ContextBuilder
from .durable_operations import (
    AttemptOutcome,
    CommittedCommandPlan,
    claim_attempt_for_provider,
    commit_verified_command_plan,
    fail_operation,
    prepare_operation,
    record_attempt_result,
    record_verification,
)
from .operation_executor import (
    STATE_CONTEXT_STALE,
    TurnExecutionStatus,
    _artifact,
    _attempt_classification,
    _conformance_artifact,
    _evidence_artifact,
    _load_and_validate_provider_gate,
    _load_artifact,
    _load_attempt,
    _load_checkpoint,
    _load_state,
    _request_artifact,
    _request_for_checkpoint,
    _resolve_conformance_policy,
    _resolve_projection_policy,
    _resolved_call_for_request,
    _retry_request,
    _timeout_envelope,
    turn_execution_uuid,
)
from .persistence import AttemptStatus, VNextUnitOfWork
from .question_select import (
    materialize_question_selection,
    question_select_projection,
    verify_question_select_output,
)


STAGE = "question.select_and_respond"
QUESTION_CONTEXT_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-select-context.v1.schema.json"
)
QUESTION_INPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-select-input.v1.schema.json"
)
QUESTION_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-select-output.v1.schema.json"
)
QUESTION_REPORT_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-select-verification-report.v1.schema.json"
)
CONTEXT_MANIFEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-selection-manifest.v2.schema.json"
)
CONTEXT_BUDGET_SCHEMA_ID = (
    "https://caliburn.local/schemas/context-budget-report.v2.schema.json"
)

QUESTION_CONTEXT_KIND = "interview.question_select_context.v1"
QUESTION_INPUT_KIND = "interview.question_select_input.v1"
QUESTION_OUTPUT_KIND = "interview.question_select_output.v1"
QUESTION_REPORT_KIND = "interview.question_select_verification_report.v1"


class QuestionSelectExecutionOutcome(DomainModel):
    status: TurnExecutionStatus
    checkpoint: OperationCheckpoint
    context_packet_ref: ArtifactRef | None = None
    input_ref: ArtifactRef | None = None
    provider_result: ModelCallResult | None = None
    verification_report: QuestionSelectVerificationReport | None = None
    output: QuestionSelectOutput | None = None
    command_plan: CommittedCommandPlan | None = None
    response_artifact: ArtifactRef | None = None
    reason_code: StableName | None = None


def _project_output_schema(
    binding: ProviderBinding,
) -> tuple[dict, SchemaProjectionReport]:
    policy = _resolve_projection_policy(binding)
    schema_id, title, _factory = SCHEMA_EXPORTS[
        "question-select-output.v1.schema.json"
    ]
    source = {
        **QuestionSelectOutput.model_json_schema(),
        "$id": schema_id,
        "title": title,
    }
    projected = project_portable_strict_output_schema(
        source,
        source_schema_id=schema_id,
        target_profile=policy.target_profile,
    )
    return projected.schema, projected.report


def _local_output(
    result: ModelCallResult,
) -> tuple[QuestionSelectOutput | None, str | None]:
    if result.outcome != ModelOutcome.SUCCEEDED or result.parsed_output is None:
        return None, None
    try:
        return QuestionSelectOutput.model_validate(result.parsed_output.load()), None
    except ValidationError as exc:
        return None, canonical_json(
            {
                "errors": tuple(
                    {
                        "location": tuple(str(part) for part in item["loc"]),
                        "type": item["type"],
                        "message": item["msg"],
                    }
                    for item in exc.errors(include_url=False, include_context=False)
                )
            }
        )
    except (TypeError, ValueError):
        return None, canonical_json(
            {
                "errors": (
                    {
                        "location": (),
                        "type": "local_contract_error",
                        "message": "parsed output is not a valid question contract",
                    },
                )
            }
        )


async def _fresh_request(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    session_id: UUID,
    operation_id: UUID,
    idempotency_key: str,
    job_digest: JobStateDigest,
    operation: OperationSpec,
    binding: ProviderBinding,
    provider_config: object,
    started_at: datetime,
    contains_test_data: bool,
) -> tuple[OperationCheckpoint, ModelCallRequest]:
    state = await _load_state(
        uow_factory, tenant_id=tenant_id, session_id=session_id
    )
    agenda = build_question_agenda(state=state, job_digest=job_digest)
    context = ContextBuilder().build_question_select(
        state=state,
        agenda=agenda,
        job_digest=job_digest,
        operation_id=operation_id,
        operation_definition_hash=operation.definition_hash,
        policy=QUESTION_SELECT_CONTEXT_POLICY_V1,
    )
    projection = question_select_projection(context.packet)
    prompt = QUESTION_SELECT_PROMPT_PATH.read_text(encoding="utf-8")
    output_schema, projection_report = _project_output_schema(binding)
    turn_id = context.packet.turn_id
    common = dict(
        operation_id=operation_id,
        run_id=run_id,
        session_id=session_id,
        turn_id=turn_id,
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
        schema_id=QUESTION_OUTPUT_SCHEMA_ID,
    )
    context_artifact = _artifact(
        **common,
        label="context-packet",
        kind=QUESTION_CONTEXT_KIND,
        media_type="application/json",
        payload=context.packet,
        schema_id=QUESTION_CONTEXT_SCHEMA_ID,
    )
    manifest_artifact = _artifact(
        **common,
        label="context-manifest",
        kind="interview.context_selection_manifest.v2",
        media_type="application/json",
        payload=context.manifest,
        schema_id=CONTEXT_MANIFEST_SCHEMA_ID,
    )
    budget_artifact = _artifact(
        **common,
        label="context-budget",
        kind="interview.context_budget_report.v2",
        media_type="application/json",
        payload=context.budget,
        schema_id=CONTEXT_BUDGET_SCHEMA_ID,
    )
    input_artifact = _artifact(
        **common,
        label="question-input",
        kind=QUESTION_INPUT_KIND,
        media_type="application/json",
        payload=projection.input,
        schema_id=QUESTION_INPUT_SCHEMA_ID,
    )
    agenda_artifact = _artifact(
        **common,
        label="question-agenda",
        kind="interview.question_agenda.v1",
        media_type="application/json",
        payload=agenda,
    )
    binding_artifact = _artifact(
        **common,
        label="provider-binding",
        kind="model.provider_binding",
        media_type="application/json",
        payload=binding,
        schema_id=PROVIDER_BINDING_SCHEMA_ID,
    )
    config_artifact = _artifact(
        **common,
        label="provider-config",
        kind="provider.config",
        media_type="application/json",
        payload=provider_config,
    )
    projection_artifact = _artifact(
        **common,
        label="schema-projection",
        kind="model.schema_projection",
        media_type="application/json",
        payload=projection_report,
        schema_id=SCHEMA_PROJECTION_SCHEMA_ID,
    )
    if config_artifact.ref.content_hash != binding.provider_config_hash:
        raise CheckpointConflict(
            "provider config artifact hash does not match question binding"
        )

    request = ModelCallRequest(
        run_id=run_id,
        session_id=session_id,
        turn_id=turn_id,
        operation_id=operation_id,
        attempt_id=turn_execution_uuid(operation_id, "attempt/1"),
        attempt=1,
        operation_name=operation.name,
        operation_definition_hash=operation.definition_hash,
        idempotency_key=f"{idempotency_key}:attempt:1",
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        requested_model=binding.requested_model,
        instructions=prompt,
        messages=(
            ModelMessage(
                role=MessageRole.USER,
                text=canonical_json(projection.input),
            ),
        ),
        prompt_artifact=prompt_artifact.ref,
        output_schema_id=QUESTION_OUTPUT_SCHEMA_ID,
        output_schema_artifact=schema_artifact.ref,
        context_artifact=context_artifact.ref,
        selection_manifest_artifact=manifest_artifact.ref,
        binding_artifact=binding_artifact.ref,
        provider_config_artifact=config_artifact.ref,
        schema_projection_artifact=projection_artifact.ref,
        created_at=started_at,
        deadline_at=started_at + timedelta(milliseconds=operation.timeout_ms),
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
            agenda_artifact,
            binding_artifact,
            config_artifact,
            projection_artifact,
        ),
        expected_state_hash=context.packet.state_hash,
        turn_id=turn_id,
        stage=STAGE,
        step_event_id=turn_execution_uuid(operation_id, "event/started"),
        occurred_at=started_at,
    )
    return checkpoint, request


async def _load_context(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    request: ModelCallRequest,
) -> QuestionSelectContextPacket:
    record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=request.context_artifact.artifact_id,
    )
    if record.ref != request.context_artifact:
        raise CheckpointConflict("question context artifact reference changed")
    return QuestionSelectContextPacket.model_validate_json(
        record.inline_content or ""
    )


async def _load_verification_report(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
    output: QuestionSelectOutput,
) -> QuestionSelectVerificationReport:
    if checkpoint.verification_artifact is None:
        raise CheckpointConflict(
            "verified question checkpoint has no verification artifact"
        )
    record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=checkpoint.verification_artifact.artifact_id,
    )
    if record.ref != checkpoint.verification_artifact:
        raise CheckpointConflict(
            "question verification artifact reference changed"
        )
    try:
        report = QuestionSelectVerificationReport.model_validate_json(
            record.inline_content or ""
        )
    except ValidationError as exc:
        raise CheckpointConflict(
            "question verification artifact failed validation"
        ) from exc
    if (
        report.action != output.action
        or report.selected_gap_ordinal != output.selected_gap_ordinal
    ):
        raise CheckpointConflict(
            "question output and persisted verification report disagree"
        )
    return report


async def _terminal_outcome(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    checkpoint: OperationCheckpoint,
) -> QuestionSelectExecutionOutcome:
    if checkpoint.status == CheckpointStatus.FAILED:
        return QuestionSelectExecutionOutcome(
            status=TurnExecutionStatus.FAILED,
            checkpoint=checkpoint,
            reason_code=checkpoint.failure_reason_code,
        )
    if checkpoint.status != CheckpointStatus.COMMITTED:
        return QuestionSelectExecutionOutcome(
            status=TurnExecutionStatus.PENDING,
            checkpoint=checkpoint,
        )
    assert checkpoint.response_artifact is not None
    assert checkpoint.domain_result_artifact is not None
    response = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=checkpoint.response_artifact.artifact_id,
    )
    plan_record = await _load_artifact(
        uow_factory,
        tenant_id=tenant_id,
        artifact_id=checkpoint.domain_result_artifact.artifact_id,
    )
    if (
        response.ref != checkpoint.response_artifact
        or plan_record.ref != checkpoint.domain_result_artifact
    ):
        raise CheckpointConflict("question committed artifact reference changed")
    return QuestionSelectExecutionOutcome(
        status=TurnExecutionStatus.COMMITTED,
        checkpoint=checkpoint,
        output=QuestionSelectOutput.model_validate_json(
            response.inline_content or ""
        ),
        command_plan=CommittedCommandPlan.model_validate_json(
            plan_record.inline_content or ""
        ),
        response_artifact=response.ref,
    )


async def execute_question_select(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    run_id: UUID,
    session_id: UUID,
    operation_id: UUID,
    idempotency_key: str,
    job_digest: JobStateDigest,
    llm: LlmPort,
    binding: ProviderBinding,
    provider_config: object,
    started_at: datetime,
    now: datetime,
    operation: OperationSpec | None = None,
    contains_test_data: bool = False,
) -> QuestionSelectExecutionOutcome:
    """Execute one durable next-question decision without provider-held state."""

    operation = operation or question_select_operation()
    if operation != question_select_operation():
        raise ValueError("executor only accepts question.select/1.0.0")
    if binding.operation_name != operation.name:
        raise ValueError("binding operation does not match question.select")
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
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            job_digest=job_digest,
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
            or checkpoint.operation_definition_hash != operation.definition_hash
            or checkpoint.idempotency_key != idempotency_key
        ):
            raise CheckpointConflict("existing question checkpoint scope mismatch")
        if checkpoint.status in {
            CheckpointStatus.COMMITTED,
            CheckpointStatus.FAILED,
        }:
            return await _terminal_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
        request = await _request_for_checkpoint(
            uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
        )
        if (
            request.binding_id != binding.binding_id
            or request.binding_hash != binding.binding_hash
        ):
            raise CheckpointConflict(
                "question binding does not match persisted request"
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
                stage=STAGE,
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
                    return QuestionSelectExecutionOutcome(
                        status=TurnExecutionStatus.PENDING,
                        checkpoint=checkpoint,
                    )
                else:
                    resolved = await _resolved_call_for_request(
                        uow_factory, tenant_id=tenant_id, request=request
                    )
                    envelope = await llm.generate_structured(resolved)
                result = envelope.result
                conformance = evaluate_conformance(
                    policy=conformance_policy,
                    binding=binding,
                    evidence=envelope.execution_evidence,
                    wire_outcome=result.outcome,
                )
                local_output, local_errors = (
                    _local_output(result)
                    if result.outcome == ModelOutcome.SUCCEEDED
                    and conformance.eligible
                    else (None, None)
                )
                classification, reason, schema_repair = _attempt_classification(
                    result=result,
                    conformance_eligible=conformance.eligible,
                    local_output_valid=local_output is not None,
                    attempt=request.attempt,
                    operation=operation,
                )
                assert request.turn_id is not None
                result_artifact = _artifact(
                    operation_id=operation_id,
                    label=f"attempt/{request.attempt}/result",
                    kind="model.result",
                    media_type="application/json",
                    payload=result,
                    schema_id=MODEL_RESULT_SCHEMA_ID,
                    run_id=run_id,
                    session_id=session_id,
                    turn_id=request.turn_id,
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
                    execution_evidence_artifact=_evidence_artifact(
                        envelope.execution_evidence,
                        request=request,
                        created_at=result.completed_at,
                        contains_test_data=contains_test_data,
                    ),
                    conformance_artifact=_conformance_artifact(
                        conformance,
                        request=request,
                        created_at=result.completed_at,
                        contains_test_data=contains_test_data,
                    ),
                    extra_result_artifacts=envelope.supporting_artifacts,
                    outcome=classification,
                    max_attempts=operation.max_attempts,
                    failure_reason_code=reason,
                    stage=STAGE,
                    result_event_id=turn_execution_uuid(
                        operation_id, f"event/attempt/{request.attempt}/result"
                    ),
                    conformance_event_id=turn_execution_uuid(
                        operation_id,
                        f"event/attempt/{request.attempt}/conformance",
                    ),
                    occurred_at=result.completed_at,
                )
                if checkpoint.status == CheckpointStatus.FAILED:
                    return await _terminal_outcome(
                        uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
                    )
                if classification == AttemptOutcome.RETRYABLE_FAILURE:
                    request = _retry_request(
                        request,
                        result,
                        next_attempt=request.attempt + 1,
                        operation=operation,
                        schema_repair=schema_repair,
                        local_validation_errors=local_errors,
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
                        stage=STAGE,
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
                        "recorded question attempt has no result"
                    )
                _, gate = await _load_and_validate_provider_gate(
                    uow_factory,
                    tenant_id=tenant_id,
                    request=request,
                    result_artifact_id=attempt.result_artifact_id,
                    require_eligible=None,
                )
                result = gate.result
                local_output, local_errors = (
                    _local_output(result)
                    if result.outcome == ModelOutcome.SUCCEEDED
                    and gate.conformance.eligible
                    else (None, None)
                )
                classification, _reason, schema_repair = _attempt_classification(
                    result=result,
                    conformance_eligible=gate.conformance.eligible,
                    local_output_valid=local_output is not None,
                    attempt=request.attempt,
                    operation=operation,
                )
                if classification != AttemptOutcome.RETRYABLE_FAILURE:
                    raise CheckpointConflict(
                        "calling question checkpoint has non-retryable result"
                    )
                request = _retry_request(
                    request,
                    result,
                    next_attempt=request.attempt + 1,
                    operation=operation,
                    schema_repair=schema_repair,
                    local_validation_errors=local_errors,
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
                    stage=STAGE,
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
            request = await _request_for_checkpoint(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
            _, gate = await _load_and_validate_provider_gate(
                uow_factory,
                tenant_id=tenant_id,
                request=request,
                result_ref=checkpoint.provider_result_artifact,
                evidence_ref=checkpoint.provider_execution_evidence_artifact,
                conformance_ref=checkpoint.provider_conformance_artifact,
                require_eligible=True,
            )
            result = gate.result
            if result.parsed_output is None:
                raise CheckpointConflict(
                    "provider-completed question result has no parsed output"
                )
            output = QuestionSelectOutput.model_validate(
                result.parsed_output.load()
            )
            context = await _load_context(
                uow_factory, tenant_id=tenant_id, request=request
            )
            report = verify_question_select_output(
                output=output, context=context
            )
            verified_at = result.completed_at + timedelta(microseconds=1)
            assert request.turn_id is not None
            verification_artifact = _artifact(
                operation_id=operation_id,
                label="verification",
                kind=QUESTION_REPORT_KIND,
                media_type="application/json",
                payload=report,
                schema_id=QUESTION_REPORT_SCHEMA_ID,
                run_id=run_id,
                session_id=session_id,
                turn_id=request.turn_id,
                created_at=verified_at,
                contains_test_data=contains_test_data,
            )
            checkpoint = await record_verification(
                uow_factory,
                tenant_id=tenant_id,
                operation_id=operation_id,
                verification_artifact=verification_artifact,
                accepted=report.accepted,
                rejection_reason_code="question_select_verification_rejected",
                stage=STAGE,
                event_id=turn_execution_uuid(operation_id, "event/verified"),
                occurred_at=verified_at,
            )
            if not report.accepted:
                return QuestionSelectExecutionOutcome(
                    status=TurnExecutionStatus.FAILED,
                    checkpoint=checkpoint,
                    context_packet_ref=request.context_artifact,
                    provider_result=result,
                    verification_report=report,
                    reason_code=checkpoint.failure_reason_code,
                )
        else:
            result = None
            output = None
            report = None
            context = None
            request = await _request_for_checkpoint(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )

        if checkpoint.status == CheckpointStatus.VERIFIED:
            if result is None or output is None or report is None or context is None:
                _, gate = await _load_and_validate_provider_gate(
                    uow_factory,
                    tenant_id=tenant_id,
                    request=request,
                    result_ref=checkpoint.provider_result_artifact,
                    evidence_ref=checkpoint.provider_execution_evidence_artifact,
                    conformance_ref=checkpoint.provider_conformance_artifact,
                    require_eligible=True,
                )
                result = gate.result
                output = QuestionSelectOutput.model_validate(
                    result.parsed_output.load()
                )
                context = await _load_context(
                    uow_factory, tenant_id=tenant_id, request=request
                )
                report = await _load_verification_report(
                    uow_factory,
                    tenant_id=tenant_id,
                    checkpoint=checkpoint,
                    output=output,
                )
                if not report.accepted:
                    raise CheckpointConflict(
                        "persisted verified question report is no longer accepted"
                    )
            state = await _load_state(
                uow_factory, tenant_id=tenant_id, session_id=session_id
            )
            plan = materialize_question_selection(
                state=state,
                context=context,
                output=output,
                operation_id=operation_id,
                occurred_at=max(
                    checkpoint.updated_at + timedelta(microseconds=1),
                    result.completed_at + timedelta(microseconds=2),
                ),
            )
            committed_at = plan.append_question.occurred_at
            try:
                checkpoint, committed_plan, response_ref = (
                    await commit_verified_command_plan(
                        uow_factory,
                        tenant_id=tenant_id,
                        operation_id=operation_id,
                        run_id=run_id,
                        commands=plan.commands,
                        response_payload=output,
                        plan_result_artifact_id=turn_execution_uuid(
                            operation_id, "command-plan-result"
                        ),
                        response_artifact_id=turn_execution_uuid(
                            operation_id, "response"
                        ),
                        command_artifact_ids=tuple(
                            turn_execution_uuid(
                                operation_id, f"command/{index}/artifact"
                            )
                            for index in range(1, len(plan.commands) + 1)
                        ),
                        reduction_artifact_ids=tuple(
                            turn_execution_uuid(
                                operation_id, f"command/{index}/reduction"
                            )
                            for index in range(1, len(plan.commands) + 1)
                        ),
                        transition_event_ids=tuple(
                            turn_execution_uuid(
                                operation_id, f"event/command/{index}"
                            )
                            for index in range(1, len(plan.commands) + 1)
                        ),
                        step_event_id=turn_execution_uuid(
                            operation_id, "event/completed"
                        ),
                        committed_at=committed_at,
                        expected_state_hash=context.state_hash,
                        stage=STAGE,
                        response_artifact_kind=QUESTION_OUTPUT_KIND,
                        response_schema_id=QUESTION_OUTPUT_SCHEMA_ID,
                        contains_test_data=contains_test_data,
                    )
                )
            except StateContextStale:
                actual = await _load_state(
                    uow_factory, tenant_id=tenant_id, session_id=session_id
                )
                failure = _artifact(
                    operation_id=operation_id,
                    label="state-context-stale",
                    kind="operation.local_failure",
                    media_type="application/json",
                    payload={
                        "reason_code": STATE_CONTEXT_STALE,
                        "expected_state_version": context.state_version,
                        "actual_state_version": actual.session.state_version,
                        "expected_state_hash": context.state_hash,
                        "actual_state_hash": canonical_hash(actual),
                    },
                    run_id=run_id,
                    session_id=session_id,
                    turn_id=context.turn_id,
                    created_at=committed_at,
                    contains_test_data=contains_test_data,
                )
                checkpoint = await fail_operation(
                    uow_factory,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    failure_artifact=failure,
                    reason_code=STATE_CONTEXT_STALE,
                    stage=STAGE,
                    event_id=turn_execution_uuid(
                        operation_id, "event/state-context-stale"
                    ),
                    occurred_at=committed_at,
                )
                return QuestionSelectExecutionOutcome(
                    status=TurnExecutionStatus.FAILED,
                    checkpoint=checkpoint,
                    context_packet_ref=request.context_artifact,
                    provider_result=result,
                    verification_report=report,
                    output=output,
                    reason_code=STATE_CONTEXT_STALE,
                )
            return QuestionSelectExecutionOutcome(
                status=TurnExecutionStatus.COMMITTED,
                checkpoint=checkpoint,
                context_packet_ref=request.context_artifact,
                input_ref=ArtifactRef.model_validate(
                    (
                        await _load_artifact(
                            uow_factory,
                            tenant_id=tenant_id,
                            artifact_id=turn_execution_uuid(
                                operation_id, "question-input"
                            ),
                        )
                    ).ref
                ),
                provider_result=result,
                verification_report=report,
                output=output,
                command_plan=committed_plan,
                response_artifact=response_ref,
            )

        if checkpoint.status in {
            CheckpointStatus.COMMITTED,
            CheckpointStatus.FAILED,
        }:
            return await _terminal_outcome(
                uow_factory, tenant_id=tenant_id, checkpoint=checkpoint
            )
