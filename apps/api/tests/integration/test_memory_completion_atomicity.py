"""Only the real Memory parent completes snapshots and both role histories together."""

from uuid import uuid4

import pytest

from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryConflictError,
    HistoryWindowKind,
    context_thread_id,
    stage_thread_id,
)
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.work_memory import candidate_queries, consolidation_requests
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_analysis.results import AnalysisComplete, MemoryAnalysisResult
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from tests.integration.test_memory_batch_orchestration import (
    complete_turn,
    execute,
    role_context,
    start_turn,
)

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    "missing_role",
    [
        AgentRole.WORK_SITUATION_ANALYST,
        AgentRole.WORK_UNDERSTANDING_ANALYST,
    ],
)
def test_missing_role_preparation_rolls_back_publication_and_completion(
    database_settings, missing_role
):
    async def scenario(database):
        requests = MemoryConsolidationWorkflow(database.sessions)
        turn = await start_turn(database)
        await requests.request(turn, uuid4())
        await complete_turn(database, turn)
        work = await requests.claim(turn.scope.job_file_id, writer_id=uuid4())
        assert work is not None
        stages = {}

        async def run_role(writer, stage, *, situation_changes=None, recovery=None):
            role = (
                AgentRole.WORK_SITUATION_ANALYST
                if stage.phase == MemoryLayer.WORK_SITUATION
                else AgentRole.WORK_UNDERSTANDING_ANALYST
            )
            stages[role] = stage
            if role == missing_role:
                root = context_thread_id(writer.scope, role, HistoryWindowKind.COMPLETED_WORK)
                context = ContextPosition(
                    stage_thread_id(root, stage.generation_id, stage.stage_id),
                    "completed",
                    HistoryWindowKind.COMPLETED_WORK,
                )
            else:
                context = await role_context(database, writer, stage)
            return MemoryAnalysisResult(stage, AnalysisComplete(status="complete"), context)

        parent = MemoryBatchWorkflow(database.sessions, run_role=run_role, cpu=MemoryCpu())
        with pytest.raises(HistoryConflictError, match="adopted preparation"):
            await parent.run(work.writer)
        async with database.sessions() as session:
            assert (
                await candidate_queries.read_latest_snapshot(session, turn.scope.job_file_id)
                is None
            )
            assert (
                await executions.read_execution(session, work.writer.scope)
            ).status == ExecutionStatus.ACTIVE
            records = await consolidation_requests.list_stage_results(
                session, turn.scope.job_file_id, work.writer.scope.execution_id
            )
            assert len(records) == 1  # B1 handoff survives; failed B2 completion rolls back.
            for role in stages:
                binding = await history.read_context_history(session, work.writer.scope, role)
                assert binding is None or binding.completed is None

        # Repair only the deliberately missing preparation; resume the same parent/batch.
        await role_context(database, work.writer, stages[missing_role])
        snapshot = await parent.run(work.writer)
        assert snapshot is not None
        assert await parent.run(work.writer) == snapshot
        async with database.sessions() as session:
            assert (
                await executions.read_execution(session, work.writer.scope)
            ).status == ExecutionStatus.COMPLETED
            for role in stages:
                binding = await history.read_context_history(session, work.writer.scope, role)
                assert binding is not None and binding.completed is not None

    execute(database_settings, scenario)
