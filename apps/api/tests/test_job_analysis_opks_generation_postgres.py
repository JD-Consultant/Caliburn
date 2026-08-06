"""Durable OPKS generation：provider 在交易外，commit 前重驗 authority。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    OpksGenerationOutcome,
    OpksGenerationPayload,
    StaleAuthoritySnapshot,
    add_opks_item,
    create_document,
    generate_opks_proposals,
    load_document,
)
from app.job_analysis.application.errors import IdempotencyConflict
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
)
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)


pytestmark = pytest.mark.asyncio
CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=1024,
    timeout_seconds=90,
)


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def source(source_id: str = "turn-1") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id)


def work_task(task_id: str, statement: str) -> Task:
    return Task(
        task_id=task_id,
        statement=statement,
        action="彙整",
        object="營運資料",
        support_links=(
            SupportLink(
                source_ref=source(f"source-{task_id}"),
                quote=statement,
            ),
        ),
    )


def current_knowledge() -> OpksItem:
    return OpksItem(
        entity_id="knowledge-existing",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        display_order=0,
        evidence_links=(
            OpksEvidenceLink(
                source_ref=source("source-existing"),
                quote="我會先確認營運指標定義",
            ),
        ),
    )


async def seed(
    session_factory,
    document_id,
    *,
    include_second_task: bool = False,
    items: tuple[OpksItem, ...] = (),
):
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    tasks = [work_task("task-1", "我每週彙整營運週報")]
    jd = [JdTask(task_id="task-1", statement="彙整營運週報", display_order=0)]
    if include_second_task:
        tasks.append(work_task("task-2", "我每月整理排班資料"))
        jd.append(JdTask(task_id="task-2", statement="整理排班資料", display_order=1))
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        await uow.tasks.replace(document_id, tuple(jd))
        await uow.opks.replace(document_id, items)
        updated = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=JdHeader(),
            work_model=CurrentWorkModel(tasks=tuple(tasks)),
            active_question=record.active_question,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert updated
        await uow.commit()
    return uow_factory


def provider_response(wire: OpksResultWire) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        body={
            "model": CONFIG.model,
            "choices": [
                {
                    "message": {"content": wire.model_dump_json(), "refusal": None},
                    "finish_reason": "stop",
                }
            ],
        },
    )


class RecordingTransport:
    def __init__(self, wire: OpksResultWire, before_return=None):
        self.response = provider_response(wire)
        self.before_return = before_return
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        if self.before_return is not None:
            await self.before_return()
        return self.response


def adapter(transport) -> OpenRouterAdapter:
    return OpenRouterAdapter(
        config=CONFIG,
        api_key="sk-test",
        transport=transport,
    )


def add_output_wire() -> OpksResultWire:
    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="營運週報",
            ),
        )
    )


async def test_generation_persists_one_proposal_and_receipt_then_replays_without_call(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    transport = RecordingTransport(add_output_wire())

    first = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-1",
    )
    replay = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-1",
    )
    loaded = await load_document(uow_factory, document_id)

    assert first == replay
    assert first.outcome is OpksGenerationOutcome.PROPOSED
    assert first.proposal_ids == ("generate-1-op0",)
    assert transport.calls == 1
    assert loaded is not None
    assert loaded.document.authority_generation == 2
    proposal = loaded.state.opks_proposals[0]
    assert proposal.proposal_id == "generate-1-op0"
    assert proposal.entity_id == "generate-1-o0"
    assert proposal.after is not None
    assert proposal.after.task_refs == ("task-1",)
    assert loaded.state.current_opks.items == ()

    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-1")
    assert receipt is not None
    assert isinstance(receipt.payload, OpksGenerationPayload)
    assert receipt.payload.selected_task_id == "task-1"
    assert receipt.payload.proposal_ids == ("generate-1-op0",)


async def test_same_key_for_another_task_is_an_idempotency_conflict_before_provider(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        include_second_task=True,
    )
    transport = RecordingTransport(add_output_wire())
    model = adapter(transport)
    await generate_opks_proposals(
        uow_factory,
        adapter=model,
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-same-key",
    )

    with pytest.raises(IdempotencyConflict):
        await generate_opks_proposals(
            uow_factory,
            adapter=model,
            document_id=document_id,
            task_id="task-2",
            operation_id="generate-same-key",
        )

    assert transport.calls == 1


async def test_empty_verified_result_commits_a_no_candidate_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)
    transport = RecordingTransport(OpksResultWire(items=()))

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-empty",
    )

    assert outcome.outcome is OpksGenerationOutcome.NO_GROUNDED_CANDIDATES
    assert outcome.proposal_ids == ()
    assert transport.calls == 1
    async with uow_factory() as uow:
        receipt = await uow.journal.get(document_id, "generate-empty")
        proposals = await uow.opks_proposals.list(document_id)
    assert receipt is not None
    assert proposals == ()


async def test_reuse_existing_resolves_ordinal_to_stable_entity_id(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        items=(current_knowledge(),),
    )
    transport = RecordingTransport(
        OpksResultWire(
            items=(
                OpksWireItem(
                    entity_kind=OpksEntityKind.KNOWLEDGE,
                    decision=OpksDecision.REUSE_EXISTING,
                    target_ordinal=1,
                    text="",
                ),
            )
        )
    )

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-reuse",
    )
    loaded = await load_document(uow_factory, document_id)

    assert outcome.proposal_ids == ("generate-reuse-op0",)
    assert loaded is not None
    proposal = loaded.state.opks_proposals[0]
    assert proposal.entity_id == "knowledge-existing"
    assert proposal.before == current_knowledge()
    assert proposal.after is not None
    assert proposal.after.task_refs == ("task-1",)


async def test_reuse_that_adds_nothing_is_recorded_without_an_empty_proposal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    already_linked = OpksItem(
        entity_id="knowledge-linked",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        display_order=0,
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=source("source-task-1"),
                quote="我每週彙整營運週報",
            ),
        ),
    )
    uow_factory = await seed(
        postgres_session_factory,
        document_id,
        items=(already_linked,),
    )
    transport = RecordingTransport(
        OpksResultWire(
            items=(
                OpksWireItem(
                    entity_kind=OpksEntityKind.KNOWLEDGE,
                    decision=OpksDecision.REUSE_EXISTING,
                    target_ordinal=1,
                    text="",
                ),
            )
        )
    )

    outcome = await generate_opks_proposals(
        uow_factory,
        adapter=adapter(transport),
        document_id=document_id,
        task_id="task-1",
        operation_id="generate-noop-reuse",
    )
    loaded = await load_document(uow_factory, document_id)

    assert outcome.outcome is OpksGenerationOutcome.NO_GROUNDED_CANDIDATES
    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    assert loaded.state.current_opks.items == (already_linked,)


async def test_authority_change_during_provider_call_discards_result_and_receipt(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed(postgres_session_factory, document_id)

    async def mutate_authority():
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="edit-during-provider",
            entity_kind=OpksEntityKind.ATTITUDE,
            text="主動釐清異常",
        )

    transport = RecordingTransport(add_output_wire(), before_return=mutate_authority)

    with pytest.raises(StaleAuthoritySnapshot):
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter(transport),
            document_id=document_id,
            task_id="task-1",
            operation_id="generate-stale",
        )

    assert transport.calls == 1
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.opks_proposals == ()
    async with uow_factory() as uow:
        assert await uow.journal.get(document_id, "generate-stale") is None
