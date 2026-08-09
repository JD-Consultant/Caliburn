"""HTTP authority vertical for employee OPKS order within one entity kind."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.api.job_analysis_deps import get_job_analysis_uow_factory
from app.main import app


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def opks_reorder_api_client(postgres_session_factory):
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    app.dependency_overrides[get_job_analysis_uow_factory] = lambda: factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def opks_payload(kind: str, text: str, task_refs: list[str] | None = None):
    return {
        "entity_kind": kind,
        "text": text,
        "task_refs": task_refs or [],
        "indicator_refs": [],
    }


async def test_reorder_opks_is_kind_scoped_and_idempotent(
    opks_reorder_api_client,
    cleanup_job_analysis_rows,
):
    client = opks_reorder_api_client
    root = f"/api/v1/job-analysis/documents/{cleanup_job_analysis_rows}"
    assert (await client.put(root, json={"title": "門市營運專員"})).status_code == 201
    task = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "opks-order-task"},
        json={
            "statement": "彙整週報",
            "purpose_result": None,
            "context": None,
            "frequency_text": None,
            "responsibility_role": None,
            "enablers": [],
        },
    )
    task_id = task.json()["task_id"]
    first = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "opks-order-first"},
        json=opks_payload("output", "週報", [task_id]),
    )
    second = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "opks-order-second"},
        json=opks_payload("output", "月報", [task_id]),
    )
    knowledge = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "opks-order-knowledge"},
        json=opks_payload("knowledge", "數據定義"),
    )

    reordered = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-reorder"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [
                second.json()["entity_id"],
                first.json()["entity_id"],
            ],
        },
    )
    replay = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-reorder"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [
                second.json()["entity_id"],
                first.json()["entity_id"],
            ],
        },
    )
    invalid = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-invalid"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [knowledge.json()["entity_id"]],
        },
    )
    duplicate = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-duplicate"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [
                first.json()["entity_id"],
                first.json()["entity_id"],
            ],
        },
    )
    omission = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-omission"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [first.json()["entity_id"]],
        },
    )
    stale = await client.put(
        f"{root}/opks-order",
        headers={"Idempotency-Key": "opks-order-stale"},
        json={
            "entity_kind": "output",
            "ordered_entity_ids": [
                first.json()["entity_id"],
                "missing-output",
            ],
        },
    )
    reloaded = await client.get(root)

    assert reordered.status_code == 200
    assert [item["entity_id"] for item in reordered.json()] == [
        second.json()["entity_id"],
        first.json()["entity_id"],
    ]
    assert [item["display_order"] for item in reordered.json()] == [0, 1]
    assert replay.json() == reordered.json()
    for response in (invalid, duplicate, omission, stale):
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-opks-order")
    assert [
        item["entity_id"]
        for item in reloaded.json()["opks_items"]
        if item["entity_kind"] == "output"
    ] == [second.json()["entity_id"], first.json()["entity_id"]]
    assert next(
        item for item in reloaded.json()["opks_items"]
        if item["entity_id"] == knowledge.json()["entity_id"]
    )["display_order"] == 0
