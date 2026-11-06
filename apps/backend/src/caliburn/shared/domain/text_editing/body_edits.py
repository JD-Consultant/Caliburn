"""Pure, all-or-none edits of one caller-bound Markdown body."""

import difflib
import re
from dataclasses import dataclass

from caliburn.shared.domain.text_editing.errors import InvalidTextError, TextEditError
from caliburn.shared.domain.text_editing.matching import locate_hunk
from caliburn.shared.domain.text_editing.patches import V4ASyntaxError, parse_body_diff


@dataclass(frozen=True, slots=True)
class EditLimits:
    max_body_characters: int
    max_patch_characters: int
    max_hunks: int
    max_scan_characters: int

    def __post_init__(self) -> None:
        for value in (
            self.max_body_characters,
            self.max_patch_characters,
            self.max_hunks,
            self.max_scan_characters,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("Text edit limits must be positive integers")


@dataclass(frozen=True, slots=True)
class _LineEdit:
    start: int
    stop: int
    inserted_lines: tuple[str, ...]


def apply_body_diff(
    body: str,
    diff: str,
    *,
    limits: EditLimits,
) -> str:
    """Return revised body; never perform filesystem or persistence operations."""
    _require_storable_text(body)
    if len(body) > limits.max_body_characters:
        raise TextEditError("patch_limit_exceeded", "Body exceeds the edit limit")
    if len(diff) > limits.max_patch_characters:
        raise TextEditError("patch_limit_exceeded", "Patch exceeds the edit limit")
    _require_storable_text(diff)
    try:
        hunks = parse_body_diff(diff)
    except V4ASyntaxError as error:
        raise TextEditError("invalid_patch", str(error)) from error
    if len(hunks) > limits.max_hunks:
        raise TextEditError("patch_limit_exceeded", "Patch exceeds the hunk limit")
    # Only LF/CRLF are line separators. Other Unicode separators are source text.
    raw_lines = split_body_lines(body)
    lines = tuple(_line_content(line) for line in raw_lines)
    scan_characters = sum(
        len(lines) * sum(len(line) for line in (*hunk.context, *hunk.anchors))
        + len(body) * (len(hunk.context) + len(hunk.anchors))
        for hunk in hunks
    )
    if scan_characters > limits.max_scan_characters:
        raise TextEditError(
            "patch_limit_exceeded",
            "Complete ambiguity scan exceeds the limit",
        )
    edits: list[_LineEdit] = []
    cursor = 0
    for number, hunk in enumerate(hunks, 1):
        start = locate_hunk(lines, hunk, cursor=cursor, hunk_number=number)
        for chunk in hunk.chunks:
            edit_start = start + chunk.original_index
            edits.append(
                _LineEdit(
                    edit_start,
                    edit_start + len(chunk.deleted_lines),
                    chunk.inserted_lines,
                )
            )
        cursor = start + len(hunk.context)
    # All syntax and locations have succeeded before any returned body is built.
    result: list[str] = []
    cursor = 0
    for edit in edits:
        result.extend(raw_lines[cursor : edit.start])
        if lines[edit.start : edit.stop] == edit.inserted_lines:
            result.extend(raw_lines[edit.start : edit.stop])
            cursor = edit.stop
            continue
        newline = _local_newline(raw_lines, edit.start)
        inserted = [line + newline for line in edit.inserted_lines]
        if inserted and edit.stop == len(raw_lines) and not body.endswith("\n"):
            inserted[-1] = inserted[-1][: -len(newline)]
        if inserted and result and not result[-1].endswith("\n"):
            result[-1] += newline
        result.extend(inserted)
        cursor = edit.stop
    result.extend(raw_lines[cursor:])
    revised = "".join(result)
    if len(revised) > limits.max_body_characters:
        raise TextEditError(
            "patch_limit_exceeded", "Revised body exceeds the configured edit limit"
        )
    return revised


def split_body_lines(body: str) -> list[str]:
    """Only LF/CRLF separate lines; preserve other separators as source text."""
    return re.findall(r"[^\n]*\n|[^\n]+$", body)


def _line_content(line: str) -> str:
    return line[:-2] if line.endswith("\r\n") else line.removesuffix("\n")


def _local_newline(lines: list[str], start: int) -> str:
    if start < len(lines) and lines[start].endswith("\n"):
        return "\r\n" if lines[start].endswith("\r\n") else "\n"
    if start and lines[start - 1].endswith("\n"):
        return "\r\n" if lines[start - 1].endswith("\r\n") else "\n"
    return "\n"


def describe_body_change(before: str, after: str) -> str:
    """Describe actual text changes as unified diff, not executable V4A."""
    lines = difflib.unified_diff(
        split_body_lines(before),
        split_body_lines(after),
        fromfile="body_before",
        tofile="body_after",
        n=3,
    )
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in lines
    )


def _require_storable_text(text: str) -> None:
    if "\x00" in text or any("\ud800" <= char <= "\udfff" for char in text):
        raise InvalidTextError("Text contains an unsupported character")
