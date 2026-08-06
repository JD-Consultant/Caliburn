"""Current State → 公版版面的決定性組裝（ADR 0058 決定 1–5）。

純函式，零 IO，**不 import transport contract**——同一條界線比照 `assess_readiness()`
（ADR 0052 決定 1）。所有位置碼在這裡算出，**只存在於回傳值裡，不落庫**
（ADR 0052 決定 10：`T1`／`O1.1.1` 是版面位置碼，不是 identity）。

渲染是另一步：這裡不知道 XLSX、不知道儲存格，只回一個已排好序、位置碼已算好的值物件。

**K/S 掛在每個 Task 底下，但編號是文件層的。** 官方表格（2026-08-06 逐份核對七份官方
職能基準範例）的主表有七欄，最後兩欄是「職能內涵（K=knowledge知識）」與
「職能內涵（S=skills技能）」——同一個 `K01` 會在多個 Task 列重複出現。這與
ADR 0048 決定 7 一致：「不必複製」講的是 identity（不鑄 `K01-a`／`K01-b`），
而同一條決定明文允許「UI 可把 K/S 投影在 Task 底下」。

**未指派主要職責的 Task 沒有位置碼**，歸進 `unassigned_tasks`；不得為了湊出 `T{i}.{j}`
而虛構 Duty（ADR 0052 決定 13 的匯出端體現）。同理，沒有連上任何 Task 的 K/S 歸進
`unlinked_knowledge`／`unlinked_skills`——排不進主表不是讓它從成品上消失的理由。
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
    """一條 O／P／K／S／A。

    `position_code` 為 `None` 只發生在**未指派主要職責的 Task** 底下的 O／P：
    沒有 `T{i}.{j}` 就推不出 `O{i}.{j}.{k}`。**內容仍然帶出來**——排不進表格不是
    把它從成品上刪掉的理由（ADR 0052 決定 5：缺漏要看得見，不是靜默省略）。
    """

    position_code: NonEmptyText | None
    text: NonEmptyText

    @property
    def rendered(self) -> str:
        """官方版面是位置碼與文字**直接相連、不留空格**（`O1.1.1提款單/匯款單`）。"""

        if self.position_code is None:
            return self.text
        return f"{self.position_code}{self.text}"


class ExportTaskEntry(DomainModel):
    """一條工作任務。`position_code` 為 `None` 代表尚未歸入主要職責。"""

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

    @property
    def rendered(self) -> str:
        return f"{self.position_code}{self.statement}"


class ExportDocument(DomainModel):
    title: NonEmptyText
    header: JdHeader
    duties: tuple[ExportDutySection, ...] = ()
    unassigned_tasks: tuple[ExportTaskEntry, ...] = ()
    #: 沒有連上任何 Task 的知識／技能。主表放不下它們，但不得因此消失。
    unlinked_knowledge: tuple[ExportOpksEntry, ...] = ()
    unlinked_skills: tuple[ExportOpksEntry, ...] = ()
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


def _document_codes(
    current_opks: CurrentJdOpks,
    kind: OpksEntityKind,
    prefix: str,
) -> dict[str, ExportOpksEntry]:
    """K／S／A 的**文件層平坦編號**（`K01`）。同一條到哪一列都是同一個碼。"""

    return {
        item.entity_id: ExportOpksEntry(
            position_code=f"{prefix}{index:02d}", text=item.text
        )
        for index, item in enumerate(_in_kind(current_opks, kind), start=1)
    }


def _tasks_of(item: OpksItem, indicator_tasks: dict[str, tuple[str, ...]]) -> set[str]:
    """一條 K／S 屬於哪些 Task：直接 `task_refs`，或透過它引用的行為指標。

    ADR 0048 決定 6：K/S 與 Task／Indicator 是多對多。只看 `task_refs` 會漏掉
    「只掛在指標上」的那些。
    """

    tasks = set(item.task_refs)
    for indicator_id in item.indicator_refs:
        tasks.update(indicator_tasks.get(indicator_id, ()))
    return tasks


def assemble_export_document(
    state: JobAnalysisState,
    *,
    title: str,
) -> ExportDocument:
    """把 Current State 排成公版版面。同輸入同輸出，零 IO。"""

    opks = state.current_opks
    knowledge_codes = _document_codes(opks, OpksEntityKind.KNOWLEDGE, "K")
    skill_codes = _document_codes(opks, OpksEntityKind.SKILL, "S")
    indicator_tasks = {
        item.entity_id: item.task_refs
        for item in _in_kind(opks, OpksEntityKind.INDICATOR)
    }
    kind_by_entity = {
        item.entity_id: _tasks_of(item, indicator_tasks)
        for item in opks.items
        if item.entity_kind in {OpksEntityKind.KNOWLEDGE, OpksEntityKind.SKILL}
    }

    def competencies(
        task_id: str,
        kind: OpksEntityKind,
        codes: dict[str, ExportOpksEntry],
    ) -> tuple[ExportOpksEntry, ...]:
        return tuple(
            codes[item.entity_id]
            for item in _in_kind(opks, kind)
            if task_id in kind_by_entity.get(item.entity_id, set())
        )

    def task_entry(task: JdTask, position_code: str | None) -> ExportTaskEntry:
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
                        for item in _in_kind(opks, kind)
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
            knowledge=competencies(
                task.task_id, OpksEntityKind.KNOWLEDGE, knowledge_codes
            ),
            skills=competencies(task.task_id, OpksEntityKind.SKILL, skill_codes),
        )

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
                    task_entry(task, f"{duty_code}.{task_index}")
                    for task_index, task in enumerate(in_duty, start=1)
                ),
            )
        )

    unassigned = tuple(
        task_entry(task, None)
        for task in ordered_tasks
        if task.task_id not in assigned
    )

    current_task_ids = {task.task_id for task in ordered_tasks}

    def unlinked(
        kind: OpksEntityKind, codes: dict[str, ExportOpksEntry]
    ) -> tuple[ExportOpksEntry, ...]:
        return tuple(
            codes[item.entity_id]
            for item in _in_kind(opks, kind)
            if not (kind_by_entity.get(item.entity_id, set()) & current_task_ids)
        )

    return ExportDocument(
        title=title,
        header=state.jd_header,
        duties=tuple(duties),
        unassigned_tasks=unassigned,
        unlinked_knowledge=unlinked(OpksEntityKind.KNOWLEDGE, knowledge_codes),
        unlinked_skills=unlinked(OpksEntityKind.SKILL, skill_codes),
        attitudes=tuple(
            _document_codes(opks, OpksEntityKind.ATTITUDE, "A").values()
        ),
    )


__all__ = [
    "ExportDocument",
    "ExportDutySection",
    "ExportOpksEntry",
    "ExportTaskEntry",
    "assemble_export_document",
]
