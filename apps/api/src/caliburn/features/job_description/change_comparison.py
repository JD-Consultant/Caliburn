"""人工兩端 net；結構判變與來源支持內容的核對政策各有用途。"""

from dataclasses import dataclass, fields
from uuid import UUID

from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.navigation import JdReadTarget, jd_read_ref
from caliburn.features.job_description.sources import JdSourceReference
from caliburn.features.job_description.work_models import JdWorkRevision


@dataclass(frozen=True, slots=True)
class JdChangeSnapshot:
    profile: JdProfile
    work: JdWorkRevision
    sources: tuple[JdSourceReference, ...]


@dataclass(frozen=True, slots=True)
class JdNetChanges:
    before: JdChangeSnapshot
    after: JdChangeSnapshot
    profile_fields: tuple[ProfileField, ...]
    item_refs: tuple[str, ...]
    citation_ids: tuple[UUID, ...]


def compare_jd_snapshots(before: JdChangeSnapshot, after: JdChangeSnapshot) -> JdNetChanges:
    old, new = _items(before.work), _items(after.work)
    old_sources = {item.citation_id: item for item in before.sources}
    new_sources = {item.citation_id: item for item in after.sources}
    return JdNetChanges(
        before,
        after,
        tuple(
            field
            for field in ProfileField
            if getattr(before.profile, field.value) != getattr(after.profile, field.value)
        ),
        tuple(ref for ref in dict.fromkeys((*old, *new)) if old.get(ref) != new.get(ref)),
        tuple(
            key
            for key in dict.fromkeys((*old_sources, *new_sources))
            if old_sources.get(key) != new_sources.get(key)
        ),
    )


def _items(work: JdWorkRevision) -> dict[str, tuple[object, ...]]:
    values: dict[str, tuple[object, ...]] = {}

    def add(item: JdReadTarget, siblings: tuple[JdReadTarget, ...], *relations: object) -> None:
        # 正文修訂號只是保存位置；穩定身分、順序和關係則是人工最終狀態。
        body = tuple(
            getattr(item, field.name)
            for field in fields(item)
            if field.name != "content_revision_id"
        )
        values[jd_read_ref(item)] = (body, siblings.index(item), *relations)

    for area in work.areas:
        add(
            area,
            work.areas,
            tuple(task.task_id for task in work.tasks if task.area_id == area.area_id),
        )
    for task in work.tasks:
        add(
            task,
            tuple(item for item in work.tasks if item.area_id == task.area_id),
            tuple(link.capability_id for link in work.task_links if link.task_id == task.task_id),
        )
        for detail in task.details:
            add(
                detail,
                tuple(item for item in task.details if item.kind == detail.kind),
                task.task_id,
            )
    for capability in work.capabilities:
        add(
            capability,
            tuple(item for item in work.capabilities if item.kind == capability.kind),
            tuple(
                link.task_id
                for link in work.task_links
                if link.capability_id == capability.capability_id
            ),
        )
    for collaborator in work.collaborators:
        add(collaborator, work.collaborators)
    for condition in work.conditions:
        add(condition, tuple(item for item in work.conditions if item.kind == condition.kind))
    return values
