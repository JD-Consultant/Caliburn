"""`ExportDocument` → XLSX 位元組（ADR 0058 決定 9–13）。

渲染層。它只知道 `ExportDocument` 與 `DocumentReadiness`，**不知道 Current State、
不碰 IO、不算位置碼**——那是 `assemble_export_document()` 的事。

兩個工作表（決定 12）：

1. **職能基準表** —— 公版版面。未填欄位維持**空白儲存格**：欄位必須在，只是空的。
   不自動補、不由 LLM 生成、**不靜默省略那一格**，也不印「（尚未填寫）」這類雜訊
   （要交給主管／HR 的是這張表）。
2. **iCAP 版型缺漏** —— 呼叫 `assess_readiness()` 的結果。這是**落實 ADR 0052 決定 4**
   「未來 exporter 呼叫同一套 assessment」；若匯出完全不呼叫它，那條決定就成了死條文。

`職能基準代碼`／`職類別代碼` 固定印「（iCAP 計畫執行單位提供）」——它們由 iCAP 配發，
不開輸入欄、不生成（ADR 0052 決定 8）。
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from .export import ExportDocument, ExportTaskEntry
from .readiness import DocumentReadiness, ReadinessIssueCode


SHEET_FORM = "職能基準表"
SHEET_READINESS = "iCAP 版型缺漏"

#: ADR 0040 決定 33 的公版措辭。匯出檔案上固定出現，不可省略。
DISCLAIMER = (
    "採 iCAP 職能基準欄位版型的客製職務說明書，不代表勞動部認證或官方職能基準。"
)

#: ADR 0052 決定 8：由 iCAP 計畫執行單位配發，不開輸入欄、不生成。
ISSUED_BY_ICAP = "（iCAP 計畫執行單位提供）"

UNASSIGNED_LABEL = "（尚未歸入主要職責）"

#: readiness issue 的呈現文案。Web 另有一份（`lib/jobAnalysisHeader.ts`）——
#: 兩個呈現面各自持有文案，但**都不得自行判斷缺漏**（ADR 0052 決定 3）。
#: 有測試斷言每個 `ReadinessIssueCode` 都有對應文案，新增 code 卻忘了文案會變紅。
READINESS_LABELS: dict[ReadinessIssueCode, str] = {
    ReadinessIssueCode.COMPETENCY_NAME_MISSING: "職能基準名稱",
    ReadinessIssueCode.WORK_DESCRIPTION_MISSING: "工作描述",
    ReadinessIssueCode.COMPETENCY_LEVEL_MISSING: "基準級別",
    ReadinessIssueCode.TASK_DUTY_MISSING: "工作任務的所屬主要職責",
    ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING: "工作任務的職能級別",
    ReadinessIssueCode.DUTY_WITHOUT_TASK: "主要職責底下的工作任務",
}

_TABLE_HEADERS = (
    "主要職責",
    "工作任務",
    "工作產出",
    "行為指標",
    "職能級別",
)

_BOLD = Font(bold=True)
_WRAP = Alignment(vertical="top", wrap_text=True)


def _label(sheet: Worksheet, row: int, text: str, value: object = None) -> int:
    sheet.cell(row=row, column=1, value=text).font = _BOLD
    if value is not None:
        sheet.cell(row=row, column=2, value=value).alignment = _WRAP
    return row + 1


def _write_header_block(sheet: Worksheet, document: ExportDocument) -> int:
    header = document.header
    row = 1
    sheet.cell(row=row, column=1, value=document.title).font = Font(bold=True, size=14)
    row += 2

    row = _label(sheet, row, "職能基準代碼", ISSUED_BY_ICAP)
    row = _label(sheet, row, "職能基準名稱", header.competency_name)
    row = _label(sheet, row, "職類別", header.occupation_category_name)
    row = _label(sheet, row, "職類別代碼", ISSUED_BY_ICAP)
    row = _label(sheet, row, "職業別", header.occupation_name)
    row = _label(sheet, row, "職業別代碼", header.occupation_code)
    row = _label(sheet, row, "行業別", header.industry_name)
    row = _label(sheet, row, "行業別代碼", header.industry_code)
    row = _label(sheet, row, "工作描述", header.work_description)
    row = _label(sheet, row, "基準級別", header.competency_level)
    return row + 1


def _write_task_rows(
    sheet: Worksheet,
    row: int,
    *,
    duty_cell: str | None,
    entry: ExportTaskEntry,
) -> int:
    """一條 Task 佔 max(1, |O|, |P|) 列；職責／任務／級別只寫在第一列。"""

    span = max(1, len(entry.outputs), len(entry.indicators))
    for offset in range(span):
        current = row + offset
        if offset == 0:
            if duty_cell is not None:
                sheet.cell(row=current, column=1, value=duty_cell).alignment = _WRAP
            task_cell = (
                f"{entry.position_code} {entry.statement}"
                if entry.position_code is not None
                else entry.statement
            )
            sheet.cell(row=current, column=2, value=task_cell).alignment = _WRAP
            if entry.competency_level is not None:
                sheet.cell(row=current, column=5, value=entry.competency_level)
        for column, items in ((3, entry.outputs), (4, entry.indicators)):
            if offset < len(items):
                item = items[offset]
                text = (
                    f"{item.position_code} {item.text}"
                    if item.position_code is not None
                    else item.text
                )
                sheet.cell(row=current, column=column, value=text).alignment = _WRAP
    return row + span


def _write_table(sheet: Worksheet, row: int, document: ExportDocument) -> int:
    for column, title in enumerate(_TABLE_HEADERS, start=1):
        sheet.cell(row=row, column=column, value=title).font = _BOLD
    row += 1

    for section in document.duties:
        duty_cell = f"{section.position_code} {section.statement}"
        if not section.tasks:
            # 空職責照樣出現——那正是 readiness 的 `duty_without_task` 要讓人看見的缺漏
            sheet.cell(row=row, column=1, value=duty_cell).alignment = _WRAP
            row += 1
            continue
        for index, entry in enumerate(section.tasks):
            row = _write_task_rows(
                sheet,
                row,
                duty_cell=duty_cell if index == 0 else None,
                entry=entry,
            )

    # 未歸入主要職責的 Task 必須有自己的區塊——排不進表格不是讓它消失的理由
    # （ADR 0058 決定 3 的硬性要求）
    for index, entry in enumerate(document.unassigned_tasks):
        row = _write_task_rows(
            sheet,
            row,
            duty_cell=UNASSIGNED_LABEL if index == 0 else None,
            entry=entry,
        )
    return row + 1


def _write_document_level(sheet: Worksheet, row: int, document: ExportDocument) -> int:
    for title, entries in (
        ("職能內涵：知識", document.knowledge),
        ("職能內涵：技能", document.skills),
        ("態度", document.attitudes),
    ):
        sheet.cell(row=row, column=1, value=title).font = _BOLD
        row += 1
        for entry in entries:
            sheet.cell(row=row, column=1, value=entry.position_code)
            sheet.cell(row=row, column=2, value=entry.text).alignment = _WRAP
            row += 1
        row += 1
    return row


def _render_form(sheet: Worksheet, document: ExportDocument) -> None:
    sheet.column_dimensions["A"].width = 24
    for letter in ("B", "C", "D"):
        sheet.column_dimensions[letter].width = 40
    sheet.column_dimensions["E"].width = 10

    row = _write_header_block(sheet, document)
    row = _write_table(sheet, row, document)
    row = _write_document_level(sheet, row, document)
    row = _label(sheet, row, "說明與補充事項", document.header.notes)
    row += 1
    sheet.cell(row=row, column=1, value=DISCLAIMER).alignment = _WRAP


def _render_readiness(sheet: Worksheet, readiness: DocumentReadiness) -> None:
    """措辭沿用 ADR 0052 決定 7，**不得**用「不完整／不合格／未通過」。"""

    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 40
    sheet.cell(
        row=1,
        column=1,
        value=f"iCAP 版型欄位尚有 {readiness.issue_count} 項未填",
    ).font = _BOLD
    sheet.cell(row=3, column=1, value="項目").font = _BOLD
    sheet.cell(row=3, column=2, value="欄位").font = _BOLD
    for offset, issue in enumerate(readiness.issues):
        sheet.cell(
            row=4 + offset,
            column=1,
            value=READINESS_LABELS.get(issue.code, issue.code.value),
        )
        sheet.cell(row=4 + offset, column=2, value=issue.field)


def render_xlsx(
    document: ExportDocument,
    readiness: DocumentReadiness,
) -> bytes:
    workbook = Workbook()
    form = workbook.active
    assert form is not None
    form.title = SHEET_FORM
    _render_form(form, document)
    _render_readiness(workbook.create_sheet(SHEET_READINESS), readiness)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


__all__ = [
    "DISCLAIMER",
    "ISSUED_BY_ICAP",
    "READINESS_LABELS",
    "SHEET_FORM",
    "SHEET_READINESS",
    "UNASSIGNED_LABEL",
    "render_xlsx",
]
