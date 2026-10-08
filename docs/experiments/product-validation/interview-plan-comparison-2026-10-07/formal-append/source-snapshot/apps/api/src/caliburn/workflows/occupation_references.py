"""Reference tools: explicit work exclusions and qualified per-Turn state."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_files import service as job_files
from caliburn.features.occupation_references import service
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateError,
    ReferenceStatePosition,
    select_references,
    update_excluded_work,
)
from caliburn.workflows.occupation_reference_reads import read_formal_reference_state


@dataclass(frozen=True, slots=True)
class ReferenceStateChange:
    job_file_id: UUID
    operation_id: UUID
    position: ReferenceStatePosition
    state: OccupationReferenceState


class OccupationReferenceWorkflow:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], client: OccupationReferenceClient
    ) -> None:
        self.sessions = sessions
        self.client = client

    async def start(self, writer: ExecutionWriter) -> ReferenceStatePosition:
        _require_consultant(writer)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            current = await service.read_candidate(
                session, writer.scope.job_file_id, writer.scope.execution_id
            )
            if current is not None:
                return current
            frontier = await interviews.read_history_frontier(session, writer.scope.job_file_id)
            base = await read_formal_reference_state(
                session, InterviewReadScope(writer.scope.job_file_id, frontier)
            )
            return await service.start_candidate(
                session, writer.scope.job_file_id, writer.scope.execution_id, base
            )

    async def read(self, writer: ExecutionWriter) -> dict[str, object]:
        _require_consultant(writer)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            position = await _position(session, writer)
            return _project(position.state)

    async def prepare_select(
        self, writer: ExecutionWriter, reference_ids: tuple[str, ...], operation_id: UUID
    ) -> ReferenceStateChange:
        _require_consultant(writer)
        # Validate public identities outside the database transaction. The saved change
        # can subsequently replay without repeating an external service request.
        selection = select_references(OccupationReferenceState(), reference_ids)
        for reference_id in selection.selected_reference_ids or ():
            await self.client.read(reference_id)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            position = await _position(session, writer)
            return ReferenceStateChange(
                writer.scope.job_file_id,
                operation_id,
                position,
                select_references(position.state, reference_ids),
            )

    async def prepare_excluded_work(
        self,
        writer: ExecutionWriter,
        add: tuple[str, ...],
        remove: tuple[str, ...],
        operation_id: UUID,
    ) -> ReferenceStateChange:
        _require_consultant(writer)
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            position = await _position(session, writer)
            state = update_excluded_work(position.state, add, remove)
            return ReferenceStateChange(writer.scope.job_file_id, operation_id, position, state)

    async def execute(
        self, writer: ExecutionWriter, change: ReferenceStateChange
    ) -> dict[str, object]:
        _require_consultant(writer)
        if (change.job_file_id, change.position.execution_id) != (
            writer.scope.job_file_id,
            writer.scope.execution_id,
        ):
            raise ReferenceStateError("A saved reference change belongs to another Turn")
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            result = await service.apply_state(
                session,
                writer.scope.job_file_id,
                change.position,
                change.operation_id,
                change.state,
            )
            return _project(result.state)

    async def restore(
        self,
        writer: ExecutionWriter,
        position: ReferenceStatePosition,
        target_revision_id: UUID,
        operation_id: UUID,
    ) -> ReferenceStatePosition:
        _require_consultant(writer)
        if position.execution_id != writer.scope.execution_id:
            raise ReferenceStateError("Reference position belongs to another Turn")
        async with self.sessions.begin() as session:
            await _lock_writer(session, writer)
            return await service.restore_candidate(
                session, writer.scope.job_file_id, position, target_revision_id, operation_id
            )


def _require_consultant(writer: ExecutionWriter) -> None:
    if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only a consultant Turn can use reference state")


async def _lock_writer(session: AsyncSession, writer: ExecutionWriter) -> None:
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    await executions.lock_active_writer(session, writer)


async def _position(session: AsyncSession, writer: ExecutionWriter) -> ReferenceStatePosition:
    position = await service.read_candidate(
        session, writer.scope.job_file_id, writer.scope.execution_id
    )
    if position is None:
        raise ReferenceStateError("Start the reference candidate before using state tools")
    return position


def _project(state: OccupationReferenceState) -> dict[str, object]:
    return {
        "selected_reference_ids": list(state.selected_reference_ids)
        if state.selected_reference_ids is not None
        else None,
        "excluded_work": list(state.excluded_work),
    }
