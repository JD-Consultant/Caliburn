"""`ExportDocument` → XLSX 位元組（ADR 0058 決定 9–13）。

渲染層。它只知道 `ExportDocument` 與 `DocumentReadiness`，**不知道 Current State、
不碰 IO、不算位置碼**——那是 `assemble_export_document()` 的事。

版面依 **2026-08-06 逐份核對的七份官方職能基準範例**（`.odt` 2023 版與 `.docx` 2025 版
結構一致），不是照手冊散文推的：

- 主表**七欄**：主要職責｜工作任務｜工作產出｜行為指標｜職能級別｜職能內涵（K）｜職能內涵（S）
- 同一格內多筆以**換行**並列，不是一筆一列
- 位置碼與文字**直接相連不留空格**（`O1.1.1提款單/匯款單`）
- 主要職責格**跨其工作任務列垂直合併**
- 態度與說明與補充事項**各自獨立表格**

兩個工作表（決定 12）：

1. **職能基準表** —— 公版版面。未填欄位維持**空白儲存格**：欄位必須在，只是空的。
   不自動補、不由 LLM 生成、**不靜默省略那一格**，也不印「（尚未填寫）」這類雜訊
   （要交給主管／HR 的是這張表）。
2. **iCAP 版型缺漏** —— 呼叫 `assess_readiness()` 的結果。這是**落實 ADR 0052 決定 4**
   「未來 exporter 呼叫同一套 assessment」；若匯出完全不呼叫它，那條決定就成了死條文。

`職能基準代碼`／`職類別代碼` 固定印「（iCAP 計畫執行單位提供）」——它們由 iCAP 配發，
不開輸入欄、不生成（ADR 0052 決定 8）。官方範例那兩格填的是官方核發的真實代碼，
我們產出的是客製 JD，不是送審的職能基準（ADR 0040 決定 33–34）。
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from .export import ExportDocument, ExportOpksEntry, ExportTaskEntry
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
UNLINKED_LABEL = "（尚未連結工作任務）"

#: 官方主表的七個欄位標題，逐字照抄範例。
TABLE_HEADERS = (
    "主要職責",
    "工作任務",
    "工作產出",
    "行為指標",
    "職能級別",
    "職能內涵（K=knowledge知識）",
    "職能內涵（S=skills技能）",
)

ATTITUDE_HEADER = "職能內涵（A=attitude態度）"
NOTES_HEADER = "說明與補充事項"

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

_BOLD = Font(bold=True)
_WRAP = Alignment(vertical="top", wrap_text=True)
_LAST_COLUMN = len(TABLE_HEADERS)


def _stack(entries: tuple[ExportOpksEntry, ...]) -> str | None:
    """同一格內多筆以換行並列——官方版面就是這樣，不是一筆一列。"""

    return "\n".join(entry.rendered for entry in entries) or None


def _put(sheet: Worksheet, row: int, column: int, value: object, *, bold=False) -> None:
    cell = sheet.cell(row=row, column=column, value=value)
    cell.alignment = _WRAP
    if bold:
        cell.font = _BOLD


def _merge(sheet: Worksheet, row: int, first: int, last: int) -> None:
    if last > first:
        sheet.merge_cells(start_row=row, start_column=first, end_row=row, end_column=last)


def _write_header_block(sheet: Worksheet, document: ExportDocument) -> int:
    header = document.header
    row = 1
    _put(sheet, row, 1, f"{header.competency_name or document.title}職能基準", bold=True)
    _merge(sheet, row, 1, _LAST_COLUMN)
    row += 2

    _put(sheet, row, 1, "職能基準代碼", bold=True)
    _put(sheet, row, 2, ISSUED_BY_ICAP)
    _merge(sheet, row, 2, _LAST_COLUMN)
    row += 1

    # 官方是「職能基準名稱（擇一填寫）」＋職類／職業兩列。我們產出的是**特定職位**的
    # 職務說明書，所以名稱填在「職業」列；「職類」列留空由員工自行判斷是否改填。
    name_row = row
    _put(sheet, row, 1, "職能基準名稱\n（擇一填寫）", bold=True)
    _put(sheet, row, 2, "職類", bold=True)
    _merge(sheet, row, 3, _LAST_COLUMN)
    row += 1
    _put(sheet, row, 2, "職業", bold=True)
    _put(sheet, row, 3, header.competency_name)
    _merge(sheet, row, 3, _LAST_COLUMN)
    # 標籤跨兩列垂直合併，照官方版面
    sheet.merge_cells(start_row=name_row, start_column=1, end_row=row, end_column=1)
    row += 1

    category_row = row
    _put(sheet, row, 1, "所屬類別", bold=True)
    for label, name, code_label, code in (
        ("職類別", header.occupation_category_name, "職類別代碼", ISSUED_BY_ICAP),
        ("職業別", header.occupation_name, "職業別代碼", header.occupation_code),
        ("行業別", header.industry_name, "行業別代碼", header.industry_code),
    ):
        _put(sheet, row, 2, label, bold=True)
        _put(sheet, row, 3, name)
        _put(sheet, row, 5, code_label, bold=True)
        _put(sheet, row, 6, code)
        _merge(sheet, row, 3, 4)
        _merge(sheet, row, 6, _LAST_COLUMN)
        row += 1
    sheet.merge_cells(
        start_row=category_row, start_column=1, end_row=row - 1, end_column=1
    )

    _put(sheet, row, 1, "工作描述", bold=True)
    _put(sheet, row, 2, header.work_description)
    _merge(sheet, row, 2, _LAST_COLUMN)
    row += 1
    _put(sheet, row, 1, "基準級別", bold=True)
    _put(sheet, row, 2, header.competency_level)
    _merge(sheet, row, 2, _LAST_COLUMN)
    return row + 2


def _write_task_row(sheet: Worksheet, row: int, entry: ExportTaskEntry) -> None:
    task_cell = (
        f"{entry.position_code}{entry.statement}"
        if entry.position_code is not None
        else entry.statement
    )
    _put(sheet, row, 2, task_cell)
    _put(sheet, row, 3, _stack(entry.outputs))
    _put(sheet, row, 4, _stack(entry.indicators))
    _put(sheet, row, 5, entry.competency_level)
    _put(sheet, row, 6, _stack(entry.knowledge))
    _put(sheet, row, 7, _stack(entry.skills))


def _write_table(sheet: Worksheet, row: int, document: ExportDocument) -> int:
    for column, title in enumerate(TABLE_HEADERS, start=1):
        _put(sheet, row, column, title, bold=True)
    row += 1

    for section in document.duties:
        if not section.tasks:
            # 空職責照樣出現——那正是 readiness 的 `duty_without_task` 要讓人看見的缺漏
            _put(sheet, row, 1, section.rendered)
            row += 1
            continue
        first = row
        _put(sheet, row, 1, section.rendered)
        for entry in section.tasks:
            _write_task_row(sheet, row, entry)
            row += 1
        # 主要職責格跨其工作任務列垂直合併，照官方版面
        if row - first > 1:
            sheet.merge_cells(
                start_row=first, start_column=1, end_row=row - 1, end_column=1
            )

    # 未歸入主要職責的 Task 必須有自己的區塊——排不進表格不是讓它消失的理由
    # （ADR 0058 決定 3 的硬性要求）
    if document.unassigned_tasks:
        first = row
        _put(sheet, row, 1, UNASSIGNED_LABEL)
        for entry in document.unassigned_tasks:
            _write_task_row(sheet, row, entry)
            row += 1
        if row - first > 1:
            sheet.merge_cells(
                start_row=first, start_column=1, end_row=row - 1, end_column=1
            )

    # 沒有連上任何 Task 的 K/S 同理：主表放不下，但不得從成品上消失
    if document.unlinked_knowledge or document.unlinked_skills:
        _put(sheet, row, 1, UNLINKED_LABEL)
        _put(sheet, row, 6, _stack(document.unlinked_knowledge))
        _put(sheet, row, 7, _stack(document.unlinked_skills))
        row += 1
    return row + 1


def _write_block(sheet: Worksheet, row: int, title: str, body: object) -> int:
    _put(sheet, row, 1, title, bold=True)
    _merge(sheet, row, 1, _LAST_COLUMN)
    row += 1
    _put(sheet, row, 1, body)
    _merge(sheet, row, 1, _LAST_COLUMN)
    return row + 2


def _render_form(sheet: Worksheet, document: ExportDocument) -> None:
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 24
    for letter in ("C", "D"):
        sheet.column_dimensions[letter].width = 42
    sheet.column_dimensions["E"].width = 8
    for letter in ("F", "G"):
        sheet.column_dimensions[letter].width = 30

    row = _write_header_block(sheet, document)
    row = _write_table(sheet, row, document)
    row = _write_block(sheet, row, ATTITUDE_HEADER, _stack(document.attitudes))
    row = _write_block(sheet, row, NOTES_HEADER, document.header.notes)
    _put(sheet, row, 1, DISCLAIMER)
    _merge(sheet, row, 1, _LAST_COLUMN)


def _render_readiness(sheet: Worksheet, readiness: DocumentReadiness) -> None:
    """措辭沿用 ADR 0052 決定 7，**不得**用「不完整／不合格／未通過」。"""

    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 40
    _put(
        sheet,
        1,
        1,
        f"iCAP 版型欄位尚有 {readiness.issue_count} 項未填",
        bold=True,
    )
    _put(sheet, 3, 1, "項目", bold=True)
    _put(sheet, 3, 2, "欄位", bold=True)
    for offset, issue in enumerate(readiness.issues):
        _put(
            sheet,
            4 + offset,
            1,
            READINESS_LABELS.get(issue.code, issue.code.value),
        )
        _put(sheet, 4 + offset, 2, issue.field)


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
    "ATTITUDE_HEADER",
    "DISCLAIMER",
    "ISSUED_BY_ICAP",
    "NOTES_HEADER",
    "READINESS_LABELS",
    "SHEET_FORM",
    "SHEET_READINESS",
    "TABLE_HEADERS",
    "UNASSIGNED_LABEL",
    "UNLINKED_LABEL",
    "render_xlsx",
]
