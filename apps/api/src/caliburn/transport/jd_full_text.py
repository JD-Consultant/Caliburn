"""Shared finished-product Markdown projection of one visible JD revision."""

from uuid import UUID

from caliburn.features.job_description.capabilities import Capability, CapabilityKind
from caliburn.features.job_description.conditions import ConditionKind
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.tasks import DetailKind, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision

_CAPABILITY_LABELS = {
    CapabilityKind.KNOWLEDGE: "知識",
    CapabilityKind.SKILL: "技能",
}
_CONDITION_LABELS = {
    ConditionKind.WORK_ENVIRONMENT: "工作環境",
    ConditionKind.SCHEDULE_TRAVEL: "工時與出差",
    ConditionKind.SHARED_AUTHORITY: "共通權限界線",
    ConditionKind.SHARED_COLLABORATION: "共通協作界線",
    ConditionKind.QUALIFICATION: "必要資格",
}


def project_jd_full_text(profile: JdProfile, work: JdWorkRevision) -> str:
    """Render complete text; the caller binds profile/work to one trusted visible revision.

    Document ordinals distinguish unnamed or same-named items, not persistent read refs.
    Text is neither summarized nor normalized. Missing values stay absent. A dangling
    relationship raises ValueError instead of returning an apparently complete document.
    """
    tasks_by_area: dict[UUID | None, list[WorkTask]] = {None: []}
    tasks_by_area.update((area.area_id, []) for area in work.areas)
    for task in work.tasks:
        if task.area_id not in tasks_by_area:
            raise ValueError("Task refers to an area outside this JD revision")
        tasks_by_area[task.area_id].append(task)

    capabilities_by_id = {item.capability_id: item for item in work.capabilities}
    capabilities_by_task: dict[UUID, list[Capability]] = {task.task_id: [] for task in work.tasks}
    for link in work.task_links:
        if link.task_id not in capabilities_by_task or link.capability_id not in capabilities_by_id:
            raise ValueError("Task capability link refers outside this JD revision")
        capabilities_by_task[link.task_id].append(capabilities_by_id[link.capability_id])

    capability_groups: dict[CapabilityKind, list[Capability]] = {
        kind: [] for kind in CapabilityKind
    }
    capability_labels: dict[UUID, str] = {}
    for item in work.capabilities:
        group = capability_groups[item.kind]
        group.append(item)
        capability_labels[item.capability_id] = _item_label(
            _CAPABILITY_LABELS[item.kind], len(group), item.name
        )

    blocks = ["# 職務說明書"]
    profile_blocks: list[str] = []
    for label, value in (
        ("職稱", profile.job_title),
        ("組織單位", profile.organization_unit),
        ("匯報對象", profile.reports_to),
    ):
        if value is not None:
            profile_blocks.extend((f"**{label}**", value))
    if profile_blocks:
        blocks.extend(("## 職務基本資料", *profile_blocks))
    if profile.purpose is not None:
        blocks.extend(("## 職務目的", profile.purpose))

    if work.areas or work.tasks:
        blocks.append("## 主要職責與工作任務")
    for position, area in enumerate(work.areas, start=1):
        blocks.append(f"### {_item_label('職責', position, area.title)}")
        if area.scope_text is not None:
            blocks.append(area.scope_text)
        for task_position, task in enumerate(tasks_by_area[area.area_id], start=1):
            blocks.extend(
                _task_blocks(
                    task, task_position, capabilities_by_task[task.task_id], capability_labels
                )
            )
    if tasks_by_area[None]:
        blocks.append("### 未歸屬任務")
        for position, task in enumerate(tasks_by_area[None], start=1):
            blocks.extend(
                _task_blocks(task, position, capabilities_by_task[task.task_id], capability_labels)
            )

    for kind, items in capability_groups.items():
        if items:
            blocks.append(f"## 所需{_CAPABILITY_LABELS[kind]}總覽")
        for item in items:
            blocks.append(f"### {capability_labels[item.capability_id]}")
            if item.description is not None:
                blocks.append(item.description)

    if work.collaborators:
        blocks.append("## 主要協作對象")
    for position, collaborator in enumerate(work.collaborators, start=1):
        blocks.append(f"### {_item_label('協作對象', position, collaborator.name)}")
        if collaborator.scope_text is not None:
            blocks.append(collaborator.scope_text)

    if work.conditions:
        blocks.append("## 工作條件與責任邊界")
    for condition in work.conditions:
        blocks.extend((f"### {_CONDITION_LABELS[condition.kind]}", condition.text))
    return "\n\n".join(blocks) + "\n"


def _item_label(kind: str, position: int, name: str | None) -> str:
    label = f"{kind} {position}"
    return label if name is None else f"{label}：{name}"


def _task_blocks(
    task: WorkTask,
    position: int,
    linked_capabilities: list[Capability],
    capability_labels: dict[UUID, str],
) -> list[str]:
    blocks = [f"#### {_item_label('任務', position, task.title)}"]
    if task.description is not None:
        blocks.append(task.description)
    for detail_kind, heading, label in (
        (DetailKind.OUTCOME, "成果", "成果"),
        (DetailKind.REQUIREMENT, "工作執行要求", "要求"),
    ):
        details = [detail for detail in task.details if detail.kind == detail_kind]
        if details:
            blocks.append(f"##### {heading}")
        for detail_position, detail in enumerate(details, start=1):
            blocks.extend((f"**{label} {detail_position}**", detail.text))

    for capability_kind, label in _CAPABILITY_LABELS.items():
        linked = [item for item in linked_capabilities if item.kind == capability_kind]
        if linked:
            blocks.extend(
                (
                    f"##### 所需{label}",
                    "\n".join(f"- {capability_labels[item.capability_id]}" for item in linked),
                )
            )
    return blocks
