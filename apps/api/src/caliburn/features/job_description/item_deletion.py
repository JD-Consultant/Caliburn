"""Delete one candidate item through existing JD ownership and dependent-reference rules."""

from uuid import UUID

from caliburn.features.job_description.areas import DeleteArea, EditJdAreas, ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    DeleteCapability,
    EditJdCapabilities,
)
from caliburn.features.job_description.capability_changes import require_unused_capability
from caliburn.features.job_description.collaborators import (
    Collaborator,
    DeleteCollaborator,
    EditJdCollaborators,
)
from caliburn.features.job_description.conditions import (
    DeleteCondition,
    EditJdConditions,
    JobCondition,
)
from caliburn.features.job_description.navigation import resolve_jd_read_ref
from caliburn.features.job_description.sources import InvalidJdSourceError
from caliburn.features.job_description.tasks import DeleteTask, EditJdTasks, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision

type DeletionCommand = (
    EditJdAreas | EditJdTasks | EditJdCapabilities | EditJdCollaborators | EditJdConditions
)


def prepare_item_deletion(
    work: JdWorkRevision, *, command_id: UUID, read_ref: str
) -> tuple[DeletionCommand, int]:
    """Resolve a deletable item and validate the same policy as owner execution."""
    target = resolve_jd_read_ref(work, read_ref)
    revision = work.revision_id
    command: DeletionCommand
    detached_task_count = 0
    match target:
        case ResponsibilityArea():
            command = EditJdAreas(command_id, revision, DeleteArea(target.area_id))
            detached_task_count = sum(task.area_id == target.area_id for task in work.tasks)
        case WorkTask():
            command = EditJdTasks(command_id, revision, DeleteTask(target.task_id))
        case Capability():
            require_unused_capability(work.task_links, target.capability_id)
            command = EditJdCapabilities(
                command_id, revision, DeleteCapability(target.capability_id)
            )
        case Collaborator():
            command = EditJdCollaborators(
                command_id, revision, DeleteCollaborator(target.collaborator_id)
            )
        case JobCondition():
            command = EditJdConditions(command_id, revision, DeleteCondition(target.condition_id))
        case _:
            raise InvalidJdSourceError("Remove task details through revise_jd_item on their task")
    return command, detached_task_count
