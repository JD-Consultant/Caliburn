"""Pure persistence ports for the greenfield job-analysis engine.

SQLAlchemy rows and JSON dictionaries stop at the adapter boundary. Application
services exchange only these immutable records and domain contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import model_validator

from app.job_analysis.domain import (
    CurrentWorkModel,
    DomainModel,
    Identifier,
    JdTask,
    NonEmptyText,
    Proposal,
    ProposalStatus,
    TaskId,
)

from .context import ActiveQuestion, ConversationTurn
from .transition import JobAnalysisState
from .verifier import TurnSpeaker


WORK_MODEL_SCHEMA_ID = "job-analysis-work-model/1"
PROPOSAL_SCHEMA_ID = "job-analysis-proposal/1"
ACTIVE_QUESTION_SCHEMA_ID = "job-analysis-active-question/1"
COMPLETED_TURN_SCHEMA_ID = "job-analysis-completed-turn/1"
DIRECT_EDIT_SCHEMA_ID = "job-analysis-direct-edit/1"
PROPOSAL_DECISION_SCHEMA_ID = "job-analysis-proposal-decision/1"


@dataclass(frozen=True)
class DocumentRecord:
    document_id: UUID
    title: str
    work_model: CurrentWorkModel
    active_question: ActiveQuestion | None
    authority_generation: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("document title cannot be blank")
        if self.authority_generation < 0:
            raise ValueError("authority_generation cannot be negative")


@dataclass(frozen=True)
class LoadedDocument:
    document: DocumentRecord
    state: JobAnalysisState
    recent_turns: tuple["CompletedTurnPayload", ...]


@dataclass(frozen=True)
class DocumentSummary:
    document_id: UUID
    title: str
    task_count: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("document title cannot be blank")
        if self.task_count < 0:
            raise ValueError("task_count cannot be negative")


class CompletedTurnPayload(DomainModel):
    operation_id: Identifier
    employee_turn: ConversationTurn
    consultant_turn: ConversationTurn

    @model_validator(mode="after")
    def roles_match_the_completed_turn(self):
        if self.employee_turn.speaker is not TurnSpeaker.EMPLOYEE:
            raise ValueError("employee_turn must have the employee speaker")
        if self.consultant_turn.speaker is not TurnSpeaker.CONSULTANT:
            raise ValueError("consultant_turn must have the consultant speaker")
        return self


DirectEditKind = Literal["add", "edit", "delete", "reorder"]


class DirectEditPayload(DomainModel):
    edit_kind: DirectEditKind
    task_id: TaskId | None = None
    after: JdTask | None = None
    ordered_task_ids: tuple[TaskId, ...] = ()

    @model_validator(mode="after")
    def completed_value_matches_the_edit(self):
        if self.edit_kind == "reorder":
            if self.task_id is not None or self.after is not None:
                raise ValueError("reorder must not carry one task or completed value")
            if not self.ordered_task_ids:
                raise ValueError("reorder requires ordered_task_ids")
            if len(set(self.ordered_task_ids)) != len(self.ordered_task_ids):
                raise ValueError("reorder task ids must be distinct")
            return self
        if self.task_id is None:
            raise ValueError(f"{self.edit_kind} requires a task id")
        if self.ordered_task_ids:
            raise ValueError(f"{self.edit_kind} must not carry ordered_task_ids")
        if self.edit_kind == "delete":
            if self.after is not None:
                raise ValueError("delete direct edit must have a null completed task")
            return self
        if self.after is None:
            raise ValueError(f"{self.edit_kind} requires the completed task")
        if self.after.task_id != self.task_id:
            raise ValueError("direct edit task id must match its completed task")
        return self


EMPLOYEE_PROPOSAL_DECISIONS = frozenset(
    {
        ProposalStatus.ACCEPTED,
        ProposalStatus.EDITED,
        ProposalStatus.REJECTED,
        ProposalStatus.DEFERRED,
        ProposalStatus.REVISION_REQUESTED,
    }
)


class ProposalDecisionPayload(DomainModel):
    proposal_id: Identifier
    decision: ProposalStatus
    employee_text: NonEmptyText | None = None
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def status_is_an_employee_decision(self):
        if self.decision not in EMPLOYEE_PROPOSAL_DECISIONS:
            raise ValueError(f"{self.decision.value} is not an employee decision")
        return self


JournalKind = Literal["employee_turn", "direct_edit", "proposal_decision"]
JournalPayload = CompletedTurnPayload | DirectEditPayload | ProposalDecisionPayload

_JOURNAL_CONTRACT: dict[type[DomainModel], tuple[JournalKind, str]] = {
    CompletedTurnPayload: ("employee_turn", COMPLETED_TURN_SCHEMA_ID),
    DirectEditPayload: ("direct_edit", DIRECT_EDIT_SCHEMA_ID),
    ProposalDecisionPayload: ("proposal_decision", PROPOSAL_DECISION_SCHEMA_ID),
}


class JournalEntry(DomainModel):
    document_id: UUID
    entry_id: Identifier
    kind: JournalKind
    payload_schema_id: NonEmptyText
    payload: JournalPayload
    created_at: datetime

    @model_validator(mode="after")
    def kind_schema_and_payload_agree(self):
        expected_kind, expected_schema = _JOURNAL_CONTRACT[type(self.payload)]
        if self.kind != expected_kind:
            raise ValueError(
                f"journal kind {self.kind!r} does not match "
                f"{type(self.payload).__name__}"
            )
        if self.payload_schema_id != expected_schema:
            raise ValueError(
                f"payload_schema_id must be {expected_schema!r} "
                f"for {type(self.payload).__name__}"
            )
        return self


class DocumentRepository(Protocol):
    async def create(self, record: DocumentRecord) -> None: ...

    async def get(
        self, document_id: UUID, *, for_update: bool = False
    ) -> DocumentRecord | None: ...

    async def list(self) -> tuple[DocumentSummary, ...]: ...

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        work_model: CurrentWorkModel,
        active_question: ActiveQuestion | None,
        updated_at: datetime,
    ) -> bool: ...


class JdTaskRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[JdTask, ...]: ...

    async def replace(
        self, document_id: UUID, tasks: tuple[JdTask, ...]
    ) -> None: ...


class ProposalRepository(Protocol):
    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[ProposalStatus] | None = None,
    ) -> tuple[Proposal, ...]: ...

    async def replace(
        self, document_id: UUID, proposals: tuple[Proposal, ...]
    ) -> None: ...


class JournalRepository(Protocol):
    async def get(
        self, document_id: UUID, entry_id: Identifier
    ) -> JournalEntry | None: ...

    async def add(self, entry: JournalEntry) -> None: ...

    async def list_recent_turns(
        self, document_id: UUID, *, limit: int | None
    ) -> tuple[CompletedTurnPayload, ...]: ...


class JobAnalysisUnitOfWork(Protocol):
    documents: DocumentRepository
    tasks: JdTaskRepository
    proposals: ProposalRepository
    journal: JournalRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


JobAnalysisUnitOfWorkFactory = Callable[[], JobAnalysisUnitOfWork]
