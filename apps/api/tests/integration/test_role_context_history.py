"""Native saver windows and domain adoption agree across completed/cancelled Turns."""

import asyncio
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agent_execution.tool_steps import run_response_loop
from caliburn.features.executions import history, service
from caliburn.features.executions.history_models import AgentRole, HistoryConflictError
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.settings import DatabaseSettings
from caliburn.workflows.context_history import RoleContextHistory
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.integration.test_compaction_accounting import file_id as file_id
from tests.integration.test_compaction_accounting import runner as runner
from tests.unit.test_context_preparation import PreparationProbe
from tests.unit.test_response_loop import LoopProbe, initial_request, response_at

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("adoption_failure", [False, True], ids=["normal", "adoption-rollback"])
def test_cancelled_work_cannot_replace_prepared_history_for_new_input(
    database_settings: DatabaseSettings,
    file_id: UUID,
    runner: asyncio.Runner,
    monkeypatch: pytest.MonkeyPatch,
    adoption_failure: bool,
) -> None:
    async def scenario():
        database = Database(database_settings)
        sessions = database.sessions
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        template = ResponseRequest.from_snapshot(
            {**initial_request().create_payload(), "input": []}
        )
        preparation = PreparationProbe(128_000)

        async def start():
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            async with sessions.begin() as session:
                await service.admit_execution(session, scope)
                return await service.claim_writer(session, scope, writer_id=uuid4())

        async def prepare(work):
            runtime = CompactionRuntime(
                preparation.compact,
                preparation.account,
                work.ensure_active,
                synthetic_capacity_limits(),
            )
            return await work.prepare_history(
                template=template,
                threshold_tokens=128_000,
                compact_requested=False,
                count_input=preparation.count,
                runtime=runtime,
            )

        async def run(work, items, label, ordinal):
            probe = LoopProbe([response_at(ordinal, final=True)])
            request = ResponseRequest.from_snapshot(
                {
                    **template.create_payload(),
                    "input": [
                        *items,
                        {"role": "user", "content": f"map-{label}"},
                        {"role": "user", "content": label},
                    ],
                }
            )
            await run_response_loop(
                work.checkpointer,
                thread_id=work.response_thread_id,
                request=request,
                runtime=probe.runtime(),
                max_tool_calls=4,
                max_model_steps=3,
            )
            return probe

        try:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                first = RoleContextHistory(sessions, await start(), AgentRole.JOB_CONSULTANT, saver)
                assert await prepare(first) == []
                async with sessions.begin() as session:
                    binding = await history.read_context_history(
                        session, first.writer.scope, first.role
                    )
                    assert binding is not None and binding.prepared is not None
                await run(first, [], "completed-original", 1)
                first_position = await first.read_completed_position()
                async with sessions.begin() as session:
                    await history.complete_context_histories(
                        session, first.writer, {first.role: first_position}
                    )

                second = RoleContextHistory(
                    sessions, await start(), AgentRole.JOB_CONSULTANT, saver
                )
                if adoption_failure:
                    original_adopt = history.adopt_prepared_context

                    async def fail_transaction(*args):
                        await original_adopt(*args)
                        raise ConnectionError("synthetic failure before adoption COMMIT")

                    with monkeypatch.context() as patch:
                        patch.setattr(history, "adopt_prepared_context", fail_transaction)
                        with pytest.raises(ConnectionError):
                            await prepare(second)
                    async with sessions.begin() as session:
                        assert (
                            await history.read_adopted_context(session, file_id, second.role)
                            == first_position
                        )
                base = await prepare(second)
                assert base == preparation.window
                await run(second, base, "cancelled-a", 2)
                second_position = await second.read_completed_position()
                async with sessions.begin() as session:
                    await service.finish_execution(
                        session, second.writer, ExecutionStatus.CANCELLED
                    )
                with pytest.raises((ExecutionStateError, HistoryConflictError)):
                    async with sessions.begin() as session:
                        await history.complete_context_histories(
                            session, second.writer, {second.role: second_position}
                        )

            # Actual saver reconnect; not a claim to restore process-local unsaved results.
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                third = RoleContextHistory(sessions, await start(), AgentRole.JOB_CONSULTANT, saver)
                reused = await prepare(third)
                assert reused == preparation.window
                assert len(preparation.count_requests) == 1
                assert len(preparation.compact_requests) == 1
                probe = await run(third, reused, "new-b", 3)
                assert probe.requests[0]["input"] == [
                    *preparation.window,
                    {"role": "user", "content": "map-new-b"},
                    {"role": "user", "content": "new-b"},
                ]
                position = await third.read_completed_position()
                async with sessions.begin() as session:
                    await history.complete_context_histories(
                        session, third.writer, {third.role: position}
                    )
                # Reconcile the first completion after newer history exists: no head rewind.
                async with sessions.begin() as session:
                    await history.complete_context_histories(
                        session, first.writer, {first.role: first_position}
                    )
                    assert (
                        await history.read_adopted_context(session, file_id, third.role) == position
                    )
        finally:
            await database.close()

    runner.run(scenario())
