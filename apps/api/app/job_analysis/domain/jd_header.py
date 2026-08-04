"""JD 表頭的公版語意欄位（ADR 0053 決定 2）。

這是 Current JD authority 的一部分，不是 `DocumentMetadataWrite`：`title` 仍然只是文件庫
名稱與 rename seam（ADR 0053 決定 1），本模型承載 iCAP 2026 版型附錄二的表頭語意欄位。

**沒有 `職能基準代碼`／`職類別代碼`。** 這兩個代碼由 iCAP 計畫執行單位配發，不開輸入欄、
不列缺漏、application 與 LLM 都不得生成（ADR 0052 決定 8）。`職業別`／`行業別` 的名稱與
代碼屬分類資料，可由員工填寫（ADR 0052 決定 9），因此在這裡。

每個欄位都可為 `None`；`None` 表示「還沒填」。空字串**不是**合法值——HTTP DTO mapper 先 trim
成 `null`，半成品不進 domain。
"""

from __future__ import annotations

from pydantic import Field

from .base import DomainModel, NonEmptyText


class JdHeader(DomainModel):
    """手冊的基準級別為 1–6；未填只提示不擋，也不由 LLM 推論（ADR 0052 決定 12）。"""

    competency_name: NonEmptyText | None = None
    occupation_category_name: NonEmptyText | None = None
    occupation_name: NonEmptyText | None = None
    occupation_code: NonEmptyText | None = None
    industry_name: NonEmptyText | None = None
    industry_code: NonEmptyText | None = None
    work_description: NonEmptyText | None = None
    competency_level: int | None = Field(default=None, ge=1, le=6)
    notes: NonEmptyText | None = None

    @property
    def is_empty(self) -> bool:
        return all(
            getattr(self, name) is None for name in type(self).model_fields
        )
