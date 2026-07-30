"""Real PostgreSQL + HTTP vertical for the local job-analysis workspace."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.adapters.job_analysis_postgres.models import JobAnalysisJournalRow
from app.api.deps import get_job_analysis_adapter, get_job_analysis_uow_factory
from app.job_analysis.application import load_document
from app.job_analysis.domain import TaskFields
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
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)
from app.main import app


pytestmark = pytest.mark.asyncio


class _ConsultantTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        result = TaskAnalysisResult(
            work_signals=(
                WorkSignal(
                    anchors=(
                        SignalAnchor(
                            turn_ordinal=2,
                            quote="我每週彙整營運週報",
                        ),
                    ),
                    identity=IdentityAssessment(
                        relation=IdentityRelation.NO_MATCH
                    ),
                    disposition=SignalDisposition.TASK_CHANGE,
                    task_change=TaskChangePayload(
                        change=TaskChangeKind.ADD,
                        task_fields=TaskFields(
                            statement="每週彙整營運週報",
                            action="彙整",
                            object="營運週報",
                            purpose_result="讓主管掌握營運狀況",
                        ),
                    ),
                ),
            ),
            next_question=NextQuestion(
                text="這份週報通常提供給誰？",
                purpose="釐清產出的主要使用者",
            ),
        )
        return TransportResponse(
            status_code=200,
            body={
                "model": "anthropic/claude-opus-5",
                "choices": [
                    {
                        "message": {
                            "content": result.model_dump_json(),
                            "refusal": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )


@pytest_asyncio.fixture
async def postgres_api_client(postgres_session_factory):
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    provider = _ConsultantTransport()
    adapter = OpenRouterAdapter(
        config=OpenRouterConfig(
            model="anthropic/claude-opus-5",
            provider_order=("anthropic",),
            max_output_tokens=4096,
            timeout_seconds=90,
        ),
        api_key="sk-test",
        transport=provider,
    )
    app.dependency_overrides[get_job_analysis_uow_factory] = lambda: factory
    app.dependency_overrides[get_job_analysis_adapter] = lambda: adapter
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client, factory, provider
    app.dependency_overrides.clear()


def task_payload(
    statement: str,
    *,
    purpose_result: str | None = None,
    frequency_text: str | None = None,
):
    return {
        "statement": statement,
        "purpose_result": purpose_result,
        "context": None,
        "frequency_text": frequency_text,
        "responsibility_role": None,
        "enablers": [],
    }


async def test_local_web_task_editing_survives_reload_and_rename_is_metadata_only(
    postgres_api_client,
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    client, factory, _ = postgres_api_client
    document_id = cleanup_job_analysis_rows
    root = f"/api/v1/job-analysis/documents/{document_id}"

    assert (await client.put(root, json={"title": "門市營運專員"})).status_code == 201
    first = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "vertical-add-1"},
        json=task_payload("盤點門市耗材"),
    )
    assert first.status_code == 201
    first_id = first.json()["task_id"]
    assert first.json()["purpose_result"] is None

    edited = await client.put(
        f"{root}/tasks/{first_id}",
        headers={"Idempotency-Key": "vertical-edit-1"},
        json=task_payload(
            "盤點門市耗材",
            purpose_result="確保安全庫存充足",
            frequency_text="每月一次",
        ),
    )
    assert edited.status_code == 200

    second = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "vertical-add-2"},
        json=task_payload("每週彙整營運週報"),
    )
    second_id = second.json()["task_id"]
    reordered = await client.put(
        f"{root}/task-order",
        headers={"Idempotency-Key": "vertical-order-1"},
        json={"ordered_task_ids": [second_id, first_id]},
    )
    assert [item["task_id"] for item in reordered.json()] == [second_id, first_id]

    before_rename = await load_document(factory, document_id)
    assert before_rename is not None
    async with postgres_session_factory() as session:
        journal_before = await session.scalar(
            select(func.count())
            .select_from(JobAnalysisJournalRow)
            .where(JobAnalysisJournalRow.document_id == document_id)
        )

    renamed = await client.put(root, json={"title": "資深門市營運專員"})
    reloaded = await client.get(root)
    after_rename = await load_document(factory, document_id)
    async with postgres_session_factory() as session:
        journal_after = await session.scalar(
            select(func.count())
            .select_from(JobAnalysisJournalRow)
            .where(JobAnalysisJournalRow.document_id == document_id)
        )

    assert renamed.status_code == 200
    assert reloaded.status_code == 200
    assert reloaded.json()["title"] == "資深門市營運專員"
    assert [item["task_id"] for item in reloaded.json()["tasks"]] == [
        second_id,
        first_id,
    ]
    assert reloaded.json()["tasks"][1]["purpose_result"] == "確保安全庫存充足"
    assert reloaded.json()["tasks"][1]["frequency_text"] == "每月一次"
    assert after_rename is not None
    assert after_rename.document.authority_generation == (
        before_rename.document.authority_generation
    )
    assert after_rename.state == before_rename.state
    assert journal_after == journal_before


async def test_consultant_turn_proposal_decision_and_reload_use_real_postgres(
    postgres_api_client,
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    client, factory, provider = postgres_api_client
    document_id = cleanup_job_analysis_rows
    root = f"/api/v1/job-analysis/documents/{document_id}"
    await client.put(root, json={"title": "門市營運專員"})

    first = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "pg-turn-1"},
        json={"text": "我每週彙整營運週報"},
    )
    replay = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "pg-turn-1"},
        json={"text": "我每週彙整營運週報"},
    )
    proposal_id = first.json()["proposals"][0]["proposal_id"]
    accepted = await client.post(
        f"{root}/proposals/{proposal_id}/decisions",
        headers={"Idempotency-Key": "pg-decision-1"},
        json={"decision": "accepted"},
    )
    reloaded = await client.get(f"{root}/consultation")
    persisted = await load_document(factory, document_id)
    async with postgres_session_factory() as session:
        journal_count = await session.scalar(
            select(func.count())
            .select_from(JobAnalysisJournalRow)
            .where(JobAnalysisJournalRow.document_id == document_id)
        )

    assert first.status_code == 200
    assert replay.json() == first.json()
    assert provider.calls == 1
    assert accepted.status_code == 200
    assert accepted.json()["tasks"][0]["statement"] == "每週彙整營運週報"
    assert accepted.json()["active_question"]["text"] == "這份週報通常提供給誰？"
    assert reloaded.json() == accepted.json()
    assert persisted is not None
    assert len(persisted.conversation_turns) == 3
    assert journal_count == 3
