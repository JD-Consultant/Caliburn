"""Provider-neutral scripted runners for R1 Task Discovery."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Protocol, TypeVar

from pydantic import BaseModel, Field, ValidationError

from .contracts import (
    ConsultantContract,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TurnUnderstandInput,
    TurnUnderstandOutput,
    WorkReconcileDecideInput,
    WorkReconcileDecideOutput,
)
from .prompts import (
    OperationName,
    PromptArtifact,
    PromptProfile,
    prompt_for,
)
from .schema_projection import (
    ProviderSchemaArtifact,
    SchemaProfile,
    provider_schema_for,
)
from .verifier import (
    VerificationReport,
    verify_task_discovery,
    verify_turn_understand,
)


OperationJsonText = Annotated[str, Field(min_length=1, max_length=400_000)]


class StructuredOperationRequest(ConsultantContract):
    operation: OperationName
    operation_version: Annotated[
        str, Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    ]
    prompt: PromptArtifact
    output_schema: ProviderSchemaArtifact
    input_text: OperationJsonText


class StructuredOperationResponse(ConsultantContract):
    output_text: OperationJsonText


class OperationFailureCode(StrEnum):
    PROVIDER_FAILED = "provider_failed"
    OUTPUT_JSON_INVALID = "output_json_invalid"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    VERIFICATION_FAILED = "verification_failed"


class OperationFailure(ConsultantContract):
    code: OperationFailureCode
    operation: OperationName
    detail: Annotated[str, Field(min_length=1, max_length=512)]
    verification_report: VerificationReport | None


class OperationRunError(RuntimeError):
    def __init__(self, failure: OperationFailure) -> None:
        self.failure = failure
        super().__init__(
            f"{failure.operation.value}: {failure.code.value}: {failure.detail}"
        )


class ProviderCallError(RuntimeError):
    """Safe, provider-neutral failure emitted by an outer adapter or fake."""


class StructuredOutputProvider(Protocol):
    async def generate(
        self, request: StructuredOperationRequest
    ) -> StructuredOperationResponse: ...


async def _generate(
    provider: StructuredOutputProvider,
    request: StructuredOperationRequest,
) -> StructuredOperationResponse:
    try:
        return await provider.generate(request)
    except ProviderCallError as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.PROVIDER_FAILED,
                operation=request.operation,
                detail="provider boundary reported a call failure",
                verification_report=None,
            )
        ) from exc


class _InvalidJson(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJson(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> object:
    raise _InvalidJson(f"non-standard JSON constant: {value}")


_OutputT = TypeVar("_OutputT", bound=BaseModel)


def _parse_output(
    operation: OperationName,
    output_text: str,
    model: type[_OutputT],
) -> _OutputT:
    if output_text.startswith("\ufeff"):
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_JSON_INVALID,
                operation=operation,
                detail="provider output contains a UTF-8 BOM",
                verification_report=None,
            )
        )
    try:
        json.loads(
            output_text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, _InvalidJson) as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_JSON_INVALID,
                operation=operation,
                detail="provider output is not strict JSON",
                verification_report=None,
            )
        ) from exc
    try:
        return model.model_validate_json(output_text)
    except ValidationError as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_SCHEMA_INVALID,
                operation=operation,
                detail="provider output does not match the operation contract",
                verification_report=None,
            )
        ) from exc


def _raise_verification_failure(
    operation: OperationName, report: VerificationReport
) -> None:
    raise OperationRunError(
        OperationFailure(
            code=OperationFailureCode.VERIFICATION_FAILED,
            operation=operation,
            detail="provider output failed deterministic verification",
            verification_report=report,
        )
    )


def _canonical_input(source: ConsultantContract) -> str:
    return json.dumps(
        source.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )


async def run_task_discovery_once(
    source: TaskDiscoveryInput,
    *,
    provider: StructuredOutputProvider,
    prompt_profile: PromptProfile,
    schema_profile: SchemaProfile,
) -> TaskDiscoveryOutput:
    request = StructuredOperationRequest(
        operation=OperationName.TASK_DISCOVERY,
        operation_version="1.0.0",
        prompt=prompt_for(OperationName.TASK_DISCOVERY, prompt_profile),
        output_schema=provider_schema_for(
            OperationName.TASK_DISCOVERY, schema_profile
        ),
        input_text=_canonical_input(source),
    )
    response = await _generate(provider, request)
    result = _parse_output(
        OperationName.TASK_DISCOVERY,
        response.output_text,
        TaskDiscoveryOutput,
    )
    report = verify_task_discovery(source, result)
    if not report.passed:
        _raise_verification_failure(OperationName.TASK_DISCOVERY, report)
    return result


async def run_task_discovery_two_stage(
    source: TaskDiscoveryInput,
    *,
    provider: StructuredOutputProvider,
    schema_profile: SchemaProfile,
) -> TaskDiscoveryOutput:
    understanding_input = TurnUnderstandInput(
        schema_version="turn_understand_input.v1",
        employee_message=source.employee_message,
        question_context=source.question_context,
        recent_transcript=source.recent_transcript,
        prior_claims=source.prior_claims,
        omitted_relevant_context=source.omitted_relevant_context,
    )
    understanding_request = StructuredOperationRequest(
        operation=OperationName.TURN_UNDERSTAND,
        operation_version="1.0.0",
        prompt=prompt_for(OperationName.TURN_UNDERSTAND, PromptProfile.FULL),
        output_schema=provider_schema_for(
            OperationName.TURN_UNDERSTAND, schema_profile
        ),
        input_text=_canonical_input(understanding_input),
    )
    understanding_response = await _generate(provider, understanding_request)
    understanding = _parse_output(
        OperationName.TURN_UNDERSTAND,
        understanding_response.output_text,
        TurnUnderstandOutput,
    )
    understanding_report = verify_turn_understand(
        understanding_input, understanding
    )
    if not understanding_report.passed:
        _raise_verification_failure(
            OperationName.TURN_UNDERSTAND, understanding_report
        )

    reconciliation_input = WorkReconcileDecideInput(
        schema_version="work_reconcile_decide_input.v1",
        employee_message=source.employee_message,
        understanding=understanding,
        prior_claims=source.prior_claims,
        prior_stories=source.prior_stories,
        prior_work_units=source.prior_work_units,
        existing_task_candidates=source.existing_task_candidates,
        recent_questions=source.recent_questions,
        omitted_relevant_context=source.omitted_relevant_context,
    )
    reconciliation_request = StructuredOperationRequest(
        operation=OperationName.WORK_RECONCILE_DECIDE,
        operation_version="1.0.0",
        prompt=prompt_for(
            OperationName.WORK_RECONCILE_DECIDE, PromptProfile.FULL
        ),
        output_schema=provider_schema_for(
            OperationName.WORK_RECONCILE_DECIDE, schema_profile
        ),
        input_text=_canonical_input(reconciliation_input),
    )
    reconciliation_response = await _generate(
        provider, reconciliation_request
    )
    reconciliation = _parse_output(
        OperationName.WORK_RECONCILE_DECIDE,
        reconciliation_response.output_text,
        WorkReconcileDecideOutput,
    )
    result = TaskDiscoveryOutput(
        schema_version="task_discovery_output.v1",
        claims=understanding.claims,
        unmapped_signals=understanding.unmapped_signals,
        stories=reconciliation.stories,
        work_units=reconciliation.work_units,
        decisions=reconciliation.decisions,
        task_candidates=reconciliation.task_candidates,
        next_question=reconciliation.next_question,
    )
    report = verify_task_discovery(source, result)
    if not report.passed:
        _raise_verification_failure(
            OperationName.WORK_RECONCILE_DECIDE, report
        )
    return result
