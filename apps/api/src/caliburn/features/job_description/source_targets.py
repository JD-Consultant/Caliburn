"""Semantic JD source owners; arrangement and child evidence are not inherited content."""

from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.sources import JdSourceTarget, SourceTargetKind
from caliburn.features.job_description.work_models import JdWorkRevision


def source_target_contents(
    profile: JdProfile, work: JdWorkRevision
) -> dict[JdSourceTarget, tuple[str | None, ...]]:
    result: dict[JdSourceTarget, tuple[str | None, ...]] = {
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field): (getattr(profile, field),)
        for field in ProfileField
    }
    for area in work.areas:
        result[JdSourceTarget(SourceTargetKind.AREA, area.area_id)] = (area.title, area.scope_text)
    for task in work.tasks:
        result[JdSourceTarget(SourceTargetKind.TASK, task.task_id)] = (task.title, task.description)
        for detail in task.details:
            result[
                JdSourceTarget(SourceTargetKind.DETAIL, detail.detail_id, task_id=task.task_id)
            ] = (
                detail.kind.value,
                detail.text,
            )
    for capability in work.capabilities:
        result[JdSourceTarget(SourceTargetKind.CAPABILITY, capability.capability_id)] = (
            capability.kind.value,
            capability.name,
            capability.description,
        )
    tasks = {item.task_id: item for item in work.tasks}
    capabilities = {item.capability_id: item for item in work.capabilities}
    for link in work.task_links:
        task = tasks[link.task_id]
        capability = capabilities[link.capability_id]
        # This evidence supports the use of this definition in this task, not its position.
        result[
            JdSourceTarget(
                SourceTargetKind.TASK_CAPABILITY, link.capability_id, task_id=link.task_id
            )
        ] = (
            task.title,
            task.description,
            capability.kind.value,
            capability.name,
            capability.description,
        )
    for collaborator in work.collaborators:
        result[JdSourceTarget(SourceTargetKind.COLLABORATOR, collaborator.collaborator_id)] = (
            collaborator.name,
            collaborator.scope_text,
        )
    for condition in work.conditions:
        result[JdSourceTarget(SourceTargetKind.CONDITION, condition.condition_id)] = (
            condition.kind.value,
            condition.text,
        )
    return result
