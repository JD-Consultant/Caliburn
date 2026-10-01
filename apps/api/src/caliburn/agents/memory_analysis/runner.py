"""Coordinate Memory stage owners with native execution; no role prompt or new loop."""

from dataclasses import dataclass
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import restore_response
from caliburn.agent_execution.context_compaction import (
    HeldCompaction,
    HeldPreparationCount,
    bind_window_compaction,
    prepare_context_history,
)
from caliburn.agent_execution.request_capacity import (
    MID_WORK_COMPACTION_THRESHOLD_TOKENS,
    ReceivedInputCount,
    RequestCapacityError,
)
from caliburn.agent_execution.response_steps import inspect_response_step
from caliburn.agent_execution.tool_steps import (
    HeldInputCount,
    HeldModelResponse,
    PausedResponseLoop,
    ResponseStepRuntime,
    read_completed_response_history,
    run_response_loop,
)
from caliburn.agents.memory_analysis.context import capture_analysis_context, stage_thread_id
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionWriter
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_analysis import MemoryAnalysisTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.transport.model_tools.memory_writes import MemoryWriteTools
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.memory_analysis.results import (
    AnalysisOutcomeError,
    AnalysisRecovery,
    MemoryAnalysisResult,
    SituationGap,
    parse_outcome,
)
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import CandidateMemoryRead, MemoryReadWorkflow
from caliburn.workflows.memory_writes import MemoryWritePreparation
from caliburn.workflows.model_runtime import bind_model_runtime, fix_execution_policy

HISTORY_THRESHOLD_TOKENS = 128_000  # Owner-approved pre-batch policy, not provider capacity.


@dataclass(frozen=True, slots=True)
class MemoryAnalysisRunner:
    """Concrete common assembly, not a BaseAgent, scheduler or second tool/model loop.

    A stage has an original immutable context thread and native response-loop thread.
    Parent must retain the same-role result across handoffs, and separately validate
    completion eligibility before adopting both references and publishing Memory.
    No exception is converted to success, no cancellation caught, no retry here.
    """

    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings

    async def run(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        role: AgentRole,
        instructions: str,
        previous: MemoryAnalysisResult | None = None,
        gaps: tuple[SituationGap, ...] = (),
        situation_changes: list[dict[str, JsonValue]] | None = None,
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult:
        expected_role = {
            MemoryLayer.WORK_SITUATION: AgentRole.WORK_SITUATION_ANALYST,
            MemoryLayer.WORK_UNDERSTANDING: AgentRole.WORK_UNDERSTANDING_ANALYST,
        }[stage.phase]
        if writer.scope.kind != ExecutionKind.MEMORY_BATCH or role != expected_role:
            raise ValueError("The role does not match this Memory batch stage")
        binding = CandidateMemoryRead(writer.scope, stage)
        history = RoleContextHistory(self.sessions, writer, role, self.checkpointer)
        thread_id = stage_thread_id(history, stage)
        if recovery is not None:
            permitted_boundary = (
                context_thread_id(writer.scope, role, HistoryWindowKind.PREPARED_HISTORY)
                if previous is None
                else f"{thread_id}:handoff_capacity"
            )
            if isinstance(recovery, (HeldModelResponse, HeldInputCount)):
                matches = recovery.thread_id == thread_id
            else:
                matches = recovery.thread_id == permitted_boundary or (
                    isinstance(recovery, HeldCompaction)
                    and recovery.thread_id.startswith(f"{thread_id}:compact:")
                )
            if not matches:
                raise ValueError("Recovery must retain the original role and stage boundary")

        async def ensure_active() -> None:
            async with self.sessions.begin() as session:
                await executions.lock_active_writer(session, writer)
                await candidate_queries.require_stage(session, stage)

        await ensure_active()
        policy = await fix_execution_policy(self.sessions, writer, self.settings)
        tools = MemoryAnalysisTools(
            MemoryReadTools(MemoryReadWorkflow(self.sessions), binding),
            MemoryWriteTools(
                MemoryWritePreparation(self.sessions),
                MemoryCandidateWorkflow(self.sessions),
                binding,
                writer,
            ),
        )
        model = bind_model_runtime(
            self.sessions, writer, self.client, self.settings, ensure_active=ensure_active
        )
        executor = model.executor
        template = ResponseRequest(
            model=self.settings.model,
            instructions=instructions,
            input_items=[],
            tools=tools.definitions(),
            reasoning_effort=self.settings.reasoning_effort,
            max_output_tokens=self.settings.max_output_tokens,
        )
        preparation_recovery = (
            recovery if isinstance(recovery, (HeldCompaction, HeldPreparationCount)) else None
        )
        if previous is None:
            items = await history.prepare_history(
                template=template,
                threshold_tokens=HISTORY_THRESHOLD_TOKENS,
                compact_requested=False,
                count_input=executor.count_input,
                runtime=model.compaction,
                recovery=preparation_recovery,
            )
        else:
            _require_previous(history, stage, previous)
            window = await read_completed_response_history(
                self.checkpointer,
                thread_id=previous.history_position.thread_id,
                checkpoint_id=previous.history_position.checkpoint_id,
            )
            items = window.items
        request = await capture_analysis_context(
            history,
            stage,
            template=template,
            history_items=items,
            continuation=previous is not None,
            gaps=gaps,
            situation_changes=situation_changes,
        )
        config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        saved = await self.checkpointer.aget_tuple(config)
        if previous is not None and saved is None:
            # A handoff follows a complete Step. Apply the shared compact boundary to
            # the FULL continuation, including this handoff, not the pre-batch base.
            # This is not adopted as prepared_history and never repeats initial data.
            items = await prepare_context_history(
                self.checkpointer,
                thread_id=f"{thread_id}:handoff_capacity",
                history_request=request,
                threshold_tokens=MID_WORK_COMPACTION_THRESHOLD_TOKENS,
                compact_requested=False,
                count_input=executor.count_input,
                runtime=model.compaction,
                recovery=preparation_recovery,
            )
            request = ResponseRequest.from_snapshot({**request.create_payload(), "input": items})

        async def count_input(current: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
            count = await executor.count_input(current, request_id)
            if (
                previous is not None
                and saved is None
                and current.create_payload() == request.create_payload()
                and count["input_tokens"] >= MID_WORK_COMPACTION_THRESHOLD_TOKENS
            ):
                # The handoff boundary already compacted this window once. Never send
                # or repeatedly compact an unchanged still-oversized result.
                raise RequestCapacityError(
                    "The handoff continuation remains above the compact guard"
                )
            return count

        compact_window = bind_window_compaction(
            self.checkpointer,
            response_thread_id=thread_id,
            runtime=model.compaction,
            recovery=recovery,
        )

        runtime = ResponseStepRuntime(
            request_model=executor.request_model,
            prepare_tool=tools.prepare,
            execute_tool=tools.execute,
            ensure_active=ensure_active,
            account_response=executor.account_response,
            count_input=count_input,
            capacity_limits=model.capacity_limits,
            compact_window=compact_window,
        )
        step_recovery = (
            recovery if isinstance(recovery, (HeldModelResponse, HeldInputCount)) else None
        )
        result = await run_response_loop(
            self.checkpointer,
            thread_id=thread_id,
            request=request if saved is None and step_recovery is None else None,
            runtime=runtime,
            max_tool_calls=self.settings.max_tool_calls_per_step,
            max_model_steps=policy.max_model_steps,
            recovery=step_recovery,
        )
        if isinstance(result, PausedResponseLoop):
            raise ValueError("Memory roles cannot expose consultant pause controls")
        step = inspect_response_step(restore_response(result["response_snapshot"]))
        if any(part.type == "refusal" for message in step.messages for part in message.content):
            raise AnalysisOutcomeError("analysis_outcome_refused")
        text = "\n".join(
            part.text
            for message in step.messages
            if message.phase == "final_answer"
            for part in message.content
            if part.type == "output_text"
        )
        outcome = parse_outcome(text, stage.phase)
        window = await read_completed_response_history(self.checkpointer, thread_id=thread_id)
        await ensure_active()
        async with self.sessions() as session:
            current_stage = candidate_queries.batch_position(
                await candidate_queries.require_stage(session, stage)
            )
        return MemoryAnalysisResult(
            current_stage,
            outcome,
            ContextPosition(thread_id, window.checkpoint_id, HistoryWindowKind.COMPLETED_WORK),
        )


def _require_previous(
    history: RoleContextHistory, stage: MemoryBatchPosition, previous: MemoryAnalysisResult
) -> None:
    old = previous.stage
    if (old.job_file_id, old.execution_id, old.generation_id, old.phase) != (
        stage.job_file_id,
        stage.execution_id,
        stage.generation_id,
        stage.phase,
    ):
        raise ValueError("Only the same role's original batch history may continue")
    if old.stage_id == stage.stage_id:
        raise ValueError("Resume a saved stage directly, not as a new handoff")
    if (
        previous.history_position.kind != HistoryWindowKind.COMPLETED_WORK
        or previous.history_position.thread_id != stage_thread_id(history, old)
    ):
        raise ValueError("The history reference does not belong to this role stage")
