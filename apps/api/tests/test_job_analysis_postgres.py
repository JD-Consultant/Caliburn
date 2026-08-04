"""Real-PostgreSQL tests for the greenfield Current State adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.adapters.job_analysis_postgres import (
    PersistedJobAnalysisCorruption,
    SqlAlchemyJobAnalysisUnitOfWork,
)
from app.adapters.job_analysis_postgres import serialization as ser
from app.job_analysis.application import (
    COMPLETED_TURN_SCHEMA_ID,
    CONSULTANT_OPENING_SCHEMA_ID,
    OPKS_ITEM_SCHEMA_ID,
    OPKS_PROPOSAL_SCHEMA_ID,
    ActiveQuestion,
    CompletedTurnPayload,
    ConsultantOpeningPayload,
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
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ResponsibilityRole,
    SingleTaskTarget,
    SourceKind,
    SourceRef,
)


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)


async def test_consultant_opening_journal_serialization_round_trip():
    turn = ConversationTurn(
        turn_id="consultant-opening",
        speaker=TurnSpeaker.CONSULTANT,
        text="先說說這個職位主要替誰解決什麼問題？",
    )
    entry = ser.load_journal(
        SimpleNamespace(
            document_id=UUID(int=45),
            entry_id="consultant-opening",
            kind="consultant_opening",
            payload_schema_id=CONSULTANT_OPENING_SCHEMA_ID,
            payload=ConsultantOpeningPayload(
                consultant_turn=turn
            ).model_dump(mode="json"),
            created_at=NOW,
        )
    )

    assert isinstance(entry.payload, ConsultantOpeningPayload)
    assert entry.payload.consultant_turn == turn


def document(document_id: UUID) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        title="門市營運專員",
        jd_header=JdHeader(),
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


def opks_item() -> OpksItem:
    return OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="employee-1",
                ),
                quote="我每週會彙整營運週報",
            ),
        ),
    )


def opks_proposal() -> OpksProposal:
    return OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        action=OpksProposalAction.ADD,
        after=opks_item(),
        base_authority_generation=0,
        created_at=NOW,
    )


async def test_opks_serialization_round_trip_and_corruption_fail_closed():
    item = opks_item()
    item_row = SimpleNamespace(
        entity_id=item.entity_id,
        entity_kind=item.entity_kind.value,
        item_schema_id=OPKS_ITEM_SCHEMA_ID,
        item_payload=ser.dump_opks_item_payload(item),
    )
    proposal_value = opks_proposal()
    proposal_row = SimpleNamespace(
        proposal_id=proposal_value.proposal_id,
        operation_id=proposal_value.operation_id,
        entity_id=proposal_value.entity_id,
        entity_kind=proposal_value.entity_kind.value,
        action=proposal_value.action.value,
        status=proposal_value.status.value,
        base_authority_generation=proposal_value.base_authority_generation,
        proposal_schema_id=OPKS_PROPOSAL_SCHEMA_ID,
        proposal_payload=ser.dump_opks_proposal_payload(proposal_value),
        created_at=proposal_value.created_at,
        resolved_at=proposal_value.resolved_at,
    )

    assert ser.load_opks_item(item_row) == item
    assert ser.load_opks_proposal(proposal_row) == proposal_value

    item_row.item_schema_id = "job-analysis-opks-item/9"
    with pytest.raises(PersistedJobAnalysisCorruption, match="OPKS item schema"):
        ser.load_opks_item(item_row)
    proposal_row.proposal_payload = {}
    with pytest.raises(PersistedJobAnalysisCorruption, match="OPKS Proposal"):
        ser.load_opks_proposal(proposal_row)


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
        await uow.opks.replace(document_id, (opks_item(),))
        await uow.opks_proposals.replace(document_id, (opks_proposal(),))
        await uow.journal.add(
            completed_turn(document_id, entry_id="entry-1", minute=1)
        )
        await uow.journal.add(
            completed_turn(document_id, entry_id="entry-2", minute=2)
        )
        await uow.commit()

    deferred = proposal().model_copy(update={"status": ProposalStatus.DEFERRED})
    deferred_opks = opks_proposal().model_copy(
        update={"status": OpksProposalStatus.DEFERRED}
    )
    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        await uow.proposals.replace(document_id, (deferred,))
        await uow.opks_proposals.replace(document_id, (deferred_opks,))
        await uow.commit()

    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        loaded_document = await uow.documents.get(document_id)
        loaded_tasks = await uow.tasks.list(document_id)
        loaded_proposals = await uow.proposals.list(document_id)
        loaded_opks = await uow.opks.list(document_id)
        loaded_opks_proposals = await uow.opks_proposals.list(document_id)
        conversation = await uow.journal.list_conversation_turns(document_id)
        summaries = await uow.documents.list()

    assert loaded_document == document(document_id)
    assert loaded_tasks == (jd_task(),)
    assert loaded_proposals == (deferred,)
    assert loaded_opks == (opks_item(),)
    assert loaded_opks_proposals == (deferred_opks,)
    assert [turn.speaker for turn in conversation] == [
        TurnSpeaker.EMPLOYEE,
        TurnSpeaker.CONSULTANT,
        TurnSpeaker.EMPLOYEE,
        TurnSpeaker.CONSULTANT,
    ]
    assert conversation[-1].turn_id == "consultant-2"
    summary = next(item for item in summaries if item.document_id == document_id)
    assert summary.task_count == 1


async def test_opks_identity_is_document_scoped_and_document_delete_cascades(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    first_id = cleanup_job_analysis_rows
    second_id = uuid4()
    try:
        async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
            for document_id in (first_id, second_id):
                await uow.documents.create(document(document_id))
                await uow.tasks.replace(document_id, (jd_task(),))
                await uow.opks.replace(document_id, (opks_item(),))
                await uow.opks_proposals.replace(
                    document_id,
                    (opks_proposal(),),
                )
            await uow.commit()

        async with postgres_session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM job_analysis_documents "
                    "WHERE document_id = :document_id"
                ),
                {"document_id": str(first_id)},
            )
            await session.commit()

        async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
            assert await uow.opks.list(first_id) == ()
            assert await uow.opks_proposals.list(first_id) == ()
            assert await uow.opks.list(second_id) == (opks_item(),)
            assert await uow.opks_proposals.list(second_id) == (opks_proposal(),)
    finally:
        async with postgres_session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM job_analysis_documents "
                    "WHERE document_id = :document_id"
                ),
                {"document_id": str(second_id)},
            )
            await session.commit()


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
                    jd_header=JdHeader(),
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
