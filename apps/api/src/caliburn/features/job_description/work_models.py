"""Fixed JD work values without storage or framework dependencies."""

from dataclasses import dataclass
from uuid import UUID

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
