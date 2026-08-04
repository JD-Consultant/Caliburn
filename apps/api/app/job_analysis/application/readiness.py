"""iCAP 版型缺漏評估（ADR 0052 決定 1–7、ADR 0053 決定 6–8）。

純函式，住 `app/job_analysis`：規則是 domain 的事，**不依賴 transport contract、不碰 IO**
（ADR 0052 決定 1）。transport 只承載結果與固定 issue code（決定 2），Web 直接呈現、
不自行重算（決定 3），未來 exporter 呼叫同一支（決定 4）。

**只提示，不阻止。** 未填欄位不阻止保存、不阻止繼續訪談、也不阻止匯出（ADR 0052 決定 5）。
因此缺漏必須在成品上看得見是缺的——不自動補、不由 LLM 生成、不靜默省略。

第一版**只回 issue 清單**：沒有 `is_complete`／`ready`／完成百分比，零 issue 時保持安靜，
不宣稱整份 JD 已完整（ADR 0053 決定 6）。範圍僅限**目前 UI 可修復、且官方規則能確定**的
表頭缺漏；Duty 與每個 Task 的職能級別規則等該結構切片完成時**加進本函式**，不新增
scope／version 欄位（ADR 0053 決定 7）。

刻意不發聲的欄位：

- `說明與補充事項` 是條件式欄位，空白不列缺漏（ADR 0053 決定 8）。
- `所屬類別`（職類別／職業別／行業別）——**owner 於 2026-08-05 裁定非必填**，
  所以空白永遠不發聲。這在此之前是依 ADR 0052 決定 6「無法確定的一律不提示」的保守暫定，
  現在是正式決定；要翻案需先有官方依據。
- `職能基準代碼`／`職類別代碼` 由 iCAP 配發，本來就沒有欄位（ADR 0052 決定 8）。
"""

from __future__ import annotations

from enum import StrEnum

from app.job_analysis.domain import DomainModel, JdHeader, NonEmptyText


class ReadinessIssueCode(StrEnum):
    COMPETENCY_NAME_MISSING = "competency_name_missing"
    WORK_DESCRIPTION_MISSING = "work_description_missing"
    COMPETENCY_LEVEL_MISSING = "competency_level_missing"


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


def assess_readiness(header: JdHeader) -> DocumentReadiness:
    """回報目前可確定的表頭缺漏；沒有缺漏時回空清單。"""

    return DocumentReadiness(
        issues=tuple(
            ReadinessIssue(code=code, field=field)
            for field, code in _HEADER_CHECKS
            if getattr(header, field) is None
        )
    )
