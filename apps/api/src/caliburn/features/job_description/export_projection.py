"""Printable projection of one immutable formal JD revision."""

from html import escape
from uuid import UUID

from caliburn.features.job_description.capabilities import CapabilityKind
from caliburn.features.job_description.conditions import ConditionKind
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.tasks import DetailKind, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def project_jd_export_html(profile: JdProfile, work: JdWorkRevision) -> str:
    """Escape plain JD text; no employee metadata, citations or candidate lookup exists here."""
    blocks = ["<h1>職務說明書</h1>"]
    for label, value in (
        ("職稱", profile.job_title),
        ("組織單位", profile.organization_unit),
        ("匯報對象", profile.reports_to),
        ("職務目的", profile.purpose),
    ):
        if value is not None:
            blocks.extend((_heading(2, label), _paragraph(value)))
    tasks_by_area: dict[UUID | None, list[WorkTask]] = {None: []}
    tasks_by_area.update((area.area_id, []) for area in work.areas)
    for task in work.tasks:
        # Never silently omit an orphan from an apparently complete export.
        tasks_by_area[task.area_id].append(task)
    capability_labels: dict[UUID, str] = {}
    for kind, label in ((CapabilityKind.KNOWLEDGE, "知識"), (CapabilityKind.SKILL, "技能")):
        for index, item in enumerate((item for item in work.capabilities if item.kind == kind), 1):
            capability_labels[item.capability_id] = f"{label} {index}" + (
                f"：{item.name}" if item.name else ""
            )
    if work.areas or work.tasks:
        blocks.append(_heading(2, "主要職責與工作任務"))
    for index, area in enumerate(work.areas, 1):
        blocks.append(_heading(3, f"職責 {index}" + (f"：{area.title}" if area.title else "")))
        if area.scope_text is not None:
            blocks.append(_paragraph(area.scope_text))
        blocks.extend(_tasks(tasks_by_area[area.area_id], work, capability_labels))
    if tasks_by_area[None]:
        blocks.append(_heading(3, "未歸屬任務"))
        blocks.extend(_tasks(tasks_by_area[None], work, capability_labels))
    for kind, label in ((CapabilityKind.KNOWLEDGE, "知識"), (CapabilityKind.SKILL, "技能")):
        items = [item for item in work.capabilities if item.kind == kind]
        if items:
            blocks.append(_heading(2, f"所需{label}"))
        for item in items:
            blocks.append(_heading(3, capability_labels[item.capability_id]))
            if item.description is not None:
                blocks.append(_paragraph(item.description))
    if work.collaborators:
        blocks.append(_heading(2, "主要協作對象"))
    for index, collaborator in enumerate(work.collaborators, 1):
        blocks.append(_heading(3, collaborator.name or f"協作對象 {index}"))
        if collaborator.scope_text is not None:
            blocks.append(_paragraph(collaborator.scope_text))
    if work.conditions:
        blocks.append(_heading(2, "工作條件與責任邊界"))
    labels = {
        ConditionKind.WORK_ENVIRONMENT: "工作環境",
        ConditionKind.SCHEDULE_TRAVEL: "工時與出差",
        ConditionKind.SHARED_AUTHORITY: "共通權限界線",
        ConditionKind.SHARED_COLLABORATION: "共通協作界線",
        ConditionKind.QUALIFICATION: "必要資格",
    }
    for condition in work.conditions:
        blocks.extend((_heading(3, labels[condition.kind]), _paragraph(condition.text)))
    if len(blocks) == 1:
        blocks.append(_paragraph("尚無已保存的職務內容"))
    return "\n".join(blocks)


def _heading(level: int, text: str) -> str:
    return f"<h{level}>{escape(text)}</h{level}>"


def _paragraph(text: str) -> str:
    return f"<p>{escape(text)}</p>"


def _tasks(tasks: list[WorkTask], work: JdWorkRevision, labels: dict[UUID, str]) -> list[str]:
    blocks = []
    kinds = {item.capability_id: item.kind for item in work.capabilities}
    for index, task in enumerate(tasks, 1):
        blocks.append(_heading(4, f"任務 {index}" + (f"：{task.title}" if task.title else "")))
        if task.description is not None:
            blocks.append(_paragraph(task.description))
        for kind, label in ((DetailKind.OUTCOME, "成果 O"), (DetailKind.REQUIREMENT, "執行要求 P")):
            details = [detail for detail in task.details if detail.kind == kind]
            if details:
                blocks.extend((_heading(5, label), "<ul>"))
                blocks.extend(f"<li>{escape(detail.text)}</li>" for detail in details)
                blocks.append("</ul>")
        for capability_kind, label in (
            (CapabilityKind.KNOWLEDGE, "知識 K"),
            (CapabilityKind.SKILL, "技能 S"),
        ):
            linked = [
                link.capability_id
                for link in work.task_links
                if link.task_id == task.task_id and kinds[link.capability_id] == capability_kind
            ]
            if linked:
                blocks.extend(
                    (_heading(5, label), _paragraph("；".join(labels[item] for item in linked)))
                )
    return blocks
