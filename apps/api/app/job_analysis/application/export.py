"""Current State → 公版版面的決定性組裝（ADR 0058 決定 1–5）。

純函式，零 IO，**不 import transport contract**——同一條界線比照 `assess_readiness()`
（ADR 0052 決定 1）。所有位置碼在這裡算出，**只存在於回傳值裡，不落庫**
（ADR 0052 決定 10：`T1`／`O1.1.1` 是版面位置碼，不是 identity）。

渲染是另一步：這裡不知道 XLSX、不知道儲存格，只回一個已排好序、位置碼已算好的值物件。

**未指派主要職責的 Task 沒有位置碼**，歸進 `unassigned_tasks`；不得為了湊出 `T{i}.{j}`
而虛構 Duty（ADR 0052 決定 13 的匯出端體現）。渲染層必須把這群 Task 呈現出來。
"""

from __future__ import annotations

from app.job_analysis.domain import (
    CurrentJdOpks,
    DomainModel,
    Duty,
    JdHeader,
    JdTask,
    NonEmptyText,
    OpksEntityKind,
    OpksItem,
)

from .transition import JobAnalysisState


class ExportOpksEntry(DomainModel):
    """一條 O／P／K／S／A。

    `position_code` 為 `None` 只發生在**未指派主要職責的 Task** 底下的 O／P：
    沒有 `T{i}.{j}` 就推不出 `O{i}.{j}.{k}`。**內容仍然帶出來**——排不進表格不是
    把它從成品上刪掉的理由（ADR 0052 決定 5：缺漏要看得見，不是靜默省略）。
    """

    position_code: NonEmptyText | None
    text: NonEmptyText


class ExportTaskEntry(DomainModel):
    """一條工作任務。`position_code` 為 `None` 代表尚未歸入主要職責。"""

    task_id: NonEmptyText
    position_code: NonEmptyText | None
    statement: NonEmptyText
    competency_level: int | None
    outputs: tuple[ExportOpksEntry, ...] = ()
    indicators: tuple[ExportOpksEntry, ...] = ()


class ExportDutySection(DomainModel):
    position_code: NonEmptyText
    statement: NonEmptyText
    tasks: tuple[ExportTaskEntry, ...] = ()


class ExportDocument(DomainModel):
    title: NonEmptyText
    header: JdHeader
    duties: tuple[ExportDutySection, ...] = ()
    unassigned_tasks: tuple[ExportTaskEntry, ...] = ()
    knowledge: tuple[ExportOpksEntry, ...] = ()
    skills: tuple[ExportOpksEntry, ...] = ()
    attitudes: tuple[ExportOpksEntry, ...] = ()


def _in_kind(
    current_opks: CurrentJdOpks,
    kind: OpksEntityKind,
) -> tuple[OpksItem, ...]:
    """該 kind 的項目，依 `display_order` 明確排序。

    **不依賴 tuple 既有順序**：`CurrentJdOpks` 只保證同 kind 內 `display_order` 唯一，
    不保證 tuple 已排好（切片 A 的裁決）。位置碼的正確性由這裡的排序負責。
    """

    return tuple(
        sorted(
            (item for item in current_opks.items if item.entity_kind is kind),
            key=lambda item: item.display_order,
        )
    )


def _document_level(
    current_opks: CurrentJdOpks,
    kind: OpksEntityKind,
    prefix: str,
) -> tuple[ExportOpksEntry, ...]:
    """K／S／A 是**文件層平坦編號**（`K01`），不分 Duty／Task（ADR 0048 決定 5）。"""

    return tuple(
        ExportOpksEntry(position_code=f"{prefix}{index:02d}", text=item.text)
        for index, item in enumerate(_in_kind(current_opks, kind), start=1)
    )


def _task_entry(
    task: JdTask,
    *,
    position_code: str | None,
    current_opks: CurrentJdOpks,
) -> ExportTaskEntry:
    def scoped(kind: OpksEntityKind, prefix: str) -> tuple[ExportOpksEntry, ...]:
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
                (
                    item
                    for item in _in_kind(current_opks, kind)
                    if task.task_id in item.task_refs
                ),
                start=1,
            )
        )

    return ExportTaskEntry(
        task_id=task.task_id,
        position_code=position_code,
        statement=task.statement,
        competency_level=task.competency_level,
        outputs=scoped(OpksEntityKind.OUTPUT, "O"),
        indicators=scoped(OpksEntityKind.INDICATOR, "P"),
    )


def assemble_export_document(
    state: JobAnalysisState,
    *,
    title: str,
) -> ExportDocument:
    """把 Current State 排成公版版面。同輸入同輸出，零 IO。"""

    duties: list[ExportDutySection] = []
    assigned: set[str] = set()
    ordered_duties = sorted(state.current_duties, key=lambda duty: duty.display_order)
    ordered_tasks = sorted(state.current_jd, key=lambda task: task.display_order)

    for duty_index, duty in enumerate(ordered_duties, start=1):
        duty_code = f"T{duty_index}"
        in_duty = [task for task in ordered_tasks if task.duty_id == duty.duty_id]
        assigned.update(task.task_id for task in in_duty)
        duties.append(
            ExportDutySection(
                position_code=duty_code,
                statement=duty.statement,
                tasks=tuple(
                    _task_entry(
                        task,
                        position_code=f"{duty_code}.{task_index}",
                        current_opks=state.current_opks,
                    )
                    for task_index, task in enumerate(in_duty, start=1)
                ),
            )
        )

    unassigned = tuple(
        _task_entry(task, position_code=None, current_opks=state.current_opks)
        for task in ordered_tasks
        if task.task_id not in assigned
    )

    return ExportDocument(
        title=title,
        header=state.jd_header,
        duties=tuple(duties),
        unassigned_tasks=unassigned,
        knowledge=_document_level(state.current_opks, OpksEntityKind.KNOWLEDGE, "K"),
        skills=_document_level(state.current_opks, OpksEntityKind.SKILL, "S"),
        attitudes=_document_level(state.current_opks, OpksEntityKind.ATTITUDE, "A"),
    )


__all__ = [
    "ExportDocument",
    "ExportDutySection",
    "ExportOpksEntry",
    "ExportTaskEntry",
    "assemble_export_document",
]
