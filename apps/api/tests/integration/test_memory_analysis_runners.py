"""Synthetic SDK + real PostgreSQL candidate/checkpoints; no provider acceptance claim."""

import asyncio
import json
from decimal import Decimal
from uuid import uuid4

import httpx2
import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.tool_steps import (
    ResponseStepSaveError,
    read_completed_response_history,
)
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import budgets, history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.memory_analysis.results import AnalysisComplete
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import CandidateMemoryRead, MemoryReadWorkflow
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("after_tool_tokens", "recover_first_response", "max_cost_usd"),
    [
        (159_999, False, Decimal("1.00")),
        (160_000, False, Decimal("1.00")),
        (159_999, True, Decimal("1.00")),
        (500, False, Decimal("0.02")),
        (500, False, None),
    ],
)
def test_b1_b2_publish_preserves_role_boundaries_native_history_and_fixed_frontier(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    after_tool_tokens: int,
    recover_first_response: bool,
    max_cost_usd: Decimal | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id, source_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'B roles','B roles','synthetic')",
        (file_id, uuid4()),
    )
    for sequence, identity, speaker, text in [
        (1, uuid4(), "app", "你實際做什麼？"),
        (2, source_id, "employee", "案例A核對庫存；案例B月底維護。本人不核准。"),
        (3, uuid4(), "consultant", "LATE_AFTER_FIXED_F"),
        (4, uuid4(), "employee", "LATE_AFTER_FIXED_F"),
    ]:
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,%s)",
            (file_id, identity, speaker, text),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, identity),
        )
    sent, paths, compactions = [], [], []

    def call(name, arguments, number):
        return {
            "type": "function_call",
            "id": f"fc_{number}",
            "call_id": f"call_{number}",
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        }

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            after_tool = any(
                item.get("type") == "function_call_output" for item in payload["input"]
            )
            compacted = any(item.get("type") == "compaction" for item in payload["input"])
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": after_tool_tokens if after_tool and not compacted else 500,
                },
            )
        if request.url.path.endswith("/compact"):
            compactions.append(payload)
            return httpx2.Response(
                200,
                json={
                    "id": f"cmp_{len(compactions)}",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": [
                        {
                            "type": "compaction",
                            "id": f"cmp_item_{len(compactions)}",
                            "encrypted_content": "opaque-synthetic",
                        },
                        *payload["input"],
                    ],
                    "usage": {
                        "input_tokens": after_tool_tokens,
                        "output_tokens": 100,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                        "total_tokens": after_tool_tokens + 100,
                    },
                },
            )
        assert request.url.path.endswith("/responses")
        sent.append(payload)
        step = len(sent)
        assert 1 <= step <= 4, "Saved role results must not resend model requests"
        raw = response_at(step, final=step in (2, 4), tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        if step == 1:
            raw["output"] += [
                call(
                    "create_work_situation",
                    {
                        "title": title,
                        "description": "工作案例",
                        "body": title + "原有工作",
                        "interview_references": [2],
                    },
                    title,
                )
                for title in ("案例A", "案例B")
            ]
            raw["output"] += [
                call("read_work_situation_map", {}, "map"),
                call("read_work_understanding", {"target_title": "PRIVATE_B2"}, "forbidden"),
                call("read_interview", {"query": {"kind": "messages", "sequences": [3]}}, "late"),
            ]
        elif step == 3:
            raw["output"] += [
                call(
                    "create_work_understanding",
                    {
                        "title": "PRIVATE_B2",
                        "description": "PRIVATE_B2",
                        "body": "PRIVATE_B2 工作理解",
                        "work_situation_references": ["案例A"],
                    },
                    "understanding",
                ),
                call(
                    "update_work_situation",
                    {"target_title": "案例B", "changes": [{"field": "title", "value": "不應修改"}]},
                    "forbidden-b2",
                ),
            ]
        else:
            raw["output"][1]["content"][0]["text"] = '{"status":"complete"}'
        return httpx2.Response(200, json=raw)

    async def scenario() -> None:
        database = Database(database_settings)
        sdk = create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        try:
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with database.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            candidates = MemoryCandidateWorkflow(database.sessions)
            stage = await candidates.start(writer, source_id)
            assert stage is not None
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
            ) as saver:
                await saver.setup()
                b1 = WorkSituationAnalystRunner(
                    database.sessions,
                    saver,
                    sdk,
                    ModelSettings(api_key="synthetic", max_cost_usd=max_cost_usd),
                )
                b2 = WorkUnderstandingAnalystRunner(
                    database.sessions,
                    saver,
                    sdk,
                    ModelSettings(api_key="synthetic", max_cost_usd=max_cost_usd),
                )
                if recover_first_response:
                    original_put, original_writes = saver.aput, saver.aput_writes

                    async def fail_put(config, checkpoint, metadata, new_versions):
                        if checkpoint["channel_values"].get("response_snapshot"):
                            raise psycopg.errors.UndefinedTable("synthetic local result-save fault")
                        return await original_put(config, checkpoint, metadata, new_versions)

                    async def fail_writes(config, writes, task_id, task_path=""):
                        if any(name == "response_snapshot" for name, _ in writes):
                            raise psycopg.errors.UndefinedTable("synthetic local result-save fault")
                        return await original_writes(config, writes, task_id, task_path)

                    with monkeypatch.context() as fault:
                        fault.setattr(saver, "aput", fail_put)
                        fault.setattr(saver, "aput_writes", fail_writes)
                        with pytest.raises(ResponseStepSaveError) as failed:
                            await b1.run(writer, stage)
                    assert len(sent) == 1
                    first = await b1.run(writer, stage, recovery=failed.value.recovery)
                else:
                    first = await b1.run(writer, stage)
                assert isinstance(first.outcome, AnalysisComplete)
                assert first.stage.phase == MemoryLayer.WORK_SITUATION
                requests_before_reentry = len(paths)
                assert await b1.run(writer, stage) == first
                assert len(paths) == requests_before_reentry
                assert len(sent) == 2
                async with database.sessions() as session:
                    prepared_b1 = await history.read_context_history(
                        session, scope, AgentRole.WORK_SITUATION_ANALYST
                    )
                    budget_before = await budgets.read_execution_budget(session, scope)
                stage2 = await candidates.handoff(writer, first.stage, uuid4())
                assert stage2.phase == MemoryLayer.WORK_UNDERSTANDING
                assert stage2.generation_id == first.stage.generation_id
                second = await b2.run(
                    writer,
                    stage2,
                    situation_changes=[
                        {"kind": "added", "target_title": "案例A"},
                        {"kind": "added", "target_title": "案例B"},
                    ],
                )
                assert isinstance(second.outcome, AnalysisComplete)
                assert second.stage.phase == MemoryLayer.WORK_UNDERSTANDING
                requests_before_reentry = len(paths)
                assert await b2.run(writer, stage2, situation_changes=[]) == second
                assert len(paths) == requests_before_reentry
                assert len(sent) == 4
                assert first.history_position.thread_id != second.history_position.thread_id
                for result, request_index in [(first, 0), (second, 2)]:
                    window = await read_completed_response_history(
                        saver,
                        thread_id=result.history_position.thread_id,
                        checkpoint_id=result.history_position.checkpoint_id,
                    )
                    initial_items = sent[request_index]["input"]
                    continued_items = sent[request_index + 1]["input"]
                    prefix = 1 if after_tool_tokens == 160_000 else 0
                    assert continued_items[prefix : prefix + len(initial_items)] == initial_items
                    assert window.items[: len(continued_items)] == continued_items
                    tool_step = request_index + 1
                    reasoning = next(
                        item
                        for item in continued_items
                        if item.get("id") == f"reasoning_{tool_step}"
                    )
                    assert reasoning["encrypted_content"] == f"synthetic-opaque-{tool_step}"
                    assert reasoning["provider_extension"] == {"must_survive": True}
                    assert (
                        next(
                            item
                            for item in continued_items
                            if item.get("id") == f"message_{tool_step}"
                        )["phase"]
                        == "commentary"
                    )
                    assert [
                        item["call_id"]
                        for item in continued_items
                        if item.get("type") == "function_call_output"
                    ] == [
                        item["call_id"]
                        for item in continued_items
                        if item.get("type") == "function_call"
                    ]
                    assert window.items[-1]["phase"] == "final_answer"
                    assert json.loads(window.items[-1]["content"][0]["text"]) == {
                        "status": "complete"
                    }
                    assert (
                        sum(
                            "memory_analysis_input" in str(item.get("content", ""))
                            for item in window.items
                        )
                        == 1
                    )
                async with database.sessions() as session:
                    assert (
                        await history.read_context_history(
                            session, scope, AgentRole.WORK_SITUATION_ANALYST
                        )
                        == prepared_b1
                    )
                    assert await budgets.read_execution_budget(session, scope) == budget_before
                    assert (
                        await executions.read_execution(session, scope)
                    ).status == ExecutionStatus.ACTIVE
                reader = MemoryReadWorkflow(database.sessions)
                binding = CandidateMemoryRead(scope, second.stage)
                items = await reader.read_map(binding, MemoryLayer.WORK_SITUATION)
                assert sorted((item.title, item.description) for item in items) == [
                    ("案例A", "工作案例"),
                    ("案例B", "工作案例"),
                ]
                assert (
                    await reader.read_object(binding, MemoryLayer.WORK_UNDERSTANDING, "PRIVATE_B2")
                ).content.body == "PRIVATE_B2 工作理解"
                published = await candidates.publish(writer, second.stage, uuid4())
                assert published.through_source_id == source_id
                assert published.covered_through_sequence == 2
                assert await candidates.read_latest_snapshot(file_id) == published
                assert (
                    await candidates.read_snapshot_map(
                        file_id, published.snapshot_id, MemoryLayer.WORK_SITUATION
                    )
                    == items
                )
                assert [
                    item.title
                    for item in await candidates.read_snapshot_map(
                        file_id, published.snapshot_id, MemoryLayer.WORK_UNDERSTANDING
                    )
                ] == ["PRIVATE_B2"]
                async with database.sessions() as session:
                    assert (
                        await executions.read_execution(session, scope)
                    ).status == ExecutionStatus.COMPLETED
        finally:
            await sdk.close()
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
    assert len(compactions) == (2 if after_tool_tokens == 160_000 else 0)
    assert "LATE_AFTER_FIXED_F" not in json.dumps(sent, ensure_ascii=False)
    initial = json.loads(sent[0]["input"][0]["content"])
    assert initial["required_interview_range"] == {"start_sequence": 1, "end_sequence": 2}
    assert [item["interview_sequence"] for item in initial["historical_interview"]["messages"]] == [
        1,
        2,
    ]
    assert "work_understanding_map" not in initial
    understanding_input = json.loads(sent[2]["input"][0]["content"])
    assert {
        item["target_title"] for item in understanding_input["work_situation_map"]["items"]
    } == {"案例A", "案例B"}
    assert len(understanding_input["work_situation_changes"]) == 2
    for index in (0, 1):
        payload = sent[index]
        names = {tool["name"] for tool in payload["tools"]}
        assert "read_work_understanding_map" not in names
        assert "read_work_understanding" not in names
        assert "create_work_understanding" not in names
        # A forbidden call's model-selected title may persist, but no private body arrives.
        assert "PRIVATE_B2 工作理解" not in json.dumps(payload, ensure_ascii=False)
    for index in (2, 3):
        names = {tool["name"] for tool in sent[index]["tools"]}
        assert "create_work_situation" not in names
        assert "update_work_situation" not in names
        assert "delete_work_situation" not in names
    for request_index, call_id in [(1, "call_forbidden"), (3, "call_forbidden-b2")]:
        observation = next(
            item["output"]
            for item in sent[request_index]["input"]
            if item.get("type") == "function_call_output" and item["call_id"] == call_id
        )
        assert "scope_not_allowed" in observation
    late_observation = next(
        item["output"]
        for item in sent[1]["input"]
        if item.get("type") == "function_call_output" and item["call_id"] == "call_late"
    )
    assert "source_not_available" in late_observation or "scope_not_allowed" in late_observation
