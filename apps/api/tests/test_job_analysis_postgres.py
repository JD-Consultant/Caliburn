"""Real-PostgreSQL tests for the greenfield Current State adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text

from app.adapters.job_analysis_postgres import (
    PersistedJobAnalysisCorruption,
    SqlAlchemyJobAnalysisUnitOfWork,
)
from app.job_analysis.application import (
    COMPLETED_TURN_SCHEMA_ID,
    ActiveQuestion,
    CompletedTurnPayload,
    ConversationTurn,
    DocumentRecord,
    JournalEntry,
    TurnSpeaker,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    Enabler,
    EnablerKind,
    JdEntry,
    JdTask,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ResponsibilityRole,
    SingleTaskTarget,
)


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)


def document(document_id: UUID) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        title="門市營運專員",
        work_model=CurrentWorkModel(),
        active_question=ActiveQuestion(
            turn_id="turn-1",
            text="請說說你最常做的工作。",
        ),
        authority_generation=0,
        created_at=NOW,
        updated_at=NOW,
    )


def jd_task() -> JdTask:
    return JdTask(
        task_id="task-1",
        statement="每週彙整營運週報",
        purpose_result="讓主管掌握營運狀況",
        context="每週五結算後",
        frequency_text="每週一次",
        responsibility_role=ResponsibilityRole.PRIMARY,
        enablers=(Enabler(kind=EnablerKind.TOOL_SYSTEM, name="Excel"),),
        display_order=0,
    )


def proposal() -> Proposal:
    task = jd_task()
    return Proposal(
        proposal_id="proposal-1",
        target=SingleTaskTarget(
            action=ProposalAction.ADD,
            task_id=task.task_id,
        ),
        jd_before=(JdEntry(task_id=task.task_id, value=None),),
        jd_after=(JdEntry(task_id=task.task_id, value=task),),
    )


def completed_turn(document_id: UUID, *, entry_id: str, minute: int) -> JournalEntry:
    payload = CompletedTurnPayload(
        operation_id=f"operation-{minute}",
        employee_turn=ConversationTurn(
            turn_id=f"employee-{minute}",
            speaker=TurnSpeaker.EMPLOYEE,
            text="我每週會彙整營運週報",
        ),
        consultant_turn=ConversationTurn(
            turn_id=f"consultant-{minute}",
            speaker=TurnSpeaker.CONSULTANT,
            text="這份週報主要交給誰？",
        ),
    )
    return JournalEntry(
        document_id=document_id,
        entry_id=entry_id,
        kind="employee_turn",
        payload_schema_id=COMPLETED_TURN_SCHEMA_ID,
        payload=payload,
        created_at=NOW + timedelta(minutes=minute),
    )


async def seed_document(session_factory, document_id: UUID) -> None:
    async with SqlAlchemyJobAnalysisUnitOfWork(session_factory) as uow:
        await uow.documents.create(document(document_id))
        await uow.commit()


async def test_document_tasks_proposal_and_recent_turns_round_trip(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        await uow.documents.create(document(document_id))
        await uow.tasks.replace(document_id, (jd_task(),))
        await uow.proposals.replace(document_id, (proposal(),))
        await uow.journal.add(
            completed_turn(document_id, entry_id="entry-1", minute=1)
        )
        await uow.journal.add(
            completed_turn(document_id, entry_id="entry-2", minute=2)
        )
        await uow.commit()

    deferred = proposal().model_copy(update={"status": ProposalStatus.DEFERRED})
    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        await uow.proposals.replace(document_id, (deferred,))
        await uow.commit()

    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        loaded_document = await uow.documents.get(document_id)
        loaded_tasks = await uow.tasks.list(document_id)
        loaded_proposals = await uow.proposals.list(document_id)
        recent = await uow.journal.list_recent_turns(document_id, limit=1)
        summaries = await uow.documents.list()

    assert loaded_document == document(document_id)
    assert loaded_tasks == (jd_task(),)
    assert loaded_proposals == (deferred,)
    assert [turn.operation_id for turn in recent] == ["operation-2"]
    summary = next(item for item in summaries if item.document_id == document_id)
    assert summary.task_count == 1


async def test_document_for_update_really_holds_the_row_lock(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    await seed_document(postgres_session_factory, document_id)

    holder = SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await holder.__aenter__()
    contender = None
    try:
        await holder.documents.get(document_id, for_update=True)

        async def update_from_another_transaction() -> bool:
            async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
                changed = await uow.documents.update_authority(
                    document_id,
                    expected_generation=0,
                    work_model=CurrentWorkModel(),
                    active_question=None,
                    updated_at=NOW + timedelta(minutes=1),
                )
                await uow.commit()
                return changed

        contender = asyncio.create_task(update_from_another_transaction())
        await asyncio.sleep(0.05)
        assert not contender.done()
    finally:
        # Rollback is enough to release the read-side lock. Keep this in finally
        # so a failed assertion never strands the cleanup transaction.
        await holder.__aexit__(None, None, None)

    assert contender is not None
    assert await asyncio.wait_for(contender, timeout=1) is True


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        (
            "UPDATE job_analysis_documents "
            "SET work_model_schema_id = 'unknown/9' "
            "WHERE document_id = :document_id",
            "work model schema",
        ),
        (
            "UPDATE job_analysis_jd_tasks "
            "SET enablers_json = '[{\"kind\":\"wrong\",\"name\":\"Excel\"}]'::jsonb "
            "WHERE document_id = :document_id",
            "JD Task",
        ),
        (
            "UPDATE job_analysis_proposals "
            "SET proposal_payload = '{}'::jsonb "
            "WHERE document_id = :document_id",
            "Proposal",
        ),
    ],
)
async def test_corrupt_rows_fail_closed(
    statement,
    message,
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        await uow.documents.create(document(document_id))
        await uow.tasks.replace(document_id, (jd_task(),))
        await uow.proposals.replace(document_id, (proposal(),))
        await uow.commit()

    async with postgres_session_factory() as session:
        await session.execute(text(statement), {"document_id": str(document_id)})
        await session.commit()

    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(PersistedJobAnalysisCorruption, match=message):
            if "documents" in statement:
                await uow.documents.get(document_id)
            elif "jd_tasks" in statement:
                await uow.tasks.list(document_id)
            else:
                await uow.proposals.list(document_id)
