"""OCS PDF → OCSDocument transformer (thin orchestrator).

Delegates each PDF section to its extractor in ``sections/``; shared stateless
helpers live in ``support/``. See the Phase 3b decomposition plan.
"""

import pdfplumber

from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.transformers.base import BaseOCSTransformer
from jd_pdf_to_json.transformers.sections import (
    attitude_extractor,
    content_extractor,
    notes_extractor,
    profile_extractor,
    version_extractor,
)
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.utils.logger import logger


class OCSTransformer(BaseOCSTransformer):
    """Transform PDF raw data into an OCSDocument by orchestrating section extractors."""

    def __init__(self):
        self.logger = logger

    def transform(self, raw_data: dict) -> OCSDocument:
        """Transform raw PDF data into a structured OCSDocument.

        Args:
            raw_data: Dict with key 'file_path' (the PDF is re-opened here).

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
