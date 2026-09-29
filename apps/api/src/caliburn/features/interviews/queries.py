"""Formal history only; execution originals without formal membership stay invisible."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews.models import InterviewMessage
from caliburn.features.interviews.persistence import list_formal_interviews


async def read_interview_history(
    session: AsyncSession, job_file_id: UUID
) -> list[InterviewMessage]:
    return await list_formal_interviews(session, job_file_id)
