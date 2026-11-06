"""Preserve coded and uncoded attitudes from the attitude section."""

import re

from ocs_contract.models import CodeName, OcsAttitude

from caliburn.modules.occupation_reference.domain.text import join_wrapped_lines

from ...parsers.models import PDFDocument
from ..support import text as txt


def extract_attitude(pdf: PDFDocument) -> OcsAttitude:
    """Extract attitude competency items (A-codes) from full PDF text.

    Handles both one-per-line and multiple-per-line formats, e.g.
    'A01外部意識、A02溝通協調能力、A03成果導向' all on a single line.
    """
    lines = txt.section_lines(pdf, "職能內涵", end="說明與補充", qualifier="attitude")
    body = ""
    for line in lines:
        body = join_wrapped_lines(body, line)
    matches = list(re.finditer(r"(?<![A-Za-z0-9])A(\d{1,2})(?!\d)", body))
    attitudes = []
    if not matches:
        if body:
            attitudes.append(CodeName(code=None, name=body))
    else:
        if body[: matches[0].start()].strip("、,，;； "):
            attitudes.append(
                CodeName(code=None, name=body[: matches[0].start()].strip())
            )
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            name = body[match.end() : end].strip("、,，;； \t")
            if name:
                attitudes.append(CodeName(code=match.group(0), name=name))
    return OcsAttitude(attitudes=attitudes)
