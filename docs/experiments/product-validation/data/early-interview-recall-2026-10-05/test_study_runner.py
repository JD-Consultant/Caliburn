"""Real database/checkpoints/tools; scripted SDK responses are not quality evidence."""

import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx2
import pytest
from baseline_store import seed_baseline
from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.executions.persistence import ExecutionRecord
from caliburn.features.interviews.persistence import list_formal_interviews
from caliburn.features.job_description import queries, source_persistence
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import JdChangesWorkflow
from caliburn.workflows.memory_reads import MemoryReadWorkflow
from caliburn.workflows.model_requests import ModelRequestFailedError
from jd_workspace import begin_turn
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from memory_fixture import read_memory_fixture, seed_memory
from psycopg.conninfo import make_conninfo
from sqlalchemy import select
from study_runner import StudyCapacityError, StudyRunner
from study_tools import StudyTools
from tests.unit.test_response_loop import response_at

pytest_plugins = ("tests.integration.conftest",)
pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("arm", ["raw", "summary", "memory"])
def test_two_turns_reopen_native_history_and_save_real_jd(database_settings, arm):
    requests = []
    replies = []
    history_counts = []

    def respond(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            history_counts.append(payload)
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 900}
            )
        assert request.url.path.endswith("/responses"), "No pre-work compact is allowed"
        requests.append(payload)
        index = len(requests)
        raw = response_at(index, final=index % 2 == 0, tools=index % 2).model_dump(mode="json")
        raw["model"] = "gpt-6-luna"
        raw["service_tier"] = "default"
        if index % 2:
            raw["output"][-1].update(
                name="revise_jd_profile",
                arguments=json.dumps(
                    {
                        "changes": [
                            {
                                "action": "set_field",
                                "field": "job_title",
                                "value": f"合成接續{index}",
                            },
                            {
                                "action": "add_source",
                                "field": "job_title",
                                "source": {"kind": "current_input"},
                            },
                        ]
                    }
                ),
            )
        else:
            raw["output"][1]["content"][0]["text"] = f"合成正式回答{index}"
        replies.append(raw)
        return httpx2.Response(200, json=raw)

    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            snapshot_id = await seed_memory(database, file_id) if arm == "memory" else None
            settings = ModelSettings(
                api_key="synthetic", model="gpt-6-luna", reasoning_effort="high"
            )
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            exchanges = []
            for ordinal in (1, 2):
                # Reopen both clients: the second Turn cannot rely on an in-memory list.
                async with AsyncPostgresSaver.from_conn_string(
                    dsn, serde=create_graph_serializer()
                ) as saver:
                    await saver.setup()
                    async with create_responses_client(
                        api_key="synthetic-not-a-real-key",
                        timeout_seconds=5,
                        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
                    ) as client:
                        runner = StudyRunner(database, saver, client, settings, "合成共用指引")
                        exchanges.append(
                            await runner.run(
                                file_id,
                                arm=arm,
                                snapshot_id=snapshot_id,
                                employee_input=f"合成當次輸入{ordinal}",
                            )
                        )
                async with database.sessions() as session:
                    profile = await queries.read_profile(session, file_id)
                    assert profile.profile.job_title == f"合成接續{ordinal * 2 - 1}"
                    refs = await source_persistence.read_source_references(
                        session, file_id, profile.revision_id
                    )
                    assert any(
                        r.source.source_id == exchanges[-1].employee_input.source_id for r in refs
                    )
            assert [e.employee_input.interview_sequence for e in exchanges] == [106, 108]
            assert [e.consultant_reply.interview_sequence for e in exchanges] == [107, 109]
            assert len(requests) == 4
            assert requests[0]["input"][-1]["content"] == "合成當次輸入1"
            assert requests[2]["input"][-1]["content"] == "合成當次輸入2"
            # Response-only status is omitted on replay; every other field must survive.
            replay_outputs = [
                [{k: v for k, v in item.items() if k != "status"} for item in reply["output"]]
                for reply in replies
            ]
            expected_prefix = [*requests[1]["input"], *replay_outputs[1]]
            assert requests[2]["input"][: len(expected_prefix)] == expected_prefix
            assert any(p["input"] == expected_prefix for p in history_counts)
            assert requests[1]["input"][-1]["type"] == "function_call_output"
            assert requests[1]["input"][-1]["output"] == "updated"
            # Encrypted state and message phases survive the real saver and next Turn.
            assert replay_outputs[0][0] in requests[2]["input"]
            assert replay_outputs[0][1] in requests[2]["input"]
            assert replay_outputs[1][1] in requests[2]["input"]
            app = json.loads(requests[0]["input"][0]["content"])
            seqs = [m["interview_sequence"] for m in app["historical_interview"]["messages"]]
            assert seqs == (list(range(1, 106)) if arm == "raw" else [101, 102, 103, 104, 105])
            tool_names = {tool["name"] for tool in requests[0]["tools"]}
            assert "read_interview" in tool_names and "read_jd" in tool_names
            assert "request_memory_consolidation" not in tool_names
            assert "request_context_compaction" not in tool_names
            assert ("read_work_understanding" in tool_names) == (arm == "memory")
            assert ("work_summary" in app) == (arm == "summary")
            assert ("work_understanding_map" in app) == (arm == "memory")
            if arm == "memory":
                assert len(app["work_situation_map"]["items"]) == 12
                assert len(app["work_understanding_map"]["items"]) == 1
                for revision in read_memory_fixture().objects:
                    assert revision.content.body not in requests[0]["input"][0]["content"]
            # Test sentinels for future/grade data are never passed to run(), hence not loaded.
            rendered = json.dumps(requests, ensure_ascii=False)
            assert "2026-11-01" not in rendered
            assert "grading-cases.json" not in rendered
            assert "criterion_id" not in rendered
            assert requests[0]["instructions"] == requests[2]["instructions"]
            assert all(p["truncation"] == "disabled" and p["store"] is False for p in requests)
            assert all("previous_response_id" not in p for p in requests)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(exercise())


@pytest.mark.parametrize("arm", ["raw", "summary"])
def test_hidden_memory_is_rejected_even_when_snapshot_exists(database_settings, arm):
    def no_network(request):
        pytest.fail("This routing check must not dispatch even a synthetic provider request")

    async def exercise():
        async with scripted_study(database_settings, no_network) as (runner, file_id):
            await seed_memory(runner.database, file_id)
            turn = await begin_turn(runner.database, file_id, "合成工具權限檢查")
            candidate = await JdCandidateWorkflow(runner.database.sessions).read(turn.writer.scope)
            tools = StudyTools(
                turn,
                MemoryReadTools(MemoryReadWorkflow(runner.database.sessions), turn.binding),
                JdChangesTools(
                    JdChangesWorkflow(runner.database.sessions),
                    turn.binding,
                    manual_jd_start_revision_id=candidate.position.base_revision_id,
                ),
                arm,
            )
            call = response_at(1, tools=1).output[-1]
            call.name = "read_work_understanding_map"
            call.arguments = "{}"
            rejected = json.loads(await tools.prepare(call, uuid4()))
            assert rejected["status"] == "rejected"
            assert rejected["code"] == "scope_not_allowed"
            assert "items" not in rejected
            assert "read_work_understanding_map" not in {d["name"] for d in tools.definitions()}

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(exercise())


@asynccontextmanager
async def scripted_study(database_settings, respond):
    database = Database(database_settings)
    try:
        file_id = await seed_baseline(database)
        settings = ModelSettings(api_key="synthetic", model="gpt-6-luna", reasoning_effort="high")
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            async with create_responses_client(
                api_key="synthetic-not-a-real-key",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            ) as client:
                yield StudyRunner(database, saver, client, settings, "合成共用指引"), file_id
    finally:
        await database.close()


def test_in_work_compaction_adopts_whole_output_without_reappending_input(database_settings):
    requests, compactions = [], []
    output = []

    def respond(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            count = 160_000 if len(requests) == 1 and not compactions else 900
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": count}
            )
        if request.url.path.endswith("/compact"):
            compactions.append(payload)
            # Keep both user items and another item: adopting only the encrypted item must fail.
            output.extend(
                [
                    *requests[0]["input"],
                    {
                        "type": "compaction",
                        "id": "cmp_test",
                        "encrypted_content": "synthetic-compact",
                    },
                ]
            )
            return httpx2.Response(
                200,
                json={
                    "id": "cmp_response",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": output,
                    "usage": {
                        "input_tokens": 160_000,
                        "output_tokens": 100,
                        "input_tokens_details": {"cached_tokens": 0},
                        "total_tokens": 160_100,
                    },
                },
            )
        assert request.url.path.endswith("/responses")
        requests.append(payload)
        index = len(requests)
        raw = response_at(index, final=index == 2, tools=int(index == 1)).model_dump(mode="json")
        raw["service_tier"] = "default"
        if index == 1:
            raw["output"][-1].update(name="read_jd", arguments='{"view":"map","read_ref":null}')
        return httpx2.Response(200, json=raw)

    async def exercise():
        async with scripted_study(database_settings, respond) as (runner, file_id):
            await runner.run(file_id, arm="raw", employee_input="合成壓縮當次輸入")
            assert len(compactions) == 1 and len(requests) == 2
            assert requests[1]["input"] == output
            assert compactions[0]["input"][-1]["type"] == "function_call_output"
            assert json.loads(compactions[0]["input"][-1]["output"])["profile"]["job_title"]
            assert sum(i.get("content") == "合成壓縮當次輸入" for i in requests[1]["input"]) == 1
            assert requests[1]["input"][-1]["encrypted_content"] == "synthetic-compact"

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(exercise())


def test_failure_after_tool_keeps_formal_jd_and_pending_native_work(database_settings):
    requests = []

    def respond(request):
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 900}
            )
        assert request.url.path.endswith("/responses")
        requests.append(json.loads(request.content))
        if len(requests) == 2:
            return httpx2.Response(
                400,
                json={
                    "error": {
                        "message": "synthetic terminal failure",
                        "type": "invalid_request_error",
                        "code": "invalid_request_error",
                    }
                },
            )
        raw = response_at(1, tools=1).model_dump(mode="json")
        raw["service_tier"] = "default"
        raw["output"][-1].update(
            name="revise_jd_profile",
            arguments=json.dumps(
                {"changes": [{"action": "set_field", "field": "job_title", "value": "只在候選中"}]}
            ),
        )
        return httpx2.Response(200, json=raw)

    async def exercise():
        async with scripted_study(database_settings, respond) as (runner, file_id):
            async with runner.database.sessions() as session:
                before = await queries.read_profile(session, file_id)
            with pytest.raises(ModelRequestFailedError):
                await runner.run(file_id, arm="raw", employee_input="合成中途失敗")
            async with runner.database.sessions() as session:
                assert await queries.read_profile(session, file_id) == before
                assert len(await list_formal_interviews(session, file_id)) == 105
                execution = (await session.scalars(select(ExecutionRecord))).one()
                assert execution.status == "active"
                scope = ExecutionScope(
                    file_id, execution.execution_id, ExecutionKind.CONSULTANT_TURN
                )
            candidate = await JdCandidateWorkflow(runner.database.sessions).read(scope)
            assert candidate.profile.job_title == "只在候選中"
            assert len(requests) == 2
            assert requests[1]["input"][-1]["output"] == "updated"
            # Stop for diagnosis; no automatic new Turn or paid resend on this failure.
            assert len([item async for item in runner.checkpointer.alist(None, limit=1)]) == 1

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(exercise())


@pytest.mark.parametrize("stop_on_turn", [1, 2])
def test_capacity_stop_never_calls_pre_work_compaction_or_next_generation(
    database_settings, stop_on_turn
):
    requests = []
    counts = []

    def respond(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            counts.append(payload)
            tokens = 128_001 if len(requests) == stop_on_turn - 1 else 900
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": tokens}
            )
        assert request.url.path.endswith("/responses"), "No pre-work compaction permitted"
        requests.append(payload)
        raw = response_at(1, final=True).model_dump(mode="json")
        raw["service_tier"] = "default"
        return httpx2.Response(200, json=raw)

    async def exercise():
        async with scripted_study(database_settings, respond) as (runner, file_id):
            if stop_on_turn == 2:
                await runner.run(file_id, arm="raw", employee_input="先成功一次")
            with pytest.raises(StudyCapacityError):
                await runner.run(file_id, arm="raw", employee_input="容量停止不外送生成")
            assert len(requests) == stop_on_turn - 1
            async with runner.database.sessions() as session:
                assert len(await list_formal_interviews(session, file_id)) == 105 + 2 * (
                    stop_on_turn - 1
                )
            assert counts

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
        loop.run(exercise())
