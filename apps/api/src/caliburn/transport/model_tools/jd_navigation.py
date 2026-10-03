"""Model-visible JD navigation; no storage, model calls or new summaries."""

from uuid import UUID

from caliburn.contracts.generated.tools.jd_map import (
    JdAreaMap,
    JdConditionMapItem,
    JdMap,
    JdNamedMapItem,
    JdProfileMap,
    JdTaskMap,
)
from caliburn.features.job_description.capabilities import CapabilityKind
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.tasks import DetailKind, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision


def project_jd_map(
    profile: JdProfile, work: JdWorkRevision, *, preview_characters: int = 120
) -> JdMap:
    """Include every item in source order; only explicitly named previews may be shortened."""
    if preview_characters < 1:
        raise ValueError("JD preview character limit must be positive")
    profile_map = JdProfileMap(
        job_title=profile.job_title,
        organization_unit=profile.organization_unit,
        reports_to=profile.reports_to,
    )
    if profile.purpose is not None:
        profile_map.job_purpose_preview = _preview(profile.purpose, preview_characters)
    tasks_by_area: dict[UUID | None, list[JdTaskMap]] = {}
    for task in work.tasks:
        tasks_by_area.setdefault(task.area_id, []).append(_task_map(task, preview_characters))
    areas = []
    for area in work.areas:
        area_map = JdAreaMap(
            read_ref=jd_read_ref(area),
            title=area.title,
            work_tasks=tasks_by_area.get(area.area_id, []),
        )
        if area.scope_text is not None:
            area_map.scope_preview = _preview(area.scope_text, preview_characters)
        areas.append(area_map)
    return JdMap(
        profile=profile_map,
        responsibility_areas=areas,
        unassigned_work_tasks=tasks_by_area.get(None, []),
        required_knowledge=[
            JdNamedMapItem(read_ref=jd_read_ref(item), name=item.name)
            for item in work.capabilities
            if item.kind == CapabilityKind.KNOWLEDGE
        ],
        required_skills=[
            JdNamedMapItem(read_ref=jd_read_ref(item), name=item.name)
            for item in work.capabilities
            if item.kind == CapabilityKind.SKILL
        ],
        main_collaborators=[
            JdNamedMapItem(read_ref=jd_read_ref(item), name=item.name)
            for item in work.collaborators
        ],
        job_wide_conditions=[
            JdConditionMapItem(
                read_ref=jd_read_ref(item),
                description_preview=_preview(item.text, preview_characters),
            )
            for item in work.conditions
        ],
    )


def _task_map(task: WorkTask, preview_characters: int) -> JdTaskMap:
    result = JdTaskMap(
        read_ref=jd_read_ref(task),
        title=task.title,
        outcome_count=sum(detail.kind == DetailKind.OUTCOME for detail in task.details),
        requirement_count=sum(detail.kind == DetailKind.REQUIREMENT for detail in task.details),
    )
    if task.description is not None:
        result.work_preview = _preview(task.description, preview_characters)
    return result


def _preview(text: str, characters: int) -> str:
    return text if len(text) <= characters else text[:characters] + "…"
