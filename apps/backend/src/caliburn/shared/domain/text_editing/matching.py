"""單正文的有界唯一匹配；精確與近似位置共同判斷歧義。"""

from rapidfuzz.distance import Levenshtein

from caliburn.shared.domain.text_editing.errors import TextEditError, TextMatch
from caliburn.shared.domain.text_editing.patches import V4AHunk


def locate_hunk(
    lines: tuple[str, ...],
    hunk: V4AHunk,
    *,
    cursor: int,
    hunk_number: int,
) -> int:
    """Return a zero-based unique start; do not prefer exact over qualified fuzzy.

    Anchors only advance the search floor. Every qualifying context at or after
    that floor counts, including overlapping candidates and unequal scores.
    EOF is a hard boundary, never a fallback search through the body.
    """
    for anchor_index, anchor in enumerate(hunk.anchors):
        if anchor_index == 0 and any(
            line.strip() == anchor.strip() for line in lines[:cursor]
        ):
            # A repeated parent header names earlier context without rewinding.
            # Retain the full current floor, so later duplicates still count.
            continue
        # Choosing the earliest qualifying anchor retains every later possible
        # context; a repeated anchor cannot silently suppress another match.
        position = next(
            (
                index
                for index in range(cursor, len(lines))
                if lines[index].strip() == anchor.strip()
            ),
            None,
        )
        if position is None:
            raise TextEditError(
                "patch_context_not_found",
                "Source anchor was not found",
                hunk_number=hunk_number,
            )
        cursor = position + 1

    width = len(hunk.context)
    last_start = len(lines) - width
    starts = (
        range(max(cursor, last_start), last_start + 1)
        if hunk.end_of_file
        else range(cursor, last_start + 1)
    )
    target = tuple(line.strip() for line in hunk.context)
    normalized = tuple(line.strip() for line in lines)
    matches: list[TextMatch] = []
    for start in starts:
        if all(
            _qualifies(expected, normalized[start + offset])
            for offset, expected in enumerate(target)
        ):
            matches.append(TextMatch(start + 1, start + width))
            if len(matches) == 2:
                raise TextEditError(
                    "ambiguous_patch_context",
                    "Multiple source contexts qualify",
                    hunk_number=hunk_number,
                    candidates=tuple(matches),
                )
    if not matches:
        raise TextEditError(
            "patch_context_not_found",
            "No source context qualifies",
            hunk_number=hunk_number,
        )
    return matches[0].start_line - 1


def _qualifies(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    if min(len(expected), len(actual)) < 10:
        return False
    # A per-line gate prevents a long identical context from hiding a completely
    # wrong short heading, responsibility, frequency, or deletion line.
    return (
        Levenshtein.normalized_similarity(expected, actual, score_cutoff=0.90) >= 0.90
    )
