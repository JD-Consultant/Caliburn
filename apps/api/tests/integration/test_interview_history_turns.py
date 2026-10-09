"""Formal replies locate their original public Turn without exposing native context."""

from dataclasses import asdict, replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import queries
from caliburn.settings import DatabaseSettings
from caliburn.transport.http.consultant_turns import get_consultant_status_workflow
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_status import ConsultantStatusWorkflow
from tests.fixtures.response_loop import response_at
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


def test_only_formal_replies_locate_their_original_turn_after_later_work(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    exchange = complete(client, turn)
    scope = turn.writer.scope
    url = f"/api/job-files/{scope.job_file_id}/interviews"
    original = client.get(url).json()
    messages = original["messages"]
    assert [item["execution_id"] for item in messages] == [None, None, str(scope.execution_id)]
    assert messages[-1]["source_id"] == str(exchange.consultant_reply.source_id)
    assert set(messages[-1]) == {
        "source_id",
        "interview_sequence",
        "speaker",
        "interview_text",
        "execution_id",
    }

    later = start_turn(client, file_id=scope.job_file_id)
    assert client.get(url).json() == original
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(workflow.stop, later.writer, ExecutionStatus.CANCELLED)
    assert client.get(url).json() == original

    other = start_turn(client)
    complete(client, other)
    other_messages = client.get(
        f"/api/job-files/{other.writer.scope.job_file_id}/interviews"
    ).json()["messages"]
    assert other_messages[-1]["execution_id"] == str(other.writer.scope.execution_id)
    assert str(scope.execution_id) not in str(other_messages)
    assert (
        client.get(
            f"/api/job-files/{other.writer.scope.job_file_id}/consultant-turns/{scope.execution_id}"
        ).status_code
        == 404
    )
    assert client.get(f"/api/job-files/{uuid4()}/interviews").status_code == 404

    # UI navigation does not extend the shared Agent source DTO or formal eligibility.
    sources = transact(
        client, lambda session: queries.read_interview_history(session, scope.job_file_id)
    )
    assert all("execution_id" not in asdict(source) for source in sources)
    assert [source.interview_sequence for source in sources] == [1, 2, 3]


def test_completed_history_locator_reopens_saved_public_commentary_only(
    client: TestClient,
    database_settings: DatabaseSettings,
) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    dsn = make_conninfo(database_settings.url, options=f"-c search_path={database_settings.schema}")
    commentary = response_at(1, tools=1).model_dump(mode="json")
    commentary["metadata"] = {"private": "PRIVATE_METADATA"}
    commentary["output"][1]["content"][0].update(
        text="已核對主要工作，繼續整理。", private="PRIVATE_ANNOTATION"
    )
    commentary["output"][-1]["arguments"] = "PRIVATE_TOOL_ARGUMENTS"
    final = response_at(2, final=True).model_dump(mode="json")
    final["output"][1]["content"][0]["text"] = "正式答覆：請問如何驗收成果？"

    async def save_originals() -> str:
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            config: RunnableConfig = {
                "configurable": {"thread_id": turn.completed.thread_id, "checkpoint_ns": ""}
            }
            # A repeated snapshot and a cleared context window must not lose/duplicate commentary.
            for index, raw in enumerate((commentary, commentary, {}, final)):
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "response_snapshot": raw,
                    "input_items": [{"role": "user", "content": "PRIVATE_CONTEXT"}],
                }
                checkpoint["channel_versions"] = {
                    "response_snapshot": index + 1,
                    "input_items": index + 1,
                }
                config = await saver.aput(
                    config,
                    checkpoint,
                    {"source": "loop", "step": index, "parents": {}},
                    checkpoint["channel_versions"],
                )
            return config["configurable"]["checkpoint_id"]

    checkpoint_id = client.portal.call(save_originals)
    turn = replace(turn, completed=replace(turn.completed, checkpoint_id=checkpoint_id))
    complete(client, turn, reply_text="正式答覆：請問如何驗收成果？")
    history_url = f"/api/job-files/{scope.job_file_id}/interviews"
    history_before = client.get(history_url).json()
    locator = history_before["messages"][-1]["execution_id"]
    status_url = f"/api/job-files/{scope.job_file_id}/consultant-turns/{locator}"
    # Absence of a reader is explicitly unavailable, not a fabricated empty transcript.
    unavailable = ConsultantStatusWorkflow(client.app.state.database.sessions)
    client.app.dependency_overrides[get_consultant_status_workflow] = lambda: unavailable
    assert client.get(status_url).json()["commentary"] is None

    with client.portal.wrap_async_context_manager(
        AsyncPostgresSaver.from_conn_string(dsn, serde=create_graph_serializer())
    ) as reopened:
        workflow = ConsultantStatusWorkflow(client.app.state.database.sessions, reopened)
        client.app.dependency_overrides[get_consultant_status_workflow] = lambda: workflow
        response = client.get(status_url)
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["commentary"] == [
            {
                "response_id": "response_1",
                "message_id": "message_1",
                "text": "已核對主要工作，繼續整理。",
            }
        ]
        assert response.json()["candidate"] is None
        for private in (
            "PRIVATE_",
            "synthetic-opaque",
            "checkpoint",
            "thread_id",
            "正式答覆",
            "interview_sequence",
            "source_id",
        ):
            assert private not in response.text
        assert client.get(history_url).json() == history_before
