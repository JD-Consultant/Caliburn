"""Bounded, ambiguity-rejecting whole-line location for Memory body hunks."""

from dataclasses import dataclass
from typing import Literal

from rapidfuzz.distance import Levenshtein

from caliburn.adapters.v4a_parser import V4AHunk

type BodyEditErrorCode = Literal[
    "invalid_patch", "patch_context_not_found", "ambiguous_patch_context", "patch_limit_exceeded"
]


@dataclass(frozen=True, slots=True)
class BodyMatch:
    start_line: int
    end_line: int
    excerpt: str


class BodyEditError(ValueError):
    """Safe typed rejection; candidate locations are diagnostic, not write handles."""

    def __init__(
        self,
        code: BodyEditErrorCode,
        message: str,
        *,
        hunk_number: int | None = None,
        candidates: tuple[BodyMatch, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.hunk_number = hunk_number
        self.candidates = candidates


@dataclass(frozen=True, slots=True)
class BodyMatchPolicy:
    """App-owned bounded engineering defaults, not model-supplied tool arguments."""

    line_similarity: float = 0.90
    minimum_fuzzy_line_characters: int = 10
    max_body_characters: int = 2_000_000
    max_diff_characters: int = 64_000
    max_hunks: int = 128
    max_scan_characters: int = 20_000_000

    def __post_init__(self) -> None:
        if not 0 < self.line_similarity <= 1:
            raise ValueError("Line similarity must be within (0, 1]")
        if (
            min(
                self.minimum_fuzzy_line_characters,
                self.max_body_characters,
                self.max_diff_characters,
                self.max_hunks,
                self.max_scan_characters,
            )
            < 1
        ):
            raise ValueError("Body edit limits must be positive")


def locate_hunk(
    lines: tuple[str, ...],
    hunk: V4AHunk,
    *,
    cursor: int,
    hunk_number: int,
    policy: BodyMatchPolicy,
) -> int:
    """Return a zero-based unique start; do not prefer exact over qualified fuzzy.

    Anchors only advance the search floor. Every qualifying context at or after
    that floor counts, including overlapping candidates and unequal scores.
    EOF is a hard boundary, never a fallback search through the body.
    """
    for anchor_index, anchor in enumerate(hunk.anchors):
        if anchor_index == 0 and any(line.strip() == anchor.strip() for line in lines[:cursor]):
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
            raise BodyEditError(
                "patch_context_not_found", "Source anchor was not found", hunk_number=hunk_number
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
    matches: list[BodyMatch] = []
    for start in starts:
        if all(
            _qualifies(expected, normalized[start + offset], policy)
            for offset, expected in enumerate(target)
        ):
            matches.append(
                BodyMatch(start + 1, start + width, "\n".join(lines[start : start + width])[:320])
            )
            if len(matches) == 2:
                raise BodyEditError(
                    "ambiguous_patch_context",
                    "At least two source contexts qualify; add distinguishing real context",
                    hunk_number=hunk_number,
                    candidates=tuple(matches),
                )
    if not matches:
        raise BodyEditError(
            "patch_context_not_found",
            "No qualifying source context; read the body and use complete source lines",
            hunk_number=hunk_number,
        )
    return matches[0].start_line - 1


def _qualifies(expected: str, actual: str, policy: BodyMatchPolicy) -> bool:
    if expected == actual:
        return True
    if min(len(expected), len(actual)) < policy.minimum_fuzzy_line_characters:
        return False
    # A per-line gate prevents a long identical context from hiding a completely
    # wrong short heading, responsibility, frequency, or deletion line.
    return (
        Levenshtein.normalized_similarity(expected, actual, score_cutoff=policy.line_similarity)
        >= policy.line_similarity
    )
