"""Research-only composition of the product's native loop and formal completion."""

from dataclasses import dataclass
from uuid import UUID

from baseline_store import require_research_database
from caliburn.adapters.database import Database
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import restore_response
from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    ReceivedCompaction,
    bind_window_compaction,
)
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agent_execution.response_steps import inspect_response_step
from caliburn.agent_execution.tool_steps import (
    PausedResponseLoop,
    ResponseStepRuntime,
    run_response_loop,
)
from caliburn.features.executions import history
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import JdChangesWorkflow
from caliburn.workflows.memory_reads import MemoryReadWorkflow
from caliburn.workflows.model_runtime import bind_model_runtime, fix_execution_policy
from jd_workspace import begin_turn
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from study_context import StudyArm, append_turn_input, initial_reference
from study_tools import StudyTools
from study_window import StudyCapacityError, fit_raw_reset


@dataclass(frozen=True)
class StudyRunner:
    database: Database
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings
    instructions: str

    async def run(
        self,
        file_id: UUID,
        *,
        arm: StudyArm,
        employee_input: str,
        snapshot_id: UUID | None = None,
    ) -> FormalInterviewExchange:
        require_research_database(self.database)
        if arm not in {"raw", "summary", "memory"} or (arm == "memory") != (
            snapshot_id is not None
        ):
            raise ValueError("Only the Memory arm may bind a published snapshot")
        if self.settings.model != "gpt-6-luna" or self.settings.reasoning_effort != "high":
            raise ValueError("This study fixes Luna/high")
        if self.settings.max_output_tokens != 16_384:
            raise ValueError("All arms reserve the same 16,384 output tokens")
        turn = await begin_turn(self.database, file_id, employee_input, snapshot_id=snapshot_id)
        sessions = self.database.sessions
        role = RoleContextHistory(
            sessions, turn.writer, AgentRole.JOB_CONSULTANT, self.checkpointer
        )
        policy = await fix_execution_policy(sessions, turn.writer, self.settings)
        model = bind_model_runtime(
            sessions, turn.writer, self.client, self.settings, ensure_active=role.ensure_active
        )
        memory = MemoryReadTools(MemoryReadWorkflow(sessions), turn.binding)
        candidate = await JdCandidateWorkflow(sessions).read(turn.writer.scope)
        changes = JdChangesTools(
            JdChangesWorkflow(sessions),
            turn.binding,
            manual_jd_start_revision_id=candidate.position.base_revision_id,
        )
        tools = StudyTools(turn, memory, changes, arm)
        template = ResponseRequest(
            model=self.settings.model,
            instructions=self.instructions,
            input_items=[],
            tools=tools.definitions(),
            reasoning_effort=self.settings.reasoning_effort,
            max_output_tokens=self.settings.max_output_tokens,
        )
        async with sessions() as session:
            binding = await history.read_context_history(session, turn.writer.scope, role.role)
        if binding is None:
            raise ValueError("Missing research history binding")
        is_first = binding.base is None

        async def count_history(request: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
            count = await model.executor.count_input(request, request_id)
            if count["input_tokens"] >= 128_000:
                raise StudyCapacityError("second_pre_work_reset_required")
            return count

        async def no_pre_work_compaction(
            request: ResponseRequest, request_id: UUID
        ) -> ReceivedCompaction:
            raise StudyCapacityError("pre_work_native_compaction_not_allowed")

        prepared = await role.prepare_history(
            template=template,
            threshold_tokens=128_000,
            count_input=count_history,
            runtime=CompactionRuntime(
                no_pre_work_compaction,
                model.compaction.account_compaction,
                role.ensure_active,
                model.capacity_limits,
            ),
        )
        reference: dict[str, object] = (
            await initial_reference(self.database, turn, arm, memory)
            if is_first
            else {
                "data_kind": "research_turn_reference",
            }
        )
        # New formal sequence identities are control data, not duplicated old interview text.
        reference["interview_read_boundary"] = {
            "through_sequence": turn.binding.interview_through_sequence
        }
        request = ResponseRequest.from_snapshot(
            {
                **template.create_payload(),
                "input": append_turn_input(prepared, reference, employee_input),
            }
        )
        if is_first and arm == "raw":
            request = await fit_raw_reset(request, model.executor.count_input)
        first_input = request.create_payload()["input"]

        async def count_step(current: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
            count = await model.executor.count_input(current, request_id)
            if current.create_payload()["input"] == first_input and count["input_tokens"] > 128_000:
                # S/M cannot be shortened; later turns cannot introduce a second reset.
                raise StudyCapacityError("starting_request_exceeds_study_budget")
            return count

        runtime = ResponseStepRuntime(
            request_model=model.executor.request_model,
            prepare_tool=tools.prepare,
            execute_tool=tools.execute,
            ensure_active=role.ensure_active,
            account_response=model.executor.account_response,
            count_input=count_step,
            capacity_limits=model.capacity_limits,
            compact_window=bind_window_compaction(
                self.checkpointer,
                response_thread_id=role.response_thread_id,
                runtime=model.compaction,
                recovery=None,
            ),
        )
        result = await run_response_loop(
            self.checkpointer,
            thread_id=role.response_thread_id,
            request=request,
            runtime=runtime,
            max_tool_calls=self.settings.max_tool_calls_per_step,
            max_model_steps=policy.max_model_steps,
        )
        if isinstance(result, PausedResponseLoop):
            raise ValueError("The research runner did not enable pause controls")
        step = inspect_response_step(restore_response(result["response_snapshot"]))
        reply = "\n\n".join(
            part.text if part.type == "output_text" else part.refusal
            for message in step.messages
            if message.phase == "final_answer"
            for part in message.content
        )
        position = await role.read_completed_position()
        current = await JdCandidateWorkflow(sessions).read(turn.writer.scope)
        return await ConsultantCompletionWorkflow(sessions).complete(
            turn.writer, current.position, reply, position
        )
