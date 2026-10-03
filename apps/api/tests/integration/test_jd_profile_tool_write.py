"""Model text and evidence intent is scoped, atomic and recoverable as one tool call."""

import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.models import ProfileField, SetProfileField
from caliburn.features.job_description.source_persistence import read_source_references
from caliburn.features.job_description.sources import InvalidJdSourceError, JdSourceReference
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.jd_item_movement import JdItemMovementWorkflow
from caliburn.workflows.jd_item_revision import JdItemRevisionWorkflow
from caliburn.workflows.jd_profile_writes import (
    AddProfileSource,
    AlignProfileSource,
    JdProfileWriteWorkflow,
    PreparedProfileWrite,
)
from caliburn.workflows.jd_sources import CurrentInputSourceSelection
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def test_profile_text_and_current_input_evidence_are_one_recoverable_effect(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "工具訪談",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我是前端工程師。"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    start = client.portal.call(candidates.start, writer)
    workflow = JdProfileWriteWorkflow(client.app.state.database.sessions)
    binding = PublishedMemoryRead(scope, None, 1)
    tools = JdWriteTools(
        workflow,
        JdTaskWriteWorkflow(client.app.state.database.sessions),
        binding,
        writer,
        creations=JdItemCreationWorkflow(client.app.state.database.sessions),
        revisions=JdItemRevisionWorkflow(client.app.state.database.sessions),
        deletions=JdItemDeletionWorkflow(client.app.state.database.sessions),
        movements=JdItemMovementWorkflow(client.app.state.database.sessions),
    )
    definitions = tools.definitions()
    assert {item["name"] for item in definitions} == set(tools.names)
    assert all(item["strict"] for item in definitions)

    async def prepare(text: str, *, missing: bool = False):
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            changes=(SetProfileField(ProfileField.JOB_TITLE, text),),
            sources=(AlignProfileSource(ProfileField.JOB_TITLE, "citation_missing"),)
            if missing
            else (AddProfileSource(ProfileField.JOB_TITLE, CurrentInputSourceSelection()),),
        )

    prepared = client.portal.call(
        tools.prepare,
        "revise_jd_profile",
        json.dumps(
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "前端工程師"},
                    {
                        "action": "add_source",
                        "field": "job_title",
                        "source": {"kind": "current_input"},
                    },
                ]
            }
        ),
        uuid4(),
    )
    assert isinstance(prepared, PreparedProfileWrite)
    original_insert = source_persistence.insert_source_references

    async def fail_after_source_write(
        session: AsyncSession,
        job_file_id: UUID,
        revision_id: UUID,
        references: tuple[JdSourceReference, ...],
    ) -> None:
        await original_insert(session, job_file_id, revision_id, references)
        if references:
            raise ConnectionError("synthetic failure after evidence write")

    with monkeypatch.context() as patch:
        patch.setattr(source_persistence, "insert_source_references", fail_after_source_write)
        with pytest.raises(ConnectionError, match="synthetic"):
            client.portal.call(tools.execute, prepared)
    assert client.portal.call(candidates.read, scope).position == start
    assert client.portal.call(tools.execute, prepared) == "updated"
    changed = client.portal.call(candidates.read, scope)
    assert changed.profile.job_title == "前端工程師"
    sources = transact(
        client, lambda s: read_source_references(s, file_id, changed.position.revision_id)
    )
    assert len(sources) == 1 and not sources[0].needs_review
    assert client.portal.call(workflow.execute, writer, prepared) == "updated"
    assert client.portal.call(candidates.read, scope).position == changed.position
    with pytest.raises(InvalidJdSourceError):
        client.portal.call(lambda: prepare("不能留下的變更", missing=True))
    assert client.portal.call(candidates.read, scope).position == changed.position
    assert client.get(f"/api/job-files/{file_id}/jd/profile").json()["revision_id"] == str(
        start.revision_id
    )
