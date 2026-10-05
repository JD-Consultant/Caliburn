"""Excluded work stays outside Memory and only crosses qualified, completed Turns."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.occupation_references import OccupationReferenceClient, ReferenceClientError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.interviews import service as interview_service
from caliburn.features.job_files import service as job_files
from caliburn.features.occupation_references.models import (
    ReferenceStateError,
    StaleReferenceStateError,
)
from caliburn.workflows.occupation_references import OccupationReferenceWorkflow

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def new_writer(client: TestClient, file_id: UUID | None = None) -> ExecutionWriter:
    if file_id is None:
        created = client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "公版排除",
                "employee_name": "合成員工",
            },
        )
        assert created.status_code == 201
        file_id = UUID(created.json()["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "我負責功能開發，正式環境部署是別組負責。",
        },
    )
    assert accepted.status_code == 202
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    return transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))


def finish(
    client: TestClient, writer: ExecutionWriter, status: ExecutionStatus, formal: bool = True
) -> None:
    async def apply(session: AsyncSession) -> None:
        await job_files.lock_job_file(session, writer.scope.job_file_id)
        await executions.lock_active_writer(session, writer)
        if formal:
            await interview_service.formalize_exchange(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                reply_text="已了解本人的工作範圍。",
            )
        await executions.finish_execution(session, writer, status)

    transact(client, apply)


def workflow(client: TestClient) -> tuple[OccupationReferenceWorkflow, AsyncMock]:
    provider = AsyncMock(spec=OccupationReferenceClient)
    return OccupationReferenceWorkflow(client.app.state.database.sessions, provider), provider


def test_excluded_work_survives_selection_and_completed_turn_without_answer_refs(
    client: TestClient,
) -> None:
    flow, provider = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    change = client.portal.call(
        flow.prepare_excluded_work, writer, ("不負責正式部署",), (), uuid4()
    )
    first = client.portal.call(flow.execute, writer, change)
    assert first == {"selected_reference_ids": None, "excluded_work": ["不負責正式部署"]}
    selection = client.portal.call(flow.prepare_select, writer, ("frontend", "backend"), uuid4())
    selected = client.portal.call(flow.execute, writer, selection)
    assert selected == {
        "selected_reference_ids": ["frontend", "backend"],
        "excluded_work": ["不負責正式部署"],
    }
    provider.read.assert_any_await("frontend")
    assert client.portal.call(flow.execute, writer, change) == first
    finish(client, writer, ExecutionStatus.COMPLETED)
    next_writer = new_writer(client, writer.scope.job_file_id)
    client.portal.call(flow.start, next_writer)
    assert client.portal.call(flow.read, next_writer) == selected


@pytest.mark.parametrize(
    ("status", "formal"),
    [
        (ExecutionStatus.CANCELLED, False),
        (ExecutionStatus.FAILED, False),
        (ExecutionStatus.COMPLETED, False),
        (ExecutionStatus.CANCELLED, True),
    ],
)
def test_unqualified_turn_cannot_publish_excluded_work(
    client: TestClient, status: ExecutionStatus, formal: bool
) -> None:
    flow, _ = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    change = client.portal.call(flow.prepare_excluded_work, writer, ("不負責部署",), (), uuid4())
    client.portal.call(flow.execute, writer, change)
    finish(client, writer, status, formal)
    next_writer = new_writer(client, writer.scope.job_file_id)
    position = client.portal.call(flow.start, next_writer)
    assert position.state.excluded_work == ()


def test_employee_correction_removes_exact_scope_and_unknown_removal_is_atomic(
    client: TestClient,
) -> None:
    flow, _ = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    add = client.portal.call(
        flow.prepare_excluded_work, writer, ("不負責部署", "不負責採購"), (), uuid4()
    )
    client.portal.call(flow.execute, writer, add)
    with pytest.raises(ReferenceStateError):
        client.portal.call(
            flow.prepare_excluded_work, writer, ("不負責資安",), ("不存在",), uuid4()
        )
    assert client.portal.call(flow.read, writer)["excluded_work"] == ["不負責部署", "不負責採購"]
    remove = client.portal.call(flow.prepare_excluded_work, writer, (), ("不負責部署",), uuid4())
    assert client.portal.call(flow.execute, writer, remove)["excluded_work"] == ["不負責採購"]


def test_reference_failure_scope_forgery_and_old_writer_have_no_effect(client: TestClient) -> None:
    flow, provider = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    provider.read.side_effect = ReferenceClientError("reference_not_found")
    with pytest.raises(ReferenceClientError):
        client.portal.call(flow.prepare_select, writer, ("missing",), uuid4())
    provider.read.side_effect = None
    change = client.portal.call(flow.prepare_excluded_work, writer, ("不負責部署",), (), uuid4())
    with pytest.raises(ReferenceStateError):
        client.portal.call(flow.execute, writer, replace(change, job_file_id=uuid4()))
    assert client.portal.call(flow.read, writer)["excluded_work"] == []
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s,
            writer.scope,
            writer_id=uuid4(),
            replaces_writer_id=writer.writer_id,
        ),
    )
    with pytest.raises(StaleWriterError):
        client.portal.call(flow.execute, writer, change)
    assert client.portal.call(flow.execute, replacement, change)["excluded_work"] == ["不負責部署"]


def test_latest_qualified_state_survives_skipped_cancelled_turns_and_file_isolation(
    client: TestClient,
) -> None:
    flow, _ = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    change = client.portal.call(flow.prepare_excluded_work, writer, ("不負責部署",), (), uuid4())
    client.portal.call(flow.execute, writer, change)
    finish(client, writer, ExecutionStatus.COMPLETED)
    skipped = new_writer(client, writer.scope.job_file_id)
    finish(client, skipped, ExecutionStatus.COMPLETED)
    cancelled = new_writer(client, writer.scope.job_file_id)
    client.portal.call(flow.start, cancelled)
    remove = client.portal.call(flow.prepare_excluded_work, cancelled, (), ("不負責部署",), uuid4())
    client.portal.call(flow.execute, cancelled, remove)
    finish(client, cancelled, ExecutionStatus.CANCELLED, False)
    reader = new_writer(client, writer.scope.job_file_id)
    assert client.portal.call(flow.start, reader).state.excluded_work == ("不負責部署",)
    other_file = new_writer(client)
    assert client.portal.call(flow.start, other_file).state.excluded_work == ()


def test_restoring_position_revokes_prepared_exclusion_and_preserves_original_state(
    client: TestClient,
) -> None:
    flow, _ = workflow(client)
    writer = new_writer(client)
    initial = client.portal.call(flow.start, writer)
    first = client.portal.call(flow.prepare_excluded_work, writer, ("不負責部署",), (), uuid4())
    client.portal.call(flow.execute, writer, first)
    current = client.portal.call(flow.start, writer)
    stale = client.portal.call(flow.prepare_excluded_work, writer, ("不負責採購",), (), uuid4())
    restored = client.portal.call(flow.restore, writer, current, initial.revision_id, uuid4())
    assert restored.state == initial.state
    with pytest.raises(StaleReferenceStateError):
        client.portal.call(flow.execute, writer, stale)
    assert client.portal.call(flow.read, writer)["excluded_work"] == []


def test_selection_is_not_permanently_limited_to_one_search_batch(client: TestClient) -> None:
    flow, provider = workflow(client)
    writer = new_writer(client)
    client.portal.call(flow.start, writer)
    references = tuple(f"public-{i}" for i in range(6))
    change = client.portal.call(flow.prepare_select, writer, references, uuid4())
    assert client.portal.call(flow.execute, writer, change)["selected_reference_ids"] == list(
        references
    )
    assert provider.read.await_count == 6
