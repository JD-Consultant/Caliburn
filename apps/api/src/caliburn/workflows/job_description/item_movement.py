"""Move a scoped JD candidate item without replacing identities or evidence."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import retry_database_operation
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service, revision_editing
from caliburn.features.job_description.areas import (
    EditJdAreas,
    ReviseArea,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.item_movement import (
    ItemMovement,
    MoveItemInput,
    movement_command,
    prepare_item_movement,
)
from caliburn.features.job_description.item_results import JdItemMovementResult
from caliburn.features.job_files import service as job_files
from caliburn.workflows.job_description.candidates import apply_candidate_edit


@dataclass(frozen=True, slots=True)
class PreparedItemMovement:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    movement: ItemMovement
    area_revisions: tuple[ReviseArea, ...]
    detached_from_area: bool


class JdItemMovementWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self, scope: ExecutionScope, *, command_id: UUID, intent: MoveItemInput
    ) -> PreparedItemMovement:
        if scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Only a consultant Turn can move JD items")
        async with self.sessions() as session:
            if (await executions.read_execution(session, scope)).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session,
                scope.job_file_id,
                scope.execution_id,
            )
            prepared = prepare_item_movement(preview.work, intent)
            return PreparedItemMovement(
                command_id,
                preview.position.scope,
                preview.position.revision_id,
                prepared.movement,
                prepared.area_revisions,
                prepared.detached_from_area,
            )

    @retry_database_operation
    async def execute(
        self, writer: ExecutionWriter, prepared: PreparedItemMovement
    ) -> JdItemMovementResult:
        """Apply related commands in one transaction; replay never rewinds the live candidate."""
        if (
            writer.scope.kind != ExecutionKind.CONSULTANT_TURN
            or writer.scope.execution_id != prepared.candidate.execution_id
        ):
            raise ExecutionStateError("This prepared move belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            revision = await apply_candidate_edit(
                session,
                file_id,
                prepared.candidate,
                movement_command(
                    uuid5(prepared.command_id, "move"),
                    prepared.expected_revision_id,
                    prepared.movement,
                ),
            )
            for index, area in enumerate(prepared.area_revisions):
                revision = await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    EditJdAreas(uuid5(prepared.command_id, f"area:{index}"), revision, area),
                )
            return JdItemMovementResult(
                revision,
                "unchanged" if revision == prepared.expected_revision_id else "moved",
                prepared.detached_from_area,
            )
