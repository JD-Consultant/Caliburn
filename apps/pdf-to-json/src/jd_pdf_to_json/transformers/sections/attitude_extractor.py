"""Attitude (A-code) extractor (moved verbatim from OCSTransformer, Phase 3b)."""

import re
from typing import List

from jd_pdf_to_json.core.models import Attitude, OCSAttitude
from jd_pdf_to_json.utils.logger import logger


def extract_attitude(pdf) -> OCSAttitude:
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
        logger.warning(f"態度提取失敗: {str(e)}")
    return OCSAttitude(attitudes=attitudes)
