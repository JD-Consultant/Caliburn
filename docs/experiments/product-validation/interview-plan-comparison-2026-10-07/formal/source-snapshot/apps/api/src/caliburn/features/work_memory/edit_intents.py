"""Validated model intent without provider DTOs, execution IDs or storage effects."""

from dataclasses import dataclass
from typing import Literal

from caliburn.features.work_memory.models import MemoryContent


@dataclass(frozen=True, slots=True)
class MemoryTextChange:
    field: Literal["title", "description"]
    value: str


@dataclass(frozen=True, slots=True)
class MemoryBodyChange:
    diff: str


@dataclass(frozen=True, slots=True)
class InterviewReferenceChange:
    add: tuple[int, ...] = ()
    remove: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SituationReferenceChange:
    add: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()


type MemoryFieldChange = (
    MemoryTextChange | MemoryBodyChange | InterviewReferenceChange | SituationReferenceChange
)


@dataclass(frozen=True, slots=True)
class InterviewSourceSelection:
    sequences: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SituationSourceSelection:
    titles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CreateMemoryIntent:
    content: MemoryContent
    sources: InterviewSourceSelection | SituationSourceSelection


@dataclass(frozen=True, slots=True)
class ReviseMemoryIntent:
    target_title: str
    changes: tuple[MemoryFieldChange, ...]


@dataclass(frozen=True, slots=True)
class DeleteMemoryIntent:
    target_title: str


type MemoryWriteIntent = CreateMemoryIntent | ReviseMemoryIntent | DeleteMemoryIntent
