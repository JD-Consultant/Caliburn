"""Persist the App-authored opening; not a public arbitrary formalization operation."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import persistence
from caliburn.features.interviews.opening import OPENING_TEXT


async def create_opening(session: AsyncSession, job_file_id: UUID) -> None:
    await persistence.insert_opening(
        session, job_file_id=job_file_id, source_id=uuid4(), interview_text=OPENING_TEXT
    )
