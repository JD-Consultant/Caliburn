"""在檔案建立交易內初始化 JD。"""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import persistence
from caliburn.features.job_description.models import JdProfile, JdProfileRevision


async def create_empty_jd(session: AsyncSession, job_file_id: UUID) -> None:
    """每份新檔案只建立一次初始版本。"""
    initial = JdProfileRevision(uuid4(), JdProfile())
    await persistence.insert_revision(session, job_file_id, initial, parent_revision_id=None)
    session.add(
        persistence.JobDescriptionRecord(
            job_file_id=job_file_id,
            initial_revision_id=initial.revision_id,
            current_revision_id=initial.revision_id,
        )
    )
    await session.flush()
