"""OCS PDF → OCSDocument transformer implementation."""

import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, TypeVar

import pdfplumber

from jd_pdf_to_json.core.models import (
    OCSDocument,
    VersionInfo,
    VersionEntry,
    OCSProfile,
    OCSName,
    OCSCategory,
    CategoryItem,
    OCSUnit,
    Task,
    TaskCodeEntry,
    CompetencyBlock,
    OutputItem,
    BehavioralIndicator,
    CompetencyItem,
    Attitude,
    OCSContent,
    OCSAttitude,
    Notes,
)
from jd_pdf_to_json.transformers.base import BaseOCSTransformer
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.utils.logger import logger

_T = TypeVar("_T")


class OCSTransformer(BaseOCSTransformer):
    """Transform PDF raw data into OCSDocument model."""

    # ── Column / label alias tables ───────────────────────────────────────────

    OCU_HEADER_ALIASES: Dict[str, List[str]] = {
        "task_code": ["工作任務代碼", "任務代碼", "taskcode", "task id"],
        "task_name": ["工作任務", "任務名稱", "taskname", "task"],
        "level": ["職能級別", "級別", "等級", "level"],
        "knowledge": ["知識", "knowledge", "知能"],
        "skills": ["技能", "skill"],
        "outputs": ["工作產出", "產出", "output"],
        "behavioral": ["行為指標", "behavioral", "indicator", "績效指標"],
    }

    VERSION_HEADER_ALIASES: Dict[str, List[str]] = {
        "version": ["版本", "version"],
        "ocs_code": ["職能基準代碼", "職能代碼", "ocscode"],
        "ocs_name": ["職能基準名稱", "職能名稱", "ocsname"],
        "status": ["狀態", "status"],
        "update_note": ["更新說明", "修訂內容", "備註", "note"],
        "update_date": ["發展更新日期", "更新日期", "date"],
    }

    PROFILE_LABEL_ALIASES: Dict[str, List[str]] = {
        "job_category": ["職類別", "職類", "jobcategory"],
        "occupation": ["職業", "occupation"],
        "industry": ["所屬產業", "產業", "行業別", "行業", "industry"],
        "job_description": ["工作描述", "職務描述", "jobdescription"],
        "ocs_level": ["基準級別", "職能級別", "level"],
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

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def __init__(self):
        self.logger = logger

    def transform(self, raw_data: dict) -> OCSDocument:
        """Transform raw PDF data into a structured OCSDocument.

        Args:
            raw_data: Dict with keys 'file_path', 'metadata', and 'pages'.

        Returns:
            Validated OCSDocument model.

        Raises:
            TransformationError: on failure.
        """
        try:
            file_path = raw_data.get("file_path", "")
            self.logger.info(f"開始轉換: {file_path}")

            with pdfplumber.open(file_path) as pdf:
                version_info = self._extract_version_info(pdf)
                self.logger.debug(f"✓ 版本信息: {len(version_info.versions)} 筆紀錄")

                ocs_profile = self._extract_profile(pdf, version_info)
                self.logger.debug(f"✓ Profile: {ocs_profile.ocs_code}")

                ocs_content = self._extract_content(pdf)
                self.logger.debug(f"✓ 內容: {len(ocs_content.ocu_units)} 個職能單元")

                ocs_attitude = self._extract_attitude(pdf)
                self.logger.debug(f"✓ 態度: {len(ocs_attitude.attitudes)} 個態度")

                notes = self._extract_notes(pdf)
                self.logger.debug(
                    f"✓ 補充: {len(notes.prerequisites)} 條件 / {len(notes.supplements)} 補充說明"
                )

                doc = OCSDocument(
                    version_info=version_info,
                    ocs_profile=ocs_profile,
                    ocs_content=ocs_content,
                    ocs_attitude=ocs_attitude,
                    notes=notes,
                )
                self.logger.info(f"✓ 轉換完成: {ocs_profile.ocs_code}")
                return doc

        except Exception as e:
            self.logger.error(f"✗ 轉換失敗: {str(e)}")
            raise TransformationError(f"Failed to transform PDF: {str(e)}") from e

    # ── Text normalization ────────────────────────────────────────────────────

    def _normalize_text(self, value: Any) -> str:
        """Normalize text for robust header matching across layouts."""
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value))
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"[\s　]+", "", text)
        text = re.sub(r"[：:()（）\[\]【】、,，.-]+", "", text)
        return text.lower().strip()

    def _compact_wrapped_text(self, value: Any) -> str:
        """Collapse a wrapped cell value into a single readable line."""
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value))
        text = text.replace("\r", "").replace("\n", "")
        return re.sub(r"\s+", "", text).strip()

    def _split_lines(self, value: Any) -> List[str]:
        """Split cell text by newline, keeping slash-combined phrases intact."""
        if not value:
            return []
        text = unicodedata.normalize("NFKC", str(value)).replace("\r", "\n")
        return [line.strip() for line in text.split("\n") if line and line.strip()]

    def _split_multi_value(self, value: str) -> List[str]:
        """Split a profile cell into candidate items on common delimiters."""
        normalized = unicodedata.normalize("NFKC", value)
        parts = re.split(r"[、,，;；\n]+", normalized)
        return [p.strip() for p in parts if p and p.strip()]

    def _append_text_if_new(self, original: str, tail: str) -> str:
        """Append continuation text only when it is not already present."""
        if not tail:
            return original
        if not original:
            return tail
        if tail in original:
            return original
        return f"{original}{tail}"

    # ── Table utilities ───────────────────────────────────────────────────────

    def _row_to_normalized_cells(self, row: List[Any]) -> List[str]:
        return [self._normalize_text(cell) for cell in row]

    def _row_to_joined_normalized_text(self, row: List[Any]) -> str:
        """Join all normalized row cells into one string for table-type checks."""
        return "".join(self._row_to_normalized_cells(row))

    def _merge_rows_for_header(self, rows: List[List[Any]]) -> List[Any]:
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

    def _is_page_footer_row(self, row: List[Any]) -> bool:
        """Return True for common pagination footers like '第1頁，總共11頁'."""
        text = self._row_to_joined_normalized_text(row)
        return bool(text and re.search(r"^第\d+頁總共\d+頁$", text))

    def _clean_table_rows(self, table: List[List[Any]]) -> List[List[Any]]:
        """Strip empty rows and page-footer noise from a table."""
        result: List[List[Any]] = []
        for row in table:
            if not row:
                continue
            if all(cell is None or not str(cell).strip() for cell in row):
                continue
            if self._is_page_footer_row(row):
                continue
            result.append(row)
        return result

    def _is_content_header_row(self, row: List[Any]) -> bool:
        """Return True when a row matches the fixed OCS content header layout."""
        text = self._row_to_joined_normalized_text(row)
        if not text:
            return False
        required = [
            self.CONTENT_HEADER_KEYS["task"],
            self.CONTENT_HEADER_KEYS["output"],
            self.CONTENT_HEADER_KEYS["behavioral"],
            self.CONTENT_HEADER_KEYS["level"],
        ]
        if not all(
            any(self._normalize_text(a) in text for a in aliases) for aliases in required
        ):
            return False
        has_knowledge = any(
            self._normalize_text(a) in text for a in self.CONTENT_HEADER_KEYS["knowledge"]
        )
        has_skills = any(
            self._normalize_text(a) in text for a in self.CONTENT_HEADER_KEYS["skills"]
        )
        return has_knowledge and has_skills

    def _is_split_content_header(self, rows: List[List[Any]]) -> bool:
        """Return True when adjacent rows together form the content header."""
        if not rows:
            return False
        return self._is_content_header_row(self._merge_rows_for_header(rows))

    def _detect_table_type(self, table: List[List[Any]]) -> Optional[str]:
        """Classify a table as one of five fixed section types."""
        rows = self._clean_table_rows(table)
        if not rows:
            return None

        sample = rows[: min(len(rows), 5)]
        joined = " ".join(self._row_to_joined_normalized_text(r) for r in sample)

        if any(
            "職能內涵" in self._row_to_joined_normalized_text(r)
            and "attitude" in self._row_to_joined_normalized_text(r)
            for r in sample
        ):
            return "ocs_attitude"

        if any("說明與補充事項" in self._row_to_joined_normalized_text(r) for r in sample):
            return "notes_and_appendix"

        if any(
            self._is_content_header_row(r)
            or self._is_split_content_header(rows[i : i + 2])
            or self._is_split_content_header(rows[i : i + 3])
            for i, r in enumerate(sample)
        ):
            return "ocs_content"

        if all(k in joined for k in ["版本", "職能基準代碼", "職能基準名稱", "狀態"]):
            return "version_info"

        if any(k in joined for k in ["職能基準代碼", "所屬類別", "工作描述", "基準級別"]):
            return "ocs_profile"

        return None

    def _find_ocu_header_row(
        self, table: List[List[Any]]
    ) -> tuple[Optional[int], Dict[str, int], int]:
        """Find the OCU header row; return (row_index, col_map, row_span)."""
        best: tuple[Optional[int], Dict[str, int], int, int] = (None, {}, 0, -1)

        for row_idx, row in enumerate(table):
            candidates = [(row, 1)]
            if row_idx + 1 < len(table):
                candidates.append(
                    (self._merge_rows_for_header([row, table[row_idx + 1]]), 2)
                )
            if row_idx + 2 < len(table):
                candidates.append(
                    (
                        self._merge_rows_for_header(
                            [row, table[row_idx + 1], table[row_idx + 2]]
                        ),
                        3,
                    )
                )

            for candidate, span in candidates:
                col_map = self._build_column_map(candidate, self.OCU_HEADER_ALIASES)
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

    def _is_ocu_candidate_table(self, table: List[List[Any]]) -> bool:
        """Return True when a table likely contains OCU task data."""
        return bool(table) and self._find_ocu_header_row(table)[0] is not None

    def _find_value_to_right(self, row: List[Any], index: int) -> Optional[str]:
        """Return the nearest non-empty cell to the right of *index*."""
        for cell in row[index + 1 :]:
            if cell is not None and str(cell).strip():
                return str(cell).strip()
        return None

    def _find_cell_value(self, row: List[Any], idx: int, window: int = 2) -> Optional[str]:
        """Return the nearest non-empty cell around *idx* within ±*window*."""
        for offset in range(0, window + 1):
            for sign in ([0] if offset == 0 else [1, -1]):
                check_idx = idx + sign * offset
                if 0 <= check_idx < len(row) and row[check_idx]:
                    val = str(row[check_idx]).strip()
                    if val:
                        return val
        return None

    def _build_column_map(
        self, header_row: List[Any], aliases: Dict[str, List[str]]
    ) -> Dict[str, int]:
        """Build a semantic column-index mapping from a header row."""
        mapping: Dict[str, int] = {}
        normalized_cells = self._row_to_normalized_cells(header_row)
        for idx, cell in enumerate(normalized_cells):
            if not cell:
                continue
            for field, alias_list in aliases.items():
                if field in mapping:
                    continue
                if any(self._normalize_text(a) in cell for a in alias_list):
                    mapping[field] = idx
        return mapping

    # ── Item extraction ───────────────────────────────────────────────────────

    def _extract_output_items(self, cell_value: Any) -> List[OutputItem]:
        """Parse O-code work outputs from a cell."""
        if not cell_value:
            return []
        text = self._compact_wrapped_text(cell_value)
        if not text:
            return []

        pattern = re.compile(r"(O\d+(?:[-.]\d+)*)", re.IGNORECASE)
        matches = list(pattern.finditer(text))
        if matches:
            outputs: List[OutputItem] = []
            for i, m in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                outputs.append(
                    OutputItem(code=m.group(1).strip(), name=text[m.end() : end].strip("；;，,"))
                )
            return outputs

        return [
            OutputItem(code=t, name="")
            for t in (tok.strip() for tok in re.split(r"[\s,，;；\n]+", text))
            if re.fullmatch(r"O\d+(?:[-.]\d+)*", t, flags=re.IGNORECASE)
        ]

    def _extract_behavioral_indicators(self, cell_value: Any) -> List[BehavioralIndicator]:
        """Parse P/T behavioral indicators from a cell."""
        if not cell_value:
            return []
        text = self._compact_wrapped_text(cell_value)
        if not text:
            return []

        # [PT]\.? handles both P1.1.1 and P.1.1.1 (old-format PDFs use dot after P)
        pattern = re.compile(r"([PT]\.?\d+(?:[-.]\d+)*)", re.IGNORECASE)
        matches = list(pattern.finditer(text))
        if matches:
            indicators: List[BehavioralIndicator] = []
            for i, m in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                indicator_text = text[m.end() : end].strip("；;，,") or m.group(1).strip()
                indicators.append(BehavioralIndicator(code=m.group(1).strip(), text=indicator_text))
            return indicators

        # Last-resort: numeric-only codes missing P prefix
        num_pattern = re.compile(r"(?<![A-Za-z])(\d+(?:[.-]\d+)+)")
        num_matches = list(num_pattern.finditer(text))
        indicators = []
        for i, m in enumerate(num_matches):
            end = num_matches[i + 1].start() if i + 1 < len(num_matches) else len(text)
            indicator_text = text[m.end() : end].strip("；;，,") or m.group(1).strip()
            indicators.append(BehavioralIndicator(code=f"P{m.group(1)}", text=indicator_text))
        return indicators

    def _extract_behavioral_indicators_from_row(
        self, row: List[Any]
    ) -> List[BehavioralIndicator]:
        """Fallback P-code extraction scanning all cells in a row."""
        row_text = "\n".join(
            str(c).strip() for c in row if c is not None and str(c).strip()
        )
        if not row_text:
            return []
        pattern = re.compile(r"(P\.?\d+(?:[-.]\d+)*)", re.IGNORECASE)
        matches = list(pattern.finditer(row_text))
        indicators: List[BehavioralIndicator] = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(row_text)
            indicator_text = row_text[m.end() : end].strip("；;，,") or m.group(1).strip()
            indicators.append(BehavioralIndicator(code=m.group(1).strip(), text=indicator_text))
        return indicators

    def _extract_competency_items(
        self, cell_value: Any, code_prefix: str
    ) -> List[CompetencyItem]:
        """Parse K/S competency items from a cell."""
        if not cell_value:
            return []
        raw = unicodedata.normalize("NFKC", str(cell_value)).replace("\r", "\n")
        text = "\n".join(line.strip() for line in raw.split("\n") if line and line.strip())
        if not text:
            return []
        pattern = re.compile(
            rf"({code_prefix}\d+(?:[-.]\d+)*)([\s\S]*?)(?=(?:[KS]\d+(?:[-.]\d+)*)|$)",
            flags=re.IGNORECASE,
        )
        return [
            CompetencyItem(
                code=m.group(1).strip(),
                name=re.sub(r"\s+", " ", m.group(2)).strip("；;，, ") or m.group(1).strip(),
            )
            for m in pattern.finditer(text)
        ]

    def _extract_competency_items_from_row(
        self, row: List[Any], code_prefix: str
    ) -> List[CompetencyItem]:
        """Fallback K/S extraction scanning all cells in a row."""
        row_text = "\n".join(
            str(c).strip() for c in row if c is not None and str(c).strip()
        )
        return self._extract_competency_items(row_text, code_prefix) if row_text else []

    def _extract_task_level(self, row: List[Any], col_map: Dict[str, int]) -> int:
        """Extract the task competency level from a mapped row; defaults to 3."""
        level_idx = col_map.get("level")
        if level_idx is None or level_idx >= len(row):
            return 3
        raw = str(row[level_idx]).strip() if row[level_idx] is not None else ""
        match = re.search(r"\d+", raw)
        if not match:
            return 3
        level = int(match.group(0))
        return level if 1 <= level <= 5 else 3

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _dedupe(self, items: List[_T], key: Callable[[_T], tuple]) -> List[_T]:
        """Remove duplicates from *items* preserving first-occurrence order."""
        seen: set[tuple] = set()
        result: List[_T] = []
        for item in items:
            k = key(item)
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result

    def _dedupe_outputs(self, items: List[OutputItem]) -> List[OutputItem]:
        return self._dedupe(
            items,
            lambda i: (
                self._normalize_text((i.code or "").upper()),
                self._normalize_text(i.name or ""),
            ),
        )

    def _dedupe_indicators(self, items: List[BehavioralIndicator]) -> List[BehavioralIndicator]:
        return self._dedupe(
            items,
            lambda i: (
                self._normalize_text((i.code or "").upper()),
                self._normalize_text(i.text or ""),
            ),
        )

    def _dedupe_competencies(self, items: List[CompetencyItem]) -> List[CompetencyItem]:
        return self._dedupe(
            items,
            lambda i: (
                self._normalize_text((i.code or "").upper()),
                self._normalize_text(i.name or ""),
            ),
        )

    def _dedupe_block(self, block: CompetencyBlock) -> CompetencyBlock:
        """Deduplicate all item lists in a competency block in-place."""
        block.outputs = self._dedupe_outputs(block.outputs)
        block.indicators = self._dedupe_indicators(block.indicators)
        block.knowledge = self._dedupe_competencies(block.knowledge)
        block.skills = self._dedupe_competencies(block.skills)
        return block

    # ── Historical PDF scanning ────────────────────────────────────────────────

    def _scan_ocu_names_from_text(self, pdf) -> Dict[str, str]:
        """Extract OCU T-code → name mapping from the leftmost page column.

        Uses bbox word positions to handle historical PDFs where merged table
        cells cause pdfplumber to return None for most rows.
        """
        names: Dict[str, str] = {}
        ocu_code_re = re.compile(r"^T\d+$")
        pure_code_re = re.compile(r"^[KSOP]\d+(?:[.\-]\d+)*$", re.IGNORECASE)

        for page in pdf.pages:
            left_crop = page.crop((0, 0, page.width * 0.12, page.height))
            words = left_crop.extract_words()
            current_ocu: Optional[str] = None
            name_parts: List[str] = []
            ocu_x: float = 0.0

            for word in words:
                text = word["text"].strip()
                if not text:
                    continue
                wx = float(word.get("x0", 0))
                if ocu_code_re.match(text):
                    if current_ocu and name_parts and current_ocu not in names:
                        names[current_ocu] = "".join(name_parts)
                    current_ocu = text
                    name_parts = []
                    ocu_x = wx
                elif current_ocu and wx <= ocu_x + 30 and not pure_code_re.match(text):
                    name_parts.append(text)

            if current_ocu and name_parts and current_ocu not in names:
                names[current_ocu] = "".join(name_parts)

        return names

    def _scan_task_names_from_words(self, pdf) -> Dict[str, str]:
        """Extract T{n}.{m} → name mapping from word-level bbox positions.

        Words are bucketed into 5px rows to handle sub-pixel y differences.
        Only words within ±30px of the task-code x-position are captured.
        """
        names: Dict[str, str] = {}
        task_re = re.compile(r"^T\d+\.\d+$")

        for page in pdf.pages:
            words = sorted(
                page.extract_words(),
                key=lambda w: (round(w["top"] / 5) * 5, w["x0"]),
            )
            current_task: Optional[str] = None
            task_x: float = 0.0
            parts: List[str] = []

            for word in words:
                text = word["text"].split("\n")[0].strip()
                if not text:
                    continue
                wx = float(word.get("x0", 0))
                if task_re.match(text):
                    if current_task and parts and current_task not in names:
                        names[current_task] = "".join(parts)
                    current_task = text
                    parts = []
                    task_x = wx
                elif current_task is not None and task_x - 5 <= wx <= task_x + 30:
                    parts.append(text)

            if current_task and parts and current_task not in names:
                names[current_task] = "".join(parts)

        return names

    def _derive_task_code_from_p_codes(
        self, indicators: List[BehavioralIndicator]
    ) -> Optional[str]:
        """Derive task code from P-code when the task-code table cell is None.

        P-code format: P{ocu}.{task}.{seq} → T{ocu}.{task}. E.g. P1.1.1 → T1.1.
        """
        for ind in indicators:
            m = re.match(r"P\.?(\d+)\.(\d+)", ind.code, re.IGNORECASE)
            if m:
                return f"T{m.group(1)}.{m.group(2)}"
        return None

    # ── Unit assembly ─────────────────────────────────────────────────────────

    def _is_generic_unit_name(self, name: str) -> bool:
        """Return True when *name* is a placeholder rather than a real OCU name."""
        return self._normalize_text(name) in {"主要職責", "工作任務", "unknown", ""}

    def _merge_ocu_unit(self, unit: OCSUnit, ocu_units: List[OCSUnit]) -> None:
        """Merge *unit* into *ocu_units*, combining tasks for matching OCU codes."""
        for existing in ocu_units:
            if existing.ocu_code != unit.ocu_code:
                continue
            task_map = {t.task_codes[0].code: t for t in existing.tasks if t.task_codes}
            for task in unit.tasks:
                if not task.task_codes:
                    continue
                primary = task.task_codes[0].code
                if primary in task_map:
                    target = task_map[primary]
                    target.competency_blocks.extend(task.competency_blocks)
                    target.competency_blocks = [
                        self._dedupe_block(b) for b in target.competency_blocks
                    ]
                    existing_codes = {e.code for e in target.task_codes}
                    for entry in task.task_codes:
                        if entry.code not in existing_codes:
                            target.task_codes.append(entry)
                else:
                    existing.tasks.append(task)
            if self._is_generic_unit_name(existing.ocu_name) and not self._is_generic_unit_name(
                unit.ocu_name
            ):
                existing.ocu_name = unit.ocu_name
            return
        ocu_units.append(unit)

    # ── Profile helpers ───────────────────────────────────────────────────────

    def _match_profile_label(self, cell_norm: str, label_key: str) -> bool:
        """Match a normalized cell against profile label aliases conservatively."""
        for alias in self.PROFILE_LABEL_ALIASES.get(label_key, []):
            alias_norm = self._normalize_text(alias)
            if not alias_norm:
                continue
            # Short labels like "職業" / "產業" require exact match to avoid false positives.
            if len(alias_norm) <= 2:
                if cell_norm == alias_norm:
                    return True
            elif alias_norm in cell_norm:
                return True
        return False

    def _extract_category_code(self, cat_name: str) -> str:
        """Extract a job-category code from a category name string."""
        match = re.search(r"[A-Z]{2,}", cat_name)
        return match.group(0) if match else "Unknown"

    def _extract_occupation_code(self, text: str) -> str:
        """Extract an occupation code from full-page text."""
        match = re.search(r"職業別代碼\s*(\d+)", text)
        return match.group(1) if match else "Unknown"

    def _extract_first_code(self, text: str) -> Optional[str]:
        """Extract the first OCS code (e.g. ABC123-001) from text."""
        match = re.search(r"[A-Z]{2,}\d+-\d+(?:[vV]\d+)?", text)
        return match.group(0) if match else None

    def _extract_job_categories_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract job categories paired with MPM/INM/ISD/SET codes."""
        target_codes = {"MPM", "INM", "ISD", "SET"}
        for table in tables:
            for row in table:
                if not row or len(row) < 6:
                    continue
                names = self._split_lines(row[2] if len(row) > 2 else None)
                codes = [c.upper() for c in self._split_lines(row[5] if len(row) > 5 else None)]
                if not names or not codes:
                    continue
                if len(names) == len(codes) and set(codes).issubset(target_codes):
                    return [CategoryItem(name=n, code=c) for n, c in zip(names, codes)]
        return []

    def _extract_occupations_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract occupation items paired with 2–4-digit occupation codes."""
        for table in tables:
            for row in table:
                if not row or len(row) < 6:
                    continue
                names = self._split_lines(row[2] if len(row) > 2 else None)
                raw_codes = self._split_lines(row[5] if len(row) > 5 else None)
                codes = [c.strip() for c in raw_codes if re.fullmatch(r"\d{2,4}", c.strip())]
                if not names or not codes or len(names) != len(codes):
                    continue
                if all(re.search(r"[一-鿿]", n) for n in names):
                    return [CategoryItem(name=n, code=c) for n, c in zip(names, codes)]
        return []

    def _extract_industries_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract industry items paired with industry codes (format A12–A1234)."""
        code_pattern = re.compile(r"[A-Z]\d{2,4}")
        for table in tables:
            for row in table:
                if not row:
                    continue
                normalized_cells = self._row_to_normalized_cells(row)
                name_label_idx: Optional[int] = None
                code_label_idx: Optional[int] = None

                for idx, cell_norm in enumerate(normalized_cells):
                    if not cell_norm:
                        continue
                    if name_label_idx is None and (
                        self._match_profile_label(cell_norm, "industry") or "行業別" in cell_norm
                    ):
                        name_label_idx = idx
                    if code_label_idx is None and (
                        "行業別代碼" in cell_norm
                        or "產業代碼" in cell_norm
                        or "industrycode" in cell_norm
                    ):
                        code_label_idx = idx

                if name_label_idx is None:
                    continue
                name_value = self._find_value_to_right(row, name_label_idx)
                if not name_value:
                    continue
                names = self._split_lines(name_value)
                if not names:
                    continue

                codes: List[str] = []
                if code_label_idx is not None:
                    code_value = self._find_value_to_right(row, code_label_idx)
                    if code_value:
                        codes = [
                            c.strip().upper()
                            for c in self._split_lines(code_value)
                            if code_pattern.fullmatch(c.strip().upper())
                        ]

                if not codes:
                    return [CategoryItem(name=n, code="Unknown") for n in names]
                if len(names) == len(codes):
                    return [CategoryItem(name=n, code=c) for n, c in zip(names, codes)]
                return [CategoryItem(name=names[0], code=codes[0])]

        return []

    # ── Main extractors ───────────────────────────────────────────────────────

    def _extract_version_info(self, pdf) -> VersionInfo:
        """Extract version history from the first-page table."""
        versions = []
        try:
            tables = pdf.pages[0].extract_tables()
            if not tables:
                self.logger.warning("未找到版本表格，version_info.versions 將為空")
                return VersionInfo(versions=versions)

            for table in tables:
                header_idx: Optional[int] = None
                header_map: Dict[str, int] = {}
                for row_idx, row in enumerate(table):
                    current_map = self._build_column_map(row, self.VERSION_HEADER_ALIASES)
                    if all(k in current_map for k in ("version", "ocs_code", "ocs_name", "status")):
                        header_idx = row_idx
                        header_map = current_map
                        break

                if header_idx is None:
                    continue

                for row in table[header_idx + 1 :]:
                    version_idx = header_map.get("version")
                    version_val = (
                        self._find_cell_value(row, version_idx) or ""
                        if version_idx is not None
                        else ""
                    )
                    if not version_val:
                        continue
                    versions.append(
                        VersionEntry(
                            version=version_val,
                            ocs_code=self._find_cell_value(row, header_map["ocs_code"]) or "Unknown",
                            ocs_name=self._find_cell_value(row, header_map["ocs_name"]) or "Unknown",
                            status=self._find_cell_value(row, header_map["status"]) or "Unknown",
                            update_note=(
                                self._find_cell_value(row, header_map["update_note"])
                                if "update_note" in header_map
                                else None
                            ),
                            update_date=(
                                self._find_cell_value(row, header_map["update_date"]) or "Unknown"
                                if "update_date" in header_map
                                else "Unknown"
                            ),
                        )
                    )

        except Exception as e:
            self.logger.warning(f"版本提取失敗: {str(e)}")

        return VersionInfo(versions=versions)

    def _extract_profile(self, pdf, version_info: VersionInfo) -> OCSProfile:
        """Extract OCS profile: code, name, categories, level, and description."""
        try:
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            first_page_tables = first_page.extract_tables() or []

            ocs_code = (
                version_info.versions[0].ocs_code if version_info.versions else "Unknown"
            )
            ocs_name_str = (
                version_info.versions[0].ocs_name if version_info.versions else "Unknown"
            )

            job_categories = self._extract_job_categories_from_table(first_page_tables)
            occupations = self._extract_occupations_from_table(first_page_tables)
            industries = self._extract_industries_from_table(first_page_tables)
            explicit_job_category_name: Optional[str] = None
            explicit_job_category_code: Optional[str] = None
            explicit_occupation_name: Optional[str] = None
            job_description_text = ""
            ocs_level_value = 3

            for table in first_page_tables:
                for row_idx, row in enumerate(table):
                    if row_idx > 3:
                        break
                    normalized_cells = self._row_to_normalized_cells(row)
                    for i, cell_norm in enumerate(normalized_cells):
                        if not cell_norm:
                            continue
                        if (
                            ("職類" == cell_norm or cell_norm == "jobcategory")
                            and "職類別" not in cell_norm
                        ):
                            value = self._find_value_to_right(row, i)
                            if value:
                                explicit_job_category_name = value
                        if "職類別代碼" in cell_norm or cell_norm == "jobcategorycode":
                            value = self._find_value_to_right(row, i)
                            if value:
                                explicit_job_category_code = value.strip().upper()
                        if (
                            ("職業" == cell_norm or cell_norm == "occupation")
                            and "職業別代碼" not in str(row[i])
                        ):
                            value = self._find_value_to_right(row, i)
                            if value:
                                explicit_occupation_name = value

            for table in first_page_tables:
                for row in table:
                    normalized_cells = self._row_to_normalized_cells(row)
                    for i, cell_norm in enumerate(normalized_cells):
                        if not cell_norm:
                            continue
                        if not job_description_text and self._match_profile_label(
                            cell_norm, "job_description"
                        ):
                            values = [
                                str(c).strip()
                                for c in row[i + 1 :]
                                if c is not None and str(c).strip()
                            ]
                            if values:
                                job_description_text = "\n".join(values)
                        if self._match_profile_label(cell_norm, "ocs_level"):
                            level_raw = self._find_value_to_right(row, i)
                            if level_raw:
                                m = re.search(r"\d+", level_raw)
                                if m:
                                    level_num = int(m.group(0))
                                    if 1 <= level_num <= 5:
                                        ocs_level_value = level_num

            for page_idx in range(1):
                tables = pdf.pages[page_idx].extract_tables() or []
                for table in tables:
                    for row in table:
                        normalized_cells = self._row_to_normalized_cells(row)
                        for i, cell_norm in enumerate(normalized_cells):
                            if not cell_norm:
                                continue
                            if not job_categories and self._match_profile_label(
                                cell_norm, "job_category"
                            ):
                                value = self._find_value_to_right(row, i)
                                if value:
                                    for cat_name in self._split_multi_value(value):
                                        cat_code = (
                                            explicit_job_category_code
                                            if explicit_job_category_code
                                            else self._extract_category_code(cat_name)
                                        )
                                        if cat_name and cat_name not in [
                                            c.name for c in job_categories
                                        ]:
                                            job_categories.append(
                                                CategoryItem(name=cat_name, code=cat_code)
                                            )
                            if not occupations and self._match_profile_label(
                                cell_norm, "occupation"
                            ) and "職業別代碼" not in str(row[i]):
                                value = self._find_value_to_right(row, i)
                                if value:
                                    for occ_name in self._split_multi_value(value):
                                        occ_code = self._extract_occupation_code(text)
                                        if occ_name and occ_name not in [
                                            o.name for o in occupations
                                        ]:
                                            occupations.append(
                                                CategoryItem(name=occ_name, code=occ_code)
                                            )
                            if not industries and self._match_profile_label(
                                cell_norm, "industry"
                            ):
                                value = self._find_value_to_right(row, i)
                                if value:
                                    for ind_name in self._split_multi_value(value):
                                        if ind_name and ind_name not in [
                                            d.name for d in industries
                                        ]:
                                            industries.append(
                                                CategoryItem(
                                                    name=ind_name,
                                                    code=self._extract_category_code(ind_name),
                                                )
                                            )

            if explicit_job_category_code and job_categories:
                for item in job_categories:
                    if item.code == "Unknown":
                        item.code = explicit_job_category_code

            if not occupations:
                occupations.append(
                    CategoryItem(name=ocs_name_str, code=ocs_code.split("-")[0])
                )

            if ocs_code == "Unknown":
                ocs_code = self._extract_first_code(text) or "Unknown"

            return OCSProfile(
                ocs_code=ocs_code,
                ocs_name=OCSName(
                    job_category_name=explicit_job_category_name,
                    occupation_name=(
                        explicit_occupation_name
                        if explicit_occupation_name
                        else (occupations[0].name if occupations else None)
                    ),
                ),
                category=OCSCategory(
                    job_categories=job_categories,
                    occupations=occupations,
                    industries=industries,
                ),
                job_description=job_description_text,
                ocs_level=ocs_level_value,
            )

        except Exception as e:
            self.logger.warning(f"Profile 提取失敗: {str(e)}")
            return OCSProfile(
                ocs_code="Unknown",
                ocs_name=OCSName(job_category_name=None, occupation_name="Unknown"),
                category=OCSCategory(job_categories=[], occupations=[], industries=[]),
                job_description="",
                ocs_level=3,
            )

    def _extract_content(self, pdf) -> OCSContent:
        """Extract OCU units: tasks, outputs, behavioral indicators, K/S competencies."""
        ocu_units: List[OCSUnit] = []
        known_ocu_names: Dict[str, str] = {}

        try:
            content_header: Optional[List[Any]] = None
            merged_content_rows: List[List[Any]] = []

            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table:
                        continue
                    cleaned_rows = self._clean_table_rows(table)
                    if not cleaned_rows:
                        continue

                    header_idx, _, header_span = self._find_ocu_header_row(cleaned_rows)
                    if header_idx is None:
                        # ocs_attitude / notes_and_appendix tables are not OCU content.
                        if content_header is not None:
                            section_type = self._detect_table_type(table)
                            if section_type not in ("ocs_attitude", "notes_and_appendix"):
                                merged_content_rows.extend(cleaned_rows)
                        continue

                    if content_header is None:
                        content_header = self._merge_rows_for_header(
                            cleaned_rows[header_idx : header_idx + header_span]
                        )
                    merged_content_rows.extend(cleaned_rows[header_idx + header_span :])

            if content_header and merged_content_rows:
                merged_table = [content_header] + merged_content_rows
                parsed_units = (
                    self._parse_ocu_table_units(merged_table)
                    if self._is_ocu_candidate_table(merged_table)
                    else []
                )

                for unit in parsed_units:
                    if re.fullmatch(r"T\d+", unit.ocu_code) and not self._is_generic_unit_name(
                        unit.ocu_name
                    ):
                        known_ocu_names[unit.ocu_code] = unit.ocu_name

                    if not re.fullmatch(r"T\d+", unit.ocu_code) or self._is_generic_unit_name(
                        unit.ocu_name
                    ):
                        grouped: Dict[str, List[Task]] = {}
                        for task in unit.tasks:
                            primary_code = task.task_codes[0].code if task.task_codes else ""
                            match = re.match(r"(T\d+)", primary_code)
                            ocu_code = match.group(1) if match else unit.ocu_code
                            grouped.setdefault(ocu_code, []).append(task)

                        for ocu_code, tasks in grouped.items():
                            fallback_name = (
                                unit.ocu_name
                                if not self._is_generic_unit_name(unit.ocu_name)
                                else "Unknown"
                            )
                            self._merge_ocu_unit(
                                OCSUnit(
                                    ocu_code=ocu_code,
                                    ocu_name=known_ocu_names.get(ocu_code, fallback_name),
                                    tasks=tasks,
                                ),
                                ocu_units,
                            )
                    else:
                        self._merge_ocu_unit(unit, ocu_units)

            if any(self._is_generic_unit_name(u.ocu_name) for u in ocu_units):
                text_ocu_names = self._scan_ocu_names_from_text(pdf)
                for unit in ocu_units:
                    if self._is_generic_unit_name(unit.ocu_name) and unit.ocu_code in text_ocu_names:
                        unit.ocu_name = text_ocu_names[unit.ocu_code]

            if any(
                entry.name == ""
                for unit in ocu_units
                for task in unit.tasks
                for entry in task.task_codes
            ):
                text_task_names = self._scan_task_names_from_words(pdf)
                for unit in ocu_units:
                    for task in unit.tasks:
                        for entry in task.task_codes:
                            if entry.name == "" and entry.code in text_task_names:
                                entry.name = text_task_names[entry.code]

        except Exception as e:
            self.logger.warning(f"OCU 內容提取失敗: {str(e)}")

        return OCSContent(ocu_units=ocu_units)

    def _parse_task_codes(
        self, task_code_raw: str, task_name_raw: str, same_column: bool
    ) -> List[TaskCodeEntry]:
        """Extract one or more TaskCodeEntry from raw cell values.

        Separate columns with a clean T-code produce a single entry.
        A combined cell or embedded codes produce one entry per T-code found.
        """
        if not same_column and re.fullmatch(r"T\d+(?:\.\d+)?", task_code_raw, re.IGNORECASE):
            return [
                TaskCodeEntry(code=task_code_raw, name=self._compact_wrapped_text(task_name_raw))
            ]

        text = task_name_raw or task_code_raw
        if not text:
            return []

        matches = list(re.finditer(r"(T\d+(?:\.\d+)?)(?![.\d])", text, re.IGNORECASE))
        entries: List[TaskCodeEntry] = []
        for i, m in enumerate(matches):
            name_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            entries.append(
                TaskCodeEntry(
                    code=m.group(1),
                    name=self._compact_wrapped_text(text[m.end() : name_end]),
                )
            )
        return entries

    def _parse_ocu_table_units(self, table: List[List[Any]]) -> List[OCSUnit]:
        """Parse a merged OCU table into one or more OCSUnit objects."""
        if not table or len(table) < 2:
            return []

        try:
            header_idx, col_map, header_span = self._find_ocu_header_row(table)
            if header_idx is None:
                return []

            header = self._merge_rows_for_header(table[header_idx : header_idx + header_span])
            ocu_code = "Unknown"
            ocu_name = "Unknown"

            for meta_row in table[: header_idx + header_span]:
                for i, cell in enumerate(meta_row):
                    norm_cell = self._normalize_text(cell)
                    if "職能單元代碼" in norm_cell or "ocu代碼" in norm_cell:
                        value = self._find_value_to_right(meta_row, i)
                        if value:
                            ocu_code = value
                    if "職能單元名稱" in norm_cell or "ocu名稱" in norm_cell:
                        value = self._find_value_to_right(meta_row, i)
                        if value:
                            ocu_name = value

            if ocu_code == "Unknown" and header and header[0]:
                ocu_code = str(header[0]).strip()
            if ocu_name == "Unknown" and len(header) > 1 and header[1]:
                ocu_name = str(header[1]).strip()

            data_rows = table[header_idx + header_span :]
            units: List[OCSUnit] = []
            unit_tasks: Dict[str, List[Task]] = {}
            unit_names: Dict[str, str] = {}
            last_task_by_ocu: Dict[str, Task] = {}
            current_ocu_code = ocu_code
            current_ocu_name = ocu_name

            def _ensure_unit(code: str, name: str) -> None:
                unit_tasks.setdefault(code, [])
                unit_names.setdefault(code, name)

            _ensure_unit(current_ocu_code, current_ocu_name)

            for row in data_rows:
                if not row:
                    continue

                if col_map and row:
                    major_duty_raw = self._compact_wrapped_text(row[0])
                    duty_match = re.match(r"(T\d+)(.+)", major_duty_raw)
                    if duty_match:
                        current_ocu_code = duty_match.group(1)
                        current_ocu_name = duty_match.group(2).strip() or current_ocu_name
                        _ensure_unit(current_ocu_code, current_ocu_name)

                task_code_idx = col_map.get("task_code")
                task_name_idx = col_map.get("task_name")
                task_code = (
                    str(row[task_code_idx]).strip()
                    if task_code_idx is not None
                    and task_code_idx < len(row)
                    and row[task_code_idx]
                    else ""
                )
                task_name = (
                    str(row[task_name_idx]).strip()
                    if task_name_idx is not None
                    and task_name_idx < len(row)
                    and row[task_name_idx]
                    else ""
                )
                if not task_name and task_code_idx is not None and task_code_idx < len(row):
                    task_name = str(row[task_code_idx]).strip() if row[task_code_idx] else ""

                same_column = (
                    task_code_idx is not None
                    and task_name_idx is not None
                    and task_code_idx == task_name_idx
                )
                parsed_task_codes = self._parse_task_codes(task_code, task_name, same_column)
                primary_task_code = parsed_task_codes[0].code if parsed_task_codes else ""

                outputs = (
                    self._extract_output_items(row[col_map["outputs"]])
                    if "outputs" in col_map and col_map["outputs"] < len(row)
                    else []
                )

                knowledge: List[CompetencyItem] = []
                if "knowledge" in col_map and col_map["knowledge"] < len(row):
                    knowledge = self._extract_competency_items(row[col_map["knowledge"]], "K")
                if not knowledge:
                    knowledge = self._extract_competency_items_from_row(row, "K")

                skills: List[CompetencyItem] = []
                if "skills" in col_map and col_map["skills"] < len(row):
                    skills = self._extract_competency_items(row[col_map["skills"]], "S")
                if not skills:
                    skills = self._extract_competency_items_from_row(row, "S")

                behavioral_indicators = (
                    self._extract_behavioral_indicators(row[col_map["behavioral"]])
                    if "behavioral" in col_map and col_map["behavioral"] < len(row)
                    else []
                )
                if not behavioral_indicators:
                    behavioral_indicators = self._extract_behavioral_indicators_from_row(row)

                # Historical PDFs: task-code cell may be None (merged cell); derive from P-code.
                if (
                    not primary_task_code
                    and behavioral_indicators
                    and not last_task_by_ocu.get(current_ocu_code)
                ):
                    derived = self._derive_task_code_from_p_codes(behavioral_indicators)
                    if derived:
                        parsed_task_codes = [TaskCodeEntry(code=derived, name="")]
                        primary_task_code = derived

                # T codes without P-codes: attach to the previous task (cross-page pattern).
                if primary_task_code and not behavioral_indicators:
                    previous_task = last_task_by_ocu.get(current_ocu_code)
                    if previous_task:
                        existing_codes = {e.code for e in previous_task.task_codes}
                        for entry in parsed_task_codes:
                            if entry.code not in existing_codes:
                                previous_task.task_codes.append(entry)
                        primary_task_code = ""
                        parsed_task_codes = []

                # Continuation rows: append content to the previous task's last block.
                if not primary_task_code:
                    previous_task = last_task_by_ocu.get(current_ocu_code)
                    if previous_task:
                        if not previous_task.competency_blocks:
                            previous_task.competency_blocks.append(
                                CompetencyBlock(
                                    competency_level=self._extract_task_level(row, col_map),
                                    indicators=[],
                                    outputs=[],
                                    knowledge=[],
                                    skills=[],
                                )
                            )
                        previous_block = previous_task.competency_blocks[-1]

                        output_idx = col_map.get("outputs")
                        behavioral_idx = col_map.get("behavioral")
                        knowledge_idx = col_map.get("knowledge")
                        skills_idx = col_map.get("skills")

                        output_tail = (
                            self._compact_wrapped_text(row[output_idx])
                            if output_idx is not None and output_idx < len(row) and row[output_idx]
                            else ""
                        )
                        behavioral_tail = (
                            self._compact_wrapped_text(row[behavioral_idx])
                            if behavioral_idx is not None
                            and behavioral_idx < len(row)
                            and row[behavioral_idx]
                            else ""
                        )
                        knowledge_tail = (
                            self._compact_wrapped_text(row[knowledge_idx])
                            if knowledge_idx is not None
                            and knowledge_idx < len(row)
                            and row[knowledge_idx]
                            else ""
                        )
                        skills_tail = (
                            self._compact_wrapped_text(row[skills_idx])
                            if skills_idx is not None and skills_idx < len(row) and row[skills_idx]
                            else ""
                        )

                        if (
                            not outputs
                            and output_tail
                            and previous_block.outputs
                            and not re.search(
                                r"\bO\d+(?:[-.]\d+)*", output_tail, flags=re.IGNORECASE
                            )
                        ):
                            previous_block.outputs[-1].name = self._append_text_if_new(
                                previous_block.outputs[-1].name, output_tail
                            )

                        if (
                            not behavioral_indicators
                            and behavioral_tail
                            and previous_block.indicators
                            and not re.search(
                                r"\b[PT]\d+(?:[-.]\d+)*", behavioral_tail, flags=re.IGNORECASE
                            )
                        ):
                            previous_block.indicators[-1].text = self._append_text_if_new(
                                previous_block.indicators[-1].text, behavioral_tail
                            )

                        if (
                            not knowledge
                            and knowledge_tail
                            and previous_block.knowledge
                            and not re.search(
                                r"\bK\d+(?:[-.]\d+)*", knowledge_tail, flags=re.IGNORECASE
                            )
                        ):
                            previous_block.knowledge[-1].name = self._append_text_if_new(
                                previous_block.knowledge[-1].name, knowledge_tail
                            )

                        if (
                            not skills
                            and skills_tail
                            and previous_block.skills
                            and not re.search(
                                r"\bS\d+(?:[-.]\d+)*", skills_tail, flags=re.IGNORECASE
                            )
                        ):
                            previous_block.skills[-1].name = self._append_text_if_new(
                                previous_block.skills[-1].name, skills_tail
                            )

                        if task_name and previous_task.task_codes:
                            last_entry = previous_task.task_codes[-1]
                            last_entry.name = self._append_text_if_new(last_entry.name, task_name)

                        # New block when both a structural trigger (new O or level change)
                        # and new K/S codes are present.
                        new_level = self._extract_task_level(row, col_map)
                        level_changed = new_level != previous_block.competency_level
                        has_new_o = bool(outputs)
                        has_new_ks = bool(knowledge or skills)

                        if (has_new_o or level_changed) and has_new_ks and behavioral_indicators:
                            previous_task.competency_blocks.append(
                                CompetencyBlock(
                                    competency_level=new_level,
                                    indicators=self._dedupe_indicators(behavioral_indicators),
                                    outputs=self._dedupe_outputs(
                                        outputs if outputs else list(previous_block.outputs)
                                    ),
                                    knowledge=self._dedupe_competencies(knowledge),
                                    skills=self._dedupe_competencies(skills),
                                )
                            )
                        else:
                            previous_block.outputs.extend(outputs)
                            previous_block.indicators.extend(behavioral_indicators)
                            previous_block.knowledge.extend(knowledge)
                            previous_block.skills.extend(skills)
                            self._dedupe_block(previous_block)
                        continue

                    continue

                task_level = self._extract_task_level(row, col_map)
                if primary_task_code:
                    task = Task(
                        task_codes=parsed_task_codes,
                        competency_blocks=[
                            CompetencyBlock(
                                competency_level=task_level,
                                indicators=self._dedupe_indicators(behavioral_indicators),
                                outputs=self._dedupe_outputs(outputs),
                                knowledge=self._dedupe_competencies(knowledge),
                                skills=self._dedupe_competencies(skills),
                            )
                        ],
                    )
                    _ensure_unit(current_ocu_code, current_ocu_name)
                    unit_tasks[current_ocu_code].append(task)
                    last_task_by_ocu[current_ocu_code] = task

            for code, tasks in unit_tasks.items():
                for task in tasks:
                    task.competency_blocks = [
                        b for b in task.competency_blocks
                        if b.indicators or b.outputs or b.knowledge or b.skills
                    ]
                tasks = [t for t in tasks if t.competency_blocks]
                if tasks:
                    units.append(
                        OCSUnit(
                            ocu_code=code,
                            ocu_name=unit_names.get(code, "Unknown"),
                            tasks=tasks,
                        )
                    )

            return units

        except Exception as e:
            self.logger.warning(f"OCU 表解析失敗: {str(e)}")
            return []

    def _extract_attitude(self, pdf) -> OCSAttitude:
        """Extract attitude competency items (A-codes) from full PDF text.

        Handles both one-per-line and multiple-per-line formats, e.g.
        'A01外部意識、A02溝通協調能力、A03成果導向' all on a single line.
        """
        attitudes: List[Attitude] = []
        seen_codes: set[str] = set()
        try:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            code_re = re.compile(r"A(\d{1,2})")
            for line in full_text.splitlines():
                line = line.strip()
                if not line or not re.match(r"A\d{1,2}", line):
                    continue
                hits = list(code_re.finditer(line))
                for i, m in enumerate(hits):
                    att_code = f"A{int(m.group(1)):02d}"
                    if att_code in seen_codes:
                        continue
                    name_end = hits[i + 1].start() if i + 1 < len(hits) else len(line)
                    name = line[m.end() : name_end].strip("、,，;； \t")
                    if not name:
                        continue
                    seen_codes.add(att_code)
                    attitudes.append(Attitude(code=att_code, name=name))
        except Exception as e:
            self.logger.warning(f"態度提取失敗: {str(e)}")
        return OCSAttitude(attitudes=attitudes)

    def _extract_notes(self, pdf) -> Notes:
        """Extract prerequisites and supplementary notes from '說明與補充事項'."""
        prerequisites: List[str] = []
        supplements: List[str] = []

        # Bullet/marker characters commonly used in OCS PDFs
        _bullet_re = re.compile(r"^[\s⚫◆•◎\-＊\*\d+\.]+\s*")
        # Section header patterns
        _prereq_re = re.compile(r"建議擔任此職類.{0,6}學歷.{0,6}(經歷|經驗)")
        _supp_re = re.compile(r"其他補充說明")

        try:
            full_text = "".join(page.extract_text() or "" for page in pdf.pages)
            notes_start = full_text.find("說明與補充")
            if notes_start == -1:
                return Notes()

            in_supplements = False
            for line in full_text[notes_start:].split("\n")[1:]:
                line = line.strip()
                if not line or line.startswith("第") and "頁" in line:
                    continue
                # Section header switches
                if _prereq_re.search(line):
                    in_supplements = False
                    continue
                if _supp_re.search(line):
                    in_supplements = True
                    continue
                # Strip leading bullets/markers before storing
                clean = _bullet_re.sub("", line).strip()
                if not clean:
                    continue
                if in_supplements:
                    supplements.append(clean)
                else:
                    prerequisites.append(clean)

        except Exception as e:
            self.logger.warning(f"補充信息提取失敗: {str(e)}")

        return Notes(prerequisites=prerequisites, supplements=supplements)
