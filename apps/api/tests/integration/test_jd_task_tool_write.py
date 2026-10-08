"""Model task creation keeps each child/relation's sources separate in one transaction."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.capabilities import (
    CapabilityKind,
    CreateCapability,
    EditJdCapabilities,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import SourceTargetKind
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_sources import CurrentInputSourceSelection
from caliburn.workflows.jd_task_writes import (
    CreateTaskInput,
    JdTaskWriteWorkflow,
    TaskCapabilityInput,
    TaskDetailInput,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def test_task_detail_and_capability_relation_have_separate_evidence_and_replay(
    client: TestClient,
    database_connection: psycopg.Connection,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "任務來源",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我運用 React 製作頁面，提交可操作的網站。"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    initial = client.portal.call(candidates.start, writer)
    client.portal.call(
        candidates.edit,
        writer,
        initial.scope,
        EditJdCapabilities(
            uuid4(),
            initial.revision_id,
            CreateCapability(CapabilityKind.SKILL, "React", "介面實作能力"),
        ),
    )
    capability = client.portal.call(candidates.read, scope).work.capabilities[0]
    workflow = JdTaskWriteWorkflow(client.app.state.database.sessions)
    binding = PublishedMemoryRead(scope, None, 1)
    source = CurrentInputSourceSelection()

    async def prepare():
        return await workflow.prepare(
            binding,
            command_id=uuid4(),
            intent=CreateTaskInput(
                None,
                "製作網站頁面",
                "依已確認設計實作頁面。",
                outcomes=(TaskDetailInput("交付可操作網站", (source,)),),
                required_skills=(TaskCapabilityInput(jd_read_ref(capability), (source,)),),
                sources=(source,),
            ),
        )

    prepared = client.portal.call(prepare)
    before_count = database_connection.execute(
        "SELECT count(*) FROM jd_revisions WHERE job_file_id = %s", (file_id,)
    ).fetchone()[0]
    result = client.portal.call(workflow.execute, writer, prepared)
    after_count = database_connection.execute(
        "SELECT count(*) FROM jd_revisions WHERE job_file_id = %s", (file_id,)
    ).fetchone()[0]
    assert after_count - before_count == 1
    preview = client.portal.call(candidates.read, scope)
    assert len(preview.work.tasks) == 1
    task = preview.work.tasks[0]
    assert result == f"created · read_ref: {jd_read_ref(task)}"
    assert len(preview.work.task_links) == 1
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, file_id, preview.position.revision_id
        ),
    )
    assert {r.target.kind for r in references} == {
        SourceTargetKind.TASK,
        SourceTargetKind.DETAIL,
        SourceTargetKind.TASK_CAPABILITY,
    }
    assert all(not r.needs_review for r in references)
    assert all(r.reviewed_revision_id == preview.position.revision_id for r in references)
    assert client.portal.call(workflow.execute, writer, prepared) == result
    assert client.portal.call(candidates.read, scope).position == preview.position
