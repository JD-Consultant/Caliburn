"""Deduplication helpers for the OCS transformer (moved verbatim from OCSTransformer, Phase 3b).

Order-preserving dedupe for competency item lists and whole competency blocks.
"""

from typing import Callable, List, TypeVar

from jd_pdf_to_json.core.models import (
    BehavioralIndicator,
    CompetencyBlock,
    CompetencyItem,
    OutputItem,
)
from jd_pdf_to_json.transformers.support import text as txt

_T = TypeVar("_T")


def dedupe(items: List[_T], key: Callable[[_T], tuple]) -> List[_T]:
    """Remove duplicates from *items* preserving first-occurrence order."""
    seen: set[tuple] = set()
    result: List[_T] = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def dedupe_outputs(items: List[OutputItem]) -> List[OutputItem]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.name or ""),
        ),
    )


def dedupe_indicators(items: List[BehavioralIndicator]) -> List[BehavioralIndicator]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.text or ""),
        ),
    )


def dedupe_competencies(items: List[CompetencyItem]) -> List[CompetencyItem]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.name or ""),
        ),
    )


def dedupe_block(block: CompetencyBlock) -> CompetencyBlock:
    """Deduplicate all item lists in a competency block in-place."""
    block.outputs = dedupe_outputs(block.outputs)
    block.indicators = dedupe_indicators(block.indicators)
    block.knowledge = dedupe_competencies(block.knowledge)
    block.skills = dedupe_competencies(block.skills)
    return block
