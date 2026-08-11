"""Table utilities for the OCS transformer (moved verbatim from OCSTransformer, Phase 3b).

Stateless helpers for cleaning, classifying, and mapping pdfplumber tables. The
two alias/key tables that only these functions consume live here as module
constants.
"""

import re
from typing import Any, Dict, List, Optional

from jd_pdf_to_json.transformers.support import text as txt

# ── Column / label alias tables ───────────────────────────────────────────────

OCU_HEADER_ALIASES: Dict[str, List[str]] = {
    "task_code": ["工作任務代碼", "任務代碼", "taskcode", "task id"],
    "task_name": ["工作任務", "任務名稱", "taskname", "task"],
    "level": ["職能級別", "級別", "等級", "level"],
    "knowledge": ["知識", "knowledge", "知能"],
    "skills": ["技能", "skill"],
    "outputs": ["工作產出", "產出", "output"],
    "behavioral": ["行為指標", "behavioral", "indicator", "績效指標"],
}

CONTENT_HEADER_KEYS: Dict[str, List[str]] = {
    "major_duty": ["主要職責"],
    "task": ["工作任務"],
    "output": ["工作產出"],
    "behavioral": ["行為指標"],
    "level": ["職能級別", "職能級別"],
    "knowledge": ["知識", "kknowledge知識", "knowledge知識"],
    "skills": ["技能", "sskills技能", "skills技能"],
}


def row_to_normalized_cells(row: List[Any]) -> List[str]:
    return [txt.normalize_text(cell) for cell in row]


def row_to_joined_normalized_text(row: List[Any]) -> str:
    """Join all normalized row cells into one string for table-type checks."""
    return "".join(row_to_normalized_cells(row))


def merge_rows_for_header(rows: List[List[Any]]) -> List[Any]:
    """Column-wise merge of adjacent header rows for split table headers."""
    if not rows:
        return []
    max_len = max(len(row) for row in rows)
    merged: List[str] = []
    for idx in range(max_len):
        parts = [
            str(row[idx]).strip()
            for row in rows
            if idx < len(row) and row[idx] is not None and str(row[idx]).strip()
        ]
        merged.append(" ".join(parts))
    return merged


def is_page_footer_row(row: List[Any]) -> bool:
    """Return True for common pagination footers like '第1頁，總共11頁'."""
    text = row_to_joined_normalized_text(row)
    return bool(text and re.search(r"^第\d+頁總共\d+頁$", text))


def clean_table_rows(table: List[List[Any]]) -> List[List[Any]]:
    """Strip empty rows and page-footer noise from a table."""
    result: List[List[Any]] = []
    for row in table:
        if not row:
            continue
        if all(cell is None or not str(cell).strip() for cell in row):
            continue
        if is_page_footer_row(row):
            continue
        result.append(row)
    return result


def is_content_header_row(row: List[Any]) -> bool:
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
    if not all(
        any(txt.normalize_text(a) in text for a in aliases) for aliases in required
    ):
        return False
    has_knowledge = any(
        txt.normalize_text(a) in text for a in CONTENT_HEADER_KEYS["knowledge"]
    )
    has_skills = any(
        txt.normalize_text(a) in text for a in CONTENT_HEADER_KEYS["skills"]
    )
    return has_knowledge and has_skills


def is_split_content_header(rows: List[List[Any]]) -> bool:
    """Return True when adjacent rows together form the content header."""
    if not rows:
        return False
    return is_content_header_row(merge_rows_for_header(rows))


def detect_table_type(table: List[List[Any]]) -> Optional[str]:
    """Classify a table as one of five fixed section types."""
    rows = clean_table_rows(table)
    if not rows:
        return None

    sample = rows[: min(len(rows), 5)]
    joined = " ".join(row_to_joined_normalized_text(r) for r in sample)

    if any(
        "職能內涵" in row_to_joined_normalized_text(r)
        and "attitude" in row_to_joined_normalized_text(r)
        for r in sample
    ):
        return "ocs_attitude"

    if any("說明與補充事項" in row_to_joined_normalized_text(r) for r in sample):
        return "notes_and_appendix"

    if any(
        is_content_header_row(r)
        or is_split_content_header(rows[i : i + 2])
        or is_split_content_header(rows[i : i + 3])
        for i, r in enumerate(sample)
    ):
        return "ocs_content"

    if all(k in joined for k in ["版本", "職能基準代碼", "職能基準名稱", "狀態"]):
        return "version_info"

    if any(k in joined for k in ["職能基準代碼", "所屬類別", "工作描述", "基準級別"]):
        return "ocs_profile"

    return None


def find_ocu_header_row(
    table: List[List[Any]]
) -> tuple[Optional[int], Dict[str, int], int]:
    """Find the OCU header row; return (row_index, col_map, row_span)."""
    best: tuple[Optional[int], Dict[str, int], int, int] = (None, {}, 0, -1)

    for row_idx, row in enumerate(table):
        candidates = [(row, 1)]
        if row_idx + 1 < len(table):
            candidates.append(
                (merge_rows_for_header([row, table[row_idx + 1]]), 2)
            )
        if row_idx + 2 < len(table):
            candidates.append(
                (
                    merge_rows_for_header(
                        [row, table[row_idx + 1], table[row_idx + 2]]
                    ),
                    3,
                )
            )

        for candidate, span in candidates:
            col_map = build_column_map(candidate, OCU_HEADER_ALIASES)
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


def is_ocu_candidate_table(table: List[List[Any]]) -> bool:
    """Return True when a table likely contains OCU task data."""
    return bool(table) and find_ocu_header_row(table)[0] is not None


def find_value_to_right(row: List[Any], index: int) -> Optional[str]:
    """Return the nearest non-empty cell to the right of *index*."""
    for cell in row[index + 1 :]:
        if cell is not None and str(cell).strip():
            return str(cell).strip()
    return None


def find_cell_value(row: List[Any], idx: int, window: int = 2) -> Optional[str]:
    """Return the nearest non-empty cell around *idx* within ±*window*."""
    for offset in range(0, window + 1):
        for sign in ([0] if offset == 0 else [1, -1]):
            check_idx = idx + sign * offset
            if 0 <= check_idx < len(row) and row[check_idx]:
                val = str(row[check_idx]).strip()
                if val:
                    return val
    return None


def build_column_map(
    header_row: List[Any], aliases: Dict[str, List[str]]
) -> Dict[str, int]:
    """Build a semantic column-index mapping from a header row."""
    mapping: Dict[str, int] = {}
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
