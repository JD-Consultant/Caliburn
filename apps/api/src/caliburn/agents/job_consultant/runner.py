"""Compose A from shared native execution and existing product owners."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems, restore_response
from caliburn.agent_execution.context_compaction import CompactionRuntime, run_context_compaction
from caliburn.agent_execution.request_capacity import (
    ModelCapacityLimits,
    ReceivedInputCount,
    RequestCapacityError,
)
from caliburn.agent_execution.response_steps import (
    IncompleteModelResponseError,
    UnsupportedModelResponseError,
    inspect_response_step,
)
from caliburn.agent_execution.tool_steps import (
    HeldInputCount,
    HeldModelResponse,
    ModelStepLimitError,
    PausedResponseLoop,
    ResponseStepRuntime,
    run_response_loop,
)
from caliburn.agents.job_consultant.context_binding import TurnContext, capture_turn_context
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.tools import ConsultantTools, consultant_tool_definitions
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    ExecutionBudget,
)
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionInfo, ExecutionStatus, ExecutionWriter
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
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
from caliburn.workflows.model_requests import (
    ModelRequestAccounting,
    ModelRequestExecutor,
    ModelRequestFailedError,
)

_LOG = logging.getLogger(__name__)

_CAPACITY: ModelCapacityLimits = {
    "model": "gpt-6-luna",
    "max_input_tokens": 922_000,
    "context_window_tokens": 1_050_000,
    "max_output_tokens": 128_000,
}


@dataclass(frozen=True, slots=True)
class ConsultantRunner:
    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings

    async def run_supervised(
        self,
        writer: ExecutionWriter,
        *,
        resume_interrupt_id: str | None = None,
        recovery: HeldModelResponse | HeldInputCount | None = None,
    ) -> FormalInterviewExchange | PausedResponseLoop | ExecutionInfo:
        """Known terminal limitations roll back this Turn; unknown saves remain recoverable.

        No retry here: the shared request executor already owns its bounded retry policy.
        An arbitrary exception, lost DB acknowledgement or held native result is NOT
        proof of final failure and must stay available to the recovery supervisor.
        """
        try:
            return await self.run(
                writer, resume_interrupt_id=resume_interrupt_id, recovery=recovery
            )
        except (
            ModelRequestFailedError,
            BudgetExceededError,
            ModelStepLimitError,
            RequestCapacityError,
            IncompleteModelResponseError,
            UnsupportedModelResponseError,
        ) as error:
            result = await ConsultantCompletionWorkflow(self.sessions).stop(
                writer, ExecutionStatus.FAILED
            )
            _LOG.warning(
                "Consultant stopped at a known terminal boundary",
                extra={
                    "execution_id": str(writer.scope.execution_id),
                    "failure_kind": type(error).__name__,
                },
            )
            return result

    async def run(
        self,
        writer: ExecutionWriter,
        *,
        resume_interrupt_id: str | None = None,
        recovery: HeldModelResponse | HeldInputCount | None = None,
    ) -> FormalInterviewExchange | PausedResponseLoop:
        """One supervised writer; reentry resumes native work, never rebuilds its context.

        The supervisor reconciles terminal/uncertain outcomes and authorizes pause resume.
        This role does not implement a second retry engine or start background Memory.
        A caller may explicitly return an intact response-Step handoff; the shared
        boundary validates its original request and keeps pause authority separate.
        """
        policy = await self._fix_budget(writer)
        role_history = RoleContextHistory(
            self.sessions, writer, AgentRole.JOB_CONSULTANT, self.checkpointer
        )
        pricing = GPT_6_LUNA_STANDARD_2026_09_30
        executor = ModelRequestExecutor(
            self.sessions,
            writer,
            self.client,
            ModelRequestAccounting.from_text_pricing(
                pricing,
                reserved_cost_usd=pricing.reserve_response_cost(
                    input_tokens=_CAPACITY["max_input_tokens"],
                    max_output_tokens=self.settings.max_output_tokens,
                ),
                token_count_reservation_usd=Decimal("0.0001"),
                compaction_reservation_usd=Decimal("0.50"),
            ),
        )
        compaction = CompactionRuntime(
            executor.request_compaction,
            executor.account_compaction,
            role_history.ensure_active,
            _CAPACITY,
        )
        template = ResponseRequest(
            model=self.settings.model,
            instructions=CONSULTANT_INSTRUCTIONS,
            input_items=[],
            tools=consultant_tool_definitions(),
            reasoning_effort=self.settings.reasoning_effort,
            max_output_tokens=self.settings.max_output_tokens,
        )
        prepared = await role_history.prepare_history(
            template=template,
            threshold_tokens=128_000,
            compact_requested=False,
            count_input=executor.count_input,
            runtime=compaction,
        )
        context = await capture_turn_context(
            role_history, template=template, prepared_history=prepared
        )
        tools = self._tools(writer, context)

        async def compact_window(
            request: ResponseRequest, count: ReceivedInputCount, request_id: UUID
        ) -> NativeItems:
            return await run_context_compaction(
                self.checkpointer,
                thread_id=f"{role_history.response_thread_id}:compact:{request_id}",
                request=request,
                input_count=count,
                runtime=compaction,
            )

        runtime = ResponseStepRuntime(
            request_model=executor.request_model,
            prepare_tool=tools.prepare,
            execute_tool=tools.execute,
            ensure_active=role_history.ensure_active,
            account_response=executor.account_response,
            count_input=executor.count_input,
            capacity_limits=_CAPACITY,
            compact_window=compact_window,
        )
        config: RunnableConfig = {
            "configurable": {"thread_id": role_history.response_thread_id, "checkpoint_ns": ""}
        }
        saved = await self.checkpointer.aget_tuple(config)
        result = await run_response_loop(
            self.checkpointer,
            thread_id=role_history.response_thread_id,
            request=context.request if saved is None and recovery is None else None,
            runtime=runtime,
            max_tool_calls=self.settings.max_tool_calls_per_step,
            max_model_steps=policy.max_model_steps,
            controls=ConsultantExecutionControls(self.sessions, writer).loop_controls(),
            resume_interrupt_id=resume_interrupt_id,
            recovery=recovery,
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

    def _tools(self, writer: ExecutionWriter, context: TurnContext) -> ConsultantTools:
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
        )

    async def _fix_budget(self, writer: ExecutionWriter) -> ExecutionBudget:
        """Retain counters/deadline after restart; configuration cannot reset spent allowance."""
        pricing = GPT_6_LUNA_STANDARD_2026_09_30
        async with self.sessions.begin() as session:
            await executions.lock_active_writer(session, writer)
            policy = await budgets.read_execution_budget(session, writer.scope)
            if policy is not None:
                if policy.cost_basis != pricing.cost_basis:
                    raise BudgetConflictError("Resume requires the original pricing policy")
                return policy
            now = await budgets.read_execution_time(session, writer.scope)
            return await budgets.fix_execution_budget(
                session,
                writer,
                ExecutionBudget(
                    self.settings.max_model_steps,
                    self.settings.max_compactions,
                    self.settings.max_outbound_attempts,
                    self.settings.max_attempts_per_request,
                    now + timedelta(seconds=self.settings.turn_timeout_seconds),
                    self.settings.max_cost_usd,
                    pricing.cost_basis,
                ),
            )
