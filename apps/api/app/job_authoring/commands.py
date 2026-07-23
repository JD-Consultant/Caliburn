"""Trusted application commands for the Job Authoring Core (plan §5.4-§5.7).

Commands carry already-trusted identity: the application owns every persisted
UUID, so no ``schema_version`` field accepts a model-supplied id. Shape rules
that depend on ``action`` are enforced here; cross-row facts (target task
existence, evidence liveness) are checked in transitions/service, not here.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .contracts import (
    AuthoringModel,
    JobTitleText,
    Sha256,
    TaskBundleEditValue,
    TaskBundleProposalDraft,
    UtcDatetime,
)


class CreateJobDocumentCommand(AuthoringModel):
    schema_version: Literal["create_job_document_command.v1"] = (
        "create_job_document_command.v1"
    )
    command_id: UUID
    tenant_id: UUID
    session_id: UUID
    job_title: JobTitleText
    occurred_at: UtcDatetime


class EmployeeTaskBundleCommand(AuthoringModel):
    schema_version: Literal["employee_task_bundle_command.v1"] = (
        "employee_task_bundle_command.v1"
    )
    command_id: UUID
    tenant_id: UUID
    document_id: UUID
    expected_revision_id: UUID
    expected_revision_hash: Sha256
    action: Literal["add", "replace"]
    target_task_id: UUID | None
    expected_target_version: int | None
    value: TaskBundleEditValue
    occurred_at: UtcDatetime

    @model_validator(mode="after")
    def shape_matches_action(self) -> "EmployeeTaskBundleCommand":
        if self.action == "add":
            if self.target_task_id is not None:
                raise ValueError("add must not target an existing task")
            if self.expected_target_version is not None:
                raise ValueError("add must not carry an expected target version")
            if any(output.output_id is not None for output in self.value.outputs):
                raise ValueError("add outputs must all use a null output_id")
        else:  # replace
            if self.target_task_id is None:
                raise ValueError("replace requires target_task_id")
            if (
                self.expected_target_version is None
                or self.expected_target_version < 1
            ):
                raise ValueError("replace requires expected_target_version >= 1")
        return self


class CreateTaskProposalCommand(AuthoringModel):
    schema_version: Literal["create_task_proposal_command.v1"] = (
        "create_task_proposal_command.v1"
    )
    proposal_id: UUID
    tenant_id: UUID
    session_id: UUID
    document_id: UUID
    base_revision_id: UUID
    base_revision_hash: Sha256
    evidence_state_version: int = Field(ge=0)
    evidence_state_hash: Sha256
    source_kind: Literal["scripted", "llm_operation"]
    source_id: UUID
    draft: TaskBundleProposalDraft
    created_at: UtcDatetime


class EmployeeProposalDecisionCommand(AuthoringModel):
    schema_version: Literal["employee_proposal_decision_command.v1"] = (
        "employee_proposal_decision_command.v1"
    )
    command_id: UUID
    tenant_id: UUID
    document_id: UUID
    proposal_id: UUID
    expected_revision_id: UUID
    expected_revision_hash: Sha256
    action: Literal["accept", "edit", "reject"]
    edited_value: TaskBundleEditValue | None
    occurred_at: UtcDatetime

    @model_validator(mode="after")
    def edited_value_matches_action(self) -> "EmployeeProposalDecisionCommand":
        if self.action == "edit":
            if self.edited_value is None:
                raise ValueError("edit requires edited_value")
        elif self.edited_value is not None:
            raise ValueError("accept/reject must not carry edited_value")
        return self
