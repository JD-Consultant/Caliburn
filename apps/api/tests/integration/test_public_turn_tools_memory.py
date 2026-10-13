"""Public read-only evidence comes from originals and fixed published snapshots."""

from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


def tools_url(turn):
    scope = turn.writer.scope
    return f"/api/job-files/{scope.job_file_id}/consultant-turns/{scope.execution_id}/tools"


def save_tools(connection, turn):
    saver = PostgresSaver(connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    request_id = uuid4()
    values = {
        "request_id": request_id,
        "request_snapshot": {"instructions": "PRIVATE PROMPT", "input": ["PRIVATE CONTEXT"]},
        "response_snapshot": {
            "id": "resp_test",
            "output": [
                {"type": "reasoning", "encrypted_content": "PRIVATE OPAQUE"},
                *[
                    {"type": "function_call", "call_id": call, "name": "read_jd", "arguments": "{}"}
                    for call in ("empty", "failed", "missing")
                ],
            ],
        },
        "operation_seed": uuid4(),
    }
    checkpoint["channel_values"] = values
    checkpoint["channel_versions"] = {key: 1 for key in values}
    config = saver.put(
        {"configurable": {"thread_id": turn.completed.thread_id, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )
    saver.put_writes(
        config,
        [
            (
                "tool_results",
                [
                    {"call_id": "empty", "output": ""},
                    {"call_id": "failed", "output": "拒絕：來源不存在"},
                ],
            )
        ],
        "own-tool-task",
    )
    return request_id


def test_completed_tools_keep_order_empty_failure_and_missing_without_context(
    client, database_connection
):
    turn = start_turn(client)
    request_id = save_tools(database_connection, turn)
    complete(client, turn)
    response = client.get(tools_url(turn))
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()
    assert payload["execution_id"] == str(turn.writer.scope.execution_id)
    assert [call["call_id"] for call in payload["calls"]] == ["empty", "failed", "missing"]
    assert [call["output"] for call in payload["calls"]] == ["", "拒絕：來源不存在", None]
    assert [call["result_state"] for call in payload["calls"]] == [
        "recorded",
        "recorded",
        "not_recorded",
    ]
    assert payload["calls"][0]["request_id"] == str(request_id)
    assert "PRIVATE" not in response.text
    assert "receipt" not in response.text
    assert client.get(tools_url(turn)).json() == payload


@pytest.mark.parametrize(
    "status", [None, ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED]
)
def test_tools_require_completed_turn(client, status):
    turn = start_turn(client)
    if status == ExecutionStatus.PAUSED:
        transact(client, lambda session: executions.pause_execution(session, turn.writer))
    elif status is not None:
        workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
        client.portal.call(workflow.stop, turn.writer, status)
    assert client.get(tools_url(turn)).status_code == 409


def test_tools_scope_and_arguments_and_no_observations(client):
    turn = start_turn(client)
    complete(client, turn)
    assert client.get(tools_url(turn)).json()["calls"] == []
    foreign = tools_url(turn).replace(str(turn.writer.scope.job_file_id), str(uuid4()))
    assert client.get(foreign).status_code == 404
    assert client.get(tools_url(turn) + "?full=true").status_code == 422
    assert client.request("GET", tools_url(turn), content=b"{}").status_code == 422


def test_completed_memory_execution_cannot_be_read_as_consultant_tools(client, database_connection):
    turn = start_turn(client)
    foreign_execution = uuid4()
    database_connection.execute(
        "INSERT INTO executions(job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','completed')",
        (turn.writer.scope.job_file_id, foreign_execution),
    )
    url = tools_url(turn).replace(str(turn.writer.scope.execution_id), str(foreign_execution))
    assert client.get(url).status_code == 404


def test_memory_without_publication_is_empty_and_unknown_file_is_not_empty(client):
    turn = start_turn(client)
    url = f"/api/job-files/{turn.writer.scope.job_file_id}/memory"
    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "snapshot_id": None,
        "covered_through_sequence": 0,
        "work_situations": [],
        "work_understandings": [],
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get(f"/api/job-files/{uuid4()}/memory").status_code == 404
    assert client.get(url + "?candidate=true").status_code == 422
    assert client.request("GET", url, content=b"{}").status_code == 422


def test_memory_map_pins_body_even_after_later_publication(
    client, database_settings, database_connection
):
    from caliburn.features.work_memory import batch_persistence as batches
    from caliburn.features.work_memory.revisions import MemoryLayer
    from tests.integration.test_memory_position_storage import (
        batch_position as batch_fixture,
    )
    from tests.integration.test_memory_position_storage import (
        create_position,
        create_revision,
        execute,
        reference,
        seed_file,
    )

    window = seed_file(database_connection)
    old = create_revision(database_settings, window, "舊版")
    new = create_revision(database_settings, window, "新版")
    understanding = create_revision(
        database_settings, window, "工作理解", MemoryLayer.WORK_UNDERSTANDING
    )
    old_position = create_position(
        database_settings, window.job_file_id, (reference(old), reference(understanding))
    )
    new_position = create_position(database_settings, window.job_file_id, (reference(new),))
    batch = batch_fixture.__wrapped__(database_settings, database_connection, window)
    snapshot_id = uuid4()

    async def publish(session):
        session.add(
            batches.MemorySnapshotRecord(
                job_file_id=window.job_file_id,
                snapshot_id=snapshot_id,
                execution_id=batch.execution_id,
                position_id=old_position,
                through_source_id=window.through_source_id,
                covered_through_sequence=2,
            )
        )
        await session.flush()
        await batches.set_head(session, window.job_file_id, snapshot_id)

    execute(database_settings, publish)
    url = f"/api/job-files/{window.job_file_id}/memory"
    first = client.get(url)
    assert first.status_code == 200, first.text
    assert first.json()["snapshot_id"] == str(snapshot_id)
    assert first.json()["work_situations"][0]["object_id"] == str(old.object_id)
    assert first.json()["work_understandings"][0]["object_id"] == str(understanding.object_id)
    understanding_url = f"{url}/{snapshot_id}/objects/{understanding.object_id}"
    assert client.get(understanding_url).json() == {
        "snapshot_id": str(snapshot_id),
        "object_id": str(understanding.object_id),
        "layer": "work_understanding",
        "title": "工作理解",
        "description": "描述",
        "body": "正文",
    }
    body_url = f"{url}/{snapshot_id}/objects/{old.object_id}"
    assert client.get(body_url).json()["title"] == "舊版"
    assert client.get(body_url + "?latest=true").status_code == 422
    assert client.request("GET", body_url, content=b"{}").status_code == 422
    assert client.get(body_url.replace(str(snapshot_id), str(uuid4()))).status_code == 404
    assert client.get(f"{url}/{snapshot_id}/objects/{new.object_id}").status_code == 404
    assert client.get(body_url.replace(str(window.job_file_id), str(uuid4()))).status_code == 404
    # A different immutable publication can become current; the existing object URL stays fixed.
    later_batch = uuid4()
    database_connection.execute(
        "INSERT INTO executions(job_file_id,execution_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','completed')",
        (window.job_file_id, later_batch),
    )
    later_snapshot = uuid4()

    async def later(session):
        session.add(
            batches.MemoryBatchRecord(
                job_file_id=window.job_file_id,
                execution_id=later_batch,
                base_snapshot_id=snapshot_id,
                base_position_id=old_position,
                current_position_id=new_position,
                stage_id=uuid4(),
                phase="work_understanding",
                status="published",
                through_source_id=window.through_source_id,
                covered_through_sequence=0,
                through_sequence=2,
            )
        )
        await session.flush()
        session.add(
            batches.MemorySnapshotRecord(
                job_file_id=window.job_file_id,
                snapshot_id=later_snapshot,
                execution_id=later_batch,
                position_id=new_position,
                through_source_id=window.through_source_id,
                covered_through_sequence=2,
            )
        )
        await session.flush()
        await batches.set_head(session, window.job_file_id, later_snapshot)

    execute(database_settings, later)
    assert client.get(url).json()["snapshot_id"] == str(later_snapshot)
    assert client.get(body_url).json()["title"] == "舊版"
    assert UUID(first.json()["snapshot_id"]) == snapshot_id
