"""Human source navigation stays on formal JD and the citation's original fixed chain."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.models import ProfileField
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
from caliburn.features.work_memory.candidates import CreateMemoryObject, ReviseMemoryObject
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


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
    assert refused.status_code == 409
    complete(client, replace(turn, candidate=candidate))
    listed = client.get(endpoint).json()
    assert listed["revision_id"] == str(candidate.revision_id)
    assert listed["references"] == [
        {
            "citation_id": str(citation_id),
            "target_label": "職務名稱",
            "source_kind": "interview",
            "source_label": "訪談序號 2 · 員工",
            "needs_recheck": False,
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
    assert (
        client.get(
            f"{endpoint}/{citation_id}/changes", params={"revision_id": listed["revision_id"]}
        ).status_code
        == 422
    )


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
        old = await memory.publish(writer, understanding.position, uuid4())
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
        latest = await memory.publish(writer, phase, uuid4())
        return old, latest, understanding.object_id

    old, latest, object_id = client.portal.call(publish_scenarios)
    original = transact(
        client,
        lambda s: candidate_queries.read_snapshot_object(s, file_id, old.snapshot_id, object_id),
    )
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
    complete(client, replace(turn, candidate=candidate))
    endpoint = f"/api/job-files/{file_id}/jd/sources"
    listed = client.get(endpoint).json()
    reference = listed["references"][0]
    assert reference["needs_recheck"] is True
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
    assert "每月盤點。" in delta.json()["markdown"]
    assert "每季盤點。" in delta.json()["markdown"]
    assert client.get(endpoint).json() == listed  # Viewing is not confirmation.
    saved = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, candidate.revision_id),
    )
    assert saved[0].source.snapshot_id == old.snapshot_id != latest.snapshot_id
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
        == 409
    )
    current_other = client.get(f"/api/job-files/{other.writer.scope.job_file_id}/jd/sources").json()
    assert (
        client.get(
            f"/api/job-files/{other.writer.scope.job_file_id}/jd/sources/{citation_id}",
            params={"revision_id": current_other["revision_id"]},
        ).status_code
        == 404
    )


def test_stale_formal_jd_requires_reload_and_read_errors_do_not_become_empty_lists(
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
    assert client.get(f"{endpoint}/{uuid4()}", params={"revision_id": old_id}).status_code == 409
    assert client.get(f"/api/job-files/{uuid4()}/jd/sources").status_code == 404
