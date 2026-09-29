"""Atomically create file metadata and its opening through their respective owners."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.interviews import queries as interview_queries
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import InterviewMessage
from caliburn.features.job_files import queries as job_file_queries
from caliburn.features.job_files import service as job_file_service
from caliburn.features.job_files.models import CreateJobFile, JobFile, JobFileCreation


class JobFileWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create(self, command: CreateJobFile) -> JobFileCreation:
        async with self.sessions.begin() as session:
            result = await job_file_service.create_job_file(session, command)
            if result.is_new:
                await interview_service.create_opening(session, result.job_file.job_file_id)
        return result

    async def list_files(self) -> list[JobFile]:
        async with self.sessions() as session:
            return await job_file_queries.list_job_files(session)

    async def read_file(self, job_file_id: UUID) -> JobFile:
        async with self.sessions() as session:
            return await job_file_queries.read_job_file(session, job_file_id)

    async def read_interviews(self, job_file_id: UUID) -> list[InterviewMessage]:
        async with self.sessions() as session:
            await job_file_queries.read_job_file(session, job_file_id)
            return await interview_queries.read_interview_history(session, job_file_id)
