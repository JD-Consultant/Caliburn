"""Historical-PDF scanning and OCU unit assembly (moved verbatim from OCSTransformer, Phase 3b).

Bbox/word-position scanning recovers OCU and task names from historical PDFs
where merged cells defeat table extraction; the unit-assembly helpers merge
parsed units and recognise placeholder names.
"""

import re
from typing import List, Optional

from jd_pdf_to_json.core.models import BehavioralIndicator, OCSUnit
from jd_pdf_to_json.transformers.support import dedupe as dd
from jd_pdf_to_json.transformers.support import text as txt


def scan_ocu_names_from_text(pdf) -> dict:
    """Extract OCU T-code → name mapping from the leftmost page column.

    Uses bbox word positions to handle historical PDFs where merged table
    cells cause pdfplumber to return None for most rows.
    """
    names: dict = {}
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


def scan_task_names_from_words(pdf) -> dict:
    """Extract T{n}.{m} → name mapping from word-level bbox positions.

    Words are bucketed into 5px rows to handle sub-pixel y differences.
    Only words within ±30px of the task-code x-position are captured.
    """
    names: dict = {}
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


def derive_task_code_from_p_codes(indicators: List[BehavioralIndicator]) -> Optional[str]:
    """Derive task code from P-code when the task-code table cell is None.

    P-code format: P{ocu}.{task}.{seq} → T{ocu}.{task}. E.g. P1.1.1 → T1.1.
    """
    for ind in indicators:
        m = re.match(r"P\.?(\d+)\.(\d+)", ind.code, re.IGNORECASE)
        if m:
            return f"T{m.group(1)}.{m.group(2)}"
    return None


def is_generic_unit_name(name: str) -> bool:
    """Return True when *name* is a placeholder rather than a real OCU name."""
    return txt.normalize_text(name) in {"主要職責", "工作任務", "unknown", ""}


def merge_ocu_unit(unit: OCSUnit, ocu_units: List[OCSUnit]) -> None:
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
                    dd.dedupe_block(b) for b in target.competency_blocks
                ]
                existing_codes = {e.code for e in target.task_codes}
                for entry in task.task_codes:
                    if entry.code not in existing_codes:
                        target.task_codes.append(entry)
            else:
                existing.tasks.append(task)
        if is_generic_unit_name(existing.ocu_name) and not is_generic_unit_name(
            unit.ocu_name
        ):
            existing.ocu_name = unit.ocu_name
        return
    ocu_units.append(unit)
