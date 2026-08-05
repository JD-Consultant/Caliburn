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
    duty_id: str | None = None,
    competency_level: int | None = None,
):
    return {
        "statement": statement,
        "purpose_result": purpose_result,
        "context": None,
        "frequency_text": frequency_text,
        "responsibility_role": None,
        "enablers": [],
        "duty_id": duty_id,
        "competency_level": competency_level,
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


# -- 主要職責 routes（Duty 切片 T5）------------------------------------------


async def _document(client, document_id) -> str:
    root = f"/api/v1/job-analysis/documents/{document_id}"
    assert (await client.put(root, json={"title": "門市營運專員"})).status_code == 201
    return root


async def _add_duty(client, root, *, key: str, statement: str) -> dict:
    response = await client.post(
        f"{root}/duties",
        headers={"Idempotency-Key": key},
        json={"statement": statement},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_duty_routes_create_reorder_and_project_into_the_document(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)

    first = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")
    second = await _add_duty(client, root, key="duty-b", statement="處理帳號權限")

    assert first["display_order"] == 0
    assert second["display_order"] == 1
    document = (await client.get(root)).json()
    assert [duty["duty_id"] for duty in document["duties"]] == [
        first["duty_id"],
        second["duty_id"],
    ]

    reordered = await client.put(
        f"{root}/duty-order",
        headers={"Idempotency-Key": "order-1"},
        json={"ordered_duty_ids": [second["duty_id"], first["duty_id"]]},
    )
    assert reordered.status_code == 200
    assert [duty["duty_id"] for duty in reordered.json()] == [
        second["duty_id"],
        first["duty_id"],
    ]
    assert [duty["display_order"] for duty in reordered.json()] == [0, 1]


async def test_a_duty_route_without_an_idempotency_key_is_rejected(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)

    response = await client.post(f"{root}/duties", json={"statement": "維運門市系統"})

    assert response.status_code == 422


async def test_editing_a_duty_with_the_same_statement_is_a_problem_not_a_500(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)
    duty = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")

    response = await client.put(
        f"{root}/duties/" + duty["duty_id"],
        headers={"Idempotency-Key": "edit-1"},
        json={"statement": "維運門市營運系統"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/invalid-request")


async def test_an_unknown_duty_is_404_not_500(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    """`application_error_response()` 對沒映射的錯誤是 `raise TypeError`,
    所以漏掉 `DutyNotFound` 會變成 500——這條測試就是守那個。"""

    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)

    edited = await client.put(
        f"{root}/duties/duty-gone",
        headers={"Idempotency-Key": "edit-1"},
        json={"statement": "維運門市營運系統"},
    )
    deleted = await client.delete(
        f"{root}/duties/duty-gone",
        headers={"Idempotency-Key": "del-1"},
    )

    assert edited.status_code == 404
    assert edited.json()["type"].endswith("/duty-not-found")
    assert deleted.status_code == 404


async def test_a_partial_duty_order_is_422_not_500(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)
    duty = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")
    await _add_duty(client, root, key="duty-b", statement="處理帳號權限")

    response = await client.put(
        f"{root}/duty-order",
        headers={"Idempotency-Key": "order-1"},
        json={"ordered_duty_ids": [duty["duty_id"]]},
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("/invalid-duty-order")


async def test_a_task_carries_its_duty_and_level_and_readiness_follows(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)
    duty = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")
    created = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "task-a"},
        json=task_payload("每週彙整營運週報"),
    )
    assert created.status_code == 201
    task = created.json()
    assert task["duty_id"] is None and task["competency_level"] is None

    codes = {
        issue["code"]
        for issue in (await client.get(root)).json()["readiness"]["issues"]
    }
    assert {"task_duty_missing", "task_competency_level_missing"} <= codes

    assigned = await client.put(
        f"{root}/tasks/" + task["task_id"],
        headers={"Idempotency-Key": "assign-1"},
        json=task_payload(
            "每週彙整營運週報",
            duty_id=duty["duty_id"],
            competency_level=4,
        ),
    )
    assert assigned.status_code == 200
    assert assigned.json()["duty_id"] == duty["duty_id"]
    assert assigned.json()["competency_level"] == 4

    codes = {
        issue["code"]
        for issue in (await client.get(root)).json()["readiness"]["issues"]
    }
    assert not {"task_duty_missing", "task_competency_level_missing"} & codes
    assert "duty_without_task" not in codes


async def test_an_out_of_range_competency_level_is_rejected_by_the_contract(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)

    response = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "task-a"},
        json=task_payload("每週彙整營運週報", competency_level=7),
    )

    assert response.status_code == 422


async def test_deleting_a_duty_keeps_its_task_and_unassigns_it_over_http(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)
    duty = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")
    task = (
        await client.post(
            f"{root}/tasks",
            headers={"Idempotency-Key": "task-a"},
            json=task_payload(
                "每週彙整營運週報",
                duty_id=duty["duty_id"],
                competency_level=4,
            ),
        )
    ).json()

    deleted = await client.delete(
        f"{root}/duties/" + duty["duty_id"],
        headers={"Idempotency-Key": "del-1"},
    )

    assert deleted.status_code == 204
    document = (await client.get(root)).json()
    assert document["duties"] == []
    assert len(document["tasks"]) == 1
    assert document["tasks"][0]["task_id"] == task["task_id"]
    assert document["tasks"][0]["duty_id"] is None
    assert document["tasks"][0]["competency_level"] == 4


async def test_the_consultation_view_projects_duties_too(
    postgres_api_client,
    cleanup_job_analysis_rows,
):
    """`ConsultationPanel` 的 Current JD 讀的是 consultation 回應，不是 document,
    所以 duties 必須同時出現在兩個投影，否則一個回合之後分組就對不起來。"""

    client, _, _ = postgres_api_client
    root = await _document(client, cleanup_job_analysis_rows)
    duty = await _add_duty(client, root, key="duty-a", statement="維運門市營運系統")

    consultation = await client.get(f"{root}/consultation")

    assert consultation.status_code == 200
    assert [item["duty_id"] for item in consultation.json()["duties"]] == [
        duty["duty_id"]
    ]
