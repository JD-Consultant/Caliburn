"""Delete one candidate item through existing JD ownership and dependent-reference rules."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service, revision_editing
from caliburn.features.job_description.areas import DeleteArea, EditJdAreas, ResponsibilityArea
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityInUseError,
    DeleteCapability,
    EditJdCapabilities,
)
from caliburn.features.job_description.collaborators import (
    Collaborator,
    DeleteCollaborator,
    EditJdCollaborators,
)
from caliburn.features.job_description.conditions import (
    DeleteCondition,
    EditJdConditions,
    JobCondition,
)
from caliburn.features.job_description.item_results import JdItemDeletionResult
from caliburn.features.job_description.navigation import resolve_jd_read_ref
from caliburn.features.job_description.sources import InvalidJdSourceError
from caliburn.features.job_description.tasks import DeleteTask, EditJdTasks, WorkTask
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_candidates import apply_candidate_edit
from caliburn.workflows.memory_reads import PublishedMemoryRead

type DeletionCommand = (
    EditJdAreas | EditJdTasks | EditJdCapabilities | EditJdCollaborators | EditJdConditions
)


@dataclass(frozen=True, slots=True)
class PreparedItemDeletion:
    candidate: JdCandidateScope
    command: DeletionCommand
    detached_task_count: int


class JdItemDeletionWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self, binding: PublishedMemoryRead, *, command_id: UUID, read_ref: str
    ) -> PreparedItemDeletion:
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            target = resolve_jd_read_ref(preview.work, read_ref)
            revision = preview.position.revision_id
            command: DeletionCommand
            detached_task_count = 0
            match target:
                case ResponsibilityArea():
                    command = EditJdAreas(command_id, revision, DeleteArea(target.area_id))
                    detached_task_count = sum(
                        task.area_id == target.area_id for task in preview.work.tasks
                    )
                case WorkTask():
                    command = EditJdTasks(command_id, revision, DeleteTask(target.task_id))
                case Capability():
                    if any(
                        link.capability_id == target.capability_id
                        for link in preview.work.task_links
                    ):
                        raise CapabilityInUseError(
                            "Unlink existing task uses before deleting the definition"
                        )
                    command = EditJdCapabilities(
                        command_id, revision, DeleteCapability(target.capability_id)
                    )
                case Collaborator():
                    command = EditJdCollaborators(
                        command_id, revision, DeleteCollaborator(target.collaborator_id)
                    )
                case JobCondition():
                    command = EditJdConditions(
                        command_id, revision, DeleteCondition(target.condition_id)
                    )
                case _:
                    raise InvalidJdSourceError(
                        "Remove task details through revise_jd_item on their task"
                    )
            return PreparedItemDeletion(preview.position.scope, command, detached_task_count)

    async def execute(
        self, writer: ExecutionWriter, prepared: PreparedItemDeletion
    ) -> JdItemDeletionResult:
        if writer.scope.execution_id != prepared.candidate.execution_id:
            raise ExecutionStateError("This prepared edit belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            revision = await apply_candidate_edit(
                session, file_id, prepared.candidate, prepared.command
            )
            return JdItemDeletionResult(revision, prepared.detached_task_count)
