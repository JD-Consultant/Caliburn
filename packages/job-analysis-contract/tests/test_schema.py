"""Executable checks for the durable consultant wire contract."""

from __future__ import annotations

import json
from pathlib import Path

from job_analysis_contract import (
    ConsultantDocumentCreate,
    ConsultantSnapshotView,
    ProblemDetail,
)


PACKAGE_ROOT = Path(__file__).parents[1]
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "job-analysis-workspace.schema.json"
PROBLEM_TYPES = {
    "https://caliburn.dev/problems/job-analysis/document-not-found",
    "https://caliburn.dev/problems/job-analysis/idempotency-conflict",
    "https://caliburn.dev/problems/job-analysis/authority-conflict",
    "https://caliburn.dev/problems/job-analysis/invalid-request",
    "https://caliburn.dev/problems/job-analysis/consultant-unavailable",
    "https://caliburn.dev/problems/job-analysis/consultant-run-active",
    "https://caliburn.dev/problems/job-analysis/consultant-command-conflict",
    "https://caliburn.dev/problems/job-analysis/export-confirmation-required",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_owns_only_the_durable_consultant_wire_contract() -> None:
    schema = _schema()
    definitions = set(schema["$defs"])

    assert schema["$id"] == (
        "https://caliburn.dev/schema/job-analysis-workspace.schema.json"
    )
    assert {
        "ConsultantDocumentCreate",
        "ConsultantDocumentCatalog",
        "ConsultantSnapshotView",
        "DocumentReviewDecisionWrite",
        "RequiredClarificationView",
        "ApprovedJobDocumentView",
        "ExportReadinessView",
        "ProblemFieldError",
        "ProblemDetail",
    } <= definitions
    assert not {
        "DocumentMetadataWrite",
        "ConsultationView",
        "ProposalView",
        "JdTaskWrite",
        "OpksProposalView",
    } & definitions


def test_problem_type_is_the_closed_current_runtime_identifier_set() -> None:
    problem = _schema()["$defs"]["ProblemDetail"]

    assert set(problem["properties"]["type"]["enum"]) == PROBLEM_TYPES
    assert problem["additionalProperties"] is True


def test_generated_current_models_are_exported_from_the_package() -> None:
    document = ConsultantDocumentCreate(title="財務專員")
    problem = ProblemDetail.model_validate(
        {
            "type": "https://caliburn.dev/problems/job-analysis/invalid-request",
            "title": "Invalid request",
            "status": 422,
            "future_extension": {"safe_to_ignore": True},
        }
    )

    assert document.title == "財務專員"
    assert ConsultantSnapshotView.__name__ == "ConsultantSnapshotView"
    assert problem.model_extra == {"future_extension": {"safe_to_ignore": True}}
