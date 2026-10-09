"""Coordinate job-file creation, metadata and whole-file deletion transactions."""

from contextlib import AsyncExitStack
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.graph_checkpointer import delete_job_file_checkpoints
from caliburn.features.executions import service as execution_service
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.interviews import queries as interview_queries
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import InterviewHistoryEntry
from caliburn.features.job_description import service as jd_service
from caliburn.features.job_files import queries as job_file_queries
from caliburn.features.job_files import service as job_file_service
from caliburn.features.job_files.models import (
    CreateJobFile,
    JobFile,
    JobFileCreation,
    JobFileNotFoundError,
    RenameJobFile,
)
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.memory_supervisor import MemorySupervisor


class JobFileWorkflow:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        consultant_supervisor: ConsultantSupervisor | None = None,
        memory_supervisor: MemorySupervisor | None = None,
    ) -> None:
        self.sessions = sessions
        self.consultant_supervisor = consultant_supervisor
        self.memory_supervisor = memory_supervisor

    async def create(self, command: CreateJobFile) -> JobFileCreation:
        async with self.sessions.begin() as session:
            result = await job_file_service.create_job_file(session, command)
            if result.is_new:
                await interview_service.create_opening(session, result.job_file.job_file_id)
                await jd_service.create_empty_jd(session, result.job_file.job_file_id)
        return result

    async def list_files(self) -> list[JobFile]:
        async with self.sessions() as session:
            return await job_file_queries.list_job_files(session)

    async def rename(self, job_file_id: UUID, command: RenameJobFile) -> JobFile:
        async with self.sessions.begin() as session:
            return await job_file_service.rename_job_file(session, job_file_id, command)

    async def read_file(self, job_file_id: UUID) -> JobFile:
        async with self.sessions() as session:
            return await job_file_queries.read_job_file(session, job_file_id)

    async def delete(self, job_file_id: UUID) -> None:
        # SQL terminal state is not proof that a local invocation has exited.
        # Hold the existing dispatch gates until commit; never wait for a runner
        # while holding the job row it may need for its own final settlement.
        async with AsyncExitStack() as dispatch:
            if self.consultant_supervisor is not None:
                await dispatch.enter_async_context(self.consultant_supervisor.hold_dispatch())
                if self.consultant_supervisor.has_file_runner(job_file_id):
                    raise ExecutionBusyError("The consultant invocation is still finishing")
            if self.memory_supervisor is not None:
                await dispatch.enter_async_context(self.memory_supervisor.hold_dispatch())
                if self.memory_supervisor.has_file_runner(job_file_id):
                    raise ExecutionBusyError("The Memory invocation is still finishing")
            async with self.sessions.begin() as session:
                try:
                    await job_file_service.lock_job_file(session, job_file_id)
                except JobFileNotFoundError:
                    pass  # A repeated confirmed deletion also releases local remnants.
                else:
                    await execution_service.require_file_deletion_allowed(session, job_file_id)
                    await job_file_service.delete_job_file(session, job_file_id)
                    await delete_job_file_checkpoints(session, job_file_id)
            if self.consultant_supervisor is not None:
                self.consultant_supervisor.forget_deleted_file(job_file_id)
            if self.memory_supervisor is not None:
                self.memory_supervisor.forget_deleted_file(job_file_id)

    async def read_interviews(self, job_file_id: UUID) -> list[InterviewHistoryEntry]:
        async with self.sessions() as session:
            await job_file_queries.read_job_file(session, job_file_id)
            return await interview_queries.read_public_interview_history(session, job_file_id)
