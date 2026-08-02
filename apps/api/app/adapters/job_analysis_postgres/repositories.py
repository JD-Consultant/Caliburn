"""SQLAlchemy repositories and one-transaction Unit of Work."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.job_analysis.application import (
    OPKS_ITEM_SCHEMA_ID,
    OPKS_PROPOSAL_SCHEMA_ID,
    PROPOSAL_SCHEMA_ID,
    WORK_MODEL_SCHEMA_ID,
    ActiveQuestion,
    CompletedTurnPayload,
    ConsultantOpeningPayload,
    ConversationTurn,
    DocumentRecord,
    DocumentSummary,
    JournalEntry,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    OpksItem,
    OpksProposal,
    OpksProposalStatus,
    Proposal,
    ProposalStatus,
)

from . import serialization as ser
from .models import (
    JobAnalysisDocumentRow,
    JobAnalysisJdTaskRow,
    JobAnalysisJournalRow,
    JobAnalysisOpksItemRow,
    JobAnalysisOpksProposalRow,
    JobAnalysisProposalRow,
)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: DocumentRecord) -> None:
        self._session.add(
            JobAnalysisDocumentRow(
                document_id=record.document_id,
                title=record.title,
                work_model_schema_id=WORK_MODEL_SCHEMA_ID,
                work_model_json=ser.dump_work_model(record.work_model),
                active_question_json=ser.dump_active_question(record.active_question),
                authority_generation=record.authority_generation,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )

    async def get(
        self,
        document_id: UUID,
        *,
        for_update: bool = False,
    ) -> DocumentRecord | None:
        statement = select(JobAnalysisDocumentRow).where(
            JobAnalysisDocumentRow.document_id == document_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = await self._session.scalar(statement)
        return None if row is None else ser.load_document(row)

    async def list(self) -> tuple[DocumentSummary, ...]:
        rows = (
            await self._session.execute(
                select(
                    JobAnalysisDocumentRow,
                    func.count(JobAnalysisJdTaskRow.task_id),
                )
                .outerjoin(
                    JobAnalysisJdTaskRow,
                    JobAnalysisJdTaskRow.document_id
                    == JobAnalysisDocumentRow.document_id,
                )
                .group_by(JobAnalysisDocumentRow.document_id)
                .order_by(
                    JobAnalysisDocumentRow.updated_at.desc(),
                    JobAnalysisDocumentRow.document_id,
                )
            )
        ).all()
        return tuple(
            DocumentSummary(
                document_id=row.document_id,
                title=row.title,
                task_count=task_count,
                updated_at=row.updated_at,
            )
            for row, task_count in rows
        )

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool:
        result = await self._session.execute(
            update(JobAnalysisDocumentRow)
            .where(JobAnalysisDocumentRow.document_id == document_id)
            .values(title=title, updated_at=updated_at)
        )
        return result.rowcount == 1

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        work_model: CurrentWorkModel,
        active_question: ActiveQuestion | None,
        updated_at: datetime,
    ) -> bool:
        result = await self._session.execute(
            update(JobAnalysisDocumentRow)
            .where(
                JobAnalysisDocumentRow.document_id == document_id,
                JobAnalysisDocumentRow.authority_generation == expected_generation,
            )
            .values(
                work_model_schema_id=WORK_MODEL_SCHEMA_ID,
                work_model_json=ser.dump_work_model(work_model),
                active_question_json=ser.dump_active_question(active_question),
                authority_generation=expected_generation + 1,
                updated_at=updated_at,
            )
        )
        return result.rowcount == 1


class SqlAlchemyJdTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, document_id: UUID) -> tuple[JdTask, ...]:
        rows = (
            await self._session.scalars(
                select(JobAnalysisJdTaskRow)
                .where(JobAnalysisJdTaskRow.document_id == document_id)
                .order_by(
                    JobAnalysisJdTaskRow.display_order,
                    JobAnalysisJdTaskRow.task_id,
                )
            )
        ).all()
        return tuple(ser.load_jd_task(row) for row in rows)

    async def replace(
        self,
        document_id: UUID,
        tasks: tuple[JdTask, ...],
    ) -> None:
        await self._session.execute(
            delete(JobAnalysisJdTaskRow).where(
                JobAnalysisJdTaskRow.document_id == document_id
            )
        )
        now = datetime.now(UTC)
        self._session.add_all(
            [
                JobAnalysisJdTaskRow(
                    document_id=document_id,
                    task_id=task.task_id,
                    statement=task.statement,
                    purpose_result=task.purpose_result,
                    context=task.context,
                    frequency_text=task.frequency_text,
                    responsibility_role=(
                        task.responsibility_role.value
                        if task.responsibility_role is not None
                        else None
                    ),
                    enablers_json=ser.dump_jd_task_enablers(task),
                    display_order=task.display_order,
                    created_at=now,
                    updated_at=now,
                )
                for task in tasks
            ]
        )


class SqlAlchemyProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[ProposalStatus] | None = None,
    ) -> tuple[Proposal, ...]:
        statement = select(JobAnalysisProposalRow).where(
            JobAnalysisProposalRow.document_id == document_id
        )
        if statuses is not None:
            statement = statement.where(
                JobAnalysisProposalRow.status.in_(
                    tuple(status.value for status in statuses)
                )
            )
        rows = (
            await self._session.scalars(
                statement.order_by(
                    JobAnalysisProposalRow.created_at,
                    JobAnalysisProposalRow.proposal_id,
                )
            )
        ).all()
        return tuple(ser.load_proposal(row) for row in rows)

    async def replace(
        self,
        document_id: UUID,
        proposals: tuple[Proposal, ...],
    ) -> None:
        document = await self._session.get(JobAnalysisDocumentRow, document_id)
        if document is None:
            raise ValueError(f"document {document_id} does not exist")
        existing = {
            row.proposal_id: row
            for row in (
                await self._session.scalars(
                    select(JobAnalysisProposalRow).where(
                        JobAnalysisProposalRow.document_id == document_id
                    )
                )
            ).all()
        }
        await self._session.execute(
            delete(JobAnalysisProposalRow).where(
                JobAnalysisProposalRow.document_id == document_id
            )
        )
        now = datetime.now(UTC)
        terminal = {
            ProposalStatus.ACCEPTED,
            ProposalStatus.EDITED,
            ProposalStatus.REJECTED,
            ProposalStatus.REVISION_REQUESTED,
            ProposalStatus.STALE,
        }
        rows: list[JobAnalysisProposalRow] = []
        for proposal in proposals:
            previous = existing.get(proposal.proposal_id)
            rows.append(
                JobAnalysisProposalRow(
                    document_id=document_id,
                    proposal_id=proposal.proposal_id,
                    status=proposal.status.value,
                    base_authority_generation=document.authority_generation,
                    proposal_schema_id=PROPOSAL_SCHEMA_ID,
                    proposal_payload=ser.dump_proposal_payload(proposal),
                    caused_by_decision_id=proposal.caused_by_decision_id,
                    created_at=previous.created_at if previous is not None else now,
                    resolved_at=(
                        (
                            previous.resolved_at
                            if previous is not None
                            and previous.resolved_at is not None
                            else now
                        )
                        if proposal.status in terminal
                        else None
                    ),
                )
            )
        self._session.add_all(rows)


class SqlAlchemyOpksRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, document_id: UUID) -> tuple[OpksItem, ...]:
        rows = (
            await self._session.scalars(
                select(JobAnalysisOpksItemRow)
                .where(JobAnalysisOpksItemRow.document_id == document_id)
                .order_by(
                    JobAnalysisOpksItemRow.created_at,
                    JobAnalysisOpksItemRow.entity_id,
                )
            )
        ).all()
        return tuple(ser.load_opks_item(row) for row in rows)

    async def replace(
        self,
        document_id: UUID,
        items: tuple[OpksItem, ...],
    ) -> None:
        existing = {
            row.entity_id: row
            for row in (
                await self._session.scalars(
                    select(JobAnalysisOpksItemRow).where(
                        JobAnalysisOpksItemRow.document_id == document_id
                    )
                )
            ).all()
        }
        await self._session.execute(
            delete(JobAnalysisOpksItemRow).where(
                JobAnalysisOpksItemRow.document_id == document_id
            )
        )
        now = datetime.now(UTC)
        self._session.add_all(
            [
                JobAnalysisOpksItemRow(
                    document_id=document_id,
                    entity_id=item.entity_id,
                    entity_kind=item.entity_kind.value,
                    item_schema_id=OPKS_ITEM_SCHEMA_ID,
                    item_payload=ser.dump_opks_item_payload(item),
                    created_at=(
                        existing[item.entity_id].created_at
                        if item.entity_id in existing
                        else now
                    ),
                    updated_at=now,
                )
                for item in items
            ]
        )


class SqlAlchemyOpksProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[OpksProposalStatus] | None = None,
    ) -> tuple[OpksProposal, ...]:
        statement = select(JobAnalysisOpksProposalRow).where(
            JobAnalysisOpksProposalRow.document_id == document_id
        )
        if statuses is not None:
            statement = statement.where(
                JobAnalysisOpksProposalRow.status.in_(
                    tuple(status.value for status in statuses)
                )
            )
        rows = (
            await self._session.scalars(
                statement.order_by(
                    JobAnalysisOpksProposalRow.created_at,
                    JobAnalysisOpksProposalRow.proposal_id,
                )
            )
        ).all()
        return tuple(ser.load_opks_proposal(row) for row in rows)

    async def replace(
        self,
        document_id: UUID,
        proposals: tuple[OpksProposal, ...],
    ) -> None:
        await self._session.execute(
            delete(JobAnalysisOpksProposalRow).where(
                JobAnalysisOpksProposalRow.document_id == document_id
            )
        )
        self._session.add_all(
            [
                JobAnalysisOpksProposalRow(
                    document_id=document_id,
                    proposal_id=proposal.proposal_id,
                    operation_id=proposal.operation_id,
                    entity_id=proposal.entity_id,
                    entity_kind=proposal.entity_kind.value,
                    action=proposal.action.value,
                    status=proposal.status.value,
                    base_authority_generation=proposal.base_authority_generation,
                    proposal_schema_id=OPKS_PROPOSAL_SCHEMA_ID,
                    proposal_payload=ser.dump_opks_proposal_payload(proposal),
                    created_at=proposal.created_at,
                    resolved_at=proposal.resolved_at,
                )
                for proposal in proposals
            ]
        )


class SqlAlchemyJournalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        document_id: UUID,
        entry_id: str,
    ) -> JournalEntry | None:
        row = await self._session.scalar(
            select(JobAnalysisJournalRow).where(
                JobAnalysisJournalRow.document_id == document_id,
                JobAnalysisJournalRow.entry_id == entry_id,
            )
        )
        return None if row is None else ser.load_journal(row)

    async def add(self, entry: JournalEntry) -> None:
        self._session.add(
            JobAnalysisJournalRow(
                document_id=entry.document_id,
                entry_id=entry.entry_id,
                kind=entry.kind,
                payload_schema_id=entry.payload_schema_id,
                payload=ser.dump_journal_payload(entry),
                created_at=entry.created_at,
            )
        )

    async def list_conversation_turns(
        self,
        document_id: UUID,
    ) -> tuple[ConversationTurn, ...]:
        rows = (
            await self._session.scalars(
                select(JobAnalysisJournalRow)
                .where(
                    JobAnalysisJournalRow.document_id == document_id,
                    JobAnalysisJournalRow.kind.in_(
                        ("consultant_opening", "employee_turn")
                    ),
                )
                .order_by(JobAnalysisJournalRow.journal_sequence.asc())
            )
        ).all()
        turns: list[ConversationTurn] = []
        for row in rows:
            payload = ser.load_journal(row).payload
            if isinstance(payload, ConsultantOpeningPayload):
                turns.append(payload.consultant_turn)
            elif isinstance(payload, CompletedTurnPayload):
                turns.extend((payload.employee_turn, payload.consultant_turn))
        return tuple(turns)


class SqlAlchemyJobAnalysisUnitOfWork:
    """One AsyncSession and one explicit transaction; repositories never commit."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False
        self.documents: SqlAlchemyDocumentRepository
        self.tasks: SqlAlchemyJdTaskRepository
        self.proposals: SqlAlchemyProposalRepository
        self.opks: SqlAlchemyOpksRepository
        self.opks_proposals: SqlAlchemyOpksProposalRepository
        self.journal: SqlAlchemyJournalRepository

    async def __aenter__(self) -> "SqlAlchemyJobAnalysisUnitOfWork":
        if self._session is not None:
            raise RuntimeError("JobAnalysisUnitOfWork instances are not re-enterable")
        self._session = self._session_factory()
        await self._session.begin()
        self.documents = SqlAlchemyDocumentRepository(self._session)
        self.tasks = SqlAlchemyJdTaskRepository(self._session)
        self.proposals = SqlAlchemyProposalRepository(self._session)
        self.opks = SqlAlchemyOpksRepository(self._session)
        self.opks_proposals = SqlAlchemyOpksProposalRepository(self._session)
        self.journal = SqlAlchemyJournalRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        await self._session.commit()
        self._committed = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
