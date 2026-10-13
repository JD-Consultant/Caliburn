"""Semantic JD source owners; arrangement and child evidence are not inherited content."""

from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.sources import (
    JdSourceContents,
    JdSourceTarget,
    SourceTargetKind,
    TaskSourceCapability,
    TaskSourceContents,
)
from caliburn.features.job_description.work_models import JdWorkRevision


def source_target_contents(
    profile: JdProfile, work: JdWorkRevision
) -> dict[JdSourceTarget, JdSourceContents]:
    result: dict[JdSourceTarget, JdSourceContents] = {
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field): (getattr(profile, field),)
        for field in ProfileField
    }
    for area in work.areas:
        result[JdSourceTarget(SourceTargetKind.AREA, area.area_id)] = (area.title, area.scope_text)
    capabilities = {item.capability_id: item for item in work.capabilities}
    for task in work.tasks:
        linked = sorted(
            link.capability_id for link in work.task_links if link.task_id == task.task_id
        )
        # 只比較支持語意；排序、歸屬及不可變修訂身分不構成內容變動。
        result[JdSourceTarget(SourceTargetKind.TASK, task.task_id)] = TaskSourceContents(
            task.title,
            task.description,
            tuple(sorted(task.details, key=lambda detail: detail.detail_id)),
            tuple(
                TaskSourceCapability(
                    identity,
                    capabilities[identity].kind,
                    capabilities[identity].name,
                    capabilities[identity].description,
                )
                for identity in linked
            ),
        )
    for capability in work.capabilities:
        result[JdSourceTarget(SourceTargetKind.CAPABILITY, capability.capability_id)] = (
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
