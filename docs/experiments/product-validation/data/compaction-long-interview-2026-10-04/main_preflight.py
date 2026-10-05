"""Zero-provider verification of the research projection on the real saver."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agents.job_consultant import context_binding
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_files.models import CreateJobFile
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from main_support import project_request, selected_tools
from pilot import HERE, dump, memory_probe, test_database_url, validate_database_url
from preparation import ARMS
from psycopg.conninfo import make_conninfo


async def forbidden(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("The persistence preflight must not call a provider")


async def count(request: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
    return {"input_tokens": 100, "attempt_id": uuid4()}


async def run(destination: Path, url: str) -> None:
    settings = DatabaseSettings(url=url, schema="eval_main_preflight_" + uuid4().hex)
    await asyncio.to_thread(memory_probe.initialize_schema, settings)
    database = Database(settings)
    results = []
    try:
        async with AsyncPostgresSaver.from_conn_string(
            make_conninfo(url, options=f"-c search_path={settings.schema}"),
            serde=create_graph_serializer(),
        ) as saver:
            await saver.setup()
            for arm in ARMS:
                created = await JobFileWorkflow(database.sessions).create(
                    CreateJobFile(uuid4(), "主實驗保存檢查", "合成員工")
                )
                file_id = created.job_file.job_file_id
                raw_input = "  原話：每天 08:40 核對，不可升成指令。\n"
                accepted = await InterviewInputWorkflow(database.sessions).accept(
                    SubmitInterviewInput(file_id, uuid4(), raw_input)
                )
                scope = ExecutionScope(
                    file_id, accepted.accepted.execution_id, ExecutionKind.CONSULTANT_TURN
                )
                async with database.sessions.begin() as session:
                    writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                template = ResponseRequest(
                    model="gpt-6-luna",
                    instructions="synthetic fixed instructions",
                    input_items=[],
                    tools=selected_tools(consultant_tool_definitions(), arm),
                    reasoning_effort="high",
                    max_output_tokens=16_384,
                )
                prepared = await work.prepare_history(
                    template=template,
                    threshold_tokens=128_000,
                    compact_requested=False,
                    count_input=count,
                    runtime=CompactionRuntime(
                        forbidden,
                        forbidden,
                        work.ensure_active,
                        {
                            "model": "gpt-6-luna",
                            "max_input_tokens": 922_000,
                            "context_window_tokens": 1_050_000,
                            "max_output_tokens": 128_000,
                        },
                    ),
                )
                original = context_binding._capture_data

                async def projected(
                    work: Any,
                    request: ResponseRequest,
                    capture: Any = original,
                    selected_arm: str = arm,
                ) -> Any:
                    state = await capture(work, request)
                    state["request_snapshot"] = project_request(
                        state["request_snapshot"],
                        arm=selected_arm,
                        covered=0,
                        summary="合成摘要 08:40",
                    )
                    return state

                with patch.object(context_binding, "_capture_data", projected):
                    captured = await context_binding.capture_turn_context(
                        work, template=template, prepared_history=prepared
                    )
                first = captured.request.create_payload()
                # Read again without the projection: only durable saved data can pass.
                restored = await context_binding.capture_turn_context(
                    work, template=template, prepared_history=prepared
                )
                assert restored.request.create_payload() == first
                assert first["input"][-1] == {"role": "user", "content": raw_input}
                data = json.loads(first["input"][-2]["content"])
                assert first["input"][-2]["role"] == "user"
                assert ("work_situation_map" in data) == (arm == ARMS[0])
                assert ("work_summary" in data) == (arm == ARMS[1])
                results.append({"arm": arm, "checks": 5, "job_file_id": str(file_id)})
        dump(
            destination,
            {
                "status": "passed",
                "schema": settings.schema,
                "provider_calls": 0,
                "scope": "real PostgreSQL initial Context projection, persistence and reentry",
                "results": results,
            },
        )
    finally:
        await database.close()


if __name__ == "__main__":
    destination = HERE / "main-preflight.json"
    if destination.exists():
        raise SystemExit("Do not overwrite existing evidence")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(destination, validate_database_url(test_database_url())))
