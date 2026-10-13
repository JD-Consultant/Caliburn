"""六種內容命令共用最終差異，來源與版本保存仍由各自 owner 負責。"""

from dataclasses import dataclass, replace

from caliburn.features.job_description.area_changes import apply_area_change
from caliburn.features.job_description.areas import DeleteArea, EditJdAreas
from caliburn.features.job_description.capabilities import EditJdCapabilities
from caliburn.features.job_description.capability_changes import apply_capability_change
from caliburn.features.job_description.collaborator_changes import apply_collaborator_change
from caliburn.features.job_description.collaborators import EditJdCollaborators
from caliburn.features.job_description.compound_edits import CompoundItem
from caliburn.features.job_description.condition_changes import apply_condition_change
from caliburn.features.job_description.conditions import EditJdConditions
from caliburn.features.job_description.models import (
    JdProfile,
    ReviseJdProfile,
    apply_profile_changes,
)
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import JdSourceReference, carry_source_references
from caliburn.features.job_description.task_changes import apply_task_edit, detach_area_tasks
from caliburn.features.job_description.tasks import EditJdTasks
from caliburn.features.job_description.work_models import JdWorkRevision

type JdContentEdit = (
    ReviseJdProfile
    | EditJdAreas
    | EditJdTasks
    | EditJdCapabilities
    | EditJdCollaborators
    | EditJdConditions
)


@dataclass(frozen=True, slots=True)
class JdEditChanges:
    profile: JdProfile
    work: JdWorkRevision
    references: tuple[JdSourceReference, ...]
    changed_content: CompoundItem | None
    created_item: CompoundItem | None

    def differs_from(
        self, profile: JdProfile, work: JdWorkRevision, references: tuple[JdSourceReference, ...]
    ) -> bool:
        return self.profile != profile or self.work != work or self.references != references


def apply_content_changes(
    profile: JdProfile,
    work: JdWorkRevision,
    references: tuple[JdSourceReference, ...],
    command: JdContentEdit,
    *,
    review_changed_content: bool = False,
) -> JdEditChanges:
    before_profile, before_work = profile, work
    content: CompoundItem | None = None
    match command:
        case ReviseJdProfile():
            profile = apply_profile_changes(profile, command.changes)
        case EditJdAreas():
            areas, content = apply_area_change(work.areas, command.change)
            tasks = work.tasks
            if isinstance(command.change, DeleteArea):
                tasks = detach_area_tasks(tasks, command.change.area_id)
            work = replace(work, areas=areas, tasks=tasks)
        case EditJdTasks():
            tasks, content = apply_task_edit(
                work.tasks, tuple(a.area_id for a in work.areas), command.change
            )
            task_ids = {task.task_id for task in tasks}
            work = replace(
                work,
                tasks=tasks,
                task_links=tuple(link for link in work.task_links if link.task_id in task_ids),
            )
        case EditJdCapabilities():
            capabilities, links, content = apply_capability_change(
                work.capabilities,
                work.task_links,
                tuple(t.task_id for t in work.tasks),
                command.change,
            )
            work = replace(work, capabilities=capabilities, task_links=links)
        case EditJdCollaborators():
            collaborators, content = apply_collaborator_change(work.collaborators, command.change)
            work = replace(work, collaborators=collaborators)
        case EditJdConditions():
            conditions, content = apply_condition_change(work.conditions, command.change)
            work = replace(work, conditions=conditions)
    references = carry_source_references(
        references,
        source_target_contents(before_profile, before_work),
        source_target_contents(profile, work),
        review_changed_content=review_changed_content,
    )
    return JdEditChanges(profile, work, references, content, None)
