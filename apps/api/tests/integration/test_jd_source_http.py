"""Human source navigation stays on formal JD and the citation's original fixed chain."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import persistence, source_persistence, source_service
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import CreateTask, EditJdTasks
from caliburn.features.job_description.work_queries import read_work_at
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.executions.context_history import RoleContextHistory
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.evidence import JdEvidenceWorkflow
from caliburn.workflows.job_description.reads import JdReadWorkflow
from caliburn.workflows.job_description.undo import JdUndoWorkflow
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_consultant_completion import complete, start_turn, transact
from tests.integration.test_consultant_context_binding import capture
from tests.integration.test_consultant_context_binding import start as start_context
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("status", ["active", "paused", "cancelled", "failed", "completed"])
def test_evidence_rejects_unadopted_candidate_revisions(client: TestClient, status: str) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s,
            job_file_id=file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    middle = client.portal.call(
        workflow.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(original.source_id)),),
        ),
    )
    citation = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s,
            file_id,
            middle.revision_id,
        ),
    )[0].citation_id
    final = client.portal.call(
        workflow.edit,
        turn.writer,
        middle.scope,
        ReviseJdProfile(
            uuid4(),
            middle.revision_id,
            (SetProfileField(ProfileField.PURPOSE, "候選中間版之後的內容"),),
        ),
    )
    if status == "paused":
        transact(client, lambda s: executions.pause_execution(s, turn.writer))
    elif status in ("cancelled", "failed"):
        client.portal.call(
            ConsultantCompletionWorkflow(workflow.sessions).stop,
            turn.writer,
            ExecutionStatus(status),
        )
    elif status == "completed":
        complete(client, replace(turn, candidate=final))
    endpoint = f"/api/job-files/{file_id}/jd/sources/{citation}"
    for suffix in ("", "/changes"):
        assert (
            client.get(
                endpoint + suffix, params={"revision_id": str(middle.revision_id)}
            ).status_code
            == 404
        )
        assert client.get(
            endpoint + suffix, params={"revision_id": str(final.revision_id)}
        ).status_code == (200 if status == "completed" else 404)
    assert transact(
        client, lambda s: persistence.is_formal_revision(s, file_id, middle.base_revision_id)
    )


def test_adopted_evidence_remains_readable_after_undo(client: TestClient) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s,
            job_file_id=file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    position = client.portal.call(
        workflow.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(original.source_id)),),
        ),
    )
    complete(client, replace(turn, candidate=position))
    reference = client.get(f"/api/job-files/{file_id}/jd/sources").json()["references"][0]
    undone = client.portal.call(
        JdUndoWorkflow(workflow.sessions).undo, file_id, turn.writer.scope.execution_id
    )
    assert transact(
        client, lambda s: persistence.is_formal_revision(s, file_id, undone.revision_id)
    )
    endpoint = f"/api/job-files/{file_id}/jd/sources/{reference['citation_id']}"
    for suffix in ("", "/changes"):
        assert (
            client.get(
                endpoint + suffix, params={"revision_id": str(position.revision_id)}
            ).status_code
            == 200
        )
    assert client.get(f"/api/job-files/{file_id}/jd/profile").json()["revision_id"] == str(
        undone.revision_id
    )


def test_only_completed_jd_evidence_can_be_read_and_no_pending_input_is_exposed(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=file_id, execution_id=turn.writer.scope.execution_id
        ),
    )
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    candidate = client.portal.call(
        jd.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(original.source_id)),),
        ),
    )
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    before = client.get(endpoint)
    assert before.status_code == 200
    assert before.json()["references"] == []
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, candidate.revision_id),
    )
    citation_id = references[0].citation_id
    # Even an exact candidate ID is not a public-read capability.
    refused = client.get(
        f"{endpoint}/{citation_id}", params={"revision_id": str(candidate.revision_id)}
    )
    assert refused.status_code == 404
    complete(client, replace(turn, candidate=candidate))
    listed = client.get(endpoint).json()
    assert listed["revision_id"] == str(candidate.revision_id)
    assert listed["references"] == [
        {
            "citation_id": str(citation_id),
            "target_label": "職務名稱",
            "target": {
                "kind": "profile_field",
                "field": "job_title",
                "item_id": None,
            },
            "source_kind": "interview",
            "source_label": "訪談序號 2 · 員工",
            "needs_recheck": False,
            "jd_changed": False,
            "source_changed": False,
        }
    ]
    body = client.get(f"{endpoint}/{citation_id}", params={"revision_id": listed["revision_id"]})
    assert body.status_code == 200
    assert body.json()["content"] == {
        "kind": "interview",
        "interview_sequence": 2,
        "speaker": "employee",
        "interview_text": "我負責網站前端交付。",
    }
    changes = client.get(
        f"{endpoint}/{citation_id}/changes", params={"revision_id": listed["revision_id"]}
    )
    assert changes.status_code == 200
    assert changes.json()["source_markdown"] is None
    assert "沒有淨差異" in changes.json()["jd_markdown"]
    assert "markdown" not in changes.json()


def test_fixed_chain_survives_upstream_rename_and_diff_does_not_align_reference(
    client: TestClient,
) -> None:
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    source1 = complete(client, first).employee_input.source_id
    source2 = complete(client, start_turn(client, file_id=file_id)).employee_input.source_id

    async def publish_scenarios():
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)

        async def start(source_id):
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            stage = await memory.start(writer, source_id)
            assert stage is not None
            return writer, stage

        writer, stage = await start(source1)
        situation = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("月末盤點", "盤點範圍", "每月盤點。"),
                frozenset({source1}),
            ),
        )
        phase = await memory.handoff(writer, situation.position, uuid4())
        understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "依據盤點", "維持庫存資料可追溯。"),
                frozenset({situation.object_id}),
            ),
        )
        old = await publish_memory_owner_fixture(
            memory.sessions, writer, understanding.position, uuid4()
        )
        writer, stage = await start(source2)
        changed = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                situation.object_id,
                MemoryContentChanges(title="季度盤點", body="每季盤點。"),
            ),
        )
        phase = await memory.handoff(writer, changed.position, uuid4())
        latest = await publish_memory_owner_fixture(memory.sessions, writer, phase, uuid4())
        return old, latest, understanding.object_id

    old, latest, object_id = client.portal.call(publish_scenarios)
    original = transact(
        client,
        lambda s: candidate_queries.read_snapshot_object(s, file_id, old.snapshot_id, object_id),
    )
    published = transact(
        client,
        lambda s: candidate_queries.read_snapshot_object(s, file_id, latest.snapshot_id, object_id),
    )
    # Publication rebinds changed child revisions into a new root revision even
    # when the entire root content/body remains unchanged.
    assert published.content == original.content
    assert published.body_id == original.body_id
    assert published.work_situation_references != original.work_situation_references
    assert published.revision_id != original.revision_id
    turn = start_turn(client, file_id=file_id)
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    candidate = client.portal.call(
        jd.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (
                AddJdSource(
                    MemorySource(
                        MemorySourceLayer.WORK_UNDERSTANDING,
                        old.snapshot_id,
                        object_id,
                        original.revision_id,
                    )
                ),
            ),
        ),
    )
    third_input = complete(client, replace(turn, candidate=candidate)).employee_input.source_id
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    statements: list[str] = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        listed = client.get(endpoint).json()
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    body_reads = [statement for statement in statements if "JOIN memory_bodies" in statement]
    print(f"Source overview: {len(statements)} SQL queries; {len(body_reads)} Memory body reads")
    # The overview may read the two roots, but must not expand child bodies or
    # interview text merely to determine whether the fixed source changed.
    assert len(body_reads) <= 2
    assert not any("interview_texts.interview_text" in statement for statement in statements)
    reference = listed["references"][0]
    assert reference["needs_recheck"] is True
    assert reference["jd_changed"] is False
    assert reference["source_changed"] is True
    assert reference["source_label"] == "庫存管理"
    citation_id = reference["citation_id"]
    params = {"revision_id": listed["revision_id"]}
    root = client.get(f"{endpoint}/{citation_id}", params=params).json()["content"]
    assert root["body"] == "維持庫存資料可追溯。"
    assert root["references"][0]["label"] == "月末盤點"
    child = client.get(
        f"{endpoint}/{citation_id}",
        params={**params, "source_ref": root["references"][0]["source_ref"]},
    ).json()["content"]
    assert child["title"] == "月末盤點"
    assert child["body"] == "每月盤點。"
    leaf = client.get(
        f"{endpoint}/{citation_id}",
        params={**params, "source_ref": child["references"][0]["source_ref"]},
    ).json()["content"]
    assert leaf["interview_sequence"] == 2
    assert leaf["speaker"] == "employee"
    delta = client.get(f"{endpoint}/{citation_id}/changes", params=params)
    assert delta.status_code == 200
    assert delta.json()["source_version"] == {
        "snapshot_id": str(old.snapshot_id),
        "revision_id": str(original.revision_id),
        "covered_through_sequence": old.covered_through_sequence,
    }
    assert delta.json()["comparison_version"] == {
        "snapshot_id": str(latest.snapshot_id),
        "revision_id": str(published.revision_id),
        "covered_through_sequence": latest.covered_through_sequence,
    }
    assert "每月盤點。" in delta.json()["source_markdown"]
    assert "每季盤點。" in delta.json()["source_markdown"]
    assert "沒有淨差異" in delta.json()["jd_markdown"]
    assert client.get(endpoint).json() == listed  # Viewing is not confirmation.
    saved = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, candidate.revision_id),
    )
    assert saved[0].source.snapshot_id == old.snapshot_id != latest.snapshot_id
    edited = _edit_profile(client, file_id, candidate.revision_id, job_title="庫存專員")
    both = client.get(endpoint).json()
    assert both["references"][0]["jd_changed"] is True
    assert both["references"][0]["source_changed"] is True
    comparison = client.get(f"{endpoint}/{citation_id}/changes", params={"revision_id": edited})
    assert comparison.status_code == 200
    assert "-前端工程師" in comparison.json()["jd_markdown"]
    assert "+庫存專員" in comparison.json()["jd_markdown"]
    assert "每季盤點。" in comparison.json()["source_markdown"]
    assert client.get(endpoint).json() == both
    params = {"revision_id": edited}
    # Same file, valid interview, but not an edge from this source chain.
    assert (
        client.get(
            f"{endpoint}/{citation_id}", params={**params, "source_ref": "interview_4"}
        ).status_code
        == 404
    )
    other = start_turn(client)
    assert (
        client.get(
            f"/api/job-files/{other.writer.scope.job_file_id}/jd/sources/{citation_id}",
            params=params,
        ).status_code
        == 404
    )
    current_other = client.get(f"/api/job-files/{other.writer.scope.job_file_id}/jd/sources").json()
    assert (
        client.get(
            f"/api/job-files/{other.writer.scope.job_file_id}/jd/sources/{citation_id}",
            params={"revision_id": current_other["revision_id"]},
        ).status_code
        == 404
    )

    async def remove_and_recreate_source() -> None:
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with sessions.begin() as session:
            await executions.admit_execution(session, scope)
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        stage = await memory.start(writer, third_input)
        phase = await memory.handoff(writer, stage, uuid4())
        removed = await memory.edit(
            writer, DeleteMemoryObject(uuid4(), phase, MemoryLayer.WORK_UNDERSTANDING, object_id)
        )
        recreated = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                removed.position,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "新物件", "不能展示同名替代物件。"),
            ),
        )
        await publish_memory_owner_fixture(memory.sessions, writer, recreated.position, uuid4())

    client.portal.call(remove_and_recreate_source)
    removed_view = client.get(endpoint).json()
    assert removed_view["references"][0]["source_changed"] is True
    removed_diff = client.get(f"{endpoint}/{citation_id}/changes", params=params)
    assert removed_diff.status_code == 200
    assert "同一物件已不在" in removed_diff.json()["source_markdown"]
    assert "-維持庫存資料可追溯。" in removed_diff.json()["source_markdown"]
    assert "不能展示同名替代物件。" not in removed_diff.json()["source_markdown"]


def test_invalid_citation_and_missing_file_do_not_become_empty_lists(
    client: TestClient,
) -> None:
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    complete(client, first)
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    before = client.get(endpoint)
    assert before.status_code == 200
    old_id = before.json()["revision_id"]
    edited = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": old_id,
            "changes": [
                {"action": "set_field", "field": "purpose", "value": "人工補充，尚待確認。"}
            ],
        },
    )
    assert edited.status_code == 200
    assert client.get(f"{endpoint}/{uuid4()}", params={"revision_id": old_id}).status_code == 404
    assert client.get(f"/api/job-files/{uuid4()}/jd/sources").status_code == 404


def test_selected_formal_revision_remains_readable_after_head_moves(client: TestClient) -> None:
    file_id, old_revision = _reviewed_interview(client)
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    reference = client.get(endpoint).json()["references"][0]
    _edit_profile(client, file_id, old_revision, job_title="新的正式職稱")
    source = client.get(
        f"{endpoint}/{reference['citation_id']}", params={"revision_id": str(old_revision)}
    )
    assert source.status_code == 200
    assert source.json()["revision_id"] == str(old_revision)
    assert source.json()["content"]["interview_text"] == "我負責網站前端交付。"
    changes = client.get(
        f"{endpoint}/{reference['citation_id']}/changes",
        params={"revision_id": str(old_revision)},
    )
    assert changes.status_code == 200
    assert "沒有淨差異" in changes.json()["jd_markdown"]


def test_initial_context_and_tool_map_share_recheck_policy(
    client: TestClient,
    database_settings: DatabaseSettings,
) -> None:
    created = client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": "首次 map",
            "employee_name": "合成人員",
        },
    )
    assert created.status_code == 201
    file_id = UUID(created.json()["job_file_id"])
    old_revision = UUID(client.get(f"/api/job-files/{file_id}/jd/profile").json()["revision_id"])
    opening = transact(client, lambda s: interviews.read_interview_history(s, file_id))[0]
    # 首次原生 capture 不借用只有 owner 完成證明、沒有 saver 原件的 Turn fixture。
    cited_revision = transact(
        client,
        lambda s: source_service.revise_sources(
            s,
            file_id,
            ReviseJdSources(
                uuid4(),
                old_revision,
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
                (AddJdSource(InterviewSource(opening.source_id)),),
            ),
        ),
    )
    _edit_profile(client, file_id, cited_revision, job_title="人工新職稱")

    async def read():
        database = client.app.state.database
        writer = await start_context(database, "首次訪談", file_id)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            saver.serde = create_graph_serializer()
            await saver.setup()
            role_history = RoleContextHistory(
                database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
            )
            context = await capture(database, role_history, PreparationProbe())
            payload = context.request.create_payload()
            initial = json.loads(payload["input"][0]["content"])["jd_map"]
            assert "JD 人工最終差異" in payload["input"][-2]["content"]
            reader = JdReadWorkflow(database.sessions)
            before = await reader.read_candidate(context.memory_binding)
            async with database.sessions() as session:
                references = await source_persistence.read_source_references(
                    session, file_id, before.position.revision_id
                )
            assert len(references) == 1 and references[0].needs_review
            tools = JdReadTools(
                reader,
                context.memory_binding,
                references=JdModelReferences(database.sessions, file_id),
            )
            tool_map = json.loads(await tools.invoke("read_jd", '{"view":"map","read_ref":null}'))
            assert initial == tool_map
            assert initial["profile"]["needs_recheck"]
            assert "citation_ref" not in json.dumps(initial)
            profile = json.loads(
                await tools.invoke("read_jd", '{"view":"profile","read_ref":null}')
            )
            reference = profile["supporting_sources"]["job_title"][0]
            assert reference["needs_recheck"] and reference["jd_changed"]
            assert not reference["source_changed"]
            assert (await reader.read_candidate(context.memory_binding)).position == before.position
            async with database.sessions() as session:
                assert (
                    await source_persistence.read_source_references(
                        session, file_id, before.position.revision_id
                    )
                    == references
                )

    client.portal.call(read)


def _edit_profile(
    client: TestClient,
    file_id: UUID,
    revision_id: UUID | str,
    *,
    job_title: str,
    purpose: str | None = None,
) -> str:
    values = {"job_title": job_title}
    if purpose is not None:
        values["purpose"] = purpose
    response = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": str(revision_id),
            "changes": [
                {"action": "set_field", "field": field, "value": value}
                for field, value in values.items()
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["revision_id"]


def _reviewed_interview(client: TestClient) -> tuple[UUID, UUID]:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=file_id, execution_id=turn.writer.scope.execution_id
        ),
    )
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    candidate = client.portal.call(
        workflow.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (AddJdSource(InterviewSource(original.source_id)),),
        ),
    )
    complete(client, replace(turn, candidate=candidate))
    return file_id, candidate.revision_id


def test_jd_comparison_uses_last_review_not_previous_turn_and_only_the_cited_target(
    client: TestClient,
) -> None:
    file_id, reviewed_id = _reviewed_interview(client)
    _edit_profile(client, file_id, reviewed_id, job_title="上一 Turn 職稱")
    next_turn = start_turn(client, file_id=file_id, with_candidate=False)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    candidate = client.portal.call(workflow.start, next_turn.writer)
    changed = client.portal.call(
        workflow.edit,
        next_turn.writer,
        candidate.scope,
        ReviseJdProfile(
            uuid4(),
            candidate.revision_id,
            (SetProfileField(ProfileField.PURPOSE, "上一 Turn 僅編修目的"),),
        ),
    )
    complete(client, replace(next_turn, candidate=changed))
    current = _edit_profile(
        client,
        file_id,
        changed.revision_id,
        job_title="目前職稱",
        purpose="不可展示的其他欄位",
    )
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    before = client.get(endpoint).json()
    reference = before["references"][0]
    assert reference["jd_changed"] is True
    assert reference["source_changed"] is False
    url = f"{endpoint}/{reference['citation_id']}/changes"
    response = client.get(url, params={"revision_id": current})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["revision_id"] == current
    assert body["citation_id"] == reference["citation_id"]
    assert body["source_markdown"] is None
    assert "-前端工程師" in body["jd_markdown"]
    assert "+目前職稱" in body["jd_markdown"]
    assert "上一 Turn 職稱" not in body["jd_markdown"]
    assert "不可展示的其他欄位" not in body["jd_markdown"]
    assert client.get(endpoint).json() == before
    saved = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, UUID(current)),
    )
    assert saved[0].reviewed_revision_id == reviewed_id
    assert saved[0].needs_review

    # The query is also executable under PostgreSQL's enforced read-only transaction.
    async def read_only() -> None:
        engine = client.app.state.database.engine.execution_options(postgresql_readonly=True)
        sessions = async_sessionmaker(engine)
        async with sessions() as session:
            assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        reader = JdEvidenceWorkflow(sessions)
        overview = await reader.read_overview(file_id)
        changes = await reader.read_changes(file_id, UUID(current), saved[0].citation_id)
        assert overview.references[0].jd_changed
        assert changes.before == ("前端工程師",)
        assert changes.after == ("目前職稱",)

    client.portal.call(read_only)
    assert client.get(url, params={"revision_id": str(reviewed_id)}).status_code == 200
    assert (
        client.get(f"{endpoint}/{uuid4()}/changes", params={"revision_id": current}).status_code
        == 404
    )
    other_file, other_revision = _reviewed_interview(client)
    assert (
        client.get(
            f"/api/job-files/{other_file}/jd/sources/{reference['citation_id']}/changes",
            params={"revision_id": str(other_revision)},
        ).status_code
        == 404
    )


def test_reverting_jd_text_keeps_review_pending_with_explicit_zero_net_diff(
    client: TestClient,
) -> None:
    file_id, reviewed_id = _reviewed_interview(client)
    changed = _edit_profile(client, file_id, reviewed_id, job_title="變動後職稱")
    current = _edit_profile(client, file_id, changed, job_title="前端工程師")
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    before = client.get(endpoint).json()
    reference = before["references"][0]
    assert reference["needs_recheck"] and reference["jd_changed"]
    assert not reference["source_changed"]
    response = client.get(
        f"{endpoint}/{reference['citation_id']}/changes", params={"revision_id": current}
    )
    assert response.status_code == 200
    assert "沒有淨差異" in response.json()["jd_markdown"]
    assert "曾修改" in response.json()["jd_markdown"]
    assert "待核對" in response.json()["jd_markdown"]
    assert client.get(endpoint).json() == before


@pytest.mark.parametrize(
    "invalid",
    [
        "missing_review",
        "missing_revision",
        "unrelated_revision",
        "target",
        "source",
        "missing_target",
    ],
)
def test_unavailable_or_mismatched_review_baseline_is_not_an_empty_diff(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
) -> None:
    file_id, reviewed_id = _reviewed_interview(client)
    current = _edit_profile(client, file_id, reviewed_id, job_title="目前職稱")
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    reference = client.get(endpoint).json()["references"][0]
    read_original = source_persistence.read_source_references
    absent_target = JdSourceTarget(SourceTargetKind.TASK, uuid4())

    async def read_damaged(
        session: AsyncSession,
        selected_file: UUID,
        revision_id: UUID,
    ) -> tuple[JdSourceReference, ...]:
        references = await read_original(session, selected_file, revision_id)
        if invalid == "missing_target" and selected_file == file_id:
            return tuple(replace(value, target=absent_target) for value in references)
        if selected_file != file_id or revision_id != UUID(current):
            return references
        (value,) = references
        if invalid == "missing_review":
            value = replace(value, reviewed_revision_id=None)
        elif invalid == "missing_revision":
            value = replace(value, reviewed_revision_id=uuid4())
        elif invalid == "unrelated_revision":
            # Same file and existing target, but this revision has no review for this citation.
            initial = await persistence.read_document(session, file_id)
            value = replace(value, reviewed_revision_id=initial.initial_revision_id)
        elif invalid == "target":
            value = replace(
                value,
                target=JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
            )
        else:
            value = replace(value, source=InterviewSource(uuid4()))
        return (value,)

    monkeypatch.setattr(source_persistence, "read_source_references", read_damaged)
    response = client.get(
        f"{endpoint}/{reference['citation_id']}/changes", params={"revision_id": current}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "jd_review_baseline_not_available"


def test_task_and_detail_diffs_exclude_siblings_and_identically_named_tasks(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    current = turn.candidate
    for description in ("本項工作", "同名另一任務的原文"):
        current = client.portal.call(
            jd.edit,
            turn.writer,
            current.scope,
            EditJdTasks(
                uuid4(),
                current.revision_id,
                CreateTask(None, "同名任務", description, ("本筆原成果", "同項另一成果"), ()),
            ),
        )
    work = transact(client, lambda s: read_work_at(s, file_id, current.revision_id))
    task, other = work.tasks
    detail, sibling = task.details
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s,
            job_file_id=file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    targets = (JdSourceTarget(SourceTargetKind.TASK, task.task_id),)
    for target in targets:
        current = client.portal.call(
            jd.edit,
            turn.writer,
            current.scope,
            ReviseJdSources(
                uuid4(),
                current.revision_id,
                target,
                (AddJdSource(InterviewSource(original.source_id)),),
            ),
        )
    complete(client, replace(turn, candidate=current))
    revision_id = str(current.revision_id)
    for task_id, changes in (
        (
            task.task_id,
            [
                {"action": "set_field", "field": "title", "value": "本項改名"},
                {
                    "action": "revise_detail",
                    "detail_id": str(detail.detail_id),
                    "text": "本筆新成果",
                },
                {
                    "action": "revise_detail",
                    "detail_id": str(sibling.detail_id),
                    "text": "同項另一新成果",
                },
            ],
        ),
        (
            other.task_id,
            [{"action": "set_field", "field": "description", "value": "不可展示另一任務"}],
        ),
    ):
        edited = client.post(
            f"/api/job-files/{file_id}/jd/tasks",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": revision_id,
                "change": {"action": "revise_task", "task_id": str(task_id), "changes": changes},
            },
        )
        assert edited.status_code == 200
        revision_id = edited.json()["revision_id"]
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    overview = client.get(endpoint).json()
    results = {}
    for reference in overview["references"]:
        assert reference["jd_changed"] and not reference["source_changed"]
        response = client.get(
            f"{endpoint}/{reference['citation_id']}/changes", params={"revision_id": revision_id}
        )
        assert response.status_code == 200
        markdown = response.json()["jd_markdown"]
        results[reference["target"]["kind"]] = markdown
        assert "不可展示" not in markdown
        assert "同名另一任務的原文" not in markdown
    assert "-同名任務" in results["task"] and "+本項改名" in results["task"]
    assert "本筆原成果" in results["task"] and "本筆新成果" in results["task"]
    assert "同項另一新成果" in results["task"]
    assert set(results) == {"task"}


def test_explicit_alignment_advances_the_jd_diff_baseline(client: TestClient) -> None:
    file_id, _ = _reviewed_interview(client)
    turn = start_turn(client, file_id=file_id)
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    changed = client.portal.call(
        jd.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdProfile(
            uuid4(),
            turn.candidate.revision_id,
            (SetProfileField(ProfileField.JOB_TITLE, "新的已核對職稱"),),
        ),
    )
    (reference,) = transact(
        client, lambda s: source_persistence.read_source_references(s, file_id, changed.revision_id)
    )
    aligned = client.portal.call(
        jd.edit,
        turn.writer,
        changed.scope,
        ReviseJdSources(
            uuid4(),
            changed.revision_id,
            reference.target,
            (AlignJdSource(reference.citation_id, reference.source),),
        ),
    )
    complete(client, replace(turn, candidate=aligned))
    current = _edit_profile(client, file_id, aligned.revision_id, job_title="後續職稱")
    endpoint = f"/api/job-files/{file_id}/jd/sources/{reference.citation_id}/changes"
    response = client.get(endpoint, params={"revision_id": current})
    assert response.status_code == 200
    markdown = response.json()["jd_markdown"]
    assert "-新的已核對職稱" in markdown and "+後續職稱" in markdown
    assert "前端工程師" not in markdown
