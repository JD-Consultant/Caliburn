"""Actual PG: private candidate reads and direct citations retain fixed owner identities."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.areas import CreateArea, EditJdAreas
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_reference_fields import resolve_jd_arguments
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    app = client.app
    assert isinstance(app, FastAPI)
    assert client.portal is not None

    async def run() -> T:
        async with app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def create_file(client: TestClient) -> UUID:
    response = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "JD讀取測試",
            "employee_name": "合成員工",
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["job_file_id"])


def start_input(client: TestClient, file_id: UUID) -> ExecutionWriter:
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "不應由JD展開的原話"},
    )
    assert accepted.status_code == 202
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    return transact(
        client, lambda session: executions.claim_writer(session, scope, writer_id=uuid4())
    )


def test_current_candidate_sources_are_scoped_and_reads_do_not_formalize_or_align(
    client: TestClient,
) -> None:
    assert isinstance(client.app, FastAPI)
    assert client.portal is not None
    file_id = create_file(client)
    writer = start_input(client, file_id)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    position = client.portal.call(workflow.start, writer)
    position = client.portal.call(
        workflow.edit,
        writer,
        position.scope,
        ReviseJdProfile(
            uuid4(),
            position.revision_id,
            (
                SetProfileField(ProfileField.JOB_TITLE, "候選職稱"),
                SetProfileField(ProfileField.PURPOSE, "候選目的"),
            ),
        ),
    )
    current = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=file_id, execution_id=writer.scope.execution_id
        ),
    )
    formal = transact(client, lambda s: interviews.read_interview_history(s, file_id))[0]
    for field, source_id in (
        (ProfileField.JOB_TITLE, current.source_id),
        (ProfileField.PURPOSE, formal.source_id),
    ):
        position = client.portal.call(
            workflow.edit,
            writer,
            position.scope,
            ReviseJdSources(
                uuid4(),
                position.revision_id,
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field),
                (AddJdSource(InterviewSource(source_id)),),
            ),
        )
    position = client.portal.call(
        workflow.edit,
        writer,
        position.scope,
        ReviseJdProfile(
            uuid4(),
            position.revision_id,
            (SetProfileField(ProfileField.JOB_TITLE, "候選改名"),),
        ),
    )
    position = client.portal.call(
        workflow.edit,
        writer,
        position.scope,
        EditJdAreas(uuid4(), position.revision_id, CreateArea("職責", "完整職責")),
    )
    before = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, position.revision_id),
    )
    binding = PublishedMemoryRead(writer.scope, None, 1)
    reader = JdReadWorkflow(client.app.state.database.sessions)
    tools = JdReadTools(reader, binding)
    output = json.loads(
        client.portal.call(tools.invoke, "read_jd", '{"view":"profile","read_ref":null}')
    )
    assert output["job_title"] == "候選改名"
    # Compare the resolved UUID identities, not the model-facing representation.
    output = json.loads(
        client.portal.call(resolve_jd_arguments, tools.references, json.dumps(output))
    )
    assert output["supporting_sources"]["job_title"] == [
        {
            "citation_ref": f"citation_{before[0].citation_id.hex}",
            "kind": "current_input",
            "needs_recheck": True,
        }
    ]
    assert output["supporting_sources"]["purpose"] == [
        {
            "citation_ref": f"citation_{before[1].citation_id.hex}",
            "kind": "interview",
            "interview_sequence": 1,
        }
    ]
    assert "不應由JD展開的原話" not in json.dumps(output, ensure_ascii=False)
    assert client.get(f"/api/job-files/{file_id}/jd/profile").json()["profile"]["job_title"] is None
    assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
    inaccessible = JdReadTools(reader, replace(binding, interview_through_sequence=0))
    assert (
        json.loads(
            client.portal.call(inaccessible.invoke, "read_jd", '{"view":"profile","read_ref":null}')
        )["code"]
        == "source_not_available"
    )
    preview = client.portal.call(reader.read_candidate, binding)
    area_ref = jd_read_ref(preview.work.areas[0])
    assert (
        json.loads(
            client.portal.call(
                tools.invoke, "read_jd", json.dumps({"view": "item", "read_ref": area_ref})
            )
        )["scope_text"]
        == "完整職責"
    )
    assert json.loads(
        client.portal.call(
            tools.invoke, "read_jd", json.dumps({"view": "work_tasks", "read_ref": area_ref})
        )
    ) == {"items": []}

    # A later candidate change must be visible to the next read, not a cached preview.
    latest = client.portal.call(
        workflow.edit,
        writer,
        position.scope,
        ReviseJdProfile(
            uuid4(), position.revision_id, (SetProfileField(ProfileField.PURPOSE, "後續候選"),)
        ),
    )
    assert (
        json.loads(
            client.portal.call(tools.invoke, "read_jd", '{"view":"profile","read_ref":null}')
        )["purpose"]
        == "後續候選"
    )
    transact(client, lambda s: executions.pause_execution(s, writer))
    assert client.portal.call(
        tools.invoke, "read_jd", '{"view":"full","read_ref":null}'
    ).startswith("# 職務說明書")

    second = start_input(client, create_file(client))
    client.portal.call(workflow.start, second)
    foreign = JdReadTools(reader, PublishedMemoryRead(second.scope, None, 1))
    assert (
        json.loads(
            client.portal.call(
                foreign.invoke, "read_jd", json.dumps({"view": "item", "read_ref": area_ref})
            )
        )["code"]
        == "target_not_found"
    )
    wrong_scope = replace(writer.scope, job_file_id=second.scope.job_file_id)
    forged = JdReadTools(reader, PublishedMemoryRead(wrong_scope, None, 1))
    assert (
        json.loads(
            client.portal.call(forged.invoke, "read_jd", '{"view":"profile","read_ref":null}')
        )["code"]
        == "scope_not_allowed"
    )
    assert (
        transact(
            client,
            lambda s: source_persistence.read_source_references(s, file_id, position.revision_id),
        )
        == before
    )
    assert client.portal.call(workflow.read, writer.scope).position == latest
    latest_sources = transact(
        client, lambda s: source_persistence.read_source_references(s, file_id, latest.revision_id)
    )
    assert all(reference.needs_review for reference in latest_sources)
    transact(client, lambda s: executions.finish_execution(s, writer, ExecutionStatus.CANCELLED))
    assert (
        json.loads(client.portal.call(tools.invoke, "read_jd", '{"view":"map","read_ref":null}'))[
            "code"
        ]
        == "scope_not_allowed"
    )


def test_memory_citations_keep_fixed_identity_after_rename_removal_and_late_publication(
    client: TestClient,
) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    assert client.portal is not None
    file_id = create_file(client)
    source_ids = []
    for _ in range(3):
        writer = start_input(client, file_id)

        async def formalize(
            session: AsyncSession, completed_writer: ExecutionWriter = writer
        ) -> UUID:
            result = await record_formal_interview(
                session, completed_writer, reply_text="合成正式答覆"
            )
            await executions.finish_execution(session, completed_writer, ExecutionStatus.COMPLETED)
            return result.employee_input.source_id

        source_ids.append(transact(client, formalize))

    async def scenario() -> None:
        sessions = app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)

        async def start_batch(source_id: UUID) -> tuple[ExecutionWriter, MemoryBatchPosition]:
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            stage = await memory.start(writer, source_id)
            assert stage is not None
            return writer, stage

        first_writer, stage = await start_batch(source_ids[0])
        first = await memory.edit(
            first_writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("引用舊名", "舊導覽", "秘密舊正文"),
            ),
        )
        removed = await memory.edit(
            first_writer,
            CreateMemoryObject(
                uuid4(),
                first.position,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("刪除後同名", "舊物件", "不可展開"),
            ),
        )
        phase = await memory.handoff(first_writer, removed.position, uuid4())
        understanding = await memory.edit(
            first_writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("理解", "理解導覽", "理解完整正文"),
            ),
        )
        old_snapshot = await memory.publish(first_writer, understanding.position, uuid4())

        next_writer, stage = await start_batch(source_ids[1])
        renamed = await memory.edit(
            next_writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                first.object_id,
                MemoryContentChanges(title="固定新版名"),
            ),
        )
        deleted = await memory.edit(
            next_writer,
            DeleteMemoryObject(
                uuid4(), renamed.position, MemoryLayer.WORK_SITUATION, removed.object_id
            ),
        )
        replacement = await memory.edit(
            next_writer,
            CreateMemoryObject(
                uuid4(),
                deleted.position,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("刪除後同名", "替代者不是舊物件", "錯誤替代正文"),
            ),
        )
        phase = await memory.handoff(next_writer, replacement.position, uuid4())
        pinned_snapshot = await memory.publish(next_writer, phase, uuid4())

        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
        async with sessions.begin() as session:
            await executions.admit_execution(session, scope)
            await interview_service.accept_input(
                session,
                SubmitInterviewInput(file_id, uuid4(), "本輪原文"),
                execution_id=scope.execution_id,
            )
            advisor = await executions.claim_writer(session, scope, writer_id=uuid4())
            old_first = await candidate_queries.read_snapshot_object(
                session, file_id, old_snapshot.snapshot_id, first.object_id
            )
            old_removed = await candidate_queries.read_snapshot_object(
                session, file_id, old_snapshot.snapshot_id, removed.object_id
            )
            pinned_understanding = await candidate_queries.read_snapshot_object(
                session, file_id, pinned_snapshot.snapshot_id, understanding.object_id
            )
        binding = PublishedMemoryRead(scope, pinned_snapshot.snapshot_id, 7)
        jd = JdCandidateWorkflow(sessions)
        position = await jd.start(advisor)
        position = await jd.edit(
            advisor,
            position.scope,
            ReviseJdProfile(
                uuid4(),
                position.revision_id,
                (
                    SetProfileField(ProfileField.JOB_TITLE, "既有職稱"),
                    SetProfileField(ProfileField.PURPOSE, "既有目的"),
                    SetProfileField(ProfileField.ORGANIZATION_UNIT, "既有單位"),
                ),
            ),
        )
        for field, snapshot_id, original in (
            (ProfileField.PURPOSE, old_snapshot.snapshot_id, old_first),
            (ProfileField.JOB_TITLE, old_snapshot.snapshot_id, old_removed),
            (ProfileField.ORGANIZATION_UNIT, pinned_snapshot.snapshot_id, pinned_understanding),
        ):
            position = await jd.edit(
                advisor,
                position.scope,
                ReviseJdSources(
                    uuid4(),
                    position.revision_id,
                    JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field),
                    (
                        AddJdSource(
                            MemorySource(
                                MemorySourceLayer(original.layer.value),
                                snapshot_id,
                                original.object_id,
                                original.revision_id,
                            )
                        ),
                    ),
                ),
            )

        late_writer, stage = await start_batch(source_ids[2])
        late = await memory.edit(
            late_writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                first.object_id,
                MemoryContentChanges(title="不得追逐的晚到名稱"),
            ),
        )
        phase = await memory.handoff(late_writer, late.position, uuid4())
        await memory.publish(late_writer, phase, uuid4())

        async with sessions() as session:
            before = await source_persistence.read_source_references(
                session, file_id, position.revision_id
            )
        tools = JdReadTools(JdReadWorkflow(sessions), binding)
        output = await tools.invoke("read_jd", '{"view":"profile","read_ref":null}')
        data = json.loads(await resolve_jd_arguments(tools.references, output))[
            "supporting_sources"
        ]
        assert data["purpose"] == [
            {
                "citation_ref": f"citation_{before[0].citation_id.hex}",
                "kind": "work_situation",
                "target_title": "固定新版名",
                "historical_title": "引用舊名",
                "needs_recheck": True,
            }
        ]
        assert data["job_title"] == [
            {
                "citation_ref": f"citation_{before[1].citation_id.hex}",
                "kind": "work_situation",
                "historical_title": "刪除後同名",
                "needs_recheck": True,
            }
        ]
        assert data["organization_unit"] == [
            {
                "citation_ref": f"citation_{before[2].citation_id.hex}",
                "kind": "work_understanding",
                "target_title": "理解",
            }
        ]
        for forbidden in (
            "秘密舊正文",
            "錯誤替代正文",
            "理解完整正文",
            "不得追逐的晚到名稱",
            str(old_snapshot.snapshot_id),
            str(first.object_id),
        ):
            assert forbidden not in output
        async with sessions() as session:
            assert (
                await source_persistence.read_source_references(
                    session, file_id, position.revision_id
                )
                == before
            )

    client.portal.call(scenario)
