"""Actual role/parent composition against PG; synthetic SDK responses, no paid API."""

import asyncio
import json
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.memory_analysis.tools import MEMORY_CHECKPOINT_TYPES
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.work_memory import read_queries
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from tests.integration.test_memory_batch_orchestration import complete_turn, start_turn
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_actual_roles_publish_atomically_and_continue_next_batch(
    database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        assert request.url.path.endswith("/responses")
        sent.append(payload)
        step = len(sent)
        tool = None
        if step == 1:
            tool = (
                "create_work_situation",
                {
                    "title": "每月盤點",
                    "description": "核對帳物",
                    "body": "核對庫存並回報差異。",
                    "interview_references": [2],
                },
            )
        elif step == 3:
            tool = (
                "create_work_understanding",
                {
                    "title": "庫存資料維護",
                    "description": "盤點與回報",
                    "body": "維護庫存正確性。",
                    "work_situation_references": ["每月盤點"],
                },
            )
        elif step == 5:
            tool = (
                "update_work_situation",
                {
                    "target_title": "每月盤點",
                    "changes": [{"field": "description", "value": "核對帳物、主管核准"}],
                },
            )
        raw = response_at(step, final=tool is None, tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        if tool:
            raw["output"] = [
                {
                    "type": "function_call",
                    "id": f"fc_{step}",
                    "call_id": f"call_{step}",
                    "name": tool[0],
                    "arguments": json.dumps(tool[1], ensure_ascii=False),
                }
            ]
        else:
            raw["output"][1]["content"][0]["text"] = '{"status":"complete"}'
        return httpx2.Response(200, json=raw)

    async def scenario() -> None:
        database = Database(database_settings)
        client = create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        try:
            requests = MemoryConsolidationWorkflow(database.sessions)
            turn = await start_turn(database)
            await requests.request(turn, uuid4())
            await complete_turn(database, turn)
            work = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
            assert work is not None
            dsn = make_conninfo(
                database_settings.url, options=f"-c search_path={database_settings.schema}"
            )
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
            ) as saver:
                await saver.setup()
                settings = ModelSettings(api_key="synthetic")
                parent = MemoryBatchWorkflow(
                    database.sessions,
                    run_role=MemoryRoleDispatch(
                        WorkSituationAnalystRunner(database.sessions, saver, client, settings),
                        WorkUnderstandingAnalystRunner(database.sessions, saver, client, settings),
                    ),
                )
                candidates = MemoryCandidateWorkflow(database.sessions)

                async def fail_adoption(*args, **kwargs):
                    raise ConnectionError("Synthetic fault after publication SQL, before COMMIT")

                with monkeypatch.context() as fault:
                    fault.setattr(history, "complete_context_histories", fail_adoption)
                    with pytest.raises(ConnectionError, match="Synthetic fault"):
                        await parent.run(work.writer)
                assert len(sent) == 4
                assert await candidates.read_latest_snapshot(turn.scope.job_file_id) is None
                async with database.sessions() as session:
                    assert (await executions.read_execution(session, work.writer.scope)).status == (
                        ExecutionStatus.ACTIVE
                    )
                # B2's original native final survives; publication reentry is not regeneration.
                first = await parent.run(work.writer)
                assert first.covered_through_sequence == 2 and len(sent) == 4
                assert await parent.run(work.writer) == first and len(sent) == 4
                async with database.sessions() as session:
                    for role in (
                        AgentRole.WORK_SITUATION_ANALYST,
                        AgentRole.WORK_UNDERSTANDING_ANALYST,
                    ):
                        binding = await history.read_context_history(
                            session, work.writer.scope, role
                        )
                        assert binding is not None and binding.completed is not None
                        assert await history.read_adopted_context(
                            session, turn.scope.job_file_id, role
                        ) == (binding.completed)
                later = await start_turn(database, turn.scope.job_file_id)
                await requests.request(later, uuid4())
                await complete_turn(database, later)
                next_work = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
                assert next_work is not None
                second = await parent.run(next_work.writer)
                assert second.covered_through_sequence == 4 and len(sent) == 7
                async with database.sessions() as session:
                    original_view = await read_queries.bind_published_view(
                        session,
                        turn.scope.job_file_id,
                        first.snapshot_id,
                        MemoryLayer.WORK_SITUATION,
                    )
                    latest_view = await read_queries.bind_published_view(
                        session,
                        turn.scope.job_file_id,
                        second.snapshot_id,
                        MemoryLayer.WORK_SITUATION,
                    )
                    original_map = await read_queries.read_map(session, original_view)
                    latest_map = await read_queries.read_map(session, latest_view)
                assert original_map[0].description == "核對帳物"
                assert latest_map[0].description == "核對帳物、主管核准"
                assert await requests.discover() == ()
        finally:
            await client.close()
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
