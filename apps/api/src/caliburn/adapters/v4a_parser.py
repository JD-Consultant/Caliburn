"""Parse single-body V4A updates; no paths, filesystem, or first-match locator.

The section/chunk algorithm is adapted from OpenAI Agents Python apply_diff.py
(MIT). Attribution and changes: apps/api/THIRD_PARTY_NOTICES.md; the full
license also ships beside this module as _openai_agents_license.txt.
Caliburn requires full input consumption and leaves location to its editor.
"""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class V4AChunk:
    original_index: int
    deleted_lines: tuple[str, ...]
    inserted_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class V4AHunk:
    anchors: tuple[str, ...]
    context: tuple[str, ...]
    chunks: tuple[V4AChunk, ...]
    end_of_file: bool


class V4ASyntaxError(ValueError):
    """The entire body update must be rejected, including earlier valid hunks."""


def parse_body_diff(diff: str) -> tuple[V4AHunk, ...]:
    """Parse update hunks, optional terminal EOF/End Patch, and stacked anchors.

    Numeric unified headers, file envelopes, unconsumed tails, NUL and lone CR
    are not body V4A. Error messages deliberately do not echo arbitrary input.
    """
    if "\x00" in diff or "\r" in diff.replace("\r\n", ""):
        raise V4ASyntaxError("Diff contains an unsupported control character")
    lines = diff.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if lines and lines[-1] == "*** End Patch":
        lines.pop()
    if not lines:
        raise V4ASyntaxError("Provide a nonempty body update")

    hunks: list[V4AHunk] = []
    index = 0
    while index < len(lines):
        anchors: list[str] = []
        header_count = 0
        while index < len(lines) and (lines[index] == "@@" or lines[index].startswith("@@ ")):
            header = lines[index]
            if re.match(r"@@ [+-]\d", header):
                raise V4ASyntaxError("Use V4A @@ or source-text anchors, not numeric diff headers")
            if header != "@@":
                anchor = header[3:]
                if not anchor.strip():
                    raise V4ASyntaxError("A source-text anchor cannot be blank")
                anchors.append(anchor)
            index += 1
            header_count += 1
        if hunks and not header_count:
            raise V4ASyntaxError("Each subsequent hunk must start with @@")
        context, chunks, index, end_of_file = _read_section(lines, index)
        if not chunks or (not end_of_file and not any(line.strip() for line in context)):
            raise V4ASyntaxError("Each hunk needs an edit and source context or an explicit EOF")
        hunks.append(V4AHunk(tuple(anchors), context, chunks, end_of_file))
        if end_of_file and index != len(lines):
            raise V4ASyntaxError("End of File must terminate the body diff")
    return tuple(hunks)


def _read_section(
    lines: list[str], start_index: int
) -> tuple[tuple[str, ...], tuple[V4AChunk, ...], int, bool]:
    # OpenAI's section algorithm: context is the old side; each edit chunk has
    # a context-relative offset. Keep lines are never copied over actual text.
    context: list[str] = []
    deleted_lines: list[str] = []
    inserted_lines: list[str] = []
    chunks: list[V4AChunk] = []
    mode: Literal["keep", "add", "delete"] = "keep"
    index = start_index
    while index < len(lines):
        raw = lines[index]
        if raw == "@@" or raw.startswith("@@ ") or raw == "*** End of File":
            break
        if raw.startswith("***"):
            raise V4ASyntaxError("File operations and patch envelopes are not allowed")
        index += 1
        last_mode = mode
        line = raw if raw else " "
        prefix = line[0]
        if prefix == "+":
            mode = "add"
        elif prefix == "-":
            mode = "delete"
        elif prefix == " ":
            mode = "keep"
        else:
            raise V4ASyntaxError("Hunk lines must start with space, - or +")
        line_content = line[1:]
        if mode == "keep" and last_mode != mode and (deleted_lines or inserted_lines):
            chunks.append(
                V4AChunk(
                    len(context) - len(deleted_lines), tuple(deleted_lines), tuple(inserted_lines)
                )
            )
            deleted_lines = []
            inserted_lines = []
        if mode == "delete":
            deleted_lines.append(line_content)
            context.append(line_content)
        elif mode == "add":
            inserted_lines.append(line_content)
        else:
            context.append(line_content)
    if deleted_lines or inserted_lines:
        chunks.append(
            V4AChunk(len(context) - len(deleted_lines), tuple(deleted_lines), tuple(inserted_lines))
        )
    if index == start_index:
        raise V4ASyntaxError("Hunk has no lines")
    end_of_file = index < len(lines) and lines[index] == "*** End of File"
    return tuple(context), tuple(chunks), index + int(end_of_file), end_of_file
