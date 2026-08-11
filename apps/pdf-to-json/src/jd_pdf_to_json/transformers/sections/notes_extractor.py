"""Notes / supplementary-info extractor (moved verbatim from OCSTransformer, Phase 3b)."""

import re
from typing import List

from jd_pdf_to_json.core.models import Notes
from jd_pdf_to_json.utils.logger import logger


def extract_notes(pdf) -> Notes:
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
        logger.warning(f"補充信息提取失敗: {str(e)}")

    return Notes(prerequisites=prerequisites, supplements=supplements)
