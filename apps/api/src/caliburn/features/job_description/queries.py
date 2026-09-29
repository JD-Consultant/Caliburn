"""Read the formal JD at a fixed head; never create missing data from a GET."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import persistence
from caliburn.features.job_description.models import JdProfileRevision


async def read_profile(session: AsyncSession, job_file_id: UUID) -> JdProfileRevision:
    document = await persistence.read_document(session, job_file_id)
    return await persistence.read_revision(session, job_file_id, document.current_revision_id)
