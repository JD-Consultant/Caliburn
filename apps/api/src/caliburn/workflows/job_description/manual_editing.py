"""Coordinate human JD writes with existing file scope and execution admission."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as execution_service
from caliburn.features.job_description import (
    queries,
    revision_editing,
)
from caliburn.features.job_description.areas import EditJdAreas, JdAreasRevision
from caliburn.features.job_description.capabilities import (
    EditJdCapabilities,
    JdCapabilitiesRevision,
)
from caliburn.features.job_description.collaborators import (
    EditJdCollaborators,
    JdCollaboratorsRevision,
)
from caliburn.features.job_description.conditions import EditJdConditions, JdConditionsRevision
from caliburn.features.job_description.edit_changes import JdContentEdit
from caliburn.features.job_description.models import JdProfileRevision, ReviseJdProfile
from caliburn.features.job_description.tasks import EditJdTasks, JdTasksRevision
from caliburn.features.job_description.work_models import JdWorkRevision
from caliburn.features.job_description.work_queries import read_work
from caliburn.features.job_files import queries as file_queries
from caliburn.features.job_files import service as file_service


class JdEditingWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_profile(self, job_file_id: UUID) -> JdProfileRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_profile(session, job_file_id)

    async def revise_profile(
        self, job_file_id: UUID, command: ReviseJdProfile
    ) -> JdProfileRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_profile_at(session, job_file_id, revision)

    async def read_areas(self, job_file_id: UUID) -> JdAreasRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_areas(session, job_file_id)

    async def edit_areas(self, job_file_id: UUID, command: EditJdAreas) -> JdAreasRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_areas_at(session, job_file_id, revision)

    async def read_tasks(self, job_file_id: UUID) -> JdTasksRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_tasks(session, job_file_id)

    async def read_work(self, job_file_id: UUID) -> JdWorkRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await read_work(session, job_file_id)

    async def edit_tasks(self, job_file_id: UUID, command: EditJdTasks) -> JdTasksRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_tasks_at(session, job_file_id, revision)

    async def read_capabilities(self, job_file_id: UUID) -> JdCapabilitiesRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_capabilities(session, job_file_id)

    async def edit_capabilities(
        self, job_file_id: UUID, command: EditJdCapabilities
    ) -> JdCapabilitiesRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_capabilities_at(session, job_file_id, revision)

    async def read_collaborators(self, job_file_id: UUID) -> JdCollaboratorsRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_collaborators(session, job_file_id)

    async def edit_collaborators(
        self, job_file_id: UUID, command: EditJdCollaborators
    ) -> JdCollaboratorsRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_collaborators_at(session, job_file_id, revision)

    async def read_conditions(self, job_file_id: UUID) -> JdConditionsRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_conditions(session, job_file_id)

    async def edit_conditions(
        self, job_file_id: UUID, command: EditJdConditions
    ) -> JdConditionsRevision:
        async with self._edit_manually(job_file_id, command) as (session, revision):
            return await queries.read_conditions_at(session, job_file_id, revision)

    @asynccontextmanager
    async def _edit_manually(
        self,
        job_file_id: UUID,
        command: JdContentEdit,
    ) -> AsyncIterator[tuple[AsyncSession, UUID]]:
        """同一交易內先回復原結果，再准入新人工編輯。"""
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await revision_editing.recover_content_edit(session, job_file_id, command)
            if original is not None:
                revision = original
            else:
                await execution_service.require_manual_edit_allowed(session, job_file_id)
                revision = await revision_editing.apply_content_edit(session, job_file_id, command)
            yield session, revision
