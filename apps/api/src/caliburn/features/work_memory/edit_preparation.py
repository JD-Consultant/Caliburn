"""Pure controlled content preparation before the candidate owner's short transaction."""

import difflib
from dataclasses import dataclass
from typing import Literal

from caliburn.features.work_memory.body_edits import (
    DEFAULT_BODY_MATCH_POLICY,
    apply_body_diff,
    split_body_lines,
)
from caliburn.features.work_memory.body_matching import BodyMatchPolicy
from caliburn.features.work_memory.candidates import MemoryEdit
from caliburn.features.work_memory.edit_intents import (
    InterviewReferenceChange,
    MemoryBodyChange,
    MemoryFieldChange,
    MemoryTextChange,
    SituationReferenceChange,
)
from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemoryContentChanges,
)


@dataclass(frozen=True, slots=True)
class MemoryStatusPreview:
    status: Literal["created", "deleted", "unchanged"]


@dataclass(frozen=True, slots=True)
class MemoryUpdatePreview:
    content: MemoryContent
    changed_fields: tuple[Literal["title", "description"], ...]
    body_diff: str | None
    reference_field: Literal["interview_references", "work_situation_references"]
    added: tuple[int | str, ...]
    removed: tuple[int | str, ...]


@dataclass(frozen=True, slots=True)
class PreparedMemoryEdit:
    """Not a saved result. Runtime preserves the command before allowing its execution."""

    command: MemoryEdit
    preview: MemoryStatusPreview | MemoryUpdatePreview


def prepare_content_changes(
    current: MemoryContent,
    changes: tuple[MemoryFieldChange, ...],
    *,
    policy: BodyMatchPolicy = DEFAULT_BODY_MATCH_POLICY,
) -> MemoryContentChanges | None:
    validate_changes(changes)
    title = description = body = None
    for change in changes:
        if isinstance(change, MemoryTextChange):
            if change.field == "title":
                title = change.value
            else:
                description = change.value
        elif isinstance(change, MemoryBodyChange):
            body = apply_body_diff(current.body, change.diff, policy=policy)
    if title is None and description is None and body is None:
        return None
    return MemoryContentChanges(title, description, body)


def validate_changes(changes: tuple[MemoryFieldChange, ...]) -> None:
    if not 1 <= len(changes) <= 4:
        raise InvalidMemoryChangeError("One to four field changes are required")
    fields: list[str] = []
    for change in changes:
        if isinstance(change, MemoryTextChange):
            fields.append(change.field)
        elif isinstance(change, MemoryBodyChange):
            fields.append("body")
        elif isinstance(change, InterviewReferenceChange):
            fields.append("interview_references")
        else:
            fields.append("work_situation_references")
        if isinstance(change, InterviewReferenceChange | SituationReferenceChange):
            if not change.add and not change.remove:
                raise InvalidMemoryChangeError("A reference change cannot be empty")
    if len(fields) != len(set(fields)):
        raise InvalidMemoryChangeError("Each field may be changed only once")


def describe_body_change(before: str, after: str) -> str:
    """Standard contextual diff of actual text; not executable V4A or echoed model input."""
    lines = difflib.unified_diff(
        split_body_lines(before),
        split_body_lines(after),
        fromfile="body_before",
        tofile="body_after",
        n=3,
    )
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines
    )
