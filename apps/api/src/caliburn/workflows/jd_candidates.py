"""A-only candidate coordination; no public completion endpoint or model-selected versions."""

from dataclasses import replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import (
    area_service,
    candidate_service,
    capability_service,
    collaborator_service,
    condition_service,
    revision_editing,
    service,
    source_service,
    task_service,
)
from caliburn.features.job_description.areas import EditJdAreas
from caliburn.features.job_description.candidate_service import JdCandidatePreview
from caliburn.features.job_description.candidates import (
    CandidateStateError,
    JdCandidatePosition,
    JdCandidateScope,
)
from caliburn.features.job_description.capabilities import EditJdCapabilities
from caliburn.features.job_description.collaborators import EditJdCollaborators
from caliburn.features.job_description.conditions import EditJdConditions
from caliburn.features.job_description.models import ReviseJdProfile
from caliburn.features.job_description.sources import ReviseJdSources
from caliburn.features.job_description.tasks import EditJdTasks
from caliburn.features.job_files import service as job_files

type JdCandidateEdit = (
    ReviseJdProfile
    | EditJdAreas
    | EditJdTasks
    | EditJdCapabilities
    | EditJdCollaborators
    | EditJdConditions
    | ReviseJdSources
)


def _require_consultant(scope: ExecutionScope) -> None:
    if scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only a consultant Turn can use a JD candidate")


class JdCandidateWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def start(self, writer: ExecutionWriter) -> JdCandidatePosition:
        _require_consultant(writer.scope)
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            return await candidate_service.start_candidate(
                session, writer.scope.job_file_id, writer.scope.execution_id
            )

    async def read(self, scope: ExecutionScope) -> JdCandidatePreview:
        _require_consultant(scope)
        async with consistent_read_session(self.sessions) as session:
            execution = await executions.read_execution(session, scope)
            if execution.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
                raise ExecutionStateError("This execution no longer has a live preview")
            return await candidate_service.read_preview(
                session, scope.job_file_id, scope.execution_id
            )

    async def edit(
        self, writer: ExecutionWriter, candidate: JdCandidateScope, command: JdCandidateEdit
    ) -> JdCandidatePosition:
        _require_consultant(writer.scope)
        if candidate.execution_id != writer.scope.execution_id:
            raise CandidateStateError("Candidate does not belong to the executing Turn")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(
                session, writer.scope.job_file_id, candidate
            )
            result_revision = await apply_candidate_edit(
                session, writer.scope.job_file_id, candidate, command
            )
            position = await candidate_service.read_position(
                session, writer.scope.job_file_id, candidate.execution_id
            )
            # A replay returns its original result, not the current preview.
            return replace(position, revision_id=result_revision)

    async def restore(
        self,
        writer: ExecutionWriter,
        position: JdCandidatePosition,
        target_revision_id: UUID,
        command_id: UUID,
    ) -> JdCandidatePosition:
        _require_position_owner(writer, position)
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            return await candidate_service.restore_candidate(
                session, writer.scope.job_file_id, position, target_revision_id, command_id
            )

    async def discard(
        self, writer: ExecutionWriter, position: JdCandidatePosition, command_id: UUID
    ) -> JdCandidatePosition:
        """JD-only primitive; T08 must join execution termination in the same transaction."""
        _require_position_owner(writer, position)
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_unfinished_writer(session, writer)
            return await candidate_service.discard_candidate(
                session, writer.scope.job_file_id, position, command_id
            )


def _require_position_owner(writer: ExecutionWriter, position: JdCandidatePosition) -> None:
    _require_consultant(writer.scope)
    if writer.scope.execution_id != position.scope.execution_id:
        raise CandidateStateError("Candidate belongs to a different Turn")


async def apply_candidate_edit(
    session: AsyncSession, job_file_id: UUID, candidate: JdCandidateScope, command: JdCandidateEdit
) -> UUID:
    """Reuse typed field rules after caller acquires the file/writer/candidate guards."""
    if isinstance(command, ReviseJdSources):
        original = await source_service.recover_source_result(
            session, job_file_id, command, candidate=candidate
        )
        if original is not None:
            return original
        return await source_service.revise_sources(
            session, job_file_id, command, candidate=candidate
        )
    if isinstance(command, ReviseJdProfile):
        profile = await service.recover_profile_result(
            session, job_file_id, command, candidate=candidate
        )
        if profile is None:
            profile = await service.revise_profile(
                session, job_file_id, command, candidate=candidate
            )
        return profile.revision_id
    if isinstance(command, EditJdAreas):
        areas = await area_service.recover_area_result(
            session, job_file_id, command, candidate=candidate
        )
        if areas is None:
            areas = await area_service.edit_areas(
                session, job_file_id, command, candidate=candidate
            )
        return areas.revision_id
    if isinstance(command, EditJdTasks):
        tasks = await task_service.recover_task_result(
            session, job_file_id, command, candidate=candidate
        )
        if tasks is None:
            tasks = await task_service.edit_tasks(
                session, job_file_id, command, candidate=candidate
            )
        return tasks.revision_id
    if isinstance(command, EditJdCapabilities):
        capabilities = await capability_service.recover_capability_result(
            session, job_file_id, command, candidate=candidate
        )
        if capabilities is None:
            capabilities = await capability_service.edit_capabilities(
                session, job_file_id, command, candidate=candidate
            )
        return capabilities.revision_id
    if isinstance(command, EditJdCollaborators):
        collaborators = await collaborator_service.recover_collaborator_result(
            session, job_file_id, command, candidate=candidate
        )
        if collaborators is None:
            collaborators = await collaborator_service.edit_collaborators(
                session, job_file_id, command, candidate=candidate
            )
        return collaborators.revision_id
    if isinstance(command, EditJdConditions):
        conditions = await condition_service.recover_condition_result(
            session, job_file_id, command, candidate=candidate
        )
        if conditions is None:
            conditions = await condition_service.edit_conditions(
                session, job_file_id, command, candidate=candidate
            )
        return conditions.revision_id
    raise TypeError("Unsupported JD candidate edit")


async def adopt_candidate_jd(
    session: AsyncSession, writer: ExecutionWriter, position: JdCandidatePosition, command_id: UUID
) -> JdCandidatePosition:
    """Join the future A completion transaction; do not commit or finish the Turn here."""
    _require_position_owner(writer, position)
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    original = await candidate_service.recover_adoption(
        session, writer.scope.job_file_id, position, command_id
    )
    if original is not None:
        execution = await executions.read_execution(session, writer.scope)
        if execution.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.COMPLETED):
            raise ExecutionStateError("A JD adoption cannot belong to a cancelled or failed Turn")
        return original
    await executions.lock_active_writer(session, writer)
    return await candidate_service.adopt_candidate(
        session, writer.scope.job_file_id, position, command_id
    )
