"""iCAP 版型缺漏評估（ADR 0052 決定 1–7、ADR 0053 決定 6–8）。

純函式，住 `app/job_analysis`：規則是 domain 的事，**不依賴 transport contract、不碰 IO**
（ADR 0052 決定 1）。transport 只承載結果與固定 issue code（決定 2），Web 直接呈現、
不自行重算（決定 3），未來 exporter 呼叫同一支（決定 4）。

**只提示，不阻止。** 未填欄位不阻止保存、不阻止繼續訪談、也不阻止匯出（ADR 0052 決定 5）。
因此缺漏必須在成品上看得見是缺的——不自動補、不由 LLM 生成、不靜默省略。

第一版**只回 issue 清單**：沒有 `is_complete`／`ready`／完成百分比，零 issue 時保持安靜，
不宣稱整份 JD 已完整（ADR 0053 決定 6）。範圍僅限**目前 UI 可修復、且官方規則能確定**的
缺漏。Duty 與每個 Task 的職能級別規則已於 Duty 切片 T2 **加進本函式**，未新增
scope／version 欄位（ADR 0053 決定 7）。

刻意不發聲的欄位：

- `說明與補充事項` 是條件式欄位，空白不列缺漏（ADR 0053 決定 8）。
- **工作產出（O）缺席**——官方允許操作性質任務把成果併入行為指標（ADR 0052 決定 15），
  不得機械判成缺漏。
- **態度（A）為空**——官方「視需求納入考量」（決定 16），同樣不列。
- `所屬類別`（職類別／職業別／行業別）——**owner 於 2026-08-05 裁定非必填**，
  所以空白永遠不發聲。這在此之前是依 ADR 0052 決定 6「無法確定的一律不提示」的保守暫定，
  現在是正式決定；要翻案需先有官方依據。
- `職能基準代碼`／`職類別代碼` 由 iCAP 配發，本來就沒有欄位（ADR 0052 決定 8）。
"""

from __future__ import annotations

from enum import StrEnum

from app.job_analysis.domain import Duty, DomainModel, JdHeader, JdTask, NonEmptyText


class ReadinessIssueCode(StrEnum):
    COMPETENCY_NAME_MISSING = "competency_name_missing"
    WORK_DESCRIPTION_MISSING = "work_description_missing"
    COMPETENCY_LEVEL_MISSING = "competency_level_missing"
    TASK_DUTY_MISSING = "task_duty_missing"
    TASK_COMPETENCY_LEVEL_MISSING = "task_competency_level_missing"
    DUTY_WITHOUT_TASK = "duty_without_task"


class ReadinessIssue(DomainModel):
    code: ReadinessIssueCode
    field: NonEmptyText


class DocumentReadiness(DomainModel):
    """只有缺漏清單。措辭「iCAP 版型欄位尚有 X 項未填」由呈現層負責，

    不得使用「不完整」「不合格」「未通過」——我們產出的是客製 JD，不是送審的職能基準
    （ADR 0052 決定 7）。
    """

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
) -> DocumentReadiness:
    """回報目前可確定的缺漏；沒有缺漏時回空清單。

    三個參數都是**必填 keyword**，沒有預設值:漏傳 `tasks` 會是 `TypeError`,
    不會變成「這份文件沒有結構缺漏」這種安靜的錯答案。

    結構缺漏**一個 code 一則**,不是一個 Task 一則。readiness 是提示不是待辦清單
    （ADR 0053 決定 6）,而「哪幾條 Task 還沒歸職責」由 UI 分組直接看得出來。
    """

    issues = [
        ReadinessIssue(code=code, field=f"jd_header.{field}")
        for field, code in _HEADER_CHECKS
        if getattr(header, field) is None
    ]

    # 官方產出完整性清單（2022 指引 p38）把「主要職責及工作任務」與「職能級別」列為
    # 必備內涵,兩者都可機械判定。
    if any(task.duty_id is None for task in tasks):
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.TASK_DUTY_MISSING,
                field="current_jd.duty_id",
            )
        )
    if any(task.competency_level is None for task in tasks):
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING,
                field="current_jd.competency_level",
            )
        )
    # 空職責在版型上推不出任何 `T{i}.{j}` 列——它是被建立但沒有展開的那一層。
    assigned = {task.duty_id for task in tasks if task.duty_id is not None}
    if any(duty.duty_id not in assigned for duty in duties):
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.DUTY_WITHOUT_TASK,
                field="current_duties",
            )
        )
    return DocumentReadiness(issues=tuple(issues))
