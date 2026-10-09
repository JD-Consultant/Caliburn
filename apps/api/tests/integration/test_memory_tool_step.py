"""Real Memory effects recover through the native Step, without a second receipt store."""

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai.types.responses import Response, ResponseFunctionToolCall
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    _build_response_step,
)
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.memory_writes import MemoryWriteTools, PreparedMemoryToolCall
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import CandidateMemoryRead, MemoryReadWorkflow
from caliburn.workflows.memory_writes import MemoryWritePreparation
from tests.fixtures.response_capacity import synthetic_capacity_limits, synthetic_response_runtime

pytestmark = pytest.mark.postgres


async def account_response(received: ReceivedModelResponse) -> None:
    """Memory effect fixture, without execution cost persistence."""


def test_committed_first_write_recovers_original_before_dependent_second_write(
    database_settings: DatabaseSettings, database_connection: psycopg.Connection
) -> None:
    file_id, source_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'接續','接續','合成人員')",
        (file_id,),
    )
    for sequence, identity, speaker in [(1, uuid4(), "app"), (2, source_id, "employee")]:
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,'每月核對庫存')",
            (file_id, identity, speaker),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, identity),
        )

    async def scenario() -> None:
        database = Database(database_settings)
        try:
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with database.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            candidates = MemoryCandidateWorkflow(database.sessions)
            stage = await candidates.start(writer, source_id)
            assert stage is not None
            binding = CandidateMemoryRead(scope, stage)
            tools = MemoryWriteTools(
                MemoryWritePreparation(database.sessions, cpu=MemoryCpu()),
                candidates,
                binding,
                writer,
            )
            payload = json.loads(
                (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["output"] = [
                {
                    "type": "function_call",
                    "id": "fc_create",
                    "call_id": "create",
                    "name": "create_work_situation",
                    "arguments": json.dumps(
                        {
                            "title": "盤點",
                            "description": "核對庫存",
                            "body": "# 盤點\n每月核對庫存。",
                            "interview_references": [2],
                        }
                    ),
                },
                {
                    "type": "function_call",
                    "id": "fc_update",
                    "call_id": "update",
                    "name": "update_work_situation",
                    "arguments": json.dumps(
                        {
                            "target_title": "盤點",
                            "changes": [{"field": "title", "value": "月末盤點"}],
                        }
                    ),
                },
            ]
            response = Response.model_validate(payload)
            calls = []
            committed = None

            async def request(
                model_request: ResponseRequest, request_id: UUID, input_tokens: int
            ) -> ReceivedModelResponse:
                calls.append("model")
                return ReceivedModelResponse(response=response, attempt_id=uuid4())

            async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
                calls.append("prepare:" + call.call_id)
                return await tools.prepare(call.name, call.arguments, command_id=operation_id)

            async def execute(prepared: object) -> str:
                nonlocal committed
                # A downgraded/unknown deserialized value must never enter the tool owner.
                assert isinstance(prepared, PreparedMemoryToolCall)
                kind = "create" if isinstance(prepared.command, CreateMemoryObject) else "update"
                calls.append("execute:" + kind)
                if kind == "create" and committed is not None:
                    assert prepared == committed
                output = await tools.execute(prepared)
                if kind == "create" and committed is None:
                    committed = prepared
                    raise ConnectionError("synthetic acknowledgement lost after business commit")
                return output

            serde = create_graph_serializer(
                allowed_types=(
                    PreparedMemoryToolCall,
                    CreateMemoryObject,
                    ReviseMemoryObject,
                    DeleteMemoryObject,
                    MemoryBatchPosition,
                    MemoryLayer,
                    MemoryContent,
                    MemoryContentChanges,
                    ReferenceChanges,
                )
            )
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            config = {"configurable": {"thread_id": str(scope.execution_id)}}

            async def ensure_active() -> None:
                async with database.sessions.begin() as session:
                    await executions.lock_active_writer(session, writer)

            runtime = synthetic_response_runtime(
                request_model=request,
                prepare_tool=prepare,
                execute_tool=execute,
                ensure_active=ensure_active,
                account_response=account_response,
            )
            model_request = ResponseRequest(
                model="gpt-6-luna",
                instructions="synthetic",
                input_items=[],
                tools=[],
                reasoning_effort="low",
                max_output_tokens=512,
            )
            async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
                await saver.setup()
                graph = _build_response_step(saver, max_tool_calls=16)
                with pytest.raises(ConnectionError, match="after business commit"):
                    await graph.ainvoke(
                        {
                            "request_snapshot": model_request.create_payload(),
                            "model_step_limit": None,
                            "tool_call_limit": 16,
                            "capacity_limits": synthetic_capacity_limits(),
                            "request_id": uuid4(),
                        },
                        config,
                        context=runtime,
                        durability="sync",
                    )
                assert (await graph.aget_state(config)).next == ("execute_tool",)
                assert len(await candidates.read_map(scope, stage=stage, layer=stage.phase)) == 1
            async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
                result = await _build_response_step(saver, max_tool_calls=16).ainvoke(
                    None, config, context=runtime, durability="sync"
                )
                assert [item["call_id"] for item in result["tool_results"]] == ["create", "update"]
            assert calls == [
                "model",
                "prepare:create",
                "execute:create",
                "execute:create",
                "prepare:update",
                "execute:update",
            ]
            current = await MemoryReadWorkflow(database.sessions).read_object(
                binding, stage.phase, "月末盤點"
            )
            assert current.interview_references == (2,)
            assert current.content.body == "# 盤點\n每月核對庫存。"
            assert await candidates.read_latest_snapshot(file_id) is None
            # Start + create + revise, not a second create; no new ledger added for the test.
            assert database_connection.execute(
                "SELECT count(*) FROM memory_operations WHERE job_file_id=%s", (file_id,)
            ).fetchone() == (3,)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
