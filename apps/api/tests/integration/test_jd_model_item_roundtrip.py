"""Public model calls survive JSON checkpointing and affect only the Turn candidate."""

import json
from functools import partial
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.job_description.source_intents import InterviewSourceSelection
from caliburn.features.job_description.sources import InterviewSource
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.compound_writes import execute_prepared_jd_edit
from caliburn.workflows.job_description.item_creation import JdItemCreationWorkflow
from caliburn.workflows.job_description.item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.job_description.item_movement import JdItemMovementWorkflow
from caliburn.workflows.job_description.item_revision import JdItemRevisionWorkflow
from caliburn.workflows.job_description.profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.job_description.sources import resolve_jd_source
from caliburn.workflows.job_description.task_writes import JdTaskWriteWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead

pytestmark = pytest.mark.postgres


def test_create_revise_delete_use_the_actual_model_codec(client: TestClient) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "模型編輯",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": "我負責月底盤點。",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    sessions = client.app.state.database.sessions

    async def exercise() -> None:
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        candidates = JdCandidateWorkflow(sessions)
        await candidates.start(writer)
        tools = JdWriteTools(
            JdProfileWriteWorkflow(sessions),
            JdTaskWriteWorkflow(sessions),
            PublishedMemoryRead(scope, None, 1),
            writer,
            references=JdModelReferences(sessions, scope.job_file_id),
            execute_edit=partial(execute_prepared_jd_edit, sessions),
            creations=JdItemCreationWorkflow(sessions),
            revisions=JdItemRevisionWorkflow(sessions),
            deletions=JdItemDeletionWorkflow(sessions),
            movements=JdItemMovementWorkflow(sessions),
        )

        async def call(name: str, arguments: dict) -> str:
            prepared = await tools.prepare(name, json.dumps(arguments), uuid4())
            assert not isinstance(prepared, str), prepared
            restored = restore_jd_write(json.loads(json.dumps(snapshot_jd_write(prepared))))
            assert restored == prepared
            result = await tools.execute(restored)
            assert await tools.execute(restored) == result
            return result

        # Only the next input number is assigned to this Turn. A later number must
        # still fail without changing the candidate.
        before = await candidates.read(scope)
        rejected = await tools.prepare(
            "create_jd_item",
            json.dumps(
                {
                    "item": {
                        "kind": "responsibility_area",
                        "title": "盤點",
                        "scope_text": "月底庫存盤點",
                        "supporting_sources": [{"kind": "interview", "interview_sequence": 3}],
                    }
                }
            ),
            uuid4(),
        )
        assert isinstance(rejected, str)
        rejection = json.loads(rejected)
        assert rejection["code"] == "scope_not_allowed"
        assert "本次 input" in rejection["next_action"]
        assert "read_interview" in rejection["next_action"]
        assert await candidates.read(scope) == before

        created = await call(
            "create_jd_item",
            {
                "item": {
                    "kind": "responsibility_area",
                    "title": "盤點",
                    "scope_text": "月底庫存盤點",
                    "supporting_sources": [{"kind": "interview", "interview_sequence": 2}],
                }
            },
        )
        ref = created.split("read_ref: ")[1]
        candidate = await candidates.read(scope)
        async with sessions() as session:
            sources = await source_persistence.read_source_references(
                session, file_id, candidate.position.revision_id
            )
        assert [reference.source for reference in sources] == [
            InterviewSource(UUID(accepted["source_id"]))
        ]
        assert (
            await call(
                "revise_jd_item",
                {
                    "read_ref": ref,
                    "changes": [
                        {"action": "set_field", "field": "title", "value": "月末庫存盤點"},
                    ],
                },
            )
            == "updated"
        )
        preview = await candidates.read(scope)
        assert preview.work.areas[0].title == "月末庫存盤點"
        await call(
            "create_jd_item",
            {
                "item": {
                    "kind": "responsibility_area",
                    "title": "補貨",
                    "scope_text": None,
                    "supporting_sources": [],
                }
            },
        )
        assert (
            await call(
                "move_jd_item",
                {
                    "read_ref": ref,
                    "destination": {"kind": "current_container"},
                    "position": {"kind": "last"},
                    "content_changes": [],
                },
            )
            == "moved"
        )
        assert (await candidates.read(scope)).work.areas[-1].title == "月末庫存盤點"
        assert await call("delete_jd_item", {"read_ref": ref}) == "deleted"
        assert [area.title for area in (await candidates.read(scope)).work.areas] == ["補貨"]

    client.portal.call(exercise)
    formal = client.get(f"/api/job-files/{file_id}/jd/work")
    assert formal.status_code == 200
    assert not formal.json()["areas"]


def test_cancelled_input_number_is_reused_for_the_new_original_only(client: TestClient) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "取消後重用序號",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    sessions = client.app.state.database.sessions

    async def qualify(accepted: dict[str, str]) -> tuple[ExecutionWriter, InterviewSource]:
        scope = ExecutionScope(
            file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
        )
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            source = await resolve_jd_source(
                session, PublishedMemoryRead(scope, None, 1), InterviewSourceSelection(2)
            )
        assert isinstance(source, InterviewSource)
        assert source == InterviewSource(UUID(accepted["source_id"]))
        return writer, source

    first = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "取消的原話"},
    ).json()
    writer, first_source = client.portal.call(qualify, first)
    client.portal.call(
        ConsultantCompletionWorkflow(sessions).stop, writer, ExecutionStatus.CANCELLED
    )
    second = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "新輪原話"},
    ).json()
    _, second_source = client.portal.call(qualify, second)
    assert first_source != second_source
    assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
