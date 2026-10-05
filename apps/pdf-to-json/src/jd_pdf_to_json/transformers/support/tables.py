"""Table utilities for the OCS transformer (moved verbatim from OCSTransformer, Phase 3b).

Stateless helpers for cleaning, classifying, and mapping pdfplumber tables. The
two alias/key tables that only these functions consume live here as module
constants.
"""

import re
from typing import Any

from jd_pdf_to_json.parsers.models import PDFTable
from jd_pdf_to_json.transformers.support import text as txt
from jd_pdf_to_json.utils.exceptions import TransformationError

# ── Column / label alias tables ───────────────────────────────────────────────

OCU_HEADER_ALIASES: dict[str, list[str]] = {
    "major_duty": ["主要職責", "工作職責"],
    "task_code": ["工作任務代碼", "任務代碼", "taskcode", "task id"],
    "task_name": ["工作任務", "任務名稱", "taskname", "task"],
    "level": ["職能級別", "級別", "等級", "level"],
    "knowledge": ["知識", "knowledge", "知能"],
    "skills": ["技能", "skill"],
    "outputs": ["工作產出", "產出", "output"],
    "behavioral": ["行為指標", "behavioral", "indicator", "績效指標"],
}

CONTENT_HEADER_KEYS: dict[str, list[str]] = {
    "major_duty": ["主要職責"],
    "task": ["工作任務"],
    "output": ["工作產出"],
    "behavioral": ["行為指標"],
    "level": ["職能級別", "職能級別"],
    "knowledge": ["知識", "kknowledge知識", "knowledge知識"],
    "skills": ["技能", "sskills技能", "skills技能"],
}


def row_to_normalized_cells(row: list[Any]) -> list[str]:
    return [txt.normalize_text(cell) for cell in row]


def row_to_joined_normalized_text(row: list[Any]) -> str:
    """Join all normalized row cells into one string for table-type checks."""
    return "".join(row_to_normalized_cells(row))


def merge_rows_for_header(rows: list[list[Any]]) -> list[Any]:
    """Column-wise merge of adjacent header rows for split table headers."""
    if not rows:
        return []
    max_len = max(len(row) for row in rows)
    merged: list[str] = []
    for idx in range(max_len):
        parts = [
            str(row[idx]).strip()
            for row in rows
            if idx < len(row) and row[idx] is not None and str(row[idx]).strip()
        ]
        merged.append(" ".join(parts))
    return merged


def is_page_footer_row(row: list[Any]) -> bool:
    """Return True for common pagination footers like '第1頁，總共11頁'."""
    text = row_to_joined_normalized_text(row)
    return bool(text and re.search(r"^第\d+頁總共\d+頁$", text))


def clean_table_rows(table: list[list[Any]]) -> list[list[Any]]:
    """Strip empty rows and page-footer noise from a table."""
    result: list[list[Any]] = []
    for row in table:
        if not row:
            continue
        if all(cell is None or not str(cell).strip() for cell in row):
            continue
        if is_page_footer_row(row):
            continue
        result.append(row)
    return result


def is_content_header_row(row: list[Any]) -> bool:
    """Return True when a row matches the fixed OCS content header layout."""
    text = row_to_joined_normalized_text(row)
    if not text:
        return False
    required = [
        CONTENT_HEADER_KEYS["task"],
        CONTENT_HEADER_KEYS["output"],
        CONTENT_HEADER_KEYS["behavioral"],
        CONTENT_HEADER_KEYS["level"],
    ]
    if not all(any(txt.normalize_text(a) in text for a in aliases) for aliases in required):
        return False
    has_knowledge = any(txt.normalize_text(a) in text for a in CONTENT_HEADER_KEYS["knowledge"])
    has_skills = any(txt.normalize_text(a) in text for a in CONTENT_HEADER_KEYS["skills"])
    return has_knowledge and has_skills


def is_split_content_header(rows: list[list[Any]]) -> bool:
    """Return True when adjacent rows together form the content header."""
    if not rows:
        return False
    return is_content_header_row(merge_rows_for_header(rows))


def section_heading_type(row: list[Any]) -> str | None:
    """Recognize a standalone section heading, not a mention inside a body cell."""
    cells = [txt.normalize_text(cell) for cell in row if cell and str(cell).strip()]
    if len(cells) != 1:
        return None
    heading = cells[0]
    if heading in {"說明與補充", "說明與補充事項"}:
        return "notes_and_appendix"
    if heading.startswith(("職能內涵", "職業內涵")) and "attitude" in heading:
        return "ocs_attitude"
    return None


def detect_table_type(table: list[list[Any]]) -> str | None:
    """Classify a table as one of five fixed section types."""
    rows = clean_table_rows(table)
    if not rows:
        return None

    sample = rows[: min(len(rows), 5)]
    joined = " ".join(row_to_joined_normalized_text(r) for r in sample)

    # Revision notes may mention later section headings; the version table's
    # own labels have priority over those body references.
    if all(k in joined for k in ["版本", "職能基準代碼", "職能基準名稱", "狀態"]):
        return "version_info"

    # A physical table may contain the final task followed by attitudes. Only
    # its first row classifies the whole table as a later section.
    heading = section_heading_type(rows[0])
    if heading:
        return heading

    if any(
        is_content_header_row(r)
        or is_split_content_header(rows[i : i + 2])
        or is_split_content_header(rows[i : i + 3])
        for i, r in enumerate(sample)
    ):
        return "ocs_content"

    if any(k in joined for k in ["職能基準代碼", "所屬類別", "工作描述", "基準級別"]):
        return "ocs_profile"

    return None


def find_ocu_header_row(table: list[list[Any]]) -> tuple[int | None, dict[str, int], int]:
    """Find the OCU header row; return (row_index, col_map, row_span)."""
    best: tuple[int | None, dict[str, int], int, int] = (None, {}, 0, -1)

    for row_idx, row in enumerate(table):
        candidates = [(row, 1)]
        if row_idx + 1 < len(table):
            candidates.append((merge_rows_for_header([row, table[row_idx + 1]]), 2))
        if row_idx + 2 < len(table):
            candidates.append(
                (
                    merge_rows_for_header([row, table[row_idx + 1], table[row_idx + 2]]),
                    3,
                )
            )

        for candidate, span in candidates:
            # Body items cannot supply a missing label in a split header.
            if any(
                re.search(r"(?<![A-Za-z0-9])[TPKSO]\.?\d+", txt.normalize_code_spacing(str(cell)))
                for part in table[row_idx : row_idx + span]
                for cell in part
                if cell
            ):
                continue
            col_map = build_column_map(candidate, OCU_HEADER_ALIASES)
            if "level" not in col_map:
                level_columns = [
                    i for i, cell in enumerate(candidate) if txt.normalize_text(cell) == "職能"
                ]
                if len(level_columns) == 1:
                    col_map["level"] = level_columns[0]
            if "task_name" not in col_map:
                continue
            has_competency = any(
                k in col_map for k in ("knowledge", "skills", "outputs", "behavioral")
            )
            if not has_competency:
                continue
            if "task_code" not in col_map:
                # Common layout: task code is embedded in the task name column.
                col_map["task_code"] = col_map["task_name"]
            score = sum(
                k in col_map
                for k in ("outputs", "behavioral", "knowledge", "skills", "level", "task_code")
            )
            if score > best[3]:
                best = (row_idx, col_map, span, score)

    return best[0], best[1], best[2]


def is_ocu_candidate_table(table: list[list[Any]]) -> bool:
    """Return True when a table likely contains OCU task data."""
    return bool(table) and find_ocu_header_row(table)[0] is not None


def find_value_to_right(row: list[Any], index: int) -> str | None:
    """Return the nearest non-empty cell to the right of *index*."""
    for cell in row[index + 1 :]:
        if cell is not None and str(cell).strip():
            return str(cell).strip()
    return None


def find_cell_value(row: list[Any], idx: int, window: int = 2) -> str | None:
    """Return the nearest non-empty cell around *idx* within ±*window*."""
    for offset in range(0, window + 1):
        for sign in [0] if offset == 0 else [1, -1]:
            check_idx = idx + sign * offset
            if 0 <= check_idx < len(row) and row[check_idx]:
                val = str(row[check_idx]).strip()
                if val:
                    return val
    return None


def build_column_map(header_row: list[Any], aliases: dict[str, list[str]]) -> dict[str, int]:
    """Build a semantic column-index mapping from a header row."""
    mapping: dict[str, int] = {}
    normalized_cells = row_to_normalized_cells(header_row)
    for idx, cell in enumerate(normalized_cells):
        if not cell:
            continue
        for field, alias_list in aliases.items():
            if field in mapping:
                continue
            if any(txt.normalize_text(a) in cell for a in alias_list):
                mapping[field] = idx
    return mapping


CANONICAL_FIELDS = (
    "major_duty",
    "task_name",
    "outputs",
    "behavioral",
    "level",
    "knowledge",
    "skills",
    "task_code",
)
CANONICAL_HEADER = [
    "主要職責",
    "工作任務",
    "工作產出",
    "行為指標",
    "職能級別",
    "知識",
    "技能",
    "工作任務代碼",
]


def content_anchors(table: PDFTable) -> tuple[dict[str, float], int] | None:
    index, mapping, span = find_ocu_header_row(table.rows)
    if index is None:
        return None
    required = {"task_name", "outputs", "behavioral", "knowledge", "skills"}
    location = f"page {table.page_number}, table {table.table_number}"
    if not required.issubset(mapping):
        raise TransformationError(f"Unsupported content header at {location}: {mapping}")
    anchors = {}
    for field, column in mapping.items():
        for row_index in range(index, index + span):
            cell = table.cells[row_index][column]
            if cell is not None:
                anchors[field] = (cell[0] + cell[2]) / 2
                break
    if mapping["task_code"] == mapping["task_name"]:
        anchors.pop("task_code", None)
    return anchors, index + span


def canonical_content_rows(
    table: PDFTable, continuation_anchors: dict[str, float] | None = None
) -> list[list[str | None]] | None:
    """Map each table's body cells by its own header positions, not grid indices.

    PDF drawing rectangles can split a header into narrow blank subcolumns while
    body cells span those subcolumns. The header centre must fall inside the body
    cell; adjacent cell values are never borrowed to fill missing fields.
    """
    header = content_anchors(table)
    if header is None and continuation_anchors is None:
        return None
    anchors, body_start = header if header is not None else (continuation_anchors, 0)
    location = f"page {table.page_number}, table {table.table_number}"
    if "task_name" not in anchors:
        raise TransformationError(f"Missing task header position at {location}")
    result = []
    for row_index in range(body_start, len(table.rows)):
        row = table.rows[row_index]
        if section_heading_type(row):
            break
        if is_page_footer_row(row):
            continue
        mapped = [None] * len(CANONICAL_FIELDS)
        for column, value in enumerate(row):
            if not value or not value.strip():
                continue
            box = table.cells[row_index][column]
            fields = [field for field, x in anchors.items() if box and box[0] <= x < box[2]]
            if len(fields) != 1:
                raise TransformationError(
                    f"Unmapped content cell at {location}, row {row_index + 1}, column {column + 1}"
                )
            target = CANONICAL_FIELDS.index(fields[0])
            if value not in (mapped[target] or "").split("\n") and mapped[target] != value:
                mapped[target] = "\n".join(filter(None, (mapped[target], value)))
        if any(mapped):
            if "task_code" not in anchors:
                mapped[-1] = mapped[1]
            result.append(mapped)
    return result


def mapped_content_tables(source):
    """Recognize primary tables and geometrically aligned headerless continuations.

    pdfplumber may report nested text rectangles as extra tables. Their text is
    already present in the containing table; they are not new task rows.
    """
    anchors = None
    finished = False
    for page in source.pages:
        primary = []
        for table in page.tables:
            x0, top, x1, bottom = table.bbox
            containers = [
                other
                for other in page.tables
                if other is not table
                and other.bbox != table.bbox
                and other.bbox[0] <= x0
                and other.bbox[1] <= top
                and other.bbox[2] >= x1
                and other.bbox[3] >= bottom
            ]
            if containers:
                if not any(
                    all(
                        txt.normalize_text(cell)
                        in txt.normalize_text(
                            "".join(str(value or "") for row in parent.rows for value in row)
                        )
                        for row in table.rows
                        for cell in row
                        if cell and cell.strip()
                    )
                    for parent in containers
                ):
                    raise TransformationError(
                        f"Uncovered nested table at page {page.page_number}, table {table.table_number}"
                    )
                continue
            primary.append(table)
        for table in sorted(primary, key=lambda item: (item.bbox[1], item.bbox[0])):
            section = detect_table_type(table.rows)
            if section in ("ocs_attitude", "notes_and_appendix"):
                finished = True
            if finished or section in ("ocs_profile", "version_info"):
                continue
            header = content_anchors(table)
            if header is not None:
                anchors = header[0]
            elif anchors is None:
                if any(re.search(r"[TPKS]\d+\.?(?:\d|\b)", str(row)) for row in table.rows):
                    raise TransformationError(
                        f"Unsupported content table at page {page.page_number}, table {table.table_number}"
                    )
                continue
            rows = canonical_content_rows(table, anchors)
            if rows:
                yield table, rows
            if any(section_heading_type(row) for row in table.rows):
                finished = True
