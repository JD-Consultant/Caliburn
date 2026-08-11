"""Item extraction for the OCS transformer (moved verbatim from OCSTransformer, Phase 3b).

Stateless parsers that turn raw cell/row text into typed competency items
(O/P/T/K/S codes) and competency levels.
"""

import re
import unicodedata
from typing import Any, Dict, List

from jd_pdf_to_json.core.models import (
    BehavioralIndicator,
    CompetencyItem,
    OutputItem,
)
from jd_pdf_to_json.transformers.support import text as txt


def extract_output_items(cell_value: Any) -> List[OutputItem]:
    """Parse O-code work outputs from a cell."""
    if not cell_value:
        return []
    text = txt.compact_wrapped_text(cell_value)
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


def extract_behavioral_indicators(cell_value: Any) -> List[BehavioralIndicator]:
    """Parse P/T behavioral indicators from a cell."""
    if not cell_value:
        return []
    text = txt.compact_wrapped_text(cell_value)
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


def extract_behavioral_indicators_from_row(row: List[Any]) -> List[BehavioralIndicator]:
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


def extract_competency_items(cell_value: Any, code_prefix: str) -> List[CompetencyItem]:
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


def extract_competency_items_from_row(row: List[Any], code_prefix: str) -> List[CompetencyItem]:
    """Fallback K/S extraction scanning all cells in a row."""
    row_text = "\n".join(
        str(c).strip() for c in row if c is not None and str(c).strip()
    )
    return extract_competency_items(row_text, code_prefix) if row_text else []


def extract_task_level(row: List[Any], col_map: Dict[str, int]) -> int:
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
