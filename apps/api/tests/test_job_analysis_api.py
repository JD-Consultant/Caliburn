"""Local Web transport contract for greenfield job-analysis documents."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from app.api import deps
from app.job_analysis.application import DocumentRecord, DocumentSummary
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    SourceKind,
    SourceRef,
    TaskFields,
)
from app.job_analysis.llm import (
    IdentityRelation,
    OpksDecision,
    OpksGenerationEntityKind,
    OpksResultWire,
    OpksWireItem,
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
NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000045")


class _Store:
    def __init__(self) -> None:
        self.document: DocumentRecord | None = None
        self.duties = ()
        self.tasks: tuple[JdTask, ...] = ()
        self.proposals = ()
        self.opks = ()
        self.opks_proposals = ()
        self.journal = {}
        self.allow_authority_update = True


class _Documents:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def create(self, record: DocumentRecord) -> None:
        self.store.document = record

    async def get(self, document_id: UUID, *, for_update: bool = False):
        if self.store.document is None:
            return None
        return self.store.document if self.store.document.document_id == document_id else None

    async def list(self):
        if self.store.document is None:
            return ()
        record = self.store.document
        return (
            DocumentSummary(
                document_id=record.document_id,
                title=record.title,
                task_count=len(self.store.tasks),
                updated_at=record.updated_at,
            ),
        )

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool:
        record = await self.get(document_id)
        if record is None:
            return False
        self.store.document = replace(record, title=title, updated_at=updated_at)
        return True

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        jd_header,
        work_model,
        active_question,
        updated_at: datetime,
    ) -> bool:
        record = await self.get(document_id)
        if (
            record is None
            or not self.store.allow_authority_update
            or record.authority_generation != expected_generation
        ):
            return False
        self.store.document = replace(
            record,
            jd_header=jd_header,
            work_model=work_model,
            active_question=active_question,
            authority_generation=expected_generation + 1,
            updated_at=updated_at,
        )
        return True


class _Duties:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID):
        return self.store.duties

    async def replace(self, document_id: UUID, duties) -> None:
        self.store.duties = duties


class _Tasks:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID):
        return self.store.tasks

    async def replace(self, document_id: UUID, tasks) -> None:
        self.store.tasks = tasks


class _Proposals:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID, *, statuses=None):
        return self.store.proposals

    async def replace(self, document_id: UUID, proposals) -> None:
        self.store.proposals = proposals


class _Opks:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID):
        return self.store.opks

    async def replace(self, document_id: UUID, items) -> None:
        self.store.opks = items


class _OpksProposals:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID, *, statuses=None):
        return self.store.opks_proposals

    async def replace(self, document_id: UUID, proposals) -> None:
        self.store.opks_proposals = proposals


class _Journal:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def get(self, document_id: UUID, entry_id: str):
        return self.store.journal.get(entry_id)

    async def add(self, entry) -> None:
        self.store.journal[entry.entry_id] = entry

    async def list_conversation_turns(self, document_id: UUID):
        turns = []
        for entry in self.store.journal.values():
            payload = entry.payload
            if hasattr(payload, "consultant_turn") and not hasattr(
                payload, "employee_turn"
            ):
                turns.append(payload.consultant_turn)
            elif hasattr(payload, "employee_turn"):
                turns.extend((payload.employee_turn, payload.consultant_turn))
        return tuple(turns)


class _UnitOfWork:
    def __init__(self, store: _Store) -> None:
        self.documents = _Documents(store)
        self.duties = _Duties(store)
        self.tasks = _Tasks(store)
        self.proposals = _Proposals(store)
        self.opks = _Opks(store)
        self.opks_proposals = _OpksProposals(store)
        self.journal = _Journal(store)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def commit(self) -> None:
        return None


class _ScriptedTransport:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def __call__(self, *, url, headers, body, timeout):
        self.calls += 1
        if self.fail:
            return TransportResponse(status_code=503, text="anthropic unavailable")
        if body["response_format"]["json_schema"]["name"] == "opks_result_v1":
            result = OpksResultWire(
                items=(
                    OpksWireItem(
                        entity_kind=OpksGenerationEntityKind.OUTPUT,
                        decision=OpksDecision.ADD_NEW,
                        target_ordinal=0,
                        text="營運週報",
                    ),
                )
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
        # 劇本是**模型送出來的** wire 形狀,不是 domain 形狀;否則這條路徑會跳過 mapper。
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
async def api_client():
    store = _Store()
    provider = _ScriptedTransport()
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
    dependency = getattr(deps, "get_job_analysis_uow_factory", None)
    if dependency is not None:
        app.dependency_overrides[dependency] = lambda: lambda: _UnitOfWork(store)
    adapter_dependency = getattr(deps, "get_job_analysis_adapter", None)
    if adapter_dependency is not None:
        app.dependency_overrides[adapter_dependency] = lambda: adapter
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, store, provider
    app.dependency_overrides.clear()


async def test_put_creates_then_replaces_only_document_metadata(api_client):
    client, store, _ = api_client

    created = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    renamed = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "資深門市營運專員"},
    )

    assert created.status_code == 201
    assert renamed.status_code == 200
    assert set(renamed.json()) == {"document_id", "title", "updated_at"}
    assert renamed.json()["title"] == "資深門市營運專員"
    assert store.document is not None
    assert store.document.authority_generation == 0
    assert store.document.active_question is not None
    assert store.document.active_question.text == (
        "先不用照職稱回答：你這個職位最主要替誰解決什麼問題？"
    )
    assert len(store.journal) == 1
    opening = next(iter(store.journal.values()))
    assert opening.kind == "consultant_opening"


async def test_list_and_open_return_only_the_current_jd_projection(api_client):
    client, store, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    store.tasks = (
        JdTask(
            task_id="task-1",
            statement="每週彙整營運週報",
            display_order=0,
        ),
    )

    listed = await client.get("/api/v1/job-analysis/documents")
    opened = await client.get(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    )

    assert listed.status_code == 200
    assert listed.json()[0]["task_count"] == 1
    assert opened.status_code == 200
    assert set(opened.json()) == {
        "document_id",
        "title",
        "updated_at",
        "jd_header",
        "readiness",
        "duties",
        "tasks",
        "opks_items",
    }
    assert opened.json()["duties"] == []
    assert opened.json()["tasks"][0]["statement"] == "每週彙整營運週報"
    assert opened.json()["opks_items"] == []
    forbidden = {"authority_generation", "work_model", "journal", "proposals"}
    assert forbidden.isdisjoint(opened.json())


async def test_missing_document_uses_the_stable_problem_type(api_client):
    client, _, _ = api_client

    response = await client.get(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == (
        "https://caliburn.dev/problems/job-analysis/document-not-found"
    )


@pytest.mark.parametrize("payload", [{}, {"title": "   "}])
async def test_invalid_document_metadata_uses_problem_details(api_client, payload):
    client, _, _ = api_client

    response = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json=payload,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["type"] == (
        "https://caliburn.dev/problems/job-analysis/invalid-request"
    )
    assert response.json()["errors"]


async def test_legacy_validation_error_shape_is_unchanged(api_client):
    client, _, _ = api_client

    response = await client.get("/api/v1/occupations")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert "type" not in response.json()
    assert isinstance(response.json()["detail"], list)


def _task_payload(statement: str = " 每週彙整營運週報 "):
    return {
        "statement": statement,
        "purpose_result": " 讓主管掌握營運狀況 ",
        "context": "   ",
        "frequency_text": " 每週一次 ",
        "responsibility_role": "primary",
        "enablers": [{"kind": "tool_system", "name": " Excel "}],
        "duty_id": None,
        "competency_level": None,
    }


def _opks_payload(
    task_id: str,
    *,
    text: str = " 營運週報 ",
    entity_kind: str = "output",
):
    return {
        "entity_kind": entity_kind,
        "text": text,
        "task_refs": [task_id],
        "indicator_refs": [],
    }


async def test_task_mutations_share_the_authoring_use_cases(api_client):
    client, _, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )

    created = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-1"},
        json=_task_payload(),
    )
    replay = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-1"},
        json=_task_payload(),
    )
    task_id = created.json()["task_id"]
    edited = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "edit-1"},
        json=_task_payload("每週彙整並檢查營運週報"),
    )
    reordered = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/task-order",
        headers={"Idempotency-Key": "order-1"},
        json={"ordered_task_ids": [task_id]},
    )
    deleted = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-1"},
    )
    delete_replay = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-1"},
    )

    assert created.status_code == 201
    assert replay.json() == created.json()
    assert created.json()["statement"] == "每週彙整營運週報"
    assert created.json()["context"] is None
    assert created.json()["enablers"][0]["name"] == "Excel"
    assert edited.status_code == 200
    assert edited.json()["statement"] == "每週彙整並檢查營運週報"
    assert reordered.status_code == 200
    assert [item["task_id"] for item in reordered.json()] == [task_id]
    assert deleted.status_code == 204
    assert delete_replay.status_code == 204


async def test_opks_mutations_share_the_authority_commit_and_reload_views(api_client):
    client, _, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    task = await client.post(
        f"{root}/tasks",
        headers={"Idempotency-Key": "task-for-opks"},
        json=_task_payload(),
    )
    task_id = task.json()["task_id"]

    created = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "opks-add"},
        json=_opks_payload(task_id),
    )
    replay = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "opks-add"},
        json=_opks_payload(task_id),
    )
    entity_id = created.json()["entity_id"]
    edited = await client.put(
        f"{root}/opks/{entity_id}",
        headers={"Idempotency-Key": "opks-edit"},
        json=_opks_payload(task_id, text=" 每週營運週報 "),
    )
    wrong_kind = await client.put(
        f"{root}/opks/{entity_id}",
        headers={"Idempotency-Key": "opks-change-kind"},
        json=_opks_payload(
            task_id,
            text="每週營運週報",
            entity_kind="knowledge",
        ),
    )
    document = await client.get(root)
    consultation = await client.get(f"{root}/consultation")
    deleted = await client.delete(
        f"{root}/opks/{entity_id}",
        headers={"Idempotency-Key": "opks-delete"},
    )
    delete_replay = await client.delete(
        f"{root}/opks/{entity_id}",
        headers={"Idempotency-Key": "opks-delete"},
    )
    missing = await client.delete(
        f"{root}/opks/{entity_id}",
        headers={"Idempotency-Key": "opks-delete-new"},
    )

    assert created.status_code == 201
    assert replay.json() == created.json()
    assert created.json()["text"] == "營運週報"
    assert created.json()["evidence_quotes"] == []
    assert edited.status_code == 200
    assert edited.json()["text"] == "每週營運週報"
    assert wrong_kind.status_code == 422
    assert wrong_kind.json()["type"].endswith("/invalid-request")
    assert document.json()["opks_items"] == [edited.json()]
    assert consultation.json()["opks_items"] == [edited.json()]
    assert deleted.status_code == 204
    assert delete_replay.status_code == 204
    assert missing.status_code == 404
    assert missing.json()["type"].endswith("/opks-item-not-found")


async def test_invalid_opks_mutation_uses_invalid_request(api_client):
    client, _, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})

    response = await client.post(
        f"{root}/opks",
        headers={"Idempotency-Key": "blank-opks"},
        json={
            "entity_kind": "knowledge",
            "text": "   ",
            "task_refs": [],
            "indicator_refs": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("/invalid-request")


@pytest.mark.parametrize(
    ("method", "path", "headers", "payload", "status", "problem_type"),
    [
        (
            "post",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
            {},
            _task_payload(),
            422,
            "invalid-request",
        ),
        (
            "post",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
            {"Idempotency-Key": "blank"},
            _task_payload("   "),
            422,
            "invalid-request",
        ),
        (
            "post",
            "/api/v1/job-analysis/documents/00000000-0000-0000-0000-000000000099/tasks",
            {"Idempotency-Key": "missing-doc"},
            _task_payload(),
            404,
            "document-not-found",
        ),
        (
            "put",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/missing-task",
            {"Idempotency-Key": "missing-task"},
            _task_payload(),
            404,
            "task-not-found",
        ),
        (
            "put",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/task-order",
            {"Idempotency-Key": "bad-order"},
            {"ordered_task_ids": ["not-current"]},
            422,
            "invalid-task-order",
        ),
    ],
)
async def test_task_mutation_failures_use_stable_problem_types(
    api_client,
    method,
    path,
    headers,
    payload,
    status,
    problem_type,
):
    client, _, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )

    response = await client.request(method, path, headers=headers, json=payload)

    assert response.status_code == status
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["type"].endswith(f"/{problem_type}")


async def test_idempotency_conflict_and_authority_conflict_are_distinct(api_client):
    client, store, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "same-key"},
        json=_task_payload("工作一"),
    )
    idempotency = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "same-key"},
        json=_task_payload("工作二"),
    )
    store.allow_authority_update = False
    authority = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "new-key"},
        json=_task_payload("工作三"),
    )

    assert idempotency.status_code == 409
    assert idempotency.json()["type"].endswith("/idempotency-conflict")
    assert authority.status_code == 409
    assert authority.json()["type"].endswith("/authority-conflict")


async def test_delete_with_a_new_key_after_deletion_is_not_found(api_client):
    client, _, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    created = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-delete"},
        json=_task_payload(),
    )
    task_id = created.json()["task_id"]
    await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-old"},
    )

    response = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-new"},
    )

    assert response.status_code == 404
    assert response.json()["type"].endswith("/task-not-found")


async def test_consultation_turn_is_durable_and_replays_before_the_provider(api_client):
    client, _, provider = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})

    opened = await client.get(f"{root}/consultation")
    first = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "turn-1"},
        json={"text": "我每週彙整營運週報"},
    )
    replay = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "turn-1"},
        json={"text": "我每週彙整營運週報"},
    )
    conflict = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "turn-1"},
        json={"text": "其實我每月才做一次"},
    )

    assert opened.status_code == 200
    assert [turn["speaker"] for turn in opened.json()["conversation"]] == [
        "consultant"
    ]
    assert first.status_code == 200
    assert replay.json() == first.json()
    assert provider.calls == 1
    assert [turn["speaker"] for turn in first.json()["conversation"]] == [
        "consultant",
        "employee",
        "consultant",
    ]
    assert first.json()["active_question"]["text"] == "這份週報通常提供給誰？"
    assert first.json()["proposals"][0]["status"] == "pending"
    assert conflict.status_code == 409
    assert conflict.json()["type"].endswith("/idempotency-conflict")


async def test_consultant_failure_does_not_leak_provider_details_or_change_state(api_client):
    client, _, provider = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    provider.fail = True

    failed = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "failed-turn"},
        json={"text": "我每週彙整營運週報"},
    )
    reloaded = await client.get(f"{root}/consultation")

    assert failed.status_code == 503
    assert failed.json()["type"].endswith("/consultant-unavailable")
    assert "anthropic" not in failed.text.lower()
    assert "provider" not in failed.text.lower()
    assert len(reloaded.json()["conversation"]) == 1


async def test_opks_generation_creates_durable_proposals_and_replays_before_provider(
    api_client,
):
    client, _, provider = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    consultation = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "task-turn"},
        json={"text": "我每週彙整營運週報"},
    )
    proposal = consultation.json()["proposals"][0]
    accepted = await client.post(
        f"{root}/proposals/{proposal['proposal_id']}/decisions",
        headers={"Idempotency-Key": "accept-task"},
        json={"decision": "accepted"},
    )
    task_id = accepted.json()["tasks"][0]["task_id"]

    first = await client.post(
        f"{root}/tasks/{task_id}/opks-proposals",
        headers={"Idempotency-Key": "opks-generate-1"},
    )
    replay = await client.post(
        f"{root}/tasks/{task_id}/opks-proposals",
        headers={"Idempotency-Key": "opks-generate-1"},
    )
    reloaded = await client.get(f"{root}/consultation")

    assert first.status_code == 200
    assert first.json() == {
        "outcome": "proposed",
        "proposal_ids": ["opks-generate-1-op0"],
    }
    assert replay.json() == first.json()
    assert provider.calls == 2
    assert reloaded.json()["opks_items"] == []
    assert reloaded.json()["opks_proposals"][0]["status"] == "pending"


async def test_opks_generation_failure_is_generic_and_does_not_create_proposals(
    api_client,
):
    client, _, provider = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    consultation = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": "task-turn"},
        json={"text": "我每週彙整營運週報"},
    )
    proposal = consultation.json()["proposals"][0]
    accepted = await client.post(
        f"{root}/proposals/{proposal['proposal_id']}/decisions",
        headers={"Idempotency-Key": "accept-task"},
        json={"decision": "accepted"},
    )
    task_id = accepted.json()["tasks"][0]["task_id"]
    provider.fail = True

    failed = await client.post(
        f"{root}/tasks/{task_id}/opks-proposals",
        headers={"Idempotency-Key": "opks-failed"},
    )
    reloaded = await client.get(f"{root}/consultation")

    assert failed.status_code == 503
    assert failed.json()["type"].endswith("/consultant-unavailable")
    assert "anthropic" not in failed.text.lower()
    assert "provider" not in failed.text.lower()
    assert reloaded.json()["opks_proposals"] == []


@pytest.mark.parametrize("decision", ["accepted", "edited", "rejected", "deferred"])
async def test_proposal_decisions_preserve_the_active_question(api_client, decision):
    client, _, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    consultation = await client.post(
        f"{root}/turns",
        headers={"Idempotency-Key": f"turn-{decision}"},
        json={"text": "我每週彙整營運週報"},
    )
    proposal = consultation.json()["proposals"][0]
    body = {"decision": decision}
    if decision == "edited":
        edited = proposal["jd_after"]
        edited[0]["value"]["statement"] = "每週彙整並檢查營運週報"
        body["edited_jd_after"] = edited
    if decision == "rejected":
        body["reason"] = "這不是正式責任"

    response = await client.post(
        f"{root}/proposals/{proposal['proposal_id']}/decisions",
        headers={"Idempotency-Key": f"decision-{decision}"},
        json=body,
    )

    assert response.status_code == 200
    assert response.json()["proposals"][0]["status"] == decision
    assert response.json()["active_question"]["text"] == "這份週報通常提供給誰？"
    if decision in {"accepted", "edited"}:
        assert len(response.json()["tasks"]) == 1
    else:
        assert response.json()["tasks"] == []


async def test_missing_proposal_uses_its_own_problem_type(api_client):
    client, _, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})

    response = await client.post(
        f"{root}/proposals/missing/decisions",
        headers={"Idempotency-Key": "missing-proposal"},
        json={"decision": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["type"].endswith("/proposal-not-found")


@pytest.mark.parametrize("decision", ["accepted", "edited", "rejected", "deferred"])
async def test_opks_proposal_decisions_use_the_independent_contract(
    api_client,
    decision,
):
    client, store, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    store.tasks = (
        JdTask(
            task_id="task-1",
            statement="每週彙整營運週報",
            display_order=0,
        ),
    )
    candidate = OpksItem(
        entity_id="knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運資料定義",
        display_order=0,
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-1",
                ),
                quote="我需要理解營運資料定義",
            ),
        ),
    )
    proposal = OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id=candidate.entity_id,
        entity_kind=candidate.entity_kind,
        action=OpksProposalAction.ADD,
        after=candidate,
        base_authority_generation=0,
        created_at=NOW,
    )
    store.opks_proposals = (proposal,)
    body = {"decision": decision}
    if decision == "edited":
        body["edited_text"] = "員工確認的營運資料定義"
    if decision == "rejected":
        body["reason"] = "這不是必要知識"

    response = await client.post(
        f"{root}/opks-proposals/{proposal.proposal_id}/decisions",
        headers={"Idempotency-Key": f"opks-decision-{decision}"},
        json=body,
    )

    assert response.status_code == 200
    assert response.json()["opks_proposals"][0]["status"] == decision
    if decision in {"accepted", "edited"}:
        assert len(response.json()["opks_items"]) == 1
    else:
        assert response.json()["opks_items"] == []


async def test_remove_opks_proposal_cannot_be_edited(api_client):
    client, store, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})
    store.tasks = (
        JdTask(
            task_id="task-1",
            statement="每週彙整營運週報",
            display_order=0,
        ),
    )
    current = OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        display_order=0,
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-1",
                ),
                quote="我每週彙整營運週報",
            ),
        ),
    )
    store.opks = (current,)
    proposal = OpksProposal(
        proposal_id="remove-output-1",
        operation_id="opks-operation-remove",
        entity_id=current.entity_id,
        entity_kind=current.entity_kind,
        action=OpksProposalAction.REMOVE,
        before=current,
        base_authority_generation=0,
        created_at=NOW,
    )
    store.opks_proposals = (proposal,)

    response = await client.post(
        f"{root}/opks-proposals/{proposal.proposal_id}/decisions",
        headers={"Idempotency-Key": "edit-remove-output"},
        json={"decision": "edited", "edited_text": "換一種移除說法"},
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("/invalid-request")
    assert store.opks == (current,)
    assert store.opks_proposals == (proposal,)


async def test_missing_opks_proposal_uses_the_proposal_problem_type(api_client):
    client, _, _ = api_client
    root = f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    await client.put(root, json={"title": "門市營運專員"})

    response = await client.post(
        f"{root}/opks-proposals/missing/decisions",
        headers={"Idempotency-Key": "missing-opks-proposal"},
        json={"decision": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["type"].endswith("/proposal-not-found")
