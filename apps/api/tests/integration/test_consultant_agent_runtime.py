"""正式 A 使用框架 agent；原件先保存，路由投影失敗不能重送模型。"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.job_file_checkpointer import JobFilePostgresSaver
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.response_runtime import PausedResponseLoop
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.diagnostics.inspection import read_diagnostics
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.features.job_description import candidate_service, persistence, source_persistence
from caliburn.settings import ModelSettings
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from tests.fixtures.consultant_turn import start_consultant_turn
from tests.fixtures.response_loop import response_at
from tests.integration.test_consultant_process_recovery import invoke_worker
from tests.integration.test_consultant_runner_recovery import ORIGINAL_REPLY, faulting_runner

pytestmark = pytest.mark.postgres


def test_consultant_uses_standard_agent_messages_without_replacing_native_original(client):
    writer = start_consultant_turn(client)

    async def scenario():
        async with faulting_runner(client, "unused-channel") as (runner, calls):
            result = await runner.run(writer)
            assert isinstance(result, FormalInterviewExchange)
            assert result.consultant_reply.interview_text == ORIGINAL_REPLY
            saved = [row async for row in runner.checkpointer.alist(None)]
            agent = [row for row in saved if row.checkpoint["channel_values"].get("messages")]
            assert agent, "A must use the standard agent message/recovery topology"
            assert any(
                row.checkpoint["channel_values"].get("response_snapshot", {}).get("output")
                for row in agent
            ), "Routing messages cannot replace the complete native R"
            assert all(
                not row.checkpoint["channel_values"].get("response_snapshot")
                for row in saved
                if row.config["configurable"].get("checkpoint_ns")
            ), "Capacity/tool children must not copy the raw R"
            assert all(
                not call["args"]
                for row in agent
                for message in row.checkpoint["channel_values"]["messages"]
                for call in getattr(message, "tool_calls", [])
            ), "Routing messages need no duplicate native arguments"
            assert calls == ["/v1/responses/input_tokens", "/v1/responses"]

    client.portal.call(scenario)


def test_environment_tracing_is_explicitly_disabled_for_the_entire_turn(client, monkeypatch):
    import requests
    from langchain_core.runnables import RunnableLambda
    from langchain_core.tracers.langchain import wait_for_all_tracers
    from langsmith import tracing_context

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-not-a-real-key")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://trace.example.invalid")
    outbound = []

    def observe(session, method, url, **kwargs):
        outbound.append(url)
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        return response

    monkeypatch.setattr(requests.Session, "request", observe)
    writer = start_consultant_turn(client)

    async def scenario():
        # 正控制證明同一殼層環境確實能啟用 framework tracing，全部由 spy 截住。
        with tracing_context(enabled=True):
            await RunnableLambda(lambda value: value).ainvoke("synthetic trace canary")
        wait_for_all_tracers()
        assert outbound
        outbound.clear()
        async with faulting_runner(client, "unused-channel") as (runner, calls):
            assert isinstance(await runner.run(writer), FormalInterviewExchange)
        wait_for_all_tracers()
        assert outbound == []

    client.portal.call(scenario)


def test_background_roles_disable_environment_tracing(
    database_settings, database_connection, monkeypatch
):
    import requests
    from langchain_core.tracers.langchain import wait_for_all_tracers

    from tests.integration.test_memory_analysis_runners import (
        test_b1_b2_publish_preserves_role_boundaries_native_history_and_fixed_frontier,
    )

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-not-a-real-key")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://trace.example.invalid")
    outbound = []

    def observe(*args, **kwargs):
        outbound.append(args)
        raise AssertionError("Background analysis must not send tracing data")

    monkeypatch.setattr(requests.Session, "request", observe)
    test_b1_b2_publish_preserves_role_boundaries_native_history_and_fixed_frontier(
        database_settings,
        database_connection,
        500,
        False,
        None,
        monkeypatch,
    )
    wait_for_all_tracers()
    assert outbound == []


def test_raw_response_survives_projection_hard_exit_without_resending_model(
    client, database_settings
):
    writer = start_consultant_turn(client)
    crashed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "tests.fixtures.native_agent_worker",
            "projection",
            database_settings.schema,
            str(writer.scope.job_file_id),
            str(writer.scope.execution_id),
            str(writer.writer_id),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert crashed.returncode == 19, crashed.stderr
    first = [json.loads(line) for line in crashed.stdout.splitlines()]
    assert first[-1] == {"event": "crash", "boundary": "projection"}
    assert [(e["kind"], e["step"]) for e in first if e["event"] == "request"] == [
        ("count", 1),
        ("model", 1),
    ]
    documents = client.portal.call(
        lambda: read_diagnostics(
            database_settings, execution_id=writer.scope.execution_id, full=True
        )
    )
    assert len(documents[0]["steps"]) == 1
    raw = documents[0]["steps"][0]["response"]
    assert raw["id"] == "response_1"
    assert raw["output"][0]["encrypted_content"] == "[redacted]"
    assert raw["output"][0]["provider_extension"] == {"must_survive": True}
    resumed = invoke_worker("resume", database_settings, writer)
    assert resumed.returncode == 0, resumed.stderr
    second = [json.loads(line) for line in resumed.stdout.splitlines()]
    assert [(e["kind"], e["step"]) for e in second if e["event"] == "request"] == [
        ("count", 2),
        ("model", 2),
    ]
    tools = client.get(
        f"/api/job-files/{writer.scope.job_file_id}/consultant-turns/{writer.scope.execution_id}/tools"
    )
    assert tools.status_code == 200, tools.text
    assert [(call["name"], call["output"]) for call in tools.json()["calls"]] == [
        ("revise_jd_profile", "updated")
    ]


@pytest.mark.parametrize("control", ["complete", "resume", "cancel"])
def test_consultant_task_sources_stay_reviewed_across_linking_pause_and_reopen(
    client, database_settings, control, record_property
):
    writer = start_consultant_turn(client)
    sessions = client.app.state.database.sessions
    requests = []
    reviewed = []

    async def scenario():
        async def respond(request):
            if request.url.path.endswith("/input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 500}
                )
            payload = json.loads(request.content)
            requests.append(payload)
            step = len(requests)
            outputs = [
                item["output"]
                for item in payload["input"]
                if item.get("type") == "function_call_output"
            ]
            if step == 1:
                name, arguments = (
                    "create_jd_item",
                    {
                        "item": {
                            "kind": "skill",
                            "name": "頁面實作",
                            "description": "元件化交付",
                            "supporting_sources": [],
                        }
                    },
                )
            elif step == 2:
                assert outputs[-1].startswith("created · read_ref: skill_")
                name, arguments = (
                    "create_jd_task",
                    {
                        "parent_read_ref": None,
                        "title": "網站交付",
                        "description": "實作頁面",
                        "outcomes": [{"text": "可驗收頁面"}],
                        "requirements": [],
                        "required_knowledge": [],
                        "required_skills": [],
                        "supporting_sources": [{"kind": "interview", "interview_sequence": 2}],
                    },
                )
            elif step == 3:
                assert outputs[-1].startswith("created · read_ref: task_")
                name, arguments = (
                    "revise_jd_item",
                    {
                        "read_ref": outputs[-1].split("read_ref: ")[1],
                        "changes": [
                            {
                                "action": "set_capability",
                                "relationship": "link",
                                "capability_read_ref": outputs[-2].split("read_ref: ")[1],
                            }
                        ],
                    },
                )
            else:
                assert step == 4 and outputs[-1] == "updated"
                async with sessions.begin() as session:
                    preview = await candidate_service.read_preview(
                        session, writer.scope.job_file_id, writer.scope.execution_id
                    )
                    refs = await source_persistence.read_source_references(
                        session, writer.scope.job_file_id, preview.position.revision_id
                    )
                    assert len(refs) == 1 and not refs[0].needs_review
                    assert refs[0].reviewed_revision_id == preview.position.revision_id
                    assert len(preview.work.task_links) == 1
                    reviewed.append((preview.position, refs))
                    if control != "complete":
                        await executions.request_pause(session, writer.scope)
            raw = response_at(step, final=step == 4, tools=int(step < 4)).model_dump(mode="json")
            raw["service_tier"] = "default"
            if step < 4:
                raw["output"][-1].update(name=name, arguments=json.dumps(arguments))
            return httpx2.Response(200, json=raw)

        sdk = create_responses_client(
            api_key="synthetic-not-a-real-key",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as native:
                await native.setup()
                runner = ConsultantRunner(
                    sessions, JobFilePostgresSaver(native), sdk, ModelSettings(api_key="synthetic")
                )
                result = await runner.run(writer)
                assert len(requests) == 4
                position, refs = reviewed[0]
                if control == "complete":
                    assert isinstance(result, FormalInterviewExchange)
                else:
                    assert isinstance(result, PausedResponseLoop)
                    async with sessions() as session:
                        formal = await persistence.read_document(session, writer.scope.job_file_id)
                        assert formal.current_revision_id == position.base_revision_id
            # 新 saver 連線仍讀原中斷、原結果及 JD 核對基準。
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as reopened:
                runner = replace(runner, checkpointer=JobFilePostgresSaver(reopened))
                if control == "resume":
                    async with sessions.begin() as session:
                        await executions.resume_execution(session, writer)
                    result = await runner.run(writer, resume_interrupt_id=result.interrupt_id)
                    assert isinstance(result, FormalInterviewExchange)
                elif control == "cancel":
                    await ConsultantCompletionWorkflow(sessions).stop(
                        writer, ExecutionStatus.CANCELLED
                    )
                    with pytest.raises(ExecutionStateError):
                        await runner.run(writer)
                else:
                    assert await runner.run(writer) == result
                assert len(requests) == 4
                async with sessions() as session:
                    formal = await persistence.read_document(session, writer.scope.job_file_id)
                    assert formal.current_revision_id == (
                        position.base_revision_id if control == "cancel" else position.revision_id
                    )
                    assert (
                        await source_persistence.read_source_references(
                            session, writer.scope.job_file_id, position.revision_id
                        )
                        == refs
                    )
                    formal_refs = await source_persistence.read_source_references(
                        session, writer.scope.job_file_id, formal.current_revision_id
                    )
                    assert formal_refs == (() if control == "cancel" else refs)
        finally:
            await sdk.close()

    client.portal.call(scenario)
    documents = client.portal.call(
        lambda: read_diagnostics(
            database_settings, execution_id=writer.scope.execution_id, full=True
        )
    )
    assert documents[0]["steps"]
    assert requests[0]["instructions"]
    assert {tool["name"] for tool in requests[0]["tools"]} >= {
        "create_jd_task",
        "revise_jd_item",
    }
    assert "confirm_reference_alignment" not in json.dumps(
        [
            item
            for request in requests
            for item in request["input"]
            if item.get("type") == "function_call"
        ]
    )
    record_property("reference_policy_diagnostics", json.dumps(documents, ensure_ascii=False))
