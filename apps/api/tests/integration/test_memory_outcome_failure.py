"""Invalid saved role outcomes are terminal Memory failures, not published snapshots."""

import asyncio
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.work_memory import consolidation_requests
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.execution_failures import run_with_failure_boundary
from caliburn.workflows.memory_analysis.results import AnalysisOutcomeError
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from tests.integration.test_memory_batch_orchestration import complete_turn, start_turn
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_legacy_recorded_rework_fails_before_any_new_model_work(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        try:
            requests = MemoryConsolidationWorkflow(database.sessions)
            turn = await start_turn(database)
            await requests.request(turn, uuid4())
            await complete_turn(database, turn)
            work = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
            assert work is not None
            # A persisted outcome from the retired B2→B1 flow must not be silently
            # treated as a fresh B1 stage with its previous analysis discarded.
            async with database.sessions.begin() as session:
                await consolidation_requests.record_operation(
                    session,
                    job_file_id=turn.scope.job_file_id,
                    execution_id=work.writer.scope.execution_id,
                    command_id=uuid4(),
                    kind="stage_completion",
                    payload={},
                    result={
                        "outcome": {
                            "status": "needs_situation",
                            "gaps": [
                                {
                                    "target_title": "盤點",
                                    "question": "頻率？",
                                    "needed_clarification": "確認頻率",
                                    "interview_sequences": [2],
                                }
                            ],
                        }
                    },
                )

            async def unexpected_model_work(*args, **kwargs):
                pytest.fail("Legacy rework must be rejected before model dispatch")

            parent = MemoryBatchWorkflow(database.sessions, run_role=unexpected_model_work)
            with pytest.raises(AnalysisOutcomeError, match="analysis_outcome_malformed"):
                await parent.run(work.writer)
            assert (
                await run_with_failure_boundary(
                    work.writer, run=parent.run, settle_failure=parent.settle_failure
                )
                is None
            )
            assert (
                await requests.failure_reason(turn.scope.job_file_id)
                == "analysis_outcome_malformed"
            )
            assert await requests.discover() == ()
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize(
    ("invalid_kind", "reason"),
    [
        ("malformed", "analysis_outcome_malformed"),
        ("refusal", "analysis_outcome_refused"),
        ("legacy_rework", "analysis_outcome_malformed"),
    ],
)
def test_invalid_b2_final_is_durable_failure_without_publish_or_retry(
    database_settings: DatabaseSettings, invalid_kind: str, reason: str
) -> None:
    calls = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        assert request.url.path.endswith("/responses")
        calls += 1
        assert calls <= 2  # The parent must not regenerate a rejected final output.
        raw = response_at(calls, final=True, tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        content = raw["output"][1]["content"]
        if calls == 1:
            content[0]["text"] = '{"status":"complete"}'
        elif invalid_kind == "refusal":
            content[:] = [{"type": "refusal", "refusal": "SYNTHETIC_PRIVATE_REFUSAL"}]
        elif invalid_kind == "legacy_rework":
            content[0]["text"] = (
                '{"status":"needs_situation","gaps":[{"target_title":"盤點",'
                '"question":"頻率？","needed_clarification":"確認頻率","interview_sequences":[2]}]}'
            )
        else:
            content[0]["text"] = 'SYNTHETIC_PRIVATE_INVALID_FINAL {"status":'
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
                assert (
                    await run_with_failure_boundary(
                        work.writer, run=parent.run, settle_failure=parent.settle_failure
                    )
                    is None
                )
            assert calls == 2
            assert (
                await MemoryCandidateWorkflow(database.sessions).read_latest_snapshot(
                    turn.scope.job_file_id
                )
                is None
            )
            async with database.sessions() as session:
                assert (await executions.read_execution(session, work.writer.scope)).status == (
                    ExecutionStatus.FAILED
                )
            # Read a fresh owner instance to prove a durable reason, not a local exception.
            restarted = MemoryConsolidationWorkflow(database.sessions)
            assert await restarted.failure_reason(turn.scope.job_file_id) == reason
            assert await restarted.discover() == ()
            later = await start_turn(database, turn.scope.job_file_id)
            await restarted.request(later, uuid4())
            await complete_turn(database, later)
            assert await restarted.discover() == ()
            assert calls == 2
        finally:
            await client.close()
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_unrelated_value_error_is_not_classified_as_model_outcome(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        try:
            requests = MemoryConsolidationWorkflow(database.sessions)
            turn = await start_turn(database)
            await requests.request(turn, uuid4())
            await complete_turn(database, turn)
            work = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
            assert work is not None

            async def invalid_local_contract(*args, **kwargs):
                raise ValueError("synthetic local programming error")

            parent = MemoryBatchWorkflow(database.sessions, run_role=invalid_local_contract)
            with pytest.raises(ValueError, match="local programming error"):
                await parent.run(work.writer)
            assert await requests.failure_reason(turn.scope.job_file_id) is None
            async with database.sessions() as session:
                assert (await executions.read_execution(session, work.writer.scope)).status == (
                    ExecutionStatus.ACTIVE
                )
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
