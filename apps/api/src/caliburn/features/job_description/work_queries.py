"""Pin a formal revision once before reading related responsibility/task collections."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import area_persistence, persistence, task_persistence
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.tasks import WorkTask


@dataclass(frozen=True, slots=True)
class JdWorkRevision:
    revision_id: UUID
    areas: tuple[ResponsibilityArea, ...]
    tasks: tuple[WorkTask, ...]


async def read_work(session: AsyncSession, job_file_id: UUID) -> JdWorkRevision:
    document = await persistence.read_document(session, job_file_id)
    revision_id = document.current_revision_id
    return JdWorkRevision(
        revision_id,
        await area_persistence.read_areas(session, job_file_id, revision_id),
        await task_persistence.read_tasks(session, job_file_id, revision_id),
    )
