"""主要職責（Major Duty）—— Current JD 的第一層結構（ADR 0052 決定 13）。

官方（2022 指引 p37）：「分層展開主要職責、工作任務、工作活動（**建議以主要職責、
工作任務 2 層為主**）」。因此這裡只做 Duty → Task 兩層，**不做工作活動第三層**。

刻意**沒有**的欄位：

- **職能級別**：官方說「個別工作任務之職能級別，可能涵蓋不只一個級別」，所以級別掛
  `JdTask` 不掛 Duty。
- **`T1` 位置碼**：`T1`／`T1.1` 是匯出時依排序決定性產生的**版面位置碼**，不是 identity，
  不落庫（ADR 0052 決定 10）。內部一律用 `duty_id`。
- **purpose／outcome**：官方版型沒有這個欄位。加了就是發明版型。

「職責大小要盡量一致、跨公司共通」是**語意判斷**，verifier 攔不住，留給員工與日後 rubric。
"""

from __future__ import annotations

from pydantic import Field

from .base import DomainModel, Identifier, NonEmptyText


DutyId = Identifier


class Duty(DomainModel):
    duty_id: DutyId
    statement: NonEmptyText
    display_order: int = Field(ge=0)
