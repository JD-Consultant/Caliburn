"""Current State 到公版表格投影的決定性組裝。

這一層是純函式：不讀 DB、不碰 transport、不知道 XLSX。所有位置碼只存在於
回傳的 `ExportDocument`，不寫回 Current State。
"""

from __future__ import annotations

from app.job_analysis.domain import (
    CurrentJdOpks,
    DomainModel,
    JdHeader,
    JdTask,
    NonEmptyText,
    OpksEntityKind,
    OpksItem,
)

from .transition import JobAnalysisState


class ExportOpksEntry(DomainModel):
    position_code: NonEmptyText | None
    text: NonEmptyText


class ExportTaskEntry(DomainModel):
    task_id: NonEmptyText
    position_code: NonEmptyText | None
    statement: NonEmptyText
    competency_level: int | None
    outputs: tuple[ExportOpksEntry, ...] = ()
    indicators: tuple[ExportOpksEntry, ...] = ()
    knowledge: tuple[ExportOpksEntry, ...] = ()
    skills: tuple[ExportOpksEntry, ...] = ()


class ExportDutySection(DomainModel):
    position_code: NonEmptyText
    statement: NonEmptyText
    tasks: tuple[ExportTaskEntry, ...] = ()


class ExportDocument(DomainModel):
    title: NonEmptyText
    header: JdHeader
    duties: tuple[ExportDutySection, ...] = ()
    unassigned_tasks: tuple[ExportTaskEntry, ...] = ()
    attitudes: tuple[ExportOpksEntry, ...] = ()


def _in_kind(
    current_opks: CurrentJdOpks,
    kind: OpksEntityKind,
) -> tuple[OpksItem, ...]:
    return tuple(
        sorted(
            (item for item in current_opks.items if item.entity_kind is kind),
            key=lambda item: (item.display_order, item.entity_id),
        )
    )


def _task_ids_by_item(current_opks: CurrentJdOpks) -> dict[str, frozenset[str]]:
    indicator_tasks = {
        item.entity_id: item.task_refs
        for item in _in_kind(current_opks, OpksEntityKind.INDICATOR)
    }
    return {
        item.entity_id: frozenset(
            (*item.task_refs, *(task_id for ref in item.indicator_refs for task_id in indicator_tasks[ref]))
        )
        for item in current_opks.items
        if item.entity_kind in {OpksEntityKind.KNOWLEDGE, OpksEntityKind.SKILL}
    }


def _document_codes(
    items: tuple[OpksItem, ...],
    prefix: str,
) -> dict[str, ExportOpksEntry]:
    return {
        item.entity_id: ExportOpksEntry(
            position_code=f"{prefix}{index:02d}",
            text=item.text,
        )
        for index, item in enumerate(items, start=1)
    }


def _task_local_opks(
    task: JdTask,
    *,
    position_code: str | None,
    current_opks: CurrentJdOpks,
    kind: OpksEntityKind,
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
            (item for item in _in_kind(current_opks, kind) if task.task_id in item.task_refs),
            start=1,
        )
    )


def assemble_export_document(
    state: JobAnalysisState,
    *,
    title: str,
) -> ExportDocument:
    """把一份已驗證的 Current State 排成公版可渲染的純投影。"""

    current_opks = state.current_opks
    task_ids_by_item = _task_ids_by_item(current_opks)
    current_task_ids = {task.task_id for task in state.current_jd}

    linked_knowledge = tuple(
        item
        for item in _in_kind(current_opks, OpksEntityKind.KNOWLEDGE)
        if task_ids_by_item[item.entity_id] & current_task_ids
    )
    linked_skills = tuple(
        item
        for item in _in_kind(current_opks, OpksEntityKind.SKILL)
        if task_ids_by_item[item.entity_id] & current_task_ids
    )
    knowledge_codes = _document_codes(linked_knowledge, "K")
    skill_codes = _document_codes(linked_skills, "S")

    def competencies(
        task_id: str,
        kind: OpksEntityKind,
        codes: dict[str, ExportOpksEntry],
    ) -> tuple[ExportOpksEntry, ...]:
        return tuple(
            codes[item.entity_id]
            for item in _in_kind(current_opks, kind)
            if item.entity_id in codes and task_id in task_ids_by_item[item.entity_id]
        )

    def task_entry(task: JdTask, position_code: str | None) -> ExportTaskEntry:
        return ExportTaskEntry(
            task_id=task.task_id,
            position_code=position_code,
            statement=task.statement,
            competency_level=task.competency_level,
            outputs=_task_local_opks(
                task,
                position_code=position_code,
                current_opks=current_opks,
                kind=OpksEntityKind.OUTPUT,
                prefix="O",
            ),
            indicators=_task_local_opks(
                task,
                position_code=position_code,
                current_opks=current_opks,
                kind=OpksEntityKind.INDICATOR,
                prefix="P",
            ),
            knowledge=competencies(task.task_id, OpksEntityKind.KNOWLEDGE, knowledge_codes),
            skills=competencies(task.task_id, OpksEntityKind.SKILL, skill_codes),
        )

    ordered_duties = sorted(
        state.current_duties,
        key=lambda duty: (duty.display_order, duty.duty_id),
    )
    ordered_tasks = sorted(
        state.current_jd,
        key=lambda task: (task.display_order, task.task_id),
    )
    duties: list[ExportDutySection] = []
    assigned_task_ids: set[str] = set()
    for duty_index, duty in enumerate(ordered_duties, start=1):
        duty_code = f"T{duty_index}"
        tasks = [task for task in ordered_tasks if task.duty_id == duty.duty_id]
        assigned_task_ids.update(task.task_id for task in tasks)
        duties.append(
            ExportDutySection(
                position_code=duty_code,
                statement=duty.statement,
                tasks=tuple(
                    task_entry(task, f"{duty_code}.{task_index}")
                    for task_index, task in enumerate(tasks, start=1)
                ),
            )
        )

    unassigned_tasks = tuple(
        task_entry(task, None)
        for task in ordered_tasks
        if task.task_id not in assigned_task_ids
    )

    return ExportDocument(
        title=title,
        header=state.jd_header,
        duties=tuple(duties),
        unassigned_tasks=unassigned_tasks,
        attitudes=tuple(
            ExportOpksEntry(position_code=f"A{index:02d}", text=item.text)
            for index, item in enumerate(
                _in_kind(current_opks, OpksEntityKind.ATTITUDE),
                start=1,
            )
        ),
    )


__all__ = [
    "ExportDocument",
    "ExportDutySection",
    "ExportOpksEntry",
    "ExportTaskEntry",
    "assemble_export_document",
]
