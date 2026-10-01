"""Blind R1 eval grader: its own port, prompt, schema, and failure vocabulary.

ADR 0040 §15/§17 keeps the development-time grader separate from the generator:
it is blind, it may answer ``unknown`` per dimension, it scores dimensions
separately, and it shares only the Job Analysis Quality Rubric asset — never a
prompt, an example, a model binding, or a capture root.

The separation is typed. ``GraderProvider.grade()`` is a different port from the
generator's ``StructuredOutputProvider.generate()``, and ``GraderOperationRequest``
is a different value from ``StructuredOperationRequest``, so a generator binding
cannot be handed to the grader by accident. The grader only reads and scores; no
function here returns a modified generator product.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import Field

from app.professional_consultant.contracts import (
    Identifier,
    ShortText,
    SourceText,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
)

from .blind_projection import (
    BlindSourcePacket,
    BlindTaskDiscoveryArtifact,
    project_blind_artifact,
    project_blind_source,
    submission_id_for,
)
from .contracts import JobAnalysisQualityRubric, R1EvalModel
from .minimal_harness import MinimalTaskDiscoveryOutput


GRADER_ID = "r1.blind_grade"
GRADER_VERSION = "1.0.0"

_ASSET_ROOT = Path(__file__).with_name("grader_assets")
_PROMPT_ID = "r1-blind-grader.v1"
_PROMPT_FILENAME = "r1-blind-grader.v1.txt"
_SCHEMA_ID = "r1-blind-grader-verdict.v1"


class GraderPromptArtifact(R1EvalModel):
    prompt_id: Identifier
    content: SourceText


class GraderSchemaArtifact(R1EvalModel):
    schema_id: Identifier
    schema_text: Annotated[str, Field(min_length=1, max_length=200_000)]


class GraderModelBinding(R1EvalModel):
    """Grader model selection; never merged into the generator call budget."""

    schema_version: Literal["r1_grader_model_binding.v1"]
    requested_model: ShortText
    counted_in_generator_budget: Literal[False]


class RubricScore(StrEnum):
    SCORE_0 = "score_0"
    SCORE_1 = "score_1"
    SCORE_2 = "score_2"
    UNKNOWN = "unknown"


class RuleJudgement(StrEnum):
    PASS = "pass"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class DimensionVerdict(R1EvalModel):
    code: Identifier
    score: RubricScore
    evidence: ShortText


class RuleVerdict(R1EvalModel):
    code: Identifier
    judgement: RuleJudgement
    evidence: ShortText


class BlindGraderRequest(R1EvalModel):
    schema_version: Literal["r1_blind_grader_request.v1"]
    submission_id: Identifier
    source: BlindSourcePacket
    artifact: BlindTaskDiscoveryArtifact
    rubric: JobAnalysisQualityRubric


class BlindGraderVerdict(R1EvalModel):
    schema_version: Literal["r1_blind_grader_verdict.v1"]
    submission_id: Identifier
    dimensions: tuple[DimensionVerdict, ...]
    critical_rules: tuple[RuleVerdict, ...]
    question_rules: tuple[RuleVerdict, ...]


class GraderIssueCode(StrEnum):
    SUBMISSION_MISMATCH = "submission_mismatch"
    DIMENSION_COVERAGE_MISMATCH = "dimension_coverage_mismatch"
    CRITICAL_RULE_COVERAGE_MISMATCH = "critical_rule_coverage_mismatch"
    QUESTION_RULE_COVERAGE_MISMATCH = "question_rule_coverage_mismatch"
    DUPLICATE_CODE = "duplicate_code"


class GraderIssue(R1EvalModel):
    code: GraderIssueCode
    path: ShortText
    entity_id: Identifier | None
    message: ShortText


class GraderVerificationReport(R1EvalModel):
    schema_version: Literal["r1_blind_grader_verification_report.v1"]
    issues: tuple[GraderIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


class GraderOperationRequest(R1EvalModel):
    """What the grader model actually receives; carries no model identity."""

    grader_id: Literal["r1.blind_grade"]
    grader_version: Annotated[
        str, Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    ]
    prompt: GraderPromptArtifact
    output_schema: GraderSchemaArtifact
    input_text: Annotated[str, Field(min_length=1, max_length=400_000)]


class GraderOperationResponse(R1EvalModel):
    output_text: Annotated[str, Field(min_length=1, max_length=400_000)]


class GraderProvider(Protocol):
    async def grade(
        self, request: GraderOperationRequest
    ) -> GraderOperationResponse: ...


class GraderCallError(RuntimeError):
    """Safe, provider-neutral grader failure from an outer adapter or fake."""


class GraderFailureCode(StrEnum):
    PROVIDER_FAILED = "provider_failed"
    OUTPUT_JSON_INVALID = "output_json_invalid"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    VERIFICATION_FAILED = "verification_failed"


class GraderFailure(R1EvalModel):
    code: GraderFailureCode
    detail: Annotated[str, Field(min_length=1, max_length=512)]
    verification_report: GraderVerificationReport | None


class GraderRunError(RuntimeError):
    def __init__(self, failure: GraderFailure) -> None:
        self.failure = failure
        super().__init__(f"{GRADER_ID}: {failure.code.value}: {failure.detail}")


_VERDICT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "schema_version": {
            "type": "string",
            "enum": ["r1_blind_grader_verdict.v1"],
        },
        "submission_id": {"type": "string"},
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "score": {
                        "type": "string",
                        "enum": ["score_0", "score_1", "score_2", "unknown"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["code", "score", "evidence"],
                "additionalProperties": False,
            },
        },
        "critical_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "judgement": {
                        "type": "string",
                        "enum": ["pass", "violated", "unknown"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["code", "judgement", "evidence"],
                "additionalProperties": False,
            },
        },
        "question_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "judgement": {
                        "type": "string",
                        "enum": ["pass", "violated", "unknown"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["code", "judgement", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "schema_version",
        "submission_id",
        "dimensions",
        "critical_rules",
        "question_rules",
    ],
    "additionalProperties": False,
}


def blind_grader_prompt() -> GraderPromptArtifact:
    return GraderPromptArtifact(
        prompt_id=_PROMPT_ID,
        content=(_ASSET_ROOT / _PROMPT_FILENAME).read_text(encoding="utf-8"),
    )


def blind_grader_output_schema() -> GraderSchemaArtifact:
    return GraderSchemaArtifact(
        schema_id=_SCHEMA_ID,
        schema_text=json.dumps(
            _VERDICT_SCHEMA,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        ),
    )


def build_blind_grader_request(
    *,
    trial_id: str,
    source: TaskDiscoveryInput,
    result: TaskDiscoveryOutput | MinimalTaskDiscoveryOutput,
    rubric: JobAnalysisQualityRubric,
) -> BlindGraderRequest:
    """Blind one published generator result against the single rubric."""

    return BlindGraderRequest(
        schema_version="r1_blind_grader_request.v1",
        submission_id=submission_id_for(trial_id),
        source=project_blind_source(source),
        artifact=project_blind_artifact(result),
        rubric=rubric,
    )


def build_grader_operation_request(
    request: BlindGraderRequest,
) -> GraderOperationRequest:
    return GraderOperationRequest(
        grader_id=GRADER_ID,
        grader_version=GRADER_VERSION,
        prompt=blind_grader_prompt(),
        output_schema=blind_grader_output_schema(),
        input_text=json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        ),
    )


def _issue(
    code: GraderIssueCode, path: str, entity_id: str | None, message: str
) -> GraderIssue:
    return GraderIssue(
        code=code, path=path, entity_id=entity_id, message=message
    )


def _check_coverage(
    codes: tuple[str, ...],
    *,
    expected: tuple[str, ...],
    path: str,
    coverage_code: GraderIssueCode,
) -> list[GraderIssue]:
    issues: list[GraderIssue] = []
    seen: set[str] = set()
    for code in codes:
        if code in seen:
            issues.append(
                _issue(
                    GraderIssueCode.DUPLICATE_CODE,
                    path,
                    code,
                    "grader scored the same rubric code more than once",
                )
            )
        seen.add(code)
    for code in sorted(set(expected) - seen):
        issues.append(
            _issue(
                coverage_code,
                path,
                code,
                "grader did not score a required rubric code",
            )
        )
    for code in sorted(seen - set(expected)):
        issues.append(
            _issue(
                coverage_code,
                path,
                code,
                "grader scored a code that is not in the rubric",
            )
        )
    return issues


def verify_blind_grader_verdict(
    request: BlindGraderRequest, verdict: BlindGraderVerdict
) -> GraderVerificationReport:
    """Check the verdict against the rubric it was asked to apply."""

    issues: list[GraderIssue] = []
    if verdict.submission_id != request.submission_id:
        issues.append(
            _issue(
                GraderIssueCode.SUBMISSION_MISMATCH,
                "submission_id",
                verdict.submission_id,
                "verdict does not belong to the graded submission",
            )
        )
    issues.extend(
        _check_coverage(
            tuple(item.code for item in verdict.dimensions),
            expected=tuple(
                dimension.code
                for dimension in request.rubric.task_boundary_dimensions
            ),
            path="dimensions",
            coverage_code=GraderIssueCode.DIMENSION_COVERAGE_MISMATCH,
        )
    )
    issues.extend(
        _check_coverage(
            tuple(item.code for item in verdict.critical_rules),
            expected=tuple(
                rule.code for rule in request.rubric.critical_rules
            ),
            path="critical_rules",
            coverage_code=GraderIssueCode.CRITICAL_RULE_COVERAGE_MISMATCH,
        )
    )
    issues.extend(
        _check_coverage(
            tuple(item.code for item in verdict.question_rules),
            expected=tuple(
                rule.code for rule in request.rubric.question_rules
            ),
            path="question_rules",
            coverage_code=GraderIssueCode.QUESTION_RULE_COVERAGE_MISMATCH,
        )
    )
    return GraderVerificationReport(
        schema_version="r1_blind_grader_verification_report.v1",
        issues=tuple(
            sorted(
                issues,
                key=lambda item: (
                    item.code.value,
                    item.path,
                    item.entity_id or "",
                    item.message,
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


def _fail(code: GraderFailureCode, detail: str) -> GraderRunError:
    return GraderRunError(
        GraderFailure(code=code, detail=detail, verification_report=None)
    )


def _parse_verdict(output_text: str) -> BlindGraderVerdict:
    if output_text.startswith("\ufeff"):
        raise _fail(
            GraderFailureCode.OUTPUT_JSON_INVALID,
            "grader output contains a UTF-8 BOM",
        )
    try:
        json.loads(
            output_text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, _InvalidJson) as exc:
        raise _fail(
            GraderFailureCode.OUTPUT_JSON_INVALID,
            "grader output is not strict JSON",
        ) from exc
    try:
        return BlindGraderVerdict.model_validate_json(output_text)
    except ValueError as exc:
        raise _fail(
            GraderFailureCode.OUTPUT_SCHEMA_INVALID,
            "grader output does not match the verdict contract",
        ) from exc


async def run_blind_grading(
    request: BlindGraderRequest, *, provider: GraderProvider
) -> BlindGraderVerdict:
    """Grade one submission; the generator product is never written back."""

    operation_request = build_grader_operation_request(request)
    try:
        response = await provider.grade(operation_request)
    except GraderCallError as exc:
        raise _fail(
            GraderFailureCode.PROVIDER_FAILED,
            "grader provider boundary reported a call failure",
        ) from exc
    verdict = _parse_verdict(response.output_text)
    report = verify_blind_grader_verdict(request, verdict)
    if not report.passed:
        raise GraderRunError(
            GraderFailure(
                code=GraderFailureCode.VERIFICATION_FAILED,
                detail="grader verdict failed deterministic verification",
                verification_report=report,
            )
        )
    return verdict
