"""Pure persistence ports for the greenfield job-analysis engine.

SQLAlchemy rows and JSON dictionaries stop at the adapter boundary. Application
services exchange only these immutable records and domain contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.core.domain import (
    CurrentWorkModel,
    Duty,
    Identifier,
    JdHeader,
    JdTask,
    OpksItem,
    OpksProposal,
    OpksProposalStatus,
    Proposal,
    ProposalStatus,
)

from app.core.journal import (
    ActiveQuestion,
    ConversationTurn,
    JournalEntry,
)
from app.core.state import JobAnalysisState


WORK_MODEL_SCHEMA_ID = "job-analysis-work-model/1"
JD_HEADER_SCHEMA_ID = "job-analysis-jd-header/1"
PROPOSAL_SCHEMA_ID = "job-analysis-proposal/1"
OPKS_ITEM_SCHEMA_ID = "job-analysis-opks-item/1"
OPKS_PROPOSAL_SCHEMA_ID = "job-analysis-opks-proposal/1"
ACTIVE_QUESTION_SCHEMA_ID = "job-analysis-active-question/1"


@dataclass(frozen=True)
class DocumentRecord:
    document_id: UUID
    title: str
    jd_header: JdHeader
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
    conversation_turns: tuple[ConversationTurn, ...]


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


class DocumentRepository(Protocol):
    async def create(self, record: DocumentRecord) -> None: ...

    async def get(
        self, document_id: UUID, *, for_update: bool = False
    ) -> DocumentRecord | None: ...

    async def list(self) -> tuple[DocumentSummary, ...]: ...

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool: ...

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        jd_header: JdHeader,
        work_model: CurrentWorkModel,
        active_question: ActiveQuestion | None,
        updated_at: datetime,
    ) -> bool: ...


class JdTaskRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[JdTask, ...]: ...

    async def replace(
        self, document_id: UUID, tasks: tuple[JdTask, ...]
    ) -> None: ...


class DutyRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[Duty, ...]: ...

    async def replace(
        self,
        document_id: UUID,
        duties: tuple[Duty, ...],
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


class OpksRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[OpksItem, ...]: ...

    async def replace(
        self, document_id: UUID, items: tuple[OpksItem, ...]
    ) -> None: ...


class OpksProposalRepository(Protocol):
    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[OpksProposalStatus] | None = None,
    ) -> tuple[OpksProposal, ...]: ...

    async def replace(
        self,
        document_id: UUID,
        proposals: tuple[OpksProposal, ...],
    ) -> None: ...


class JournalRepository(Protocol):
    async def get(
        self, document_id: UUID, entry_id: Identifier
    ) -> JournalEntry | None: ...

    async def add(self, entry: JournalEntry) -> None: ...

    async def list_conversation_turns(
        self, document_id: UUID
    ) -> tuple[ConversationTurn, ...]: ...


class JobAnalysisUnitOfWork(Protocol):
    documents: DocumentRepository
    tasks: JdTaskRepository
    duties: DutyRepository
    proposals: ProposalRepository
    opks: OpksRepository
    opks_proposals: OpksProposalRepository
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
