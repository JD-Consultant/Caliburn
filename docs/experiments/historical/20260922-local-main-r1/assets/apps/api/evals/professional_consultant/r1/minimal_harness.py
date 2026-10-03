"""A1 minimal-harness baseline kept outside the production core."""

from __future__ import annotations

import json
from typing import Literal

from app.professional_consultant.contracts import (
    EmployeeMessage,
    Identifier,
    NextQuestion,
    QuestionContext,
    StatementText,
    TaskDiscoveryInput,
    TranscriptTurn,
)
from app.professional_consultant.prompts import OperationName, PromptProfile, prompt_for
from app.professional_consultant.runner import (
    OperationFailure,
    OperationFailureCode,
    OperationRunError,
    ProviderCallError,
    StructuredOperationRequest,
    StructuredOutputProvider,
)
from app.professional_consultant.schema_projection import (
    ProviderSchemaArtifact,
    SchemaProfile,
)
from app.professional_consultant.verifier import (
    VerificationIssue,
    VerificationIssueCode,
    VerificationReport,
)

from .contracts import R1EvalModel


class MinimalTaskDiscoveryInput(R1EvalModel):
    schema_version: Literal["minimal_task_discovery_input.v1"]
    employee_message: EmployeeMessage
    question_context: QuestionContext | None
    recent_transcript: tuple[TranscriptTurn, ...]


class MinimalTaskCandidate(R1EvalModel):
    candidate_id: Identifier
    statement: StatementText


class MinimalTaskDiscoveryOutput(R1EvalModel):
    schema_version: Literal["minimal_task_discovery_output.v1"]
    task_candidates: tuple[MinimalTaskCandidate, ...]
    next_question: NextQuestion


_MINIMAL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {
            "type": "string",
            "enum": ["minimal_task_discovery_output.v1"],
        },
        "task_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "statement": {"type": "string"},
                },
                "required": ["candidate_id", "statement"],
                "additionalProperties": False,
            },
        },
        "next_question": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["broaden", "deepen_story", "clarify_boundary"],
                },
                "text": {"type": "string"},
                "target_gap": {"type": "string"},
                "claim_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["action", "text", "target_gap", "claim_ids"],
            "additionalProperties": False,
        },
    },
    "required": ["schema_version", "task_candidates", "next_question"],
    "additionalProperties": False,
}


def minimal_output_schema() -> ProviderSchemaArtifact:
    return ProviderSchemaArtifact(
        schema_id="minimal-task-discover-output.light.v1",
        operation=OperationName.TASK_DISCOVERY,
        profile=SchemaProfile.LIGHT,
        schema_text=json.dumps(
            _MINIMAL_OUTPUT_SCHEMA,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        ),
    )


def _normalized_question(value: str) -> str:
    return "".join(value.split()).casefold().rstrip("?？。.!！")


def _minimal_report(
    source: TaskDiscoveryInput,
    result: MinimalTaskDiscoveryOutput,
) -> VerificationReport:
    issues: list[VerificationIssue] = []
    ids = tuple(candidate.candidate_id for candidate in result.task_candidates)
    if len(set(ids)) != len(ids):
        issues.append(
            VerificationIssue(
                code=VerificationIssueCode.DUPLICATE_ID,
                path="task_candidates/candidate_id",
                entity_id=None,
                message="minimal task candidate IDs must be unique",
            )
        )
    statements = tuple(
        " ".join(candidate.statement.split()).casefold()
        for candidate in result.task_candidates
    )
    if len(set(statements)) != len(statements):
        issues.append(
            VerificationIssue(
                code=VerificationIssueCode.DUPLICATE_RELATION,
                path="task_candidates/statement",
                entity_id=None,
                message="minimal task candidate statements must be unique",
            )
        )
    if result.next_question.claim_ids:
        issues.append(
            VerificationIssue(
                code=VerificationIssueCode.REFERENCE_MISSING,
                path="next_question/claim_ids",
                entity_id=None,
                message="minimal baseline has no claim IDs to reference",
            )
        )
    previous_questions = source.recent_questions
    if source.question_context is not None:
        previous_questions = (
            *previous_questions,
            source.question_context.question_text,
        )
    if _normalized_question(result.next_question.text) in {
        _normalized_question(question) for question in previous_questions
    }:
        issues.append(
            VerificationIssue(
                code=VerificationIssueCode.REPEATED_QUESTION,
                path="next_question/text",
                entity_id=None,
                message="next question exactly repeats a recent question",
            )
        )
    return VerificationReport(
        schema_version="task_discovery_verification_report.v1",
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.code.value,
                    issue.path,
                    issue.entity_id or "",
                    issue.message,
                ),
            )
        ),
    )


class _InvalidJson(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJson(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise _InvalidJson(f"non-standard JSON constant: {value}")


def _parse_minimal_output(output_text: str) -> MinimalTaskDiscoveryOutput:
    if output_text.startswith("\ufeff"):
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_JSON_INVALID,
                operation=OperationName.TASK_DISCOVERY,
                detail="provider output contains a UTF-8 BOM",
                verification_report=None,
            )
        )
    try:
        json.loads(
            output_text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, _InvalidJson) as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_JSON_INVALID,
                operation=OperationName.TASK_DISCOVERY,
                detail="provider output is not strict JSON",
                verification_report=None,
            )
        ) from exc
    try:
        return MinimalTaskDiscoveryOutput.model_validate_json(output_text)
    except ValueError as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.OUTPUT_SCHEMA_INVALID,
                operation=OperationName.TASK_DISCOVERY,
                detail="provider output does not match the minimal contract",
                verification_report=None,
            )
        ) from exc


async def run_minimal_task_discovery_once(
    source: TaskDiscoveryInput,
    *,
    provider: StructuredOutputProvider,
) -> MinimalTaskDiscoveryOutput:
    """Run A1 with a smaller output, context packet, and verifier policy."""

    minimal_input = MinimalTaskDiscoveryInput(
        schema_version="minimal_task_discovery_input.v1",
        employee_message=source.employee_message,
        question_context=source.question_context,
        recent_transcript=source.recent_transcript,
    )
    request = StructuredOperationRequest(
        operation=OperationName.TASK_DISCOVERY,
        operation_version="1.0.0",
        prompt=prompt_for(OperationName.TASK_DISCOVERY, PromptProfile.MINIMAL),
        output_schema=minimal_output_schema(),
        input_text=json.dumps(
            minimal_input.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        ),
    )
    try:
        response = await provider.generate(request)
    except ProviderCallError as exc:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.PROVIDER_FAILED,
                operation=OperationName.TASK_DISCOVERY,
                detail="provider boundary reported a call failure",
                verification_report=None,
            )
        ) from exc
    result = _parse_minimal_output(response.output_text)
    report = _minimal_report(source, result)
    if not report.passed:
        raise OperationRunError(
            OperationFailure(
                code=OperationFailureCode.VERIFICATION_FAILED,
                operation=OperationName.TASK_DISCOVERY,
                detail="provider output failed minimal deterministic verification",
                verification_report=report,
            )
        )
    return result
