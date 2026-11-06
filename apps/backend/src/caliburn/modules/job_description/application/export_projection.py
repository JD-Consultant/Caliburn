"""單一已保存 JD 快照的完整列印投影；不取得員工資料或來源正文。"""

from html import escape
from uuid import UUID

from caliburn.modules.job_description.application.content import TaskResult
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind


def project_jd_export_html(snapshot: JobDescriptionResult) -> str:
    """所有業務文字視為純文字；格式固定，缺歸屬／能力時拒絕部分匯出。"""
    blocks = ["<h1>職務說明書</h1>"]
    for label, value in (
        ("職稱", snapshot.job_title),
        ("組織單位", snapshot.organization_unit),
        ("匯報對象", snapshot.reports_to),
        ("職務目的", snapshot.purpose),
    ):
        if value is not None:
            blocks.extend((_heading(2, label), _paragraph(value)))
    if snapshot.baseline_competency_level is not None:
        blocks.extend(
            (
                _heading(2, "基準職能級別"),
                _paragraph(str(snapshot.baseline_competency_level)),
            )
        )
    tasks_by_duty: dict[UUID | None, list[TaskResult]] = {None: []}
    tasks_by_duty.update((duty.id, []) for duty in snapshot.duties)
    for task in snapshot.tasks:
        if task.duty_id not in tasks_by_duty:
            raise ValueError("JD 匯出內容不完整")
        tasks_by_duty[task.duty_id].append(task)
    knowledge_labels = {
        item.id: f"知識 {index}：{item.name}"
        for index, item in enumerate(snapshot.knowledge, 1)
    }
    skill_labels = {
        item.id: f"技能 {index}：{item.name}"
        for index, item in enumerate(snapshot.skills, 1)
    }
    if snapshot.duties or snapshot.tasks:
        blocks.append(_heading(2, "主要職責與工作任務"))
    for index, duty in enumerate(snapshot.duties, 1):
        blocks.append(_heading(3, f"職責 {index}：{duty.name}"))
        if duty.scope is not None:
            blocks.append(_paragraph(duty.scope))
        blocks.extend(_tasks(tasks_by_duty[duty.id], knowledge_labels, skill_labels))
    if tasks_by_duty[None]:
        blocks.append(_heading(3, "未分類任務"))
        blocks.extend(_tasks(tasks_by_duty[None], knowledge_labels, skill_labels))
    for items, label, labels in (
        (snapshot.knowledge, "知識", knowledge_labels),
        (snapshot.skills, "技能", skill_labels),
    ):
        if items:
            blocks.append(_heading(2, f"所需{label}"))
        for item in items:
            blocks.append(_heading(3, labels[item.id]))
            if item.description is not None:
                blocks.append(_paragraph(item.description))
    if snapshot.collaborations:
        blocks.append(_heading(2, "主要協作對象"))
    for collaboration in snapshot.collaborations:
        blocks.append(_heading(3, collaboration.collaborator_name))
        if collaboration.scope is not None:
            blocks.append(_paragraph(collaboration.scope))
    if snapshot.conditions:
        blocks.append(_heading(2, "工作條件與責任邊界"))
    condition_labels = {
        ConditionKind.WORK_ENVIRONMENT: "工作環境",
        ConditionKind.SCHEDULE_TRAVEL: "工時與出差",
        ConditionKind.SHARED_AUTHORITY: "共通權限界線",
        ConditionKind.SHARED_COLLABORATION: "共通協作界線",
        ConditionKind.QUALIFICATION: "必要資格",
    }
    for condition in snapshot.conditions:
        blocks.extend(
            (_heading(3, condition_labels[condition.kind]), _paragraph(condition.text))
        )
    if len(blocks) == 1:
        blocks.append(_paragraph("尚無已保存的職務內容"))
    return "\n".join(blocks)


def _heading(level: int, text: str) -> str:
    return f"<h{level}>{escape(text)}</h{level}>"


def _paragraph(text: str) -> str:
    return f"<p>{escape(text)}</p>"


def _tasks(
    tasks: list[TaskResult],
    knowledge_labels: dict[UUID, str],
    skill_labels: dict[UUID, str],
) -> list[str]:
    blocks = []
    for index, task in enumerate(tasks, 1):
        blocks.append(_heading(4, f"任務 {index}：{task.name}"))
        if task.description is not None:
            blocks.append(_paragraph(task.description))
        if task.competency_level is not None:
            blocks.append(_paragraph(f"職能級別：{task.competency_level}"))
        for details, label in (
            (task.outcomes, "成果 O"),
            (task.requirements, "執行要求 P"),
        ):
            if details:
                blocks.extend((_heading(5, label), "<ul>"))
                blocks.extend(f"<li>{escape(detail.text)}</li>" for detail in details)
                blocks.append("</ul>")
        for linked, label, labels in (
            (task.knowledge_ids, "知識 K", knowledge_labels),
            (task.skill_ids, "技能 S", skill_labels),
        ):
            if not all(identity in labels for identity in linked):
                raise ValueError("JD 匯出內容不完整")
            if linked:
                blocks.extend(
                    (
                        _heading(5, label),
                        _paragraph("；".join(labels[identity] for identity in linked)),
                    )
                )
    return blocks
