"""Compose A from shared native execution and existing product owners."""

from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.adapters.response_serialization import restore_response
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agent_execution.context_compaction import (
    HeldCompaction,
    HeldPreparationCount,
    bind_window_compaction,
)
from caliburn.agent_execution.context_windows import read_context_checkpoint
from caliburn.agent_execution.response_steps import (
    inspect_response_step,
)
from caliburn.agent_execution.tool_steps import (
    HeldInputCount,
    HeldModelResponse,
    PausedResponseLoop,
    ResponseStepRuntime,
    read_completed_response_history,
    run_response_loop,
)
from caliburn.agents.job_consultant.configuration import ConsultantConfiguration
from caliburn.agents.job_consultant.context_binding import (
    TurnContext,
    capture_turn_context,
    read_captured_turn_template,
    read_saved_turn_context,
)
from caliburn.agents.job_consultant.interview_plan_context import has_interview_plan_tools
from caliburn.agents.job_consultant.interview_plan_projection import bind_interview_plan_compaction
from caliburn.agents.job_consultant.recent_preload import fit_recent_interview_preload
from caliburn.agents.job_consultant.tools import ConsultantTools, consultant_tool_definitions
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interview_plans.models import PlanStateError
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.transport.model_tools.interview_plans import InterviewPlanTools
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.transport.model_tools.memory_consolidation import MemoryConsolidationTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.transport.model_tools.occupation_references import (
    OccupationReferenceTools,
    occupation_reference_write_result_format,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.execution_controls import ConsultantExecutionControls
from caliburn.workflows.interview_plans import InterviewPlanWorkflow
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
from caliburn.workflows.occupation_references import OccupationReferenceWorkflow

type ConsultantRecovery = HeldModelResponse | HeldInputCount | HeldCompaction | HeldPreparationCount


@dataclass(frozen=True, slots=True)
class ConsultantRunner:
    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings
    on_commentary: Callable[[ExecutionScope, PublicCommentaryUpdate], None] | None = None
    on_reasoning_summary: Callable[[ExecutionScope, PublicReasoningSummary], None] | None = None
    occupation_references: OccupationReferenceClient | None = None
    interview_plans_enabled: bool = True
    configuration: ConsultantConfiguration = ConsultantConfiguration()

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
        completed = await self._recover_completed(writer)
        if completed is not None:
            return completed
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
        reasoning_summary = self.on_reasoning_summary
        model = bind_model_runtime(
            self.sessions,
            writer,
            self.client,
            self.settings,
            ensure_active=role_history.ensure_active,
            on_commentary=(lambda update: commentary(writer.scope, update))
            if commentary is not None
            else None,
            on_reasoning_summary=(lambda update: reasoning_summary(writer.scope, update))
            if reasoning_summary is not None
            else None,
        )
        executor = model.executor
        preparation_recovery = (
            recovery
            if isinstance(recovery, (HeldCompaction, HeldPreparationCount))
            and recovery.thread_id == preparation_thread
            else None
        )
        captured_template = await read_captured_turn_template(self.checkpointer, writer.scope)
        history_template = await role_history.resolve_template(
            captured_template or (lambda: self._template(stream=commentary is not None)),
            recovery=preparation_recovery,
        )
        if _references_enabled(history_template) and self.occupation_references is None:
            raise ExecutionStateError("The saved Turn requires its occupation reference client")
        prepared = await role_history.prepare_history(
            template=history_template,
            threshold_tokens=128_000,
            count_input=executor.count_input,
            runtime=model.compaction,
            recovery=preparation_recovery,
        )
        # Summary is a generation option, not a history preparation policy. Keep the
        # pre-work count/compact request stable for older saved preparation boundaries.
        # Context binding itself restores its original request on same-Turn reentry.
        turn_payload = history_template.create_payload()
        turn_payload["reasoning"]["summary"] = "auto"
        turn_payload["stream"] = commentary is not None or reasoning_summary is not None
        context = await capture_turn_context(
            role_history,
            template=ResponseRequest.from_snapshot(turn_payload),
            prepared_history=prepared,
            jd_read_max_result_characters=self.configuration.jd_read_max_result_characters,
        )
        tools = await self._tools(writer, context, role_history)

        compact_window = bind_window_compaction(
            self.checkpointer,
            response_thread_id=role_history.response_thread_id,
            runtime=model.compaction,
            recovery=recovery,
        )
        if context.plan_position is not None:
            compact_window = bind_interview_plan_compaction(role_history, compact_window)

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
        plan = (
            await InterviewPlanWorkflow(self.sessions).read_current(writer.scope)
            if context.plan_position is not None
            else None
        )
        if context.plan_position is not None and plan is None:
            raise PlanStateError("The captured plan capability has no final candidate")
        return await ConsultantCompletionWorkflow(self.sessions).complete(
            writer,
            candidate.position,
            reply,
            position,
            plan_position=plan.position if plan is not None else None,
        )

    def _template(self, *, stream: bool) -> ResponseRequest:
        """只有沒有原生保存邊界的新回合，才組裝及驗證當前候選。"""
        return ResponseRequest(
            model=self.settings.model,
            instructions=self.configuration.instructions(
                interview_plans_enabled=self.interview_plans_enabled,
                occupation_references_enabled=self.occupation_references is not None,
            ),
            input_items=[],
            tools=self.configuration.describe_tools(
                consultant_tool_definitions(
                    occupation_references_enabled=self.occupation_references is not None,
                    interview_plans_enabled=self.interview_plans_enabled,
                )
            ),
            reasoning_effort=self.settings.reasoning_effort,
            max_output_tokens=self.settings.max_output_tokens,
            stream=stream,
        )

    async def _tools(
        self, writer: ExecutionWriter, context: TurnContext, role_history: RoleContextHistory
    ) -> ConsultantTools:
        references = None
        if _references_enabled(context.request):
            if self.occupation_references is None:
                raise ExecutionStateError("The saved Turn requires its occupation reference client")
            result_format = occupation_reference_write_result_format(
                context.request.create_payload()["tools"]
            )
            workflow = OccupationReferenceWorkflow(self.sessions, self.occupation_references)
            await workflow.start(writer)
            references = OccupationReferenceTools(
                workflow,
                self.occupation_references,
                writer,
                write_result_format=result_format,
            )
        return ConsultantTools(
            MemoryReadTools(MemoryReadWorkflow(self.sessions), context.memory_binding),
            JdReadTools(
                JdReadWorkflow(self.sessions),
                context.memory_binding,
                max_result_characters=context.jd_read_max_result_characters,
            ),
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
            occupation_references=references,
            interview_plans=(
                InterviewPlanTools(InterviewPlanWorkflow(self.sessions), writer)
                if has_interview_plan_tools(context.request)
                else None
            ),
        )

    async def _recover_completed(self, writer: ExecutionWriter) -> FormalInterviewExchange | None:
        """Read the original completed result; never reopen controls, tools, or live JD preview."""
        async with self.sessions() as session:
            execution = await executions.read_execution(session, writer.scope)
            if execution.status != ExecutionStatus.COMPLETED:
                return None
            binding = await history.read_context_history(
                session, writer.scope, AgentRole.JOB_CONSULTANT
            )
        if binding is None or binding.completed is None:
            raise ExecutionStateError("The completed Turn has no original context binding")
        position = binding.completed
        await read_completed_response_history(
            self.checkpointer, thread_id=position.thread_id, checkpoint_id=position.checkpoint_id
        )
        saved = await read_context_checkpoint(
            self.checkpointer, thread_id=position.thread_id, checkpoint_id=position.checkpoint_id
        )
        original = await read_saved_turn_context(self.checkpointer, writer.scope)
        step = inspect_response_step(
            restore_response(saved.checkpoint["channel_values"]["response_snapshot"])
        )
        reply = "\n\n".join(
            part.text if part.type == "output_text" else part.refusal
            for message in step.messages
            if message.phase == "final_answer"
            for part in message.content
        )
        plan = (
            await InterviewPlanWorkflow(self.sessions).read_current(writer.scope)
            if original.plan_position is not None
            else None
        )
        if original.plan_position is not None and plan is None:
            raise PlanStateError("The completed Turn's original plan is unavailable")
        return await ConsultantCompletionWorkflow(self.sessions).recover_completed(
            writer, position, reply, plan.position if plan is not None else None
        )


def _references_enabled(request: ResponseRequest) -> bool:
    """Use the original captured capability bundle, not today's runtime configuration."""
    required = set(OccupationReferenceTools.names)
    declared = [
        tool["name"] for tool in request.create_payload()["tools"] if tool["name"] in required
    ]
    if not declared:
        return False
    if len(declared) != len(required) or set(declared) != required:
        raise ExecutionStateError("The saved Turn has an invalid occupation reference toolkit")
    return True
