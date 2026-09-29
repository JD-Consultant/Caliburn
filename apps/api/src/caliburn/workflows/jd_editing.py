"""Coordinate human JD writes with existing file scope and execution admission."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as execution_service
from caliburn.features.job_description import (
    area_service,
    capability_service,
    queries,
    service,
    task_service,
)
from caliburn.features.job_description.areas import EditJdAreas, JdAreasRevision
from caliburn.features.job_description.capabilities import (
    EditJdCapabilities,
    JdCapabilitiesRevision,
)
from caliburn.features.job_description.models import JdProfileRevision, ReviseJdProfile
from caliburn.features.job_description.tasks import EditJdTasks, JdTasksRevision
from caliburn.features.job_description.work_queries import JdWorkRevision, read_work
from caliburn.features.job_files import queries as file_queries
from caliburn.features.job_files import service as file_service


class JdEditingWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_profile(self, job_file_id: UUID) -> JdProfileRevision:
        async with self.sessions() as session:
            await file_queries.read_job_file(session, job_file_id)
            return await queries.read_profile(session, job_file_id)

    async def revise_profile(
        self, job_file_id: UUID, command: ReviseJdProfile
    ) -> JdProfileRevision:
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await service.recover_profile_result(session, job_file_id, command)
            if original is not None:
                return original
            await execution_service.require_manual_edit_allowed(session, job_file_id)
            return await service.revise_profile(session, job_file_id, command)

    async def read_areas(self, job_file_id: UUID) -> JdAreasRevision:
        async with self.sessions() as session:
            await file_queries.read_job_file(session, job_file_id)
            return await area_service.read_areas(session, job_file_id)

    async def edit_areas(self, job_file_id: UUID, command: EditJdAreas) -> JdAreasRevision:
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await area_service.recover_area_result(session, job_file_id, command)
            if original is not None:
                return original
            await execution_service.require_manual_edit_allowed(session, job_file_id)
            return await area_service.edit_areas(session, job_file_id, command)

    async def read_tasks(self, job_file_id: UUID) -> JdTasksRevision:
        async with self.sessions() as session:
            await file_queries.read_job_file(session, job_file_id)
            return await task_service.read_tasks(session, job_file_id)

    async def read_work(self, job_file_id: UUID) -> JdWorkRevision:
        async with self.sessions() as session:
            await file_queries.read_job_file(session, job_file_id)
            return await read_work(session, job_file_id)

    async def edit_tasks(self, job_file_id: UUID, command: EditJdTasks) -> JdTasksRevision:
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await task_service.recover_task_result(session, job_file_id, command)
            if original is not None:
                return original
            await execution_service.require_manual_edit_allowed(session, job_file_id)
            return await task_service.edit_tasks(session, job_file_id, command)

    async def read_capabilities(self, job_file_id: UUID) -> JdCapabilitiesRevision:
        async with self.sessions() as session:
            await file_queries.read_job_file(session, job_file_id)
            return await capability_service.read_capabilities(session, job_file_id)

    async def edit_capabilities(
        self, job_file_id: UUID, command: EditJdCapabilities
    ) -> JdCapabilitiesRevision:
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await capability_service.recover_capability_result(
                session, job_file_id, command
            )
            if original is not None:
                return original
            await execution_service.require_manual_edit_allowed(session, job_file_id)
            return await capability_service.edit_capabilities(session, job_file_id, command)
