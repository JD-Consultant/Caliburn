"""Read references select stable JD identities within an already scoped revision."""

from collections.abc import Iterator

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.tasks import TaskDetail, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision

type JdReadTarget = (
    ResponsibilityArea | WorkTask | TaskDetail | Capability | Collaborator | JobCondition
)


class JdReadTargetNotFoundError(ValueError):
    """A reference does not identify an item in the App-bound visible JD."""


def resolve_jd_read_ref(work: JdWorkRevision, read_ref: str) -> JdReadTarget:
    """Resolve only within this revision; a ref is neither a version nor write authority."""
    for target in _read_targets(work):
        if jd_read_ref(target) == read_ref:
            return target
    raise JdReadTargetNotFoundError("No matching JD item in the visible revision")


def jd_read_ref(target: JdReadTarget) -> str:
    """Derive the single locator from existing identity; no registry or display-name lookup."""
    match target:
        case ResponsibilityArea():
            return f"area_{target.area_id.hex}"
        case WorkTask():
            return f"task_{target.task_id.hex}"
        case TaskDetail():
            return f"{target.kind.value}_{target.detail_id.hex}"
        case Capability():
            return f"{target.kind.value}_{target.capability_id.hex}"
        case Collaborator():
            return f"collaborator_{target.collaborator_id.hex}"
        case JobCondition():
            return f"condition_{target.condition_id.hex}"


def _read_targets(work: JdWorkRevision) -> Iterator[JdReadTarget]:
    yield from work.areas
    for task in work.tasks:
        yield task
        yield from task.details
    yield from work.capabilities
    yield from work.collaborators
    yield from work.conditions
