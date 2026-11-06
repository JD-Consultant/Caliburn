"""Remove identical competency items while preserving source order."""

from collections.abc import Callable, Hashable

from ocs_contract.models import (
    CodeName,
    CodeText,
    CompetencyBlock,
)

from . import text as txt


def dedupe[T](items: list[T], key: Callable[[T], Hashable]) -> list[T]:
    """Remove duplicates from *items* preserving first-occurrence order."""
    seen: set[Hashable] = set()
    result: list[T] = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def dedupe_outputs(items: list[CodeName]) -> list[CodeName]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.name or ""),
        ),
    )


def dedupe_indicators(items: list[CodeText]) -> list[CodeText]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.text or ""),
        ),
    )


def dedupe_competencies(items: list[CodeName]) -> list[CodeName]:
    return dedupe(
        items,
        lambda i: (
            txt.normalize_text((i.code or "").upper()),
            txt.normalize_text(i.name or ""),
        ),
    )


def dedupe_block(block: CompetencyBlock) -> CompetencyBlock:
    """Deduplicate all item lists in a competency block in-place."""
    block.outputs = dedupe_outputs(block.outputs or [])
    block.indicators = dedupe_indicators(block.indicators or [])
    block.knowledge = dedupe_competencies(block.knowledge or [])
    block.skills = dedupe_competencies(block.skills or [])
    return block
