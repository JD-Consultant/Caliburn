"""Pure, all-or-none edits of one caller-bound Memory Markdown body."""

import re
from dataclasses import dataclass

from caliburn.adapters.v4a_parser import V4ASyntaxError, parse_body_diff
from caliburn.features.work_memory.body_matching import (
    BodyEditError,
    BodyMatchPolicy,
    locate_hunk,
)


@dataclass(frozen=True, slots=True)
class _LineEdit:
    start: int
    stop: int
    inserted_lines: tuple[str, ...]


DEFAULT_BODY_MATCH_POLICY = BodyMatchPolicy()


def apply_body_diff(
    body: str, diff: str, *, policy: BodyMatchPolicy = DEFAULT_BODY_MATCH_POLICY
) -> str:
    """Return revised body; never perform filesystem or persistence operations."""
    if len(body) > policy.max_body_characters or len(diff) > policy.max_diff_characters:
        raise BodyEditError(
            "patch_limit_exceeded", "Body or diff exceeds the configured edit limit"
        )
    if not body.strip():
        raise BodyEditError("invalid_patch", "Update requires a nonblank source body")
    try:
        hunks = parse_body_diff(diff)
    except V4ASyntaxError as error:
        raise BodyEditError("invalid_patch", str(error)) from error
    if len(hunks) > policy.max_hunks:
        raise BodyEditError("patch_limit_exceeded", "Too many hunks; use smaller edits")
    # Only LF/CRLF are line separators. Other Unicode separators are source text.
    raw_lines = split_body_lines(body)
    lines = tuple(_line_content(line) for line in raw_lines)
    scan_characters = sum(
        len(lines) * sum(len(line) for line in (*hunk.context, *hunk.anchors))
        + len(body) * (len(hunk.context) + len(hunk.anchors))
        for hunk in hunks
    )
    if scan_characters > policy.max_scan_characters:
        raise BodyEditError(
            "patch_limit_exceeded", "Complete ambiguity scan exceeds the limit; use smaller hunks"
        )
    edits: list[_LineEdit] = []
    cursor = 0
    for number, hunk in enumerate(hunks, 1):
        start = locate_hunk(lines, hunk, cursor=cursor, hunk_number=number, policy=policy)
        for chunk in hunk.chunks:
            edit_start = start + chunk.original_index
            edits.append(
                _LineEdit(edit_start, edit_start + len(chunk.deleted_lines), chunk.inserted_lines)
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
    if len(revised) > policy.max_body_characters:
        raise BodyEditError(
            "patch_limit_exceeded", "Revised body exceeds the configured edit limit"
        )
    if not revised.strip():
        raise BodyEditError(
            "invalid_patch", "Body must remain nonblank; use delete for object removal"
        )
    return revised


def split_body_lines(body: str) -> list[str]:
    """Preserve exact source lines; Unicode separators and lone CR are content, not LF."""
    return re.findall(r"[^\n]*\n|[^\n]+$", body)


def _line_content(line: str) -> str:
    return line[:-2] if line.endswith("\r\n") else line.removesuffix("\n")


def _local_newline(lines: list[str], start: int) -> str:
    if start < len(lines) and lines[start].endswith("\n"):
        return "\r\n" if lines[start].endswith("\r\n") else "\n"
    if start and lines[start - 1].endswith("\n"):
        return "\r\n" if lines[start - 1].endswith("\r\n") else "\n"
    return "\n"
