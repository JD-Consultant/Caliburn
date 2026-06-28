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
from jd_pdf_to_json.transformers.sections import content_extractor
from jd_pdf_to_json.transformers.sections import notes_extractor
from jd_pdf_to_json.transformers.sections import profile_extractor
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

                ocs_profile = profile_extractor.extract_profile(pdf, version_info)
                self.logger.debug(f"✓ Profile: {ocs_profile.ocs_code}")

                ocs_content = content_extractor.extract_content(pdf)
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

