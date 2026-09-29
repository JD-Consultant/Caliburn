"""Complete local JD text and direct relationships, without expanding source chains."""

from pydantic import JsonValue

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability, CapabilityKind
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.navigation import (
    JdReadTarget,
    jd_read_ref,
    resolve_jd_read_ref,
)
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceTarget,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.workflows.jd_reads import JdSourceReading


class InvalidJdReadSelectionError(ValueError):
    """The view and locator do not describe one of the supported read selections."""


def select_jd_items(
    work: JdWorkRevision, view: str, read_ref: str | None
) -> tuple[JdReadTarget, ...]:
    if view in {"item", "work_tasks"}:
        if read_ref is None:
            raise InvalidJdReadSelectionError("This view requires a JD read_ref")
        item = resolve_jd_read_ref(work, read_ref)
        if view == "item":
            return (item,)
        if not isinstance(item, ResponsibilityArea):
            raise InvalidJdReadSelectionError("work_tasks requires an area read_ref")
        return tuple(task for task in work.tasks if task.area_id == item.area_id)
    if read_ref is not None:
        raise InvalidJdReadSelectionError("This view requires a null read_ref")
    match view:
        case "responsibility_areas":
            return work.areas
        case "unassigned_work_tasks":
            return tuple(task for task in work.tasks if task.area_id is None)
        case "required_knowledge":
            return tuple(
                item for item in work.capabilities if item.kind == CapabilityKind.KNOWLEDGE
            )
        case "required_skills":
            return tuple(item for item in work.capabilities if item.kind == CapabilityKind.SKILL)
        case "main_collaborators":
            return work.collaborators
        case "job_wide_conditions":
            return work.conditions
        case _:
            raise InvalidJdReadSelectionError("Select a supported local JD view")


def jd_read_source_targets(
    work: JdWorkRevision, items: tuple[JdReadTarget, ...]
) -> tuple[JdSourceTarget, ...]:
    targets = []
    for item in items:
        targets.append(_item_source_target(item, work))
        if isinstance(item, WorkTask):
            targets.extend(_item_source_target(detail, work) for detail in item.details)
            targets.extend(
                JdSourceTarget(
                    SourceTargetKind.TASK_CAPABILITY, link.capability_id, task_id=link.task_id
                )
                for link in work.task_links
                if link.task_id == item.task_id
            )
        elif isinstance(item, Capability):
            targets.extend(
                JdSourceTarget(
                    SourceTargetKind.TASK_CAPABILITY, link.capability_id, task_id=link.task_id
                )
                for link in work.task_links
                if link.capability_id == item.capability_id
            )
    return tuple(dict.fromkeys(targets))


def project_jd_profile(
    profile: JdProfile, sources: tuple[JdSourceReading, ...]
) -> dict[str, JsonValue]:
    return {
        "job_title": profile.job_title,
        "organization_unit": profile.organization_unit,
        "reports_to": profile.reports_to,
        "purpose": profile.purpose,
        "supporting_sources": {
            field.value: _source_items(
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field), sources
            )
            for field in ProfileField
        },
    }


def project_jd_item(
    item: JdReadTarget, work: JdWorkRevision, sources: tuple[JdSourceReading, ...]
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {"read_ref": jd_read_ref(item)}
    match item:
        case ResponsibilityArea():
            result.update(kind="responsibility_area", title=item.title, scope_text=item.scope_text)
        case WorkTask():
            result.update(
                kind="work_task",
                title=item.title,
                description=item.description,
                outcomes=[
                    _detail(detail, work, sources)
                    for detail in item.details
                    if detail.kind == DetailKind.OUTCOME
                ],
                requirements=[
                    _detail(detail, work, sources)
                    for detail in item.details
                    if detail.kind == DetailKind.REQUIREMENT
                ],
                required_knowledge=_task_capabilities(
                    item, work, CapabilityKind.KNOWLEDGE, sources
                ),
                required_skills=_task_capabilities(item, work, CapabilityKind.SKILL, sources),
            )
        case TaskDetail():
            result.update(kind=item.kind.value, text=item.text)
        case Capability():
            result.update(
                kind=item.kind.value,
                name=item.name,
                description=item.description,
                used_by_tasks=_capability_uses(item, work, sources),
            )
        case Collaborator():
            result.update(kind="collaborator", name=item.name, scope_text=item.scope_text)
        case JobCondition():
            result.update(kind="job_wide_condition", condition_kind=item.kind.value, text=item.text)
    result["supporting_sources"] = _source_items(_item_source_target(item, work), sources)
    return result


def _detail(
    item: TaskDetail, work: JdWorkRevision, sources: tuple[JdSourceReading, ...]
) -> dict[str, JsonValue]:
    return {
        "read_ref": jd_read_ref(item),
        "text": item.text,
        "supporting_sources": _source_items(_item_source_target(item, work), sources),
    }


def _task_capabilities(
    task: WorkTask, work: JdWorkRevision, kind: CapabilityKind, sources: tuple[JdSourceReading, ...]
) -> list[JsonValue]:
    capabilities = {item.capability_id: item for item in work.capabilities}
    result: list[JsonValue] = []
    for link in work.task_links:
        if link.task_id != task.task_id:
            continue
        item = capabilities[link.capability_id]
        if item.kind == kind:
            target = JdSourceTarget(
                SourceTargetKind.TASK_CAPABILITY, item.capability_id, task_id=task.task_id
            )
            result.append(
                {
                    "read_ref": jd_read_ref(item),
                    "name": item.name,
                    "supporting_sources": _source_items(target, sources),
                }
            )
    return result


def _capability_uses(
    item: Capability, work: JdWorkRevision, sources: tuple[JdSourceReading, ...]
) -> list[JsonValue]:
    task_ids = {
        link.task_id for link in work.task_links if link.capability_id == item.capability_id
    }
    result: list[JsonValue] = []
    for task in work.tasks:
        if task.task_id in task_ids:
            target = JdSourceTarget(
                SourceTargetKind.TASK_CAPABILITY, item.capability_id, task_id=task.task_id
            )
            result.append(
                {
                    "read_ref": jd_read_ref(task),
                    "title": task.title,
                    "supporting_sources": _source_items(target, sources),
                }
            )
    return result


def _item_source_target(item: JdReadTarget, work: JdWorkRevision) -> JdSourceTarget:
    match item:
        case ResponsibilityArea():
            return JdSourceTarget(SourceTargetKind.AREA, item.area_id)
        case WorkTask():
            return JdSourceTarget(SourceTargetKind.TASK, item.task_id)
        case TaskDetail():
            for task in work.tasks:
                if any(detail.detail_id == item.detail_id for detail in task.details):
                    return JdSourceTarget(
                        SourceTargetKind.DETAIL, item.detail_id, task_id=task.task_id
                    )
            raise InvalidJdReadSelectionError("The detail is not in this JD revision")
        case Capability():
            return JdSourceTarget(SourceTargetKind.CAPABILITY, item.capability_id)
        case Collaborator():
            return JdSourceTarget(SourceTargetKind.COLLABORATOR, item.collaborator_id)
        case JobCondition():
            return JdSourceTarget(SourceTargetKind.CONDITION, item.condition_id)


def _source_items(target: JdSourceTarget, sources: tuple[JdSourceReading, ...]) -> list[JsonValue]:
    result: list[JsonValue] = []
    for reading in sources:
        reference = reading.reference
        if reference.target != target:
            continue
        item: dict[str, JsonValue] = {"citation_ref": f"citation_{reference.citation_id.hex}"}
        if isinstance(reference.source, InterviewSource):
            if reading.interview_sequence is None:
                item["kind"] = "current_input"
            else:
                item.update(kind="interview", interview_sequence=reading.interview_sequence)
        else:
            item["kind"] = reference.source.layer.value
            if reading.target_title is not None:
                item["target_title"] = reading.target_title
            if reading.historical_title is not None:
                item["historical_title"] = reading.historical_title
        if reference.needs_review or reading.needs_recheck:
            item["needs_recheck"] = True
        result.append(item)
    return result
