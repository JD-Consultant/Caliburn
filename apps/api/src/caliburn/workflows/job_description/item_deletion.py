"""Delete one candidate item through existing JD ownership and dependent-reference rules."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import retry_database_operation
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service, revision_editing
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.item_deletion import DeletionCommand, prepare_item_deletion
from caliburn.features.job_description.item_results import JdItemDeletionResult
from caliburn.features.job_files import service as job_files
from caliburn.workflows.job_description.candidates import apply_candidate_edit


@dataclass(frozen=True, slots=True)
class PreparedItemDeletion:
    candidate: JdCandidateScope
    command: DeletionCommand
    detached_task_count: int


class JdItemDeletionWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self, scope: ExecutionScope, *, command_id: UUID, read_ref: str
    ) -> PreparedItemDeletion:
        async with self.sessions() as session:
            if (await executions.read_execution(session, scope)).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, scope.job_file_id, scope.execution_id
            )
            command, detached_task_count = prepare_item_deletion(
                preview.work, command_id=command_id, read_ref=read_ref
            )
            return PreparedItemDeletion(preview.position.scope, command, detached_task_count)

    @retry_database_operation
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
