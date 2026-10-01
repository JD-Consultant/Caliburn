"""Compose A from shared native execution and existing product owners."""

from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import restore_response
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agent_execution.context_compaction import (
    HeldCompaction,
    HeldPreparationCount,
    bind_window_compaction,
)
from caliburn.agent_execution.response_steps import (
    inspect_response_step,
)
from caliburn.agent_execution.tool_steps import (
    HeldInputCount,
    HeldModelResponse,
    PausedResponseLoop,
    ResponseStepRuntime,
    run_response_loop,
)
from caliburn.agents.job_consultant.context_binding import TurnContext, capture_turn_context
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.recent_preload import fit_recent_interview_preload
from caliburn.agents.job_consultant.tools import ConsultantTools, consultant_tool_definitions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionScope,
    ExecutionWriter,
)
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.transport.model_tools.memory_consolidation import MemoryConsolidationTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.execution_controls import ConsultantExecutionControls
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import JdChangesWorkflow
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.jd_item_movement import JdItemMovementWorkflow
from caliburn.workflows.jd_item_revision import JdItemRevisionWorkflow
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_reads import MemoryReadWorkflow
from caliburn.workflows.model_runtime import bind_model_runtime, fix_execution_policy

type ConsultantRecovery = HeldModelResponse | HeldInputCount | HeldCompaction | HeldPreparationCount


@dataclass(frozen=True, slots=True)
class ConsultantRunner:
    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings
    on_commentary: Callable[[ExecutionScope, PublicCommentaryUpdate], None] | None = None

    async def run(
        self,
        writer: ExecutionWriter,
        *,
        resume_interrupt_id: str | None = None,
        recovery: ConsultantRecovery | None = None,
    ) -> FormalInterviewExchange | PausedResponseLoop:
        """One supervised writer; reentry resumes native work, never rebuilds its context.

        The supervisor reconciles terminal/uncertain outcomes and authorizes pause resume.
        This role does not implement a second retry engine or start background Memory.
        A caller may explicitly return an intact response/count/compaction handoff; the shared
        boundary validates its original request and keeps pause authority separate.
        """
        role_history = RoleContextHistory(
            self.sessions, writer, AgentRole.JOB_CONSULTANT, self.checkpointer
        )
        preparation_thread = context_thread_id(
            writer.scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.PREPARED_HISTORY
        )
        if recovery is not None:
            if resume_interrupt_id is not None:
                raise ValueError(
                    "Explicit resume requires the original paused loop with no handoff"
                )
            if isinstance(recovery, (HeldModelResponse, HeldInputCount)):
                matches = recovery.thread_id == role_history.response_thread_id
            else:
                matches = recovery.thread_id == preparation_thread or (
                    isinstance(recovery, HeldCompaction)
                    and recovery.thread_id.startswith(f"{role_history.response_thread_id}:compact:")
                )
            if not matches:
                raise ValueError("Recovery must retain the original Step or preparation boundary")
        policy = await fix_execution_policy(self.sessions, writer, self.settings)
        commentary = self.on_commentary
        model = bind_model_runtime(
            self.sessions,
            writer,
            self.client,
            self.settings,
            ensure_active=role_history.ensure_active,
            on_commentary=(lambda update: commentary(writer.scope, update))
            if commentary is not None
            else None,
        )
        executor = model.executor
        template = ResponseRequest(
            model=self.settings.model,
            instructions=CONSULTANT_INSTRUCTIONS,
            input_items=[],
            tools=consultant_tool_definitions(),
            reasoning_effort=self.settings.reasoning_effort,
            max_output_tokens=self.settings.max_output_tokens,
            stream=commentary is not None,
        )
        prepared = await role_history.prepare_history(
            template=template,
            threshold_tokens=128_000,
            count_input=executor.count_input,
            runtime=model.compaction,
            recovery=recovery
            if isinstance(recovery, (HeldCompaction, HeldPreparationCount))
            and recovery.thread_id == preparation_thread
            else None,
        )
        context = await capture_turn_context(
            role_history, template=template, prepared_history=prepared
        )
        tools = self._tools(writer, context, role_history)

        compact_window = bind_window_compaction(
            self.checkpointer,
            response_thread_id=role_history.response_thread_id,
            runtime=model.compaction,
            recovery=recovery,
        )

        runtime = ResponseStepRuntime(
            request_model=executor.request_model,
            prepare_tool=tools.prepare,
            execute_tool=tools.execute,
            ensure_active=role_history.ensure_active,
            account_response=executor.account_response,
            count_input=executor.count_input,
            capacity_limits=model.capacity_limits,
            compact_window=compact_window,
            fit_first_request=fit_recent_interview_preload,
        )
        config: RunnableConfig = {
            "configurable": {"thread_id": role_history.response_thread_id, "checkpoint_ns": ""}
        }
        saved = await self.checkpointer.aget_tuple(config)
        step_recovery = (
            recovery if isinstance(recovery, (HeldModelResponse, HeldInputCount)) else None
        )
        result = await run_response_loop(
            self.checkpointer,
            thread_id=role_history.response_thread_id,
            request=context.request if saved is None and step_recovery is None else None,
            runtime=runtime,
            max_tool_calls=self.settings.max_tool_calls_per_step,
            max_model_steps=policy.max_model_steps,
            controls=ConsultantExecutionControls(self.sessions, writer).loop_controls(),
            resume_interrupt_id=resume_interrupt_id,
            recovery=step_recovery,
        )
        if isinstance(result, PausedResponseLoop):
            return result
        step = inspect_response_step(restore_response(result["response_snapshot"]))
        reply = "\n\n".join(
            part.text if part.type == "output_text" else part.refusal
            for message in step.messages
            if message.phase == "final_answer"
            for part in message.content
        )
        position = await role_history.read_completed_position()
        candidate = await JdCandidateWorkflow(self.sessions).read(writer.scope)
        return await ConsultantCompletionWorkflow(self.sessions).complete(
            writer, candidate.position, reply, position
        )

    def _tools(
        self, writer: ExecutionWriter, context: TurnContext, role_history: RoleContextHistory
    ) -> ConsultantTools:
        return ConsultantTools(
            MemoryReadTools(MemoryReadWorkflow(self.sessions), context.memory_binding),
            JdReadTools(JdReadWorkflow(self.sessions), context.memory_binding),
            JdWriteTools(
                JdProfileWriteWorkflow(self.sessions),
                JdTaskWriteWorkflow(self.sessions),
                context.memory_binding,
                writer,
                creations=JdItemCreationWorkflow(self.sessions),
                revisions=JdItemRevisionWorkflow(self.sessions),
                deletions=JdItemDeletionWorkflow(self.sessions),
                movements=JdItemMovementWorkflow(self.sessions),
            ),
            JdChangesTools(
                JdChangesWorkflow(self.sessions),
                context.memory_binding,
                manual_jd_start_revision_id=context.manual_jd_start_revision_id,
            ),
            MemoryConsolidationTools(MemoryConsolidationWorkflow(self.sessions), writer),
            ContextCompactionTools(role_history),
        )
