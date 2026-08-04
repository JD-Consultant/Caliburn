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
    IdentityRelation,
    SignalDisposition,
    TaskAnalysisWire,
    WireAnchor,
    WireNextQuestion,
    WireSignal,
    WireTaskChange,
    WireTaskFields,
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
        result = TaskAnalysisWire(
            work_signals=(
                WireSignal(
                    anchors=(
                        WireAnchor(
                            turn_ordinal=2,
                            quote="我每週彙整營運週報",
                        ),
                    ),
                    relation=IdentityRelation.NO_MATCH,
                    disposition=SignalDisposition.TASK_CHANGE,
                    change=WireTaskChange.ADD,
                    task=WireTaskFields(
                        statement="每週彙整營運週報",
                        action="彙整",
                        object="營運週報",
                        purpose_result="讓主管掌握營運狀況",
                    ),
                ),
            ),
            next_question=WireNextQuestion(
                text="這份週報通常提供給誰？",
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


def header_payload(
    *,
    competency_name: str | None = None,
    work_description: str | None = None,
    competency_level: int | None = None,
) -> dict:
    return {
        "competency_name": competency_name,
        "occupation_category_name": None,
        "occupation_name": None,
        "occupation_code": None,
        "industry_name": None,
        "industry_code": None,
        "work_description": work_description,
        "competency_level": competency_level,
        "notes": None,
    }


async def test_put_jd_header_persists_and_readiness_reflects_it_over_real_postgres(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    document_id = cleanup_job_analysis_rows
    root = f"/api/v1/job-analysis/documents/{document_id}"
    assert (await client.put(root, json={"title": "門市營運專員"})).status_code == 201

    empty_readiness = await client.get(root)
    assert empty_readiness.status_code == 200
    assert {
        issue["code"] for issue in empty_readiness.json()["readiness"]["issues"]
    } == {
        "competency_name_missing",
        "work_description_missing",
        "competency_level_missing",
    }

    put = await client.put(
        f"{root}/jd-header",
        headers={"Idempotency-Key": "header-1"},
        json=header_payload(
            competency_name="資訊安全維運人員",
            work_description="維運企業資訊安全設備並處理資安事件。",
            competency_level=4,
        ),
    )
    assert put.status_code == 200
    assert put.json()["competency_name"] == "資訊安全維運人員"

    reloaded = await client.get(root)
    assert reloaded.status_code == 200
    assert reloaded.json()["jd_header"]["competency_name"] == "資訊安全維運人員"
    assert reloaded.json()["jd_header"]["competency_level"] == 4
    assert reloaded.json()["readiness"]["issues"] == []

    # replay with the same Idempotency-Key and the same body is a no-op success
    replay = await client.put(
        f"{root}/jd-header",
        headers={"Idempotency-Key": "header-1"},
        json=header_payload(
            competency_name="資訊安全維運人員",
            work_description="維運企業資訊安全設備並處理資安事件。",
            competency_level=4,
        ),
    )
    assert replay.status_code == 200
    assert replay.json() == put.json()


async def test_put_jd_header_rejects_a_no_op_edit_and_out_of_range_level(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    document_id = cleanup_job_analysis_rows
    root = f"/api/v1/job-analysis/documents/{document_id}"
    assert (await client.put(root, json={"title": "門市營運專員"})).status_code == 201

    no_op = await client.put(
        f"{root}/jd-header",
        headers={"Idempotency-Key": "no-op-1"},
        json=header_payload(),
    )
    assert no_op.status_code == 422
    assert no_op.headers["content-type"] == "application/problem+json"
    assert no_op.json()["type"] == (
        "https://caliburn.dev/problems/job-analysis/invalid-request"
    )

    out_of_range = await client.put(
        f"{root}/jd-header",
        headers={"Idempotency-Key": "level-1"},
        json=header_payload(competency_level=7),
    )
    assert out_of_range.status_code == 422

    missing_key = await client.put(
        f"{root}/jd-header",
        json=header_payload(competency_name="資訊安全維運人員"),
    )
    assert missing_key.status_code == 422

    reloaded = await client.get(root)
    assert reloaded.json()["jd_header"]["competency_name"] is None


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
