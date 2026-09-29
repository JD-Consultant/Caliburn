"""Pin a formal revision once before reading related JD collections and links."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    persistence,
    task_persistence,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability, TaskCapabilityLink
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.tasks import WorkTask


@dataclass(frozen=True, slots=True)
class JdWorkRevision:
    revision_id: UUID
    areas: tuple[ResponsibilityArea, ...]
    tasks: tuple[WorkTask, ...]
    capabilities: tuple[Capability, ...]
    task_links: tuple[TaskCapabilityLink, ...]
    collaborators: tuple[Collaborator, ...]
    conditions: tuple[JobCondition, ...]


async def read_work(session: AsyncSession, job_file_id: UUID) -> JdWorkRevision:
    document = await persistence.read_document(session, job_file_id)
    revision_id = document.current_revision_id
    return JdWorkRevision(
        revision_id,
        await area_persistence.read_areas(session, job_file_id, revision_id),
        await task_persistence.read_tasks(session, job_file_id, revision_id),
        await capability_persistence.read_capabilities(session, job_file_id, revision_id),
        await capability_persistence.read_task_links(session, job_file_id, revision_id),
        await collaborator_persistence.read_collaborators(session, job_file_id, revision_id),
        await condition_persistence.read_conditions(session, job_file_id, revision_id),
    )
