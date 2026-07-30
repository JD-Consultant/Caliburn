"""Minimal durable consultation use case; no network."""

from __future__ import annotations

import app.job_analysis.application as application
import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    UncommittableOperationResult,
    create_document,
    load_document,
)
from app.job_analysis.llm import (
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    SignalAnchor,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)
from app.job_analysis.providers import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderText,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def verified_text() -> ProviderText:
    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(
                        turn_ordinal=2,
                        quote="我每週會彙整營運週報",
                    ),
                ),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields={
                        "statement": "每週彙整營運週報",
                        "action": "彙整",
                        "object": "營運週報",
                        "purpose_result": "讓主管掌握營運狀況",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="這份週報主要提供給誰？",
            purpose="釐清工作產出的使用者",
        ),
    )
    return ProviderText(text=result.model_dump_json())


class StaticAdapter:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        return self.outcome


async def test_committed_turn_replay_skips_the_provider_before_prepare(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    submit = getattr(application, "submit_employee_turn", None)
    assert submit is not None
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    adapter = StaticAdapter(verified_text())
    await create_document(uow_factory, document_id=document_id, title="營運專員")

    await submit(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-1",
        text="我每週會彙整營運週報",
    )
    await submit(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id="turn-1",
        text="我每週會彙整營運週報",
    )
    loaded = await load_document(uow_factory, document_id)

    assert adapter.calls == 1
    assert loaded is not None
    assert [turn.speaker.value for turn in loaded.conversation_turns] == [
        "consultant",
        "employee",
        "consultant",
    ]
    assert loaded.document.authority_generation == 1

    with pytest.raises(IdempotencyConflict):
        await submit(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            operation_id="turn-1",
            text="其實我每月才做一次",
        )
    assert adapter.calls == 1


async def test_provider_failure_leaves_only_the_opening(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    submit = getattr(application, "submit_employee_turn", None)
    assert submit is not None
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    adapter = StaticAdapter(
        ProviderFailure(kind=ProviderFailureKind.TIMEOUT, detail="timed out")
    )
    await create_document(uow_factory, document_id=document_id, title="營運專員")

    with pytest.raises(UncommittableOperationResult):
        await submit(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            operation_id="turn-failed",
            text="我每週會彙整營運週報",
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert adapter.calls == 1
    assert len(loaded.conversation_turns) == 1
    assert loaded.document.authority_generation == 0
