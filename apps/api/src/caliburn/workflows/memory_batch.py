"""Sequential B1/B2 parent; candidates and native role histories keep their own authority."""

import json
from typing import Protocol
from uuid import uuid5

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agent_execution.request_capacity import RequestCapacityError
from caliburn.agent_execution.response_steps import (
    IncompleteModelResponseError,
    UnsupportedModelResponseError,
)
from caliburn.agent_execution.tool_steps import ModelStepLimitError
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.budget_models import BudgetExceededError
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import (
    candidate_lifecycle,
    candidate_operations,
    candidate_queries,
    consolidation_requests,
)
from caliburn.features.work_memory.batch_models import MemoryFeedbackLimitError
from caliburn.features.work_memory.candidates import (
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemorySnapshot,
)
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_analysis.results import (
    AnalysisComplete,
    AnalysisOutcomeError,
    MemoryAnalysisResult,
    SituationGap,
    SituationRework,
    parse_outcome,
)
from caliburn.workflows.memory_analysis.runner import AnalysisRecovery
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_stage_changes import read_situation_handoff_changes
from caliburn.workflows.model_requests import ModelRequestFailedError


class MemoryRoleRunner(Protocol):
    async def __call__(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        previous: MemoryAnalysisResult | None = None,
        gaps: tuple[SituationGap, ...] = (),
        situation_changes: list[dict[str, JsonValue]] | None = None,
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult: ...


class MemoryBatchWorkflow:
    """The role callable resumes its saved native stage; the parent never retries a model.

    ModelRequestExecutor already owns bounded outbound retry and persistent budgets. A
    process/DB interruption propagates to the outer work boundary, which reconciles the
    original publication before abandoning a batch. Task shutdown preserves saved work.
    Run only with a writer claimed by the supervised local leader.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        run_role: MemoryRoleRunner,
        max_feedback_rounds: int = 2,
    ) -> None:
        if type(max_feedback_rounds) is not int or not 0 <= max_feedback_rounds <= 10:
            raise ValueError("Use a bounded Memory feedback allowance")
        self.sessions = sessions
        self.run_role = run_role
        self.max_feedback_rounds = max_feedback_rounds
        self.requests = MemoryConsolidationWorkflow(sessions)

    async def settle_failure(self, writer: ExecutionWriter, error: Exception) -> None:
        """Classify once, then let the existing owner reconcile the real outcome."""
        if isinstance(error, ModelRequestFailedError):
            reason = error.failure.kind.value
        elif isinstance(error, AnalysisOutcomeError):
            reason = error.reason_code
        elif isinstance(
            error,
            (
                BudgetExceededError,
                ModelStepLimitError,
                RequestCapacityError,
                IncompleteModelResponseError,
                UnsupportedModelResponseError,
                MemoryFeedbackLimitError,
            ),
        ):
            reason = type(error).__name__
        else:
            reason = "execution_interrupted"
        await self.requests.fail(writer, reason=reason)

    async def run(
        self, writer: ExecutionWriter, *, recovery: AnalysisRecovery | None = None
    ) -> MemorySnapshot:
        while True:
            async with self.sessions() as session:
                execution = await executions.read_execution(session, writer.scope)
                published = await consolidation_requests.read_batch_result(
                    session, writer.scope.job_file_id, writer.scope.execution_id
                )
                if published is not None:
                    if execution.status != ExecutionStatus.COMPLETED:
                        raise ExecutionStateError("Publication without completed execution")
                    return candidate_queries.snapshot_value(published)
            work = await self.requests.read_work(writer.scope)
            if work.writer != writer:
                raise ExecutionStateError("Memory writer was superseded")
            feedback = await self._feedback(work.position)
            previous = await self._previous(work.position)
            async with self.sessions() as session:
                changes = (
                    await read_situation_handoff_changes(session, work.position)
                    if work.position.phase == MemoryLayer.WORK_UNDERSTANDING
                    else None
                )
            result = await self.run_role(
                writer,
                work.position,
                previous=previous,
                gaps=feedback,
                situation_changes=changes,
                **({"recovery": recovery} if recovery is not None else {}),
            )
            # A held original belongs to this stage only, never the next role/handoff.
            recovery = None
            snapshot = await self._complete_stage(writer, work.position, result)
            if snapshot is not None:
                return snapshot

    async def _feedback(self, stage: MemoryBatchPosition) -> tuple[SituationGap, ...]:
        async with self.sessions() as session:
            records = await consolidation_requests.list_stage_results(
                session, stage.job_file_id, stage.execution_id
            )
        if stage.phase != MemoryLayer.WORK_SITUATION:
            return ()
        for record in records:
            if record.get("next_stage_id") == str(stage.stage_id):
                outcome = record.get("outcome")
                if isinstance(outcome, dict) and outcome.get("status") == "needs_situation":
                    # Public validated gap only; no understanding text or private B2 trace.
                    return SituationRework.model_validate_json(json.dumps(outcome)).gaps
        return ()

    async def _previous(self, stage: MemoryBatchPosition) -> MemoryAnalysisResult | None:
        async with self.sessions() as session:
            records = await consolidation_requests.list_stage_results(
                session, stage.job_file_id, stage.execution_id
            )
        for record in sorted(records, key=_ordinal, reverse=True):
            if record.get("role") != _role(stage.phase).value:
                continue
            original = record.get("stage")
            if not isinstance(original, dict):
                raise MemoryCandidateStateError("Missing original analysis stage")
            saved_stage = candidate_operations.result_position(original)
            return MemoryAnalysisResult(
                saved_stage,
                parse_outcome(json.dumps(record["outcome"]), saved_stage.phase),
                _saved_context(record),
            )
        return None

    async def _complete_stage(
        self, writer: ExecutionWriter, entered: MemoryBatchPosition, result: MemoryAnalysisResult
    ) -> MemorySnapshot | None:
        if (
            result.stage.job_file_id,
            result.stage.execution_id,
            result.stage.generation_id,
            result.stage.stage_id,
            result.stage.phase,
        ) != (
            entered.job_file_id,
            entered.execution_id,
            entered.generation_id,
            entered.stage_id,
            entered.phase,
        ):
            raise MemoryCandidateStateError(
                "The analysis result belongs to another candidate stage"
            )
        role = _role(entered.phase)
        _require_context(writer, role, result.stage, result.history_position)
        if entered.phase == MemoryLayer.WORK_SITUATION and not isinstance(
            result.outcome, AnalysisComplete
        ):
            raise MemoryCandidateStateError("B1 cannot request understanding rework")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            await candidate_queries.require_stage(session, result.stage, exact_position=True)
            records = await consolidation_requests.list_stage_results(
                session, entered.job_file_id, entered.execution_id
            )
            if isinstance(result.outcome, SituationRework):
                rounds = sum(_is_feedback(item) for item in records)
                if rounds >= self.max_feedback_rounds:
                    raise MemoryFeedbackLimitError("Memory feedback allowance exhausted")
            next_stage = None
            if entered.phase == MemoryLayer.WORK_SITUATION or isinstance(
                result.outcome, SituationRework
            ):
                next_stage = await candidate_lifecycle.handoff(
                    session, result.stage, uuid5(entered.stage_id, "memory.handoff")
                )
            record: dict[str, object] = {
                "ordinal": len(records),
                "role": role.value,
                "stage": candidate_operations.position_fields(result.stage),
                "outcome": result.outcome.model_dump(mode="json"),
                "thread_id": result.history_position.thread_id,
                "checkpoint_id": result.history_position.checkpoint_id,
                "next_stage_id": str(next_stage.stage_id) if next_stage is not None else None,
            }
            await consolidation_requests.record_operation(
                session,
                job_file_id=entered.job_file_id,
                execution_id=entered.execution_id,
                command_id=uuid5(entered.stage_id, "memory.stage_completion"),
                kind="stage_completion",
                payload={"stage_id": str(entered.stage_id)},
                result=record,
            )
            if next_stage is not None:
                return None
            positions = _latest_contexts((*records, record))
            # All effects use the SAME short transaction. In particular, do not call a
            # workflow which marks completed before history owner checks its references.
            snapshot = await candidate_lifecycle.publish(
                session, result.stage, uuid5(writer.scope.execution_id, "memory.publish")
            )
            await history.complete_context_histories(session, writer, positions)
            return snapshot


def _role(layer: MemoryLayer) -> AgentRole:
    return (
        AgentRole.WORK_SITUATION_ANALYST
        if layer == MemoryLayer.WORK_SITUATION
        else AgentRole.WORK_UNDERSTANDING_ANALYST
    )


def _require_context(
    writer: ExecutionWriter, role: AgentRole, stage: MemoryBatchPosition, position: ContextPosition
) -> None:
    root = context_thread_id(writer.scope, role, HistoryWindowKind.COMPLETED_WORK)
    expected = f"{root}:stage:{stage.generation_id}:{stage.stage_id}"
    if position.kind != HistoryWindowKind.COMPLETED_WORK or position.thread_id != expected:
        raise MemoryCandidateStateError("Analysis completion requires this role's saved context")


def _latest_contexts(records: tuple[dict[str, object], ...]) -> dict[AgentRole, ContextPosition]:
    ordered = sorted(records, key=_ordinal)
    positions = {}
    for record in ordered:
        role = record.get("role")
        if not isinstance(role, str):
            raise MemoryCandidateStateError("Incomplete saved role completion")
        positions[AgentRole(role)] = _saved_context(record)
    return positions


def _saved_context(record: dict[str, object]) -> ContextPosition:
    thread, checkpoint = record.get("thread_id"), record.get("checkpoint_id")
    if not isinstance(thread, str) or not isinstance(checkpoint, str):
        raise MemoryCandidateStateError("Incomplete saved role completion")
    return ContextPosition(thread, checkpoint, HistoryWindowKind.COMPLETED_WORK)


def _ordinal(record: dict[str, object]) -> int:
    ordinal = record.get("ordinal")
    if type(ordinal) is not int:
        raise MemoryCandidateStateError("Invalid saved stage ordinal")
    return ordinal


def _is_feedback(record: dict[str, object]) -> bool:
    outcome = record.get("outcome")
    return isinstance(outcome, dict) and outcome.get("status") == "needs_situation"
