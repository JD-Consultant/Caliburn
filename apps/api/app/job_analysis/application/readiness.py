"""iCAP 版型缺漏評估（ADR 0052 決定 1–7、ADR 0053 決定 6–8）。

純函式，住 `app/job_analysis`：規則是 domain 的事，**不依賴 transport contract、不碰 IO**
（ADR 0052 決定 1）。transport 只承載結果與固定 issue code（決定 2），Web 直接呈現、
不自行重算（決定 3），未來 exporter 呼叫同一支（決定 4）。

**只提示，不阻止。** 未填欄位不阻止保存、不阻止繼續訪談、也不阻止匯出（ADR 0052 決定 5）。
因此缺漏必須在成品上看得見是缺的——不自動補、不由 LLM 生成、不靜默省略。

第一版**只回 issue 清單**：沒有 `is_complete`／`ready`／完成百分比，零 issue 時保持安靜，
不宣稱整份 JD 已完整（ADR 0053 決定 6）。範圍僅限**未來可由員工編輯欄位修復、且官方
規則能確定**的表頭與 Duty／Task 結構缺漏；不新增 scope／version 欄位（ADR 0053 決定 7）。

刻意不發聲的欄位：

- `說明與補充事項` 是條件式欄位，空白不列缺漏（ADR 0053 決定 8）。
- `所屬類別`（職類別／職業別／行業別）——手冊未明確規定三者皆必填，依 ADR 0052 決定 6
  「無法確定的一律不提示」保守處理。這是刻意選擇，不是遺漏。
- `職能基準代碼`／`職類別代碼` 由 iCAP 配發，本來就沒有欄位（ADR 0052 決定 8）。
"""

from __future__ import annotations

from enum import StrEnum

from app.core.domain import (
    CurrentJdOpks,
    DomainModel,
    Duty,
    JdHeader,
    JdTask,
    OpksEntityKind,
)


class ReadinessIssueCode(StrEnum):
    COMPETENCY_NAME_MISSING = "competency_name_missing"
    WORK_DESCRIPTION_MISSING = "work_description_missing"
    COMPETENCY_LEVEL_MISSING = "competency_level_missing"
    TASK_DUTY_MISSING = "task_duty_missing"
    TASK_COMPETENCY_LEVEL_MISSING = "task_competency_level_missing"
    DUTY_WITHOUT_TASK = "duty_without_task"
    OPKS_TASK_LINK_MISSING = "opks_task_link_missing"


class ReadinessIssue(DomainModel):
    code: ReadinessIssueCode


class DocumentReadiness(DomainModel):
    """只有缺漏清單；不承擔完成判定。"""

    issues: tuple[ReadinessIssue, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)


# 依官方表頭順序；輸出順序決定性，呼叫端不需要再排序。
_HEADER_CHECKS: tuple[tuple[str, ReadinessIssueCode], ...] = (
    ("competency_name", ReadinessIssueCode.COMPETENCY_NAME_MISSING),
    ("work_description", ReadinessIssueCode.WORK_DESCRIPTION_MISSING),
    ("competency_level", ReadinessIssueCode.COMPETENCY_LEVEL_MISSING),
)


def assess_readiness(
    *,
    header: JdHeader,
    duties: tuple[Duty, ...],
    tasks: tuple[JdTask, ...],
    current_opks: CurrentJdOpks,
) -> DocumentReadiness:
    """回報目前可確定的表頭與結構缺漏；每個 code 一次。"""

    task_duty_missing = any(task.duty_id is None for task in tasks)
    task_level_missing = any(task.competency_level is None for task in tasks)
    assigned_duties = {task.duty_id for task in tasks if task.duty_id is not None}
    duty_without_task = any(duty.duty_id not in assigned_duties for duty in duties)
    current_task_ids = {task.task_id for task in tasks}
    linked_indicator_ids = {
        item.entity_id
        for item in current_opks.items
        if item.entity_kind is OpksEntityKind.INDICATOR
        and any(task_ref in current_task_ids for task_ref in item.task_refs)
    }
    unlinked_knowledge_or_skill = any(
        item.entity_kind in {OpksEntityKind.KNOWLEDGE, OpksEntityKind.SKILL}
        and not any(task_ref in current_task_ids for task_ref in item.task_refs)
        and not any(
            indicator_ref in linked_indicator_ids
            for indicator_ref in item.indicator_refs
        )
        for item in current_opks.items
    )

    structure_checks = (
        (task_duty_missing, ReadinessIssueCode.TASK_DUTY_MISSING),
        (task_level_missing, ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING),
        (duty_without_task, ReadinessIssueCode.DUTY_WITHOUT_TASK),
        (unlinked_knowledge_or_skill, ReadinessIssueCode.OPKS_TASK_LINK_MISSING),
    )

    return DocumentReadiness(
        issues=tuple(
            ReadinessIssue(code=code)
            for field, code in _HEADER_CHECKS
            if getattr(header, field) is None
        )
        + tuple(
            ReadinessIssue(code=code)
            for condition, code in structure_checks
            if condition
        )
    )
