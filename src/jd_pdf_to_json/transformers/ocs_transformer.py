"""OCS PDF → OCSDocument transformer implementation."""

import re
import unicodedata
from typing import Optional, List, Any, Dict

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
    OutputItem,
    BehavioralIndicator,
    CompetencyItem,
    Attitude,
    Requirement,
    OCSContent,
    OCSAttitude,
    NotesAndAppendix,
)
from jd_pdf_to_json.transformers.base import BaseOCSTransformer
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.utils.logger import logger


class OCSTransformer(BaseOCSTransformer):
    """Transform PDF raw data into OCSDocument model."""

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

    def __init__(self):
        """Initialize transformer."""
        self.logger = logger

    def _normalize_text(self, value: Any) -> str:
        """Normalize text for robust header matching across layouts."""
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value))
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"[\s\u3000]+", "", text)
        text = re.sub(r"[：:()（）\[\]【】、,，.-]+", "", text)
        return text.lower().strip()

    def _row_to_normalized_cells(self, row: List[Any]) -> List[str]:
        return [self._normalize_text(cell) for cell in row]

    def _find_value_to_right(self, row: List[Any], index: int) -> Optional[str]:
        """Get the nearest non-empty value on the right side of a label cell."""
        for cell in row[index + 1 :]:
            if cell is not None and str(cell).strip():
                return str(cell).strip()
        return None

    def _split_multi_value(self, value: str) -> List[str]:
        """Split profile cell values into candidate items."""
        normalized = unicodedata.normalize("NFKC", value)
        # Keep slash-joined labels as one item, e.g. 「金融財務／銀行金融業務」.
        parts = re.split(r"[、,，;；\n]+", normalized)
        return [p.strip() for p in parts if p and p.strip()]

    def _compact_wrapped_text(self, value: Any) -> str:
        """Compact wrapped cell text into a single readable line."""
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value))
        text = text.replace("\r", "").replace("\n", "")
        text = re.sub(r"\s+", "", text)
        return text.strip()

    def _split_lines(self, value: Any) -> List[str]:
        """Split cell text by line while keeping slash-combined phrases intact."""
        if not value:
            return []
        text = unicodedata.normalize("NFKC", str(value)).replace("\r", "\n")
        return [line.strip() for line in text.split("\n") if line and line.strip()]

    def _match_profile_label(self, cell_norm: str, label_key: str) -> bool:
        """Match profile labels conservatively to avoid false positives in content tables."""
        for alias in self.PROFILE_LABEL_ALIASES.get(label_key, []):
            alias_norm = self._normalize_text(alias)
            if not alias_norm:
                continue
            # For short labels like "職業" / "產業", require exact match.
            if len(alias_norm) <= 2:
                if cell_norm == alias_norm:
                    return True
            elif alias_norm in cell_norm:
                return True
        return False

    def _dedupe_outputs(self, items: List[OutputItem]) -> List[OutputItem]:
        seen: set[tuple[str, str]] = set()
        deduped: List[OutputItem] = []
        for item in items:
            key = (
                self._normalize_text((item.output_code or "").strip().upper()),
                self._normalize_text((item.output_name or "").strip()),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _dedupe_indicators(
        self, items: List[BehavioralIndicator]
    ) -> List[BehavioralIndicator]:
        seen: set[tuple[str, str]] = set()
        deduped: List[BehavioralIndicator] = []
        for item in items:
            key = (
                self._normalize_text((item.indicator_code or "").strip().upper()),
                self._normalize_text((item.indicator_text or "").strip()),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _dedupe_competencies(
        self, items: List[CompetencyItem]
    ) -> List[CompetencyItem]:
        seen: set[tuple[str, str]] = set()
        deduped: List[CompetencyItem] = []
        for item in items:
            key = (
                self._normalize_text((item.code or "").strip().upper()),
                self._normalize_text((item.name or "").strip()),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _extract_job_categories_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract job categories paired with MPM/INM/ISD/SET from profile table."""
        target_codes = {"MPM", "INM", "ISD", "SET"}

        for table in tables:
            for row in table:
                if not row or len(row) < 6:
                    continue

                names = self._split_lines(row[2] if len(row) > 2 else None)
                codes = [code.upper() for code in self._split_lines(row[5] if len(row) > 5 else None)]

                if not names or not codes:
                    continue

                if len(names) == len(codes) and set(codes).issubset(target_codes):
                    paired = []
                    for name, code in zip(names, codes):
                        paired.append(CategoryItem(name=name, code=code))
                    if paired:
                        return paired

        return []

    def _extract_occupations_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract occupation items paired with occupation codes from profile table."""
        for table in tables:
            for row in table:
                if not row or len(row) < 6:
                    continue

                names = self._split_lines(row[2] if len(row) > 2 else None)
                raw_codes = self._split_lines(row[5] if len(row) > 5 else None)
                codes = [c.strip() for c in raw_codes if re.fullmatch(r"\d{2,4}", c.strip())]

                if not names or not codes or len(names) != len(codes):
                    continue

                # 職業別通常是純中文名稱 + 2~4 位數代碼（例如 21, 2144, 3513）
                if all(re.search(r"[\u4e00-\u9fff]", name) for name in names):
                    return [
                        CategoryItem(name=name, code=code)
                        for name, code in zip(names, codes)
                    ]

        return []

    def _extract_industries_from_table(
        self, tables: List[List[List[Any]]]
    ) -> List[CategoryItem]:
        """Extract industry items paired with industry codes from profile table."""
        code_pattern = re.compile(r"[A-Z]\d{2,4}")

        for table in tables:
            for row in table:
                if not row:
                    continue

                normalized_cells = self._row_to_normalized_cells(row)

                # 優先支援「行業別 / 行業別代碼」同列版型。
                name_label_idx: Optional[int] = None
                code_label_idx: Optional[int] = None

                for idx, cell_norm in enumerate(normalized_cells):
                    if not cell_norm:
                        continue
                    if name_label_idx is None and (
                        self._match_profile_label(cell_norm, "industry")
                        or "行業別" in cell_norm
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

                # fallback：從整列尋找符合代碼格式的儲存格。
                if not codes:
                    for cell in row:
                        if cell is None:
                            continue
                        text = unicodedata.normalize("NFKC", str(cell)).strip().upper()
                        if code_pattern.fullmatch(text):
                            codes.append(text)

                if not codes:
                    return [CategoryItem(name=name, code="Unknown") for name in names]

                if len(names) == len(codes):
                    return [CategoryItem(name=name, code=code) for name, code in zip(names, codes)]

                return [CategoryItem(name=names[0], code=codes[0])]

        return []

    def _extract_competency_items_from_row(
        self, row: List[Any], code_prefix: str
    ) -> List[CompetencyItem]:
        """Fallback parser: scan the entire row and collect competency codes."""
        items: List[CompetencyItem] = []
        for cell in row:
            items.extend(self._extract_competency_items(cell, code_prefix))
        return self._dedupe_competencies(items)

    def _build_column_map(
        self, header_row: List[Any], aliases: Dict[str, List[str]]
    ) -> Dict[str, int]:
        """Build semantic column mapping from a header row."""
        mapping: Dict[str, int] = {}
        normalized_cells = self._row_to_normalized_cells(header_row)

        for idx, cell in enumerate(normalized_cells):
            if not cell:
                continue
            for field, alias_list in aliases.items():
                if field in mapping:
                    continue
                if any(self._normalize_text(alias) in cell for alias in alias_list):
                    mapping[field] = idx

        return mapping

    def _extract_competency_items(
        self, cell_value: Any, code_prefix: str
    ) -> List[CompetencyItem]:
        """Parse K/S competency items from a cell text block."""
        if not cell_value:
            return []

        raw_text = unicodedata.normalize("NFKC", str(cell_value)).replace("\r", "\n")
        lines = [line.strip() for line in raw_text.split("\n") if line and line.strip()]
        if not lines:
            return []

        results: List[CompetencyItem] = []

        # Prefer line-wise parsing where code and name are separated by whitespace.
        line_pattern = re.compile(
            rf"^({code_prefix}\d+(?:[-.]\d+)*)\s+(.+)$", flags=re.IGNORECASE
        )
        for line in lines:
            match = line_pattern.match(line)
            if not match:
                continue
            code = match.group(1).strip()
            name = match.group(2).strip("；;，,") or code
            results.append(CompetencyItem(code=code, name=name))

        if results:
            return results

        # Fallback: parse inline sequences such as "K01 AAA K02 BBB".
        text = "\n".join(lines)
        inline_pattern = re.compile(
            rf"({code_prefix}\d+(?:[-.]\d+)*)\s+", flags=re.IGNORECASE
        )
        matches = list(inline_pattern.finditer(text))
        for idx, match in enumerate(matches):
            code = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            name = text[start:end].strip("；;，,\n ") or code
            results.append(CompetencyItem(code=code, name=name))

        if results:
            return results

        # Final fallback for legacy formats without clear separators.
        legacy_pattern = re.compile(
            rf"({code_prefix}\d+(?:[-.]\d+)*)", flags=re.IGNORECASE
        )
        matches = list(legacy_pattern.finditer(text))
        for idx, match in enumerate(matches):
            code = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            name = text[start:end].strip("；;，,\n ") or code
            results.append(CompetencyItem(code=code, name=name))

        return results

    def _extract_output_items(self, cell_value: Any) -> List[OutputItem]:
        """Parse O-code work outputs from a cell text block."""
        if not cell_value:
            return []

        text = self._compact_wrapped_text(cell_value)
        if not text:
            return []

        pattern = re.compile(r"(O\d+(?:[-.]\d+)*)", re.IGNORECASE)
        outputs: List[OutputItem] = []

        matches = list(pattern.finditer(text))
        for idx, match in enumerate(matches):
            code = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            name = text[start:end].strip("；;，,")
            outputs.append(OutputItem(output_code=code, output_name=name))

        if outputs:
            return outputs

        for token in re.split(r"[\s,，;；\n]+", text):
            token = token.strip()
            if re.fullmatch(r"O\d+(?:[-.]\d+)*", token, flags=re.IGNORECASE):
                outputs.append(OutputItem(output_code=token, output_name=""))

        return outputs

    def _extract_behavioral_indicators(
        self, cell_value: Any
    ) -> List[BehavioralIndicator]:
        """Parse behavior indicators from a cell text block."""
        if not cell_value:
            return []

        text = self._compact_wrapped_text(cell_value)
        if not text:
            return []

        pattern = re.compile(r"([PT]\d+(?:[-.]\d+)*)", re.IGNORECASE)
        indicators: List[BehavioralIndicator] = []

        matches = list(pattern.finditer(text))
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            indicator_text = text[start:end].strip("；;，,") or match.group(1).strip()
            indicators.append(
                BehavioralIndicator(
                    indicator_code=match.group(1).strip(),
                    indicator_text=indicator_text,
                )
            )

        return indicators

    def _find_ocu_header_row(self, table: List[List[Any]]) -> tuple[Optional[int], Dict[str, int]]:
        """Find the header row and mapped OCU columns in a table."""
        for row_idx, row in enumerate(table):
            col_map = self._build_column_map(row, self.OCU_HEADER_ALIASES)
            if "task_name" in col_map:
                has_competency_cols = any(
                    key in col_map for key in ("knowledge", "skills", "outputs", "behavioral")
                )
                if has_competency_cols:
                    if "task_code" not in col_map:
                        # 常見版型僅有「工作任務」欄，任務代碼內嵌在文字中。
                        col_map["task_code"] = col_map["task_name"]
                    return row_idx, col_map

            normalized_cells = self._row_to_normalized_cells(row)
            if len(row) >= 6 and any("knowledge" in c for c in normalized_cells) and any(
                "skills" in c for c in normalized_cells
            ):
                # AIoT PDF 常見固定欄位：主要職責/工作任務/工作產出/行為指標/職能級別/K/S
                inferred_map = {
                    "task_name": 1,
                    "task_code": 1,
                    "outputs": 2,
                    "behavioral": 3,
                    "level": 4,
                    "knowledge": 5,
                    "skills": 6,
                }
                return row_idx, inferred_map

        # Fallback: 從第一個「看起來像任務資料列」反推欄位位置，處理多層表頭對齊偏移。
        for row_idx, row in enumerate(table):
            if not row:
                continue

            inferred: Dict[str, int] = {}
            task_code_like_idx: Optional[int] = None
            task_name_idx: Optional[int] = None

            for idx, cell in enumerate(row):
                cell_text = self._compact_wrapped_text(cell)
                if not cell_text:
                    continue

                if "outputs" not in inferred and re.search(r"\bO\d+(?:[-.]\d+)*", cell_text, re.IGNORECASE):
                    inferred["outputs"] = idx
                if "behavioral" not in inferred and re.search(r"\bP\d+(?:[-.]\d+)*", cell_text, re.IGNORECASE):
                    inferred["behavioral"] = idx
                if "knowledge" not in inferred and re.search(r"\bK\d+(?:[-.]\d+)*", cell_text, re.IGNORECASE):
                    inferred["knowledge"] = idx
                if "skills" not in inferred and re.search(r"\bS\d+(?:[-.]\d+)*", cell_text, re.IGNORECASE):
                    inferred["skills"] = idx
                if "level" not in inferred and re.fullmatch(r"[1-5]", cell_text):
                    inferred["level"] = idx

                if task_name_idx is None and re.search(r"\bT\d+\.\d+", cell_text, re.IGNORECASE):
                    task_name_idx = idx
                if task_code_like_idx is None and re.search(r"\bT\d+(?:\.\d+)?", cell_text, re.IGNORECASE):
                    task_code_like_idx = idx

            if task_name_idx is None and task_code_like_idx is not None:
                task_name_idx = task_code_like_idx

            has_task = task_name_idx is not None
            has_detail = "outputs" in inferred or "behavioral" in inferred
            has_comp = "knowledge" in inferred or "skills" in inferred

            if has_task and has_detail and has_comp:
                inferred["task_name"] = task_name_idx
                inferred["task_code"] = task_name_idx
                return max(0, row_idx - 1), inferred
        return None, {}

    def _extract_task_level(self, row: List[Any], col_map: Dict[str, int]) -> int:
        """Extract task competency level from mapped row, fallback to 3."""
        level_idx = col_map.get("level")
        if level_idx is None or level_idx >= len(row):
            return 3
        raw = str(row[level_idx]).strip() if row[level_idx] is not None else ""
        match = re.search(r"\d+", raw)
        if not match:
            return 3
        level = int(match.group(0))
        return level if 1 <= level <= 5 else 3

    def _is_ocu_candidate_table(self, table: List[List[Any]]) -> bool:
        """Check whether a table is likely an OCU task table."""
        if not table:
            return False

        header_idx, _ = self._find_ocu_header_row(table)
        if header_idx is not None:
            return True

        # Fallback heuristic: sample rows contain task code + competency/output markers.
        sample_rows = table[: min(len(table), 6)]
        has_task_code = False
        has_detail_code = False

        for row in sample_rows:
            for cell in row:
                cell_text = self._compact_wrapped_text(cell)
                if not cell_text:
                    continue
                if re.search(r"T\d+(?:\.\d+)?", cell_text, flags=re.IGNORECASE):
                    has_task_code = True
                if re.search(r"[KOSP]\d+(?:[-.]\d+)*", cell_text, flags=re.IGNORECASE):
                    has_detail_code = True

        return has_task_code and has_detail_code

    def _derive_task_code_from_items(
        self,
        outputs: List[OutputItem],
        indicators: List[BehavioralIndicator],
    ) -> Optional[str]:
        """Derive task code (e.g., T3.1) from output/indicator codes like O3.1.2."""
        for output in outputs:
            match = re.match(r"O(\d+\.\d+)\.\d+", output.output_code, flags=re.IGNORECASE)
            if match:
                return f"T{match.group(1)}"

        for indicator in indicators:
            match = re.match(r"P(\d+\.\d+)\.\d+", indicator.indicator_code, flags=re.IGNORECASE)
            if match:
                return f"T{match.group(1)}"

        return None

    def transform(self, raw_data: dict) -> OCSDocument:
        """
        Transform raw PDF data into structured OCS model.

        Args:
            raw_data: Dict with keys:
                - 'file_path': str (path to PDF)
                - 'metadata': dict (from parser)
                - 'pages': list (from parser)

        Returns:
            Validated OCSDocument model

        Raises:
            TransformationError: If transformation fails
        """
        try:
            file_path = raw_data.get("file_path", "")
            metadata = raw_data.get("metadata", {})

            self.logger.info(f"開始轉換: {file_path}")

            with pdfplumber.open(file_path) as pdf:
                # 1. 提取版本信息（通常在第一頁）
                version_info = self._extract_version_info(pdf)
                self.logger.debug(f"✓ 版本信息: {len(version_info.versions)} 筆紀錄")

                # 2. 提取 OCS Profile 信息
                ocs_profile = self._extract_profile(pdf, version_info)
                self.logger.debug(f"✓ Profile: {ocs_profile.ocs_code}")

                # 3. 提取 OCU 內容（任務、產出、知識、技能等）
                ocs_content = self._extract_content(pdf, ocs_profile)
                self.logger.debug(
                    f"✓ 內容: {len(ocs_content.ocu_units)} 個職能單元"
                )

                # 4. 提取態度信息
                ocs_attitude = self._extract_attitude(pdf)
                self.logger.debug(f"✓ 態度: {len(ocs_attitude.attitudes)} 個態度")

                # 5. 提取說明與補充
                notes_appendix = self._extract_notes_and_appendix(pdf)
                self.logger.debug(
                    f"✓ 補充: {len(notes_appendix.requirements)} 項建議"
                )

                # 組合成完整的 OCSDocument
                doc = OCSDocument(
                    version_info=version_info,
                    ocs_profile=ocs_profile,
                    ocs_content=ocs_content,
                    ocs_attitude=ocs_attitude,
                    notes_and_appendix=notes_appendix,
                )

                self.logger.info(f"✓ 轉換完成: {ocs_profile.ocs_code}")
                return doc

        except Exception as e:
            self.logger.error(f"✗ 轉換失敗: {str(e)}")
            raise TransformationError(f"Failed to transform PDF: {str(e)}") from e

    def _extract_version_info(self, pdf) -> VersionInfo:
        """提取版本歷史信息（通常在第一頁表格）。"""
        versions = []

        try:
            first_page = pdf.pages[0]
            tables = first_page.extract_tables()

            if not tables:
                self.logger.warning("未找到版本表格，version_info.versions 將為空")
                return VersionInfo(versions=versions)

            # 遍歷表格尋找版本信息
            for table in tables:
                header_idx = None
                header_map: Dict[str, int] = {}
                for row_idx, row in enumerate(table):
                    current_map = self._build_column_map(row, self.VERSION_HEADER_ALIASES)
                    if all(k in current_map for k in ("version", "ocs_code", "ocs_name", "status")):
                        header_idx = row_idx
                        header_map = current_map
                        break

                if header_idx is not None:
                    for row in table[header_idx + 1 :]:
                        version_idx = header_map.get("version")
                        version_val = (
                            str(row[version_idx]).strip()
                            if version_idx is not None and version_idx < len(row) and row[version_idx]
                            else ""
                        )
                        if not version_val:
                            continue

                        version_record = VersionEntry(
                            version=version_val,
                            ocs_code=(
                                str(row[header_map["ocs_code"]]).strip()
                                if header_map["ocs_code"] < len(row) and row[header_map["ocs_code"]]
                                else "Unknown"
                            ),
                            ocs_name=(
                                str(row[header_map["ocs_name"]]).strip()
                                if header_map["ocs_name"] < len(row) and row[header_map["ocs_name"]]
                                else "Unknown"
                            ),
                            status=(
                                str(row[header_map["status"]]).strip()
                                if header_map["status"] < len(row) and row[header_map["status"]]
                                else "Unknown"
                            ),
                            update_note=(
                                str(row[header_map["update_note"]]).strip()
                                if "update_note" in header_map
                                and header_map["update_note"] < len(row)
                                and row[header_map["update_note"]]
                                else None
                            ),
                            update_date=(
                                str(row[header_map["update_date"]]).strip()
                                if "update_date" in header_map
                                and header_map["update_date"] < len(row)
                                and row[header_map["update_date"]]
                                else "Unknown"
                            ),
                        )
                        versions.append(version_record)
                    continue

                # fallback: 舊邏輯
                for row in table:
                    if len(row) >= 4 and row[0] and "V" in str(row[0]).upper():
                        version_record = VersionEntry(
                            version=str(row[0]).strip(),
                            ocs_code=str(row[1]).strip() if row[1] else "Unknown",
                            ocs_name=str(row[2]).strip() if row[2] else "Unknown",
                            status=str(row[3]).strip() if row[3] else "Unknown",
                            update_note=(
                                str(row[4]).strip() if len(row) > 4 and row[4] else None
                            ),
                            update_date=(
                                str(row[5]).strip() if len(row) > 5 and row[5] else "Unknown"
                            ),
                        )
                        versions.append(version_record)

        except Exception as e:
            self.logger.warning(f"版本提取失敗: {str(e)}")

        return VersionInfo(versions=versions)

    def _extract_first_code(self, text: str) -> Optional[str]:
        """從文本中提取第一個職能代碼（格式：ABC123-001v1）。"""
        match = re.search(r"[A-Z]{2,}[\d]+-\d+[vV]\d+", text)
        return match.group(0) if match else None

    def _extract_profile(self, pdf, version_info: VersionInfo) -> OCSProfile:
        """提取 OCS Profile 信息（職能代碼、名稱、職類別等）。"""
        try:
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            first_page_tables = first_page.extract_tables() or []

            # 取第一個版本的代碼和名稱
            ocs_code = (
                version_info.versions[0].ocs_code
                if version_info.versions
                else "Unknown"
            )
            ocs_name_str = (
                version_info.versions[0].ocs_name
                if version_info.versions
                else "Unknown"
            )

            # 尋找職類別、職業等信息
            job_categories = self._extract_job_categories_from_table(first_page_tables)
            occupations = self._extract_occupations_from_table(first_page_tables)
            industries = self._extract_industries_from_table(first_page_tables)
            explicit_job_category_name: Optional[str] = None
            explicit_job_category_code: Optional[str] = None
            explicit_occupation_name: Optional[str] = None
            job_description_text = ""
            ocs_level_value = 3

            # 優先讀取第一頁 Profile 顶部欄位：職類 / 職業（若空白就保持 None）
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

            # 抽取工作描述與基準級別
            for table in first_page_tables:
                for row in table:
                    normalized_cells = self._row_to_normalized_cells(row)
                    for i, cell_norm in enumerate(normalized_cells):
                        if not cell_norm:
                            continue

                        if not job_description_text and self._match_profile_label(
                            cell_norm, "job_description"
                        ):
                            # 工作描述通常在同列的後續欄位，合併所有非空內容
                            values = [
                                str(cell).strip()
                                for cell in row[i + 1 :]
                                if cell is not None and str(cell).strip()
                            ]
                            if values:
                                job_description_text = "\n".join(values)

                        if self._match_profile_label(cell_norm, "ocs_level"):
                            level_raw = self._find_value_to_right(row, i)
                            if level_raw:
                                match = re.search(r"\d+", level_raw)
                                if match:
                                    level_num = int(match.group(0))
                                    if 1 <= level_num <= 5:
                                        ocs_level_value = level_num

            pages_to_scan = 1
            for page_idx in range(pages_to_scan):
                tables = pdf.pages[page_idx].extract_tables() or []
                for table in tables:
                    for row in table:
                        normalized_cells = self._row_to_normalized_cells(row)
                        for i, cell_norm in enumerate(normalized_cells):
                            if not cell_norm:
                                continue

                            # 提取職類別
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
                                        if cat_name and cat_name not in [c.name for c in job_categories]:
                                            job_categories.append(
                                                CategoryItem(name=cat_name, code=cat_code)
                                            )

                            # 提取職業
                            if not occupations and self._match_profile_label(
                                cell_norm, "occupation"
                            ) and "職業別代碼" not in str(row[i]):
                                value = self._find_value_to_right(row, i)
                                if value:
                                    for occ_name in self._split_multi_value(value):
                                        occ_code = self._extract_occupation_code(text, occ_name)
                                        if occ_name and occ_name not in [o.name for o in occupations]:
                                            occupations.append(
                                                CategoryItem(name=occ_name, code=occ_code)
                                            )

                            # 提取產業
                            if not industries and self._match_profile_label(
                                cell_norm, "industry"
                            ):
                                value = self._find_value_to_right(row, i)
                                if value:
                                    for ind_name in self._split_multi_value(value):
                                        if ind_name and ind_name not in [d.name for d in industries]:
                                            industries.append(
                                                CategoryItem(name=ind_name, code=self._extract_category_code(ind_name))
                                            )

            if explicit_job_category_code and job_categories:
                for item in job_categories:
                    if item.code == "Unknown":
                        item.code = explicit_job_category_code

            # 若未提取到職業，使用版本名稱
            if not occupations:
                occupations.append(
                    CategoryItem(name=ocs_name_str, code=ocs_code.split("-")[0])
                )

            if ocs_code == "Unknown":
                ocs_code = self._extract_first_code(text) or "Unknown"

            profile = OCSProfile(
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

            return profile

        except Exception as e:
            self.logger.warning(f"Profile 提取失敗: {str(e)}")
            return OCSProfile(
                ocs_code="Unknown",
                ocs_name=OCSName(
                    job_category_name=None, occupation_name="Unknown"
                ),
                category=OCSCategory(
                    job_categories=[], occupations=[], industries=[]
                ),
                job_description="",
                ocs_level=3,
            )

    def _extract_category_code(self, cat_name: str) -> str:
        """從職類別名稱或文本中提取代碼。"""
        # 簡單的啟發式方法：如果名稱包含代碼格式，提取出來
        match = re.search(r"[A-Z]{2,}", cat_name)
        return match.group(0) if match else "Unknown"

    def _extract_occupation_code(self, text: str, occ_name: str) -> str:
        """From text extract occupation code related to occupation name."""
        # 簡單方法：尋找職業別代碼
        pattern = r"職業別代碼\s*(\d+)"
        match = re.search(pattern, text)
        return match.group(1) if match else "Unknown"

    def _extract_content(
        self, pdf, ocs_profile: OCSProfile
    ) -> OCSContent:
        """提取 OCU 內容（任務、產出、行為指標、知識、技能等）。"""
        ocu_units: List[OCSUnit] = []
        known_ocu_names: Dict[str, str] = {}

        def is_generic_unit_name(name: str) -> bool:
            normalized = self._normalize_text(name)
            return normalized in {"主要職責", "工作任務", "unknown", ""}

        def merge_unit(unit: OCSUnit) -> None:
            """Merge parsed unit into accumulator by OCU code."""
            for existing in ocu_units:
                if existing.ocu_code == unit.ocu_code:
                    existing_task_map = {task.task_code: task for task in existing.tasks}
                    for task in unit.tasks:
                        if task.task_code in existing_task_map:
                            target = existing_task_map[task.task_code]
                            target.outputs.extend(task.outputs)
                            target.behavioral_indicators.extend(task.behavioral_indicators)
                            target.knowledge_k.extend(task.knowledge_k)
                            target.skills_s.extend(task.skills_s)
                            target.outputs = self._dedupe_outputs(target.outputs)
                            target.behavioral_indicators = self._dedupe_indicators(
                                target.behavioral_indicators
                            )
                            target.knowledge_k = self._dedupe_competencies(target.knowledge_k)
                            target.skills_s = self._dedupe_competencies(target.skills_s)
                            if not target.task_name and task.task_name:
                                target.task_name = task.task_name
                            target.competency_level = max(target.competency_level, task.competency_level)
                        else:
                            existing.tasks.append(task)
                    if is_generic_unit_name(existing.ocu_name) and not is_generic_unit_name(unit.ocu_name):
                        existing.ocu_name = unit.ocu_name
                    return
            ocu_units.append(unit)

        try:
            # 由第一頁開始掃描所有表格；有些 PDF（如金融科技）第一頁就有 OCU 主表。
            for page_idx in range(0, len(pdf.pages)):
                page = pdf.pages[page_idx]

                tables = page.extract_tables() or []
                for table in tables:
                    if not table:
                        continue
                    header_row = table[0] if table and table[0] else []
                    header_norm = "".join(self._row_to_normalized_cells(header_row))
                    # 跳過態度與補充表格，但不終止整頁/後續掃描。
                    if "attitude" in header_norm or "態度" in header_norm:
                        continue
                    if "說明與補充" in header_norm:
                        continue
                    if not self._is_ocu_candidate_table(table):
                        continue

                    parsed_units = self._parse_ocu_table_units(table)
                    if parsed_units:
                        for unit in parsed_units:
                            # 若單元代碼有效，先記住名稱，供跨頁續表回填。
                            if re.fullmatch(r"T\d+", unit.ocu_code) and not is_generic_unit_name(
                                unit.ocu_name
                            ):
                                known_ocu_names[unit.ocu_code] = unit.ocu_name

                            # 若代碼/名稱是表頭泛稱，改依 task_code 前綴回掛。
                            if not re.fullmatch(r"T\d+", unit.ocu_code) or is_generic_unit_name(
                                unit.ocu_name
                            ):
                                grouped_tasks: Dict[str, List[Task]] = {}
                                for task in unit.tasks:
                                    match = re.match(r"(T\d+)", task.task_code)
                                    ocu_code = match.group(1) if match else unit.ocu_code
                                    grouped_tasks.setdefault(ocu_code, []).append(task)

                                for ocu_code, tasks in grouped_tasks.items():
                                    fallback_name = unit.ocu_name if not is_generic_unit_name(unit.ocu_name) else "Unknown"
                                    normalized_unit = OCSUnit(
                                        ocu_code=ocu_code,
                                        ocu_name=known_ocu_names.get(ocu_code, fallback_name),
                                        tasks=tasks,
                                    )
                                    merge_unit(normalized_unit)
                            else:
                                merge_unit(unit)

        except Exception as e:
            self.logger.warning(f"OCU 內容提取失敗: {str(e)}")

        return OCSContent(ocu_units=ocu_units)

    def _parse_ocu_table_units(self, table: List[List[Any]]) -> List[OCSUnit]:
        """解析單個 OCU 表格，可能包含多個 OCU 單元。"""
        if not table or len(table) < 2:
            return []

        try:
            header_idx, col_map = self._find_ocu_header_row(table)

            if header_idx is None:
                # fallback: 嘗試舊格式（第一行視為 OCU 標題）
                header = table[0]
                ocu_code = str(header[0]).strip() if header[0] else "T0"
                ocu_name = str(header[1]).strip() if len(header) > 1 else "Unknown"
                data_rows = table[1:]
            else:
                header = table[header_idx]
                ocu_code = "Unknown"
                ocu_name = "Unknown"

                # 優先從 header 前方區塊找 OCU 代碼與名稱標籤
                for meta_row in table[: header_idx + 1]:
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

                # 若未找到，使用 header 左側欄位 fallback
                if ocu_code == "Unknown" and header and header[0]:
                    ocu_code = str(header[0]).strip()
                if ocu_name == "Unknown" and len(header) > 1 and header[1]:
                    ocu_name = str(header[1]).strip()

                data_rows = table[header_idx + 1 :]

            units: List[OCSUnit] = []
            unit_tasks: Dict[str, List[Task]] = {}
            unit_names: Dict[str, str] = {}
            last_task_by_ocu: Dict[str, Task] = {}
            current_ocu_code = ocu_code
            current_ocu_name = ocu_name

            def _ensure_unit(code: str, name: str) -> None:
                if code not in unit_tasks:
                    unit_tasks[code] = []
                if code not in unit_names:
                    unit_names[code] = name

            _ensure_unit(current_ocu_code, current_ocu_name)

            for row in data_rows:
                if not row:
                    continue

                if col_map and len(row) > 0:
                    major_duty_raw = self._compact_wrapped_text(row[0])
                    duty_match = re.match(r"(T\d+)(.+)", major_duty_raw)
                    if duty_match:
                        current_ocu_code = duty_match.group(1)
                        current_ocu_name = duty_match.group(2).strip() or current_ocu_name
                        _ensure_unit(current_ocu_code, current_ocu_name)

                # 欄位映射優先；若沒有欄位映射，採舊規則 fallback
                if col_map:
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

                    # 任務代碼常內嵌在 task_name，例如 T1.1xxxx
                    if task_name:
                        match = re.search(r"(T\d+(?:\.\d+)?)", task_name)
                        if (not task_code) or task_code == task_name:
                            task_code = match.group(1) if match else task_name
                        if match:
                            task_name = task_name.replace(match.group(1), "", 1).strip()

                    task_name = self._compact_wrapped_text(task_name)

                    outputs = self._extract_output_items(
                        row[col_map["outputs"]]
                    ) if "outputs" in col_map and col_map["outputs"] < len(row) else []

                    knowledge = self._extract_competency_items(
                        row[col_map["knowledge"]], "K"
                    ) if "knowledge" in col_map and col_map["knowledge"] < len(row) else []

                    skills = self._extract_competency_items(
                        row[col_map["skills"]], "S"
                    ) if "skills" in col_map and col_map["skills"] < len(row) else []

                    # 某些 PDF 的多層表頭會讓 K/S 欄位在資料列位移，改以整列代碼掃描補抓。
                    if not knowledge:
                        knowledge = self._extract_competency_items_from_row(row, "K")
                    if not skills:
                        skills = self._extract_competency_items_from_row(row, "S")

                    behavioral_indicators = self._extract_behavioral_indicators(
                        row[col_map["behavioral"]]
                    ) if "behavioral" in col_map and col_map["behavioral"] < len(row) else []

                    # 非標準 task_code（例如整段文字、章節小標）嘗試由 O/P 代碼反推；失敗則當續列/雜訊列處理。
                    if task_code and not re.fullmatch(r"T\d+(?:\.\d+)?", task_code, flags=re.IGNORECASE):
                        inferred_task_code = self._derive_task_code_from_items(
                            outputs, behavioral_indicators
                        )
                        task_code = inferred_task_code if inferred_task_code else ""

                    # 續列（跨頁/跨列）通常沒有 task_code，需併到上一個 task。
                    if not task_code:
                        previous_task = last_task_by_ocu.get(current_ocu_code)
                        if previous_task:
                            previous_task.outputs.extend(outputs)
                            previous_task.behavioral_indicators.extend(behavioral_indicators)
                            previous_task.knowledge_k.extend(knowledge)
                            previous_task.skills_s.extend(skills)
                            previous_task.outputs = self._dedupe_outputs(previous_task.outputs)
                            previous_task.behavioral_indicators = self._dedupe_indicators(
                                previous_task.behavioral_indicators
                            )
                            previous_task.knowledge_k = self._dedupe_competencies(
                                previous_task.knowledge_k
                            )
                            previous_task.skills_s = self._dedupe_competencies(
                                previous_task.skills_s
                            )
                            previous_task.competency_level = self._extract_task_level(row, col_map)
                            continue

                        # 若是跨頁新表第一列續接，嘗試由 O/P 代碼反推 task_code。
                        inferred_task_code = self._derive_task_code_from_items(
                            outputs, behavioral_indicators
                        )
                        if inferred_task_code:
                            task_code = inferred_task_code
                        else:
                            continue
                    task_level = self._extract_task_level(row, col_map)
                else:
                    if not row[0]:
                        continue
                    task_code = str(row[0]).strip()
                    task_name = str(row[1]).strip() if len(row) > 1 else ""
                    task_name = self._compact_wrapped_text(task_name)

                    outputs = []
                    knowledge = []
                    skills = []
                    behavioral_indicators = []
                    task_level = 3

                    for col in row:
                        if not col or not isinstance(col, str):
                            continue
                        stripped = col.strip()
                        if stripped.startswith("O"):
                            outputs.append(OutputItem(output_code=stripped, output_name=""))
                        if stripped.startswith("K"):
                            knowledge.append(CompetencyItem(code=stripped, name=stripped))
                        if stripped.startswith("S"):
                            skills.append(CompetencyItem(code=stripped, name=stripped))
                        if stripped.startswith("P") or stripped.startswith("T"):
                            behavioral_indicators.append(
                                BehavioralIndicator(
                                    indicator_code=stripped,
                                    indicator_text=stripped,
                                )
                            )

                if task_code:
                    task = Task(
                        task_code=task_code,
                        task_name=task_name,
                        outputs=self._dedupe_outputs(outputs),
                        behavioral_indicators=self._dedupe_indicators(
                            behavioral_indicators
                        ),
                        competency_level=task_level,
                        knowledge_k=self._dedupe_competencies(knowledge),
                        skills_s=self._dedupe_competencies(skills),
                    )
                    _ensure_unit(current_ocu_code, current_ocu_name)
                    unit_tasks[current_ocu_code].append(task)
                    last_task_by_ocu[current_ocu_code] = task

            for code, tasks in unit_tasks.items():
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

    def _parse_ocu_table(self, table: List[List[Any]]) -> Optional[OCSUnit]:
        """Backward-compatible wrapper: return first OCU from a table."""
        units = self._parse_ocu_table_units(table)
        return units[0] if units else None

    def _extract_attitude(self, pdf) -> OCSAttitude:
        """提取態度信息。"""
        attitudes = []

        try:
            full_text = "\n".join(
                [page.extract_text() or "" for page in pdf.pages]
            )

            # 行式解析：A01主動積極 / A02正直誠實
            seen_codes: set[str] = set()
            for line in full_text.splitlines():
                text = line.strip()
                if not text:
                    continue

                match = re.match(r"^A(\d{1,2})\s*(.+)$", text)
                if not match:
                    continue

                code_num = int(match.group(1))
                att_code = f"A{code_num:02d}"
                att_name = match.group(2).strip("、,，;； ")

                if not att_name or att_code in seen_codes:
                    continue

                seen_codes.add(att_code)
                attitudes.append(
                    Attitude(
                        attitude_code=att_code,
                        attitude_name=att_name,
                        attitude_description=None,
                    )
                )

            # 保留原正則做補捉（某些 PDF 會把多個 Axx 黏在同一行）
            if not attitudes:
                attitude_pattern = r"A(\d{1,2})\s*([^\n]+?)(?=\s*A\d{1,2}|\s*說明與補充|$)"
                for match in re.finditer(attitude_pattern, full_text, re.DOTALL):
                    code_num = int(match.group(1))
                    att_code = f"A{code_num:02d}"
                    att_name = match.group(2).strip("、,，;； \n")
                    if not att_name or att_code in seen_codes:
                        continue
                    seen_codes.add(att_code)
                    attitudes.append(
                        Attitude(
                            attitude_code=att_code,
                            attitude_name=att_name,
                            attitude_description=None,
                        )
                    )

        except Exception as e:
            self.logger.warning(f"態度提取失敗: {str(e)}")

        return OCSAttitude(attitudes=attitudes)

    def _extract_notes_and_appendix(self, pdf) -> NotesAndAppendix:
        """提取說明與補充部分。"""
        requirements = []

        try:
            # 在最後幾頁尋找說明與補充
            full_text = "".join(
                [page.extract_text() or "" for page in pdf.pages]
            )

            # 尋找 "說明與補充事項" 之後的內容
            notes_start = full_text.find("說明與補充")
            if notes_start != -1:
                notes_text = full_text[notes_start:]

                # 簡單地將 bullets 分離為建議
                lines = notes_text.split("\n")
                for line in lines[1:]:  # 跳過標題
                    line = line.strip()
                    if line and not line.startswith("第"):
                        # 這是一項建議
                        requirements.append(
                            Requirement(
                                category="建議",
                                content=line,
                                notes=None,
                            )
                        )

        except Exception as e:
            self.logger.warning(f"補充信息提取失敗: {str(e)}")

        return NotesAndAppendix(requirements=requirements)
