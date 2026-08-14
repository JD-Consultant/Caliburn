"""Temporary composition-edge projection from new authority to retained XLSX."""

from __future__ import annotations

from uuid import UUID

from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
)
from app.core.domain import JdHeader
from app.export import (
    ExportDocument,
    ExportDutySection,
    ExportOpksEntry,
    ExportTaskEntry,
)


def assemble_approved_export_document(
    document: ApprovedJobDocument,
    *,
    title: str,
) -> ExportDocument:
    def in_kind(kind: ApprovedOpksKind) -> tuple[ApprovedOpksItem, ...]:
        return tuple(
            sorted(
                (item for item in document.opks if item.kind is kind),
                key=lambda item: (item.display_order, str(item.item_id)),
            )
        )

    indicators = {
        item.item_id: item
        for item in in_kind(ApprovedOpksKind.PERFORMANCE_INDICATOR)
    }

    def linked_task_ids(item: ApprovedOpksItem) -> frozenset[UUID]:
        return frozenset(
            (
                *item.task_ids,
                *(
                    task_id
                    for indicator_id in item.indicator_ids
                    for task_id in indicators[indicator_id].task_ids
                ),
            )
        )

    knowledge = in_kind(ApprovedOpksKind.KNOWLEDGE)
    skills = in_kind(ApprovedOpksKind.SKILL)
    knowledge_codes = {
        item.item_id: ExportOpksEntry(position_code=f"K{index:02d}", text=item.text)
        for index, item in enumerate(knowledge, start=1)
    }
    skill_codes = {
        item.item_id: ExportOpksEntry(position_code=f"S{index:02d}", text=item.text)
        for index, item in enumerate(skills, start=1)
    }

    def task_local(
        task: ApprovedTask,
        *,
        position_code: str | None,
        kind: ApprovedOpksKind,
        prefix: str,
    ) -> tuple[ExportOpksEntry, ...]:
        return tuple(
            ExportOpksEntry(
                position_code=(
                    None
                    if position_code is None
                    else f"{prefix}{position_code[1:]}.{index}"
                ),
                text=item.text,
            )
            for index, item in enumerate(
                (item for item in in_kind(kind) if task.task_id in item.task_ids),
                start=1,
            )
        )

    def task_entry(
        task: ApprovedTask,
        position_code: str | None,
    ) -> ExportTaskEntry:
        return ExportTaskEntry(
            task_id=str(task.task_id),
            position_code=position_code,
            statement=task.statement,
            competency_level=task.competency_level,
            outputs=task_local(
                task,
                position_code=position_code,
                kind=ApprovedOpksKind.OUTPUT,
                prefix="O",
            ),
            indicators=task_local(
                task,
                position_code=position_code,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                prefix="P",
            ),
            knowledge=tuple(
                knowledge_codes[item.item_id]
                for item in knowledge
                if task.task_id in linked_task_ids(item)
            ),
            skills=tuple(
                skill_codes[item.item_id]
                for item in skills
                if task.task_id in linked_task_ids(item)
            ),
        )

    ordered_duties = sorted(
        document.duties,
        key=lambda item: (item.display_order, str(item.duty_id)),
    )
    ordered_tasks = sorted(
        document.tasks,
        key=lambda item: (item.display_order, str(item.task_id)),
    )
    duty_sections: list[ExportDutySection] = []
    assigned_task_ids: set[UUID] = set()
    for duty_index, duty in enumerate(ordered_duties, start=1):
        duty_code = f"T{duty_index}"
        tasks = [task for task in ordered_tasks if task.duty_id == duty.duty_id]
        assigned_task_ids.update(task.task_id for task in tasks)
        duty_sections.append(
            ExportDutySection(
                position_code=duty_code,
                statement=duty.statement,
                tasks=tuple(
                    task_entry(task, f"{duty_code}.{task_index}")
                    for task_index, task in enumerate(tasks, start=1)
                ),
            )
        )

    return ExportDocument(
        title=title,
        header=JdHeader(
            competency_name=document.job_title,
            occupation_category_name=document.occupation_category_name,
            occupation_name=document.occupation_name,
            occupation_code=document.occupation_code,
            industry_name=document.industry_name,
            industry_code=document.industry_code,
            work_description=document.work_description,
            competency_level=document.competency_level,
            notes=document.notes,
        ),
        duties=tuple(duty_sections),
        unassigned_tasks=tuple(
            task_entry(task, None)
            for task in ordered_tasks
            if task.task_id not in assigned_task_ids
        ),
        attitudes=tuple(
            ExportOpksEntry(position_code=f"A{index:02d}", text=item.text)
            for index, item in enumerate(
                in_kind(ApprovedOpksKind.ATTITUDE),
                start=1,
            )
        ),
    )


__all__ = ["assemble_approved_export_document"]
