"""Profile extractor: code, name, categories, level, description (Phase 3b).

Moved from OCSTransformer; the seven profile helpers + extract_profile.
"""

import re
from typing import Any, List, Optional

from jd_pdf_to_json.core.models import (
    CategoryItem,
    OCSCategory,
    OCSName,
    OCSProfile,
    VersionInfo,
)
from jd_pdf_to_json.transformers.support import tables as tbl
from jd_pdf_to_json.transformers.support import text as txt
from jd_pdf_to_json.utils.logger import logger

PROFILE_LABEL_ALIASES = {
    "job_category": ["職類別", "職類", "jobcategory"],
    "occupation": ["職業", "occupation"],
    "industry": ["所屬產業", "產業", "行業別", "行業", "industry"],
    "job_description": ["工作描述", "職務描述", "jobdescription"],
    "ocs_level": ["基準級別", "職能級別", "level"],
}


def match_profile_label(cell_norm: str, label_key: str) -> bool:
    """Match a normalized cell against profile label aliases conservatively."""
    for alias in PROFILE_LABEL_ALIASES.get(label_key, []):
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

def extract_category_code(cat_name: str) -> str:
    """Extract a job-category code from a category name string."""
    match = re.search(r"[A-Z]{2,}", cat_name)
    return match.group(0) if match else "Unknown"

def extract_occupation_code(text: str) -> str:
    """Extract an occupation code from full-page text."""
    match = re.search(r"職業別代碼\s*(\d+)", text)
    return match.group(1) if match else "Unknown"

def extract_first_code(text: str) -> Optional[str]:
    """Extract the first OCS code (e.g. ABC123-001) from text."""
    match = re.search(r"[A-Z]{2,}\d+-\d+(?:[vV]\d+)?", text)
    return match.group(0) if match else None

def extract_job_categories_from_table(
    tables: List[List[List[Any]]]
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

def extract_occupations_from_table(
    tables: List[List[List[Any]]]
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

def extract_industries_from_table(
    tables: List[List[List[Any]]]
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
                    match_profile_label(cell_norm, "industry") or "行業別" in cell_norm
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

def extract_profile(pdf, version_info: VersionInfo) -> OCSProfile:
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

        job_categories = extract_job_categories_from_table(first_page_tables)
        occupations = extract_occupations_from_table(first_page_tables)
        industries = extract_industries_from_table(first_page_tables)
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
                    if not job_description_text and match_profile_label(
                        cell_norm, "job_description"
                    ):
                        values = [
                            str(c).strip()
                            for c in row[i + 1 :]
                            if c is not None and str(c).strip()
                        ]
                        if values:
                            job_description_text = "\n".join(values)
                    if match_profile_label(cell_norm, "ocs_level"):
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
                        if not job_categories and match_profile_label(
                            cell_norm, "job_category"
                        ):
                            value = tbl.find_value_to_right(row, i)
                            if value:
                                for cat_name in txt.split_multi_value(value):
                                    cat_code = (
                                        explicit_job_category_code
                                        if explicit_job_category_code
                                        else extract_category_code(cat_name)
                                    )
                                    if cat_name and cat_name not in [
                                        c.name for c in job_categories
                                    ]:
                                        job_categories.append(
                                            CategoryItem(name=cat_name, code=cat_code)
                                        )
                        if not occupations and match_profile_label(
                            cell_norm, "occupation"
                        ) and "職業別代碼" not in str(row[i]):
                            value = tbl.find_value_to_right(row, i)
                            if value:
                                for occ_name in txt.split_multi_value(value):
                                    occ_code = extract_occupation_code(text)
                                    if occ_name and occ_name not in [
                                        o.name for o in occupations
                                    ]:
                                        occupations.append(
                                            CategoryItem(name=occ_name, code=occ_code)
                                        )
                        if not industries and match_profile_label(
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
                                                code=extract_category_code(ind_name),
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
            ocs_code = extract_first_code(text) or "Unknown"

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
        logger.warning(f"Profile 提取失敗: {str(e)}")
        return OCSProfile(
            ocs_code="Unknown",
            ocs_name=OCSName(job_category_name=None, occupation_name="Unknown"),
            category=OCSCategory(job_categories=[], occupations=[], industries=[]),
            job_description="",
            ocs_level=3,
        )
