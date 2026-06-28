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
from jd_pdf_to_json.transformers.sections import attitude_extractor
from jd_pdf_to_json.transformers.sections import notes_extractor
from jd_pdf_to_json.transformers.sections import version_extractor
from jd_pdf_to_json.transformers.support import dedupe as dd
from jd_pdf_to_json.transformers.support import items as itm
from jd_pdf_to_json.transformers.support import scanning as scan
from jd_pdf_to_json.transformers.support import tables as tbl
from jd_pdf_to_json.transformers.support import text as txt
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.utils.logger import logger

_T = TypeVar("_T")


class OCSTransformer(BaseOCSTransformer):
    """Transform PDF raw data into OCSDocument model."""

    # ── Column / label alias tables ───────────────────────────────────────────

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
                version_info = version_extractor.extract_version_info(pdf)
                self.logger.debug(f"✓ 版本信息: {len(version_info.versions)} 筆紀錄")

                ocs_profile = self._extract_profile(pdf, version_info)
                self.logger.debug(f"✓ Profile: {ocs_profile.ocs_code}")

                ocs_content = self._extract_content(pdf)
                self.logger.debug(f"✓ 內容: {len(ocs_content.ocu_units)} 個職能單元")

                ocs_attitude = attitude_extractor.extract_attitude(pdf)
                self.logger.debug(f"✓ 態度: {len(ocs_attitude.attitudes)} 個態度")

                notes = notes_extractor.extract_notes(pdf)
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

    # ── Profile helpers ───────────────────────────────────────────────────────

    def _match_profile_label(self, cell_norm: str, label_key: str) -> bool:
        """Match a normalized cell against profile label aliases conservatively."""
        for alias in self.PROFILE_LABEL_ALIASES.get(label_key, []):
            alias_norm = txt.normalize_text(alias)
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
                names = txt.split_lines(row[2] if len(row) > 2 else None)
                codes = [c.upper() for c in txt.split_lines(row[5] if len(row) > 5 else None)]
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
                names = txt.split_lines(row[2] if len(row) > 2 else None)
                raw_codes = txt.split_lines(row[5] if len(row) > 5 else None)
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
                normalized_cells = tbl.row_to_normalized_cells(row)
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
                name_value = tbl.find_value_to_right(row, name_label_idx)
                if not name_value:
                    continue
                names = txt.split_lines(name_value)
                if not names:
                    continue

                codes: List[str] = []
                if code_label_idx is not None:
                    code_value = tbl.find_value_to_right(row, code_label_idx)
                    if code_value:
                        codes = [
                            c.strip().upper()
                            for c in txt.split_lines(code_value)
                            if code_pattern.fullmatch(c.strip().upper())
                        ]

                if not codes:
                    return [CategoryItem(name=n, code="Unknown") for n in names]
                if len(names) == len(codes):
                    return [CategoryItem(name=n, code=c) for n, c in zip(names, codes)]
                return [CategoryItem(name=names[0], code=codes[0])]

        return []

    # ── Main extractors ───────────────────────────────────────────────────────

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
                    normalized_cells = tbl.row_to_normalized_cells(row)
                    for i, cell_norm in enumerate(normalized_cells):
                        if not cell_norm:
                            continue
                        if (
                            ("職類" == cell_norm or cell_norm == "jobcategory")
                            and "職類別" not in cell_norm
                        ):
                            value = tbl.find_value_to_right(row, i)
                            if value:
                                explicit_job_category_name = value
                        if "職類別代碼" in cell_norm or cell_norm == "jobcategorycode":
                            value = tbl.find_value_to_right(row, i)
                            if value:
                                explicit_job_category_code = value.strip().upper()
                        if (
                            ("職業" == cell_norm or cell_norm == "occupation")
                            and "職業別代碼" not in str(row[i])
                        ):
                            value = tbl.find_value_to_right(row, i)
                            if value:
                                explicit_occupation_name = value

            for table in first_page_tables:
                for row in table:
                    normalized_cells = tbl.row_to_normalized_cells(row)
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
                            level_raw = tbl.find_value_to_right(row, i)
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
                        normalized_cells = tbl.row_to_normalized_cells(row)
                        for i, cell_norm in enumerate(normalized_cells):
                            if not cell_norm:
                                continue
                            if not job_categories and self._match_profile_label(
                                cell_norm, "job_category"
                            ):
                                value = tbl.find_value_to_right(row, i)
                                if value:
                                    for cat_name in txt.split_multi_value(value):
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
                                value = tbl.find_value_to_right(row, i)
                                if value:
                                    for occ_name in txt.split_multi_value(value):
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
                                value = tbl.find_value_to_right(row, i)
                                if value:
                                    for ind_name in txt.split_multi_value(value):
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
                    cleaned_rows = tbl.clean_table_rows(table)
                    if not cleaned_rows:
                        continue

                    header_idx, _, header_span = tbl.find_ocu_header_row(cleaned_rows)
                    if header_idx is None:
                        # ocs_attitude / notes_and_appendix tables are not OCU content.
                        if content_header is not None:
                            section_type = tbl.detect_table_type(table)
                            if section_type not in ("ocs_attitude", "notes_and_appendix"):
                                merged_content_rows.extend(cleaned_rows)
                        continue

                    if content_header is None:
                        content_header = tbl.merge_rows_for_header(
                            cleaned_rows[header_idx : header_idx + header_span]
                        )
                    merged_content_rows.extend(cleaned_rows[header_idx + header_span :])

            if content_header and merged_content_rows:
                merged_table = [content_header] + merged_content_rows
                parsed_units = (
                    self._parse_ocu_table_units(merged_table)
                    if tbl.is_ocu_candidate_table(merged_table)
                    else []
                )

                for unit in parsed_units:
                    if re.fullmatch(r"T\d+", unit.ocu_code) and not scan.is_generic_unit_name(
                        unit.ocu_name
                    ):
                        known_ocu_names[unit.ocu_code] = unit.ocu_name

                    if not re.fullmatch(r"T\d+", unit.ocu_code) or scan.is_generic_unit_name(
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
                                if not scan.is_generic_unit_name(unit.ocu_name)
                                else "Unknown"
                            )
                            scan.merge_ocu_unit(
                                OCSUnit(
                                    ocu_code=ocu_code,
                                    ocu_name=known_ocu_names.get(ocu_code, fallback_name),
                                    tasks=tasks,
                                ),
                                ocu_units,
                            )
                    else:
                        scan.merge_ocu_unit(unit, ocu_units)

            if any(scan.is_generic_unit_name(u.ocu_name) for u in ocu_units):
                text_ocu_names = scan.scan_ocu_names_from_text(pdf)
                for unit in ocu_units:
                    if scan.is_generic_unit_name(unit.ocu_name) and unit.ocu_code in text_ocu_names:
                        unit.ocu_name = text_ocu_names[unit.ocu_code]

            if any(
                entry.name == ""
                for unit in ocu_units
                for task in unit.tasks
                for entry in task.task_codes
            ):
                text_task_names = scan.scan_task_names_from_words(pdf)
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
                TaskCodeEntry(code=task_code_raw, name=txt.compact_wrapped_text(task_name_raw))
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
                    name=txt.compact_wrapped_text(text[m.end() : name_end]),
                )
            )
        return entries

    def _parse_ocu_table_units(self, table: List[List[Any]]) -> List[OCSUnit]:
        """Parse a merged OCU table into one or more OCSUnit objects."""
        if not table or len(table) < 2:
            return []

        try:
            header_idx, col_map, header_span = tbl.find_ocu_header_row(table)
            if header_idx is None:
                return []

            header = tbl.merge_rows_for_header(table[header_idx : header_idx + header_span])
            ocu_code = "Unknown"
            ocu_name = "Unknown"

            for meta_row in table[: header_idx + header_span]:
                for i, cell in enumerate(meta_row):
                    norm_cell = txt.normalize_text(cell)
                    if "職能單元代碼" in norm_cell or "ocu代碼" in norm_cell:
                        value = tbl.find_value_to_right(meta_row, i)
                        if value:
                            ocu_code = value
                    if "職能單元名稱" in norm_cell or "ocu名稱" in norm_cell:
                        value = tbl.find_value_to_right(meta_row, i)
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
                    major_duty_raw = txt.compact_wrapped_text(row[0])
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
                    itm.extract_output_items(row[col_map["outputs"]])
                    if "outputs" in col_map and col_map["outputs"] < len(row)
                    else []
                )

                knowledge: List[CompetencyItem] = []
                if "knowledge" in col_map and col_map["knowledge"] < len(row):
                    knowledge = itm.extract_competency_items(row[col_map["knowledge"]], "K")
                if not knowledge:
                    knowledge = itm.extract_competency_items_from_row(row, "K")

                skills: List[CompetencyItem] = []
                if "skills" in col_map and col_map["skills"] < len(row):
                    skills = itm.extract_competency_items(row[col_map["skills"]], "S")
                if not skills:
                    skills = itm.extract_competency_items_from_row(row, "S")

                behavioral_indicators = (
                    itm.extract_behavioral_indicators(row[col_map["behavioral"]])
                    if "behavioral" in col_map and col_map["behavioral"] < len(row)
                    else []
                )
                if not behavioral_indicators:
                    behavioral_indicators = itm.extract_behavioral_indicators_from_row(row)

                # Historical PDFs: task-code cell may be None (merged cell); derive from P-code.
                if (
                    not primary_task_code
                    and behavioral_indicators
                    and not last_task_by_ocu.get(current_ocu_code)
                ):
                    derived = scan.derive_task_code_from_p_codes(behavioral_indicators)
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
                                    competency_level=itm.extract_task_level(row, col_map),
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
                            txt.compact_wrapped_text(row[output_idx])
                            if output_idx is not None and output_idx < len(row) and row[output_idx]
                            else ""
                        )
                        behavioral_tail = (
                            txt.compact_wrapped_text(row[behavioral_idx])
                            if behavioral_idx is not None
                            and behavioral_idx < len(row)
                            and row[behavioral_idx]
                            else ""
                        )
                        knowledge_tail = (
                            txt.compact_wrapped_text(row[knowledge_idx])
                            if knowledge_idx is not None
                            and knowledge_idx < len(row)
                            and row[knowledge_idx]
                            else ""
                        )
                        skills_tail = (
                            txt.compact_wrapped_text(row[skills_idx])
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
                            previous_block.outputs[-1].name = txt.append_text_if_new(
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
                            previous_block.indicators[-1].text = txt.append_text_if_new(
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
                            previous_block.knowledge[-1].name = txt.append_text_if_new(
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
                            previous_block.skills[-1].name = txt.append_text_if_new(
                                previous_block.skills[-1].name, skills_tail
                            )

                        if task_name and previous_task.task_codes:
                            last_entry = previous_task.task_codes[-1]
                            last_entry.name = txt.append_text_if_new(last_entry.name, task_name)

                        # New block when both a structural trigger (new O or level change)
                        # and new K/S codes are present.
                        new_level = itm.extract_task_level(row, col_map)
                        level_changed = new_level != previous_block.competency_level
                        has_new_o = bool(outputs)
                        has_new_ks = bool(knowledge or skills)

                        if (has_new_o or level_changed) and has_new_ks and behavioral_indicators:
                            previous_task.competency_blocks.append(
                                CompetencyBlock(
                                    competency_level=new_level,
                                    indicators=dd.dedupe_indicators(behavioral_indicators),
                                    outputs=dd.dedupe_outputs(
                                        outputs if outputs else list(previous_block.outputs)
                                    ),
                                    knowledge=dd.dedupe_competencies(knowledge),
                                    skills=dd.dedupe_competencies(skills),
                                )
                            )
                        else:
                            previous_block.outputs.extend(outputs)
                            previous_block.indicators.extend(behavioral_indicators)
                            previous_block.knowledge.extend(knowledge)
                            previous_block.skills.extend(skills)
                            dd.dedupe_block(previous_block)
                        continue

                    continue

                task_level = itm.extract_task_level(row, col_map)
                if primary_task_code:
                    task = Task(
                        task_codes=parsed_task_codes,
                        competency_blocks=[
                            CompetencyBlock(
                                competency_level=task_level,
                                indicators=dd.dedupe_indicators(behavioral_indicators),
                                outputs=dd.dedupe_outputs(outputs),
                                knowledge=dd.dedupe_competencies(knowledge),
                                skills=dd.dedupe_competencies(skills),
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

