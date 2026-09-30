"""Native PostgreSQL history projects public commentary, never private response records."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.settings import DatabaseSettings
from caliburn.transport.http.consultant_turns import get_consultant_status_workflow
from caliburn.workflows.consultant_status import ConsultantStatusWorkflow
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_reopened_native_history_exposes_only_public_commentary_in_original_order(
    client: TestClient,
    database_settings: DatabaseSettings,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "公開投影",
                "employee_name": "合成人",
            },
        ).json()["job_file_id"]
    )

    async def accept() -> ExecutionScope:
        result = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "原輸入不代表正式訪談")
        )
        return ExecutionScope(file_id, result.accepted.execution_id, ExecutionKind.CONSULTANT_TURN)

    scope = client.portal.call(accept)
    dsn = make_conninfo(database_settings.url, options=f"-c search_path={database_settings.schema}")

    def snapshot(index: int, *, final: bool = False) -> dict:
        raw = response_at(index, final=final, tools=1).model_dump(mode="json")
        raw["metadata"] = {"private": "PRIVATE_METADATA"}
        raw["output"][1]["content"][0].update(
            text=f"公開訊息 {index}", private="PRIVATE_ANNOTATION"
        )
        raw["output"][-1]["arguments"] = "PRIVATE_TOOL_ARGUMENTS"
        return raw

    async def save_originals() -> None:
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            config = {
                "configurable": {
                    "thread_id": context_thread_id(
                        scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
                    ),
                    "checkpoint_ns": "",
                }
            }
            # Old snapshots persist even when compaction clears the current window.
            for index, raw in enumerate((snapshot(1), snapshot(1), {}, snapshot(2, final=True))):
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "response_snapshot": raw,
                    "input_items": snapshot(99)["output"],
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
            await saver.aput_writes(
                config, [("response_snapshot", snapshot(3))], "original-model-result"
            )

    client.portal.call(save_originals)
    with client.portal.wrap_async_context_manager(
        AsyncPostgresSaver.from_conn_string(dsn, serde=create_graph_serializer())
    ) as reopened:
        workflow = ConsultantStatusWorkflow(client.app.state.database.sessions, reopened)
        client.app.dependency_overrides[get_consultant_status_workflow] = lambda: workflow
        response = client.get(f"/api/job-files/{file_id}/consultant-turns/{scope.execution_id}")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["commentary"] == [
            {"response_id": "response_1", "message_id": "message_1", "text": "公開訊息 1"},
            {"response_id": "response_3", "message_id": "message_3", "text": "公開訊息 3"},
        ]
        assert set(response.json()) == {
            "job_file_id",
            "execution_id",
            "status",
            "pause_requested",
            "input_text",
            "allowed_controls",
            "candidate",
            "commentary",
        }
        assert response.json()["pause_requested"] is False
        assert response.json()["candidate"] is None
        for private in (
            "PRIVATE_",
            "synthetic-opaque",
            "公開訊息 99",
            "公開訊息 2",
            "interview_sequence",
            "source_id",
        ):
            assert private not in response.text
        missing = client.get(f"/api/job-files/{uuid4()}/consultant-turns/{scope.execution_id}")
        assert missing.status_code == 404
        assert "公開訊息" not in missing.text
        assert len(client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]) == 1
