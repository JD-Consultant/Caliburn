"""Bind the real JD read/write tools to one isolated research Turn."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from baseline_store import require_research_database
from caliburn.adapters.database import Database
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.jd_item_movement import JdItemMovementWorkflow
from caliburn.workflows.jd_item_revision import JdItemRevisionWorkflow
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True)
class ResearchJdTurn:
    writer: ExecutionWriter
    binding: PublishedMemoryRead
    reads: JdReadTools
    writes: JdWriteTools


async def begin_turn(
    database: Database, file_id: UUID, text: str, *, snapshot_id: UUID | None = None
) -> ResearchJdTurn:
    require_research_database(database)
    accepted = await InterviewInputWorkflow(database.sessions).accept(
        SubmitInterviewInput(file_id, uuid4(), text)
    )
    scope = ExecutionScope(file_id, accepted.accepted.execution_id, ExecutionKind.CONSULTANT_TURN)
    async with database.sessions.begin() as session:
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        await history.bind_context_history(session, writer, AgentRole.JOB_CONSULTANT)
        frontier = await interviews.read_history_frontier(session, file_id)
    await JdCandidateWorkflow(database.sessions).start(writer)
    binding = PublishedMemoryRead(scope, snapshot_id, frontier)
    sessions = database.sessions
    writes = JdWriteTools(
        JdProfileWriteWorkflow(sessions),
        JdTaskWriteWorkflow(sessions),
        binding,
        writer,
        creations=JdItemCreationWorkflow(sessions),
        revisions=JdItemRevisionWorkflow(sessions),
        deletions=JdItemDeletionWorkflow(sessions),
        movements=JdItemMovementWorkflow(sessions),
    )
    return ResearchJdTurn(writer, binding, JdReadTools(JdReadWorkflow(sessions), binding), writes)
