"""Coordinate human JD writes with existing file scope and execution admission."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as execution_service
from caliburn.features.job_description import (
    area_service,
    capability_service,
    collaborator_service,
    condition_service,
    queries,
    service,
    task_service,
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
        return await self._edit_manually(
            job_file_id,
            command,
            recover=service.recover_profile_result,
            apply=service.revise_profile,
        )

    async def read_areas(self, job_file_id: UUID) -> JdAreasRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await area_service.read_areas(session, job_file_id)

    async def edit_areas(self, job_file_id: UUID, command: EditJdAreas) -> JdAreasRevision:
        return await self._edit_manually(
            job_file_id,
            command,
            recover=area_service.recover_area_result,
            apply=area_service.edit_areas,
        )

    async def read_tasks(self, job_file_id: UUID) -> JdTasksRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await task_service.read_tasks(session, job_file_id)

    async def read_work(self, job_file_id: UUID) -> JdWorkRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await read_work(session, job_file_id)

    async def edit_tasks(self, job_file_id: UUID, command: EditJdTasks) -> JdTasksRevision:
        return await self._edit_manually(
            job_file_id,
            command,
            recover=task_service.recover_task_result,
            apply=task_service.edit_tasks,
        )

    async def read_capabilities(self, job_file_id: UUID) -> JdCapabilitiesRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await capability_service.read_capabilities(session, job_file_id)

    async def edit_capabilities(
        self, job_file_id: UUID, command: EditJdCapabilities
    ) -> JdCapabilitiesRevision:
        return await self._edit_manually(
            job_file_id,
            command,
            recover=capability_service.recover_capability_result,
            apply=capability_service.edit_capabilities,
        )

    async def read_collaborators(self, job_file_id: UUID) -> JdCollaboratorsRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await collaborator_service.read_collaborators(session, job_file_id)

    async def edit_collaborators(
        self, job_file_id: UUID, command: EditJdCollaborators
    ) -> JdCollaboratorsRevision:
        return await self._edit_manually(
            job_file_id,
            command,
            recover=collaborator_service.recover_collaborator_result,
            apply=collaborator_service.edit_collaborators,
        )

    async def read_conditions(self, job_file_id: UUID) -> JdConditionsRevision:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            return await condition_service.read_conditions(session, job_file_id)

    async def edit_conditions(
        self, job_file_id: UUID, command: EditJdConditions
    ) -> JdConditionsRevision:
        return await self._edit_manually(
            job_file_id,
            command,
            recover=condition_service.recover_condition_result,
            apply=condition_service.edit_conditions,
        )

    async def _edit_manually[Command, Revision](
        self,
        job_file_id: UUID,
        command: Command,
        *,
        recover: Callable[[AsyncSession, UUID, Command], Awaitable[Revision | None]],
        apply: Callable[[AsyncSession, UUID, Command], Awaitable[Revision]],
    ) -> Revision:
        """One transaction per call; recover an original result before new-write admission."""
        async with self.sessions.begin() as session:
            await file_service.lock_job_file(session, job_file_id)
            original = await recover(session, job_file_id, command)
            if original is not None:
                return original
            await execution_service.require_manual_edit_allowed(session, job_file_id)
            return await apply(session, job_file_id, command)
