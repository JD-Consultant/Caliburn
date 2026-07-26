"""Portable JSON Schema registry for the ten Job Authoring seams (plan §13.1).

Only the ten top-level contracts are committed. Nested task/output/provenance
types are referenced by their parent schema, so no separate fragment files are
produced.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .commands import (
    CreateJobDocumentCommand,
    CreateTaskProposalCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from .contracts import (
    AiTaskBundleProposal,
    EmployeeProposalDecision,
    JobDocumentDraft,
    JobDocumentRevision,
    JobStateDigest,
    TaskProposalView,
)

SchemaFactory = Callable[[], dict[str, Any]]


def _model_schema(model) -> SchemaFactory:
    return model.model_json_schema


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "job-document-draft.v1.schema.json": (
        "https://caliburn.local/schemas/job-document-draft.v1.schema.json",
        "Caliburn job authoring document draft v1",
        _model_schema(JobDocumentDraft),
    ),
    "job-document-revision.v1.schema.json": (
        "https://caliburn.local/schemas/job-document-revision.v1.schema.json",
        "Caliburn job authoring document revision v1",
        _model_schema(JobDocumentRevision),
    ),
    "create-job-document-command.v1.schema.json": (
        "https://caliburn.local/schemas/create-job-document-command.v1.schema.json",
        "Caliburn job authoring create document command v1",
        _model_schema(CreateJobDocumentCommand),
    ),
    "employee-task-bundle-command.v1.schema.json": (
        "https://caliburn.local/schemas/employee-task-bundle-command.v1.schema.json",
        "Caliburn job authoring employee task bundle command v1",
        _model_schema(EmployeeTaskBundleCommand),
    ),
    "create-task-proposal-command.v1.schema.json": (
        "https://caliburn.local/schemas/create-task-proposal-command.v1.schema.json",
        "Caliburn job authoring create task proposal command v1",
        _model_schema(CreateTaskProposalCommand),
    ),
    "ai-task-bundle-proposal.v1.schema.json": (
        "https://caliburn.local/schemas/ai-task-bundle-proposal.v1.schema.json",
        "Caliburn job authoring AI task bundle proposal v1",
        _model_schema(AiTaskBundleProposal),
    ),
    "task-proposal-view.v1.schema.json": (
        "https://caliburn.local/schemas/task-proposal-view.v1.schema.json",
        "Caliburn job authoring task proposal view v1",
        _model_schema(TaskProposalView),
    ),
    "employee-proposal-decision-command.v1.schema.json": (
        "https://caliburn.local/schemas/employee-proposal-decision-command.v1.schema.json",
        "Caliburn job authoring employee proposal decision command v1",
        _model_schema(EmployeeProposalDecisionCommand),
    ),
    "employee-proposal-decision.v1.schema.json": (
        "https://caliburn.local/schemas/employee-proposal-decision.v1.schema.json",
        "Caliburn job authoring employee proposal decision v1",
        _model_schema(EmployeeProposalDecision),
    ),
    "job-state-digest.v1.schema.json": (
        "https://caliburn.local/schemas/job-state-digest.v1.schema.json",
        "Caliburn job authoring job state digest v1",
        _model_schema(JobStateDigest),
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
