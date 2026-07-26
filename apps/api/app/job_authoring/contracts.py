"""Immutable domain value objects for the Job Authoring Core.

Field shapes are the implementation contract from the 2026-07-23 minimal
authoring core plan §5. Only optional fields explicitly named there are
nullable; no additional nullable fields may be introduced.

Text rules (plan §5.1): reject blank only; never ``strip``, NFKC-normalize,
re-punctuate, or rewrite. Length bounds count Unicode code points. All
collections are tuples; all models are strict and frozen.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .canonical import canonical_hash, canonical_hash_excluding


class AuthoringModel(BaseModel):
    """Strict immutable value object (extra forbidden, frozen, tuple fields)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --- shared scalars ---------------------------------------------------------


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value cannot be blank")
    return value


def _utc_only(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC offset +00:00")
    return value


JobTitleText = Annotated[
    str, Field(min_length=1, max_length=256), AfterValidator(_not_blank)
]
TaskStatementText = Annotated[
    str, Field(min_length=1, max_length=512), AfterValidator(_not_blank)
]
OutputStatementText = Annotated[
    str, Field(min_length=1, max_length=512), AfterValidator(_not_blank)
]
PlainReasonText = Annotated[
    str, Field(min_length=1, max_length=512), AfterValidator(_not_blank)
]
ShortText = Annotated[
    str, Field(min_length=1, max_length=512), AfterValidator(_not_blank)
]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_utc_only)]

MAX_TASKS_PER_DRAFT = 64
MAX_OUTPUTS_PER_TASK = 16


# --- provenance / evidence refs (plan §5.2) ---------------------------------


class EvidenceBasisRef(AuthoringModel):
    evidence_id: UUID
    evidence_hash: Sha256


class JobFieldProvenance(AuthoringModel):
    source_kind: Literal[
        "employee_document_edit",
        "accepted_ai_proposal",
        "employee_proposal_edit",
    ]
    source_id: UUID
    evidence_basis: tuple[EvidenceBasisRef, ...] = ()


class ProposalStaleReason(StrEnum):
    DOCUMENT_REVISION_ADVANCED = "document_revision_advanced"
    BASE_REVISION_CHANGED = "base_revision_changed"
    EVIDENCE_BASIS_CHANGED = "evidence_basis_changed"


# --- task / output / draft (plan §5.3) --------------------------------------


class JobOutput(AuthoringModel):
    output_id: UUID
    statement: OutputStatementText
    provenance: JobFieldProvenance


class JobTask(AuthoringModel):
    task_id: UUID
    entity_version: int = Field(ge=1)
    statement: TaskStatementText
    outputs: tuple[JobOutput, ...] = ()
    provenance: JobFieldProvenance

    @model_validator(mode="after")
    def outputs_bounded_and_unique(self) -> "JobTask":
        if len(self.outputs) > MAX_OUTPUTS_PER_TASK:
            raise ValueError(
                f"task may hold at most {MAX_OUTPUTS_PER_TASK} outputs"
            )
        ids = [output.output_id for output in self.outputs]
        if len(set(ids)) != len(ids):
            raise ValueError("output_id must be unique within a task")
        return self


class JobDocumentDraft(AuthoringModel):
    schema_version: Literal["job_document_draft.v1"] = "job_document_draft.v1"
    document_id: UUID
    session_id: UUID
    job_title: JobTitleText
    tasks: tuple[JobTask, ...] = ()

    @model_validator(mode="after")
    def tasks_bounded_and_ids_unique(self) -> "JobDocumentDraft":
        if len(self.tasks) > MAX_TASKS_PER_DRAFT:
            raise ValueError(
                f"draft may hold at most {MAX_TASKS_PER_DRAFT} tasks"
            )
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("task_id must be unique within a draft")
        output_ids = [
            output.output_id for task in self.tasks for output in task.outputs
        ]
        if len(set(output_ids)) != len(output_ids):
            raise ValueError("output_id must be unique within a draft")
        return self


# --- revision view (plan §5.4) ----------------------------------------------


class JobDocumentRevision(AuthoringModel):
    schema_version: Literal["job_document_revision.v1"] = "job_document_revision.v1"
    revision_id: UUID
    document_id: UUID
    revision_number: int = Field(ge=0)
    parent_revision_id: UUID | None
    snapshot: JobDocumentDraft
    snapshot_hash: Sha256
    source_kind: Literal[
        "initial",
        "employee_direct_edit",
        "ai_proposal_accept",
        "employee_proposal_edit",
    ]
    command_id: UUID
    occurred_at: UtcDatetime

    @model_validator(mode="after")
    def snapshot_hash_and_lineage_coherent(self) -> "JobDocumentRevision":
        if self.snapshot_hash != canonical_hash(self.snapshot):
            raise ValueError("snapshot_hash must equal canonical_hash(snapshot)")
        if self.revision_number == 0:
            if self.source_kind != "initial" or self.parent_revision_id is not None:
                raise ValueError("revision 0 must be initial with a null parent")
        else:
            if self.source_kind == "initial" or self.parent_revision_id is None:
                raise ValueError("revision >0 must be non-initial with a parent")
        return self


# --- direct edit value payloads (plan §5.5) ---------------------------------


class EditableOutputValue(AuthoringModel):
    output_id: UUID | None
    statement: OutputStatementText


class TaskBundleEditValue(AuthoringModel):
    statement: TaskStatementText
    outputs: tuple[EditableOutputValue, ...] = ()


# --- proposal drafts and persisted payload (plan §5.6) ----------------------

EvidenceBasis = Annotated[tuple[EvidenceBasisRef, ...], Field(min_length=1)]


class ProposedOutputDraft(AuthoringModel):
    statement: OutputStatementText
    evidence_basis: EvidenceBasis


class TaskBundleProposalDraft(AuthoringModel):
    statement: TaskStatementText
    evidence_basis: EvidenceBasis
    outputs: tuple[ProposedOutputDraft, ...] = ()
    plain_language_reason: PlainReasonText
    limitations: tuple[ShortText, ...] = ()


class ProposedJobOutput(AuthoringModel):
    output_id: UUID
    statement: OutputStatementText
    evidence_basis: EvidenceBasis


class ProposedJobTask(AuthoringModel):
    task_id: UUID
    statement: TaskStatementText
    outputs: tuple[ProposedJobOutput, ...]
    evidence_basis: EvidenceBasis


class AiTaskBundleProposal(AuthoringModel):
    schema_version: Literal["ai_task_bundle_proposal.v1"] = "ai_task_bundle_proposal.v1"
    proposal_id: UUID
    session_id: UUID
    document_id: UUID
    base_revision_id: UUID
    base_revision_hash: Sha256
    evidence_state_version: int = Field(ge=0)
    evidence_state_hash: Sha256
    operation: Literal["add_task"]
    proposed_task: ProposedJobTask
    plain_language_reason: PlainReasonText
    limitations: tuple[ShortText, ...]
    source_kind: Literal["scripted", "llm_operation"]
    source_id: UUID
    created_at: UtcDatetime


# --- employee decision and proposal view (plan §5.7, §5.6) ------------------


class EmployeeProposalDecision(AuthoringModel):
    schema_version: Literal["employee_proposal_decision.v1"] = (
        "employee_proposal_decision.v1"
    )
    command_id: UUID
    proposal_id: UUID
    action: Literal["accept", "edit", "reject"]
    base_revision_id: UUID
    base_revision_hash: Sha256
    final_task: JobTask | None
    result_revision_id: UUID | None
    decided_at: UtcDatetime

    @model_validator(mode="after")
    def outcome_matches_action(self) -> "EmployeeProposalDecision":
        if self.action in ("accept", "edit"):
            if self.final_task is None or self.result_revision_id is None:
                raise ValueError(
                    "accept/edit require final_task and result_revision_id"
                )
        elif self.final_task is not None or self.result_revision_id is not None:
            raise ValueError("reject must not carry final_task or result_revision_id")
        return self


class TaskProposalView(AuthoringModel):
    schema_version: Literal["task_proposal_view.v1"] = "task_proposal_view.v1"
    proposal: AiTaskBundleProposal
    status: Literal["pending", "accepted", "edited", "rejected", "stale"]
    decision: EmployeeProposalDecision | None = None
    result_revision_id: UUID | None = None
    stale_reason: ProposalStaleReason | None = None
    resolved_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def lifecycle_shape(self) -> "TaskProposalView":
        status = self.status
        if status == "pending":
            if any(
                field is not None
                for field in (
                    self.decision,
                    self.result_revision_id,
                    self.stale_reason,
                    self.resolved_at,
                )
            ):
                raise ValueError("pending view carries no decision/result/stale")
        elif status in ("accepted", "edited"):
            if (
                self.decision is None
                or self.result_revision_id is None
                or self.resolved_at is None
                or self.stale_reason is not None
            ):
                raise ValueError(
                    "accepted/edited require decision, result, resolved; no stale"
                )
            expected = "accept" if status == "accepted" else "edit"
            if self.decision.action != expected:
                raise ValueError("decision action must match the view status")
            if self.decision.result_revision_id != self.result_revision_id:
                raise ValueError("view result must equal decision result")
        elif status == "rejected":
            if (
                self.decision is None
                or self.resolved_at is None
                or self.result_revision_id is not None
                or self.stale_reason is not None
            ):
                raise ValueError(
                    "rejected requires decision and resolved; no result/stale"
                )
            if self.decision.action != "reject":
                raise ValueError("rejected view requires a reject decision")
        else:  # stale
            if (
                self.decision is not None
                or self.result_revision_id is not None
                or self.stale_reason is None
                or self.resolved_at is None
            ):
                raise ValueError(
                    "stale requires stale_reason and resolved; no decision/result"
                )
        return self


# --- deterministic bounded digest (plan §5.8) -------------------------------


class JobStateDigestTask(AuthoringModel):
    ordinal: str
    task_id: UUID
    entity_version: int = Field(ge=1)
    statement_excerpt: str
    output_excerpts: tuple[str, ...]
    omitted_output_count: int = Field(ge=0)


class JobStateDigest(AuthoringModel):
    schema_version: Literal["job_state_digest.v1"] = "job_state_digest.v1"
    projection_version: Literal["1.0.0"] = "1.0.0"
    document_id: UUID
    session_id: UUID
    revision_id: UUID
    revision_number: int = Field(ge=0)
    revision_hash: Sha256
    job_title: JobTitleText
    tasks: tuple[JobStateDigestTask, ...]
    omitted_task_count: int = Field(ge=0)
    pending_proposal_ids: tuple[UUID, ...]
    pending_proposal_count: int = Field(ge=0)
    stale_proposal_count: int = Field(ge=0)
    digest_hash: Sha256

    @model_validator(mode="after")
    def digest_hash_matches(self) -> "JobStateDigest":
        if self.digest_hash != canonical_hash_excluding(self, exclude="digest_hash"):
            raise ValueError("digest_hash must equal the canonical hash of the body")
        return self
