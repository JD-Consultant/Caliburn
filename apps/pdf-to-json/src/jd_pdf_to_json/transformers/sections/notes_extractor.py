"""Extract note items without confusing page wrapping with item boundaries."""

import re

from jd_pdf_to_json.core.models import Notes
from jd_pdf_to_json.transformers.support import text as txt

ITEM_MARKER = re.compile(r"^(?:[⚫◆•◎＊*]+\s*|-\s+|\d+[.)、](?!\d)\s*)+")
PREREQUISITE_HEADER = re.compile(r"建議擔任此職類.{0,8}學歷.{0,8}(?:經歷|經驗)")


def extract_notes(pdf) -> Notes:
    """Keep source bullets, numbered notes and their wrapped continuations together."""
    notes = Notes()
    target = notes.supplements
    for line in txt.section_lines(pdf, "說明與補充"):
        if PREREQUISITE_HEADER.search(line):
            target = notes.prerequisites
            continue
        if "相關所屬類別" in line:
            target = notes.supplements
        if "其他補充說明" in line:
            target = notes.supplements
            line = re.split(r"[：:]", line, maxsplit=1)[-1] if re.search(r"[：:]", line) else ""
        marker = ITEM_MARKER.match(line)
        clean = ITEM_MARKER.sub("", line).strip()
        if not clean:
            continue
        starts_item = bool(marker) or clean.startswith("【註")
        if starts_item or not target or target[-1].endswith(("。", ";", "；")):
            target.append(clean)
        else:
            target[-1] = txt.join_wrapped_lines(target[-1], clean)
    return notes
