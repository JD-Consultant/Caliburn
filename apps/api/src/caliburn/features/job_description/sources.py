"""JD-owned direct evidence, distinct from source content and model-visible locators."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

from caliburn.features.job_description.models import ProfileField


class InvalidJdSourceError(ValueError):
    """Evidence must keep its precise JD owner and original source identity."""


class SourceTargetKind(StrEnum):
    PROFILE_FIELD = "profile_field"
    AREA = "area"
    TASK = "task"
    DETAIL = "detail"
    CAPABILITY = "capability"
    COLLABORATOR = "collaborator"
    CONDITION = "condition"
    TASK_CAPABILITY = "task_capability"


@dataclass(frozen=True, slots=True)
class JdSourceTarget:
    kind: SourceTargetKind
    item_id: UUID | None = None
    field: ProfileField | None = None
    task_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.kind == SourceTargetKind.PROFILE_FIELD:
            valid = self.field is not None and self.item_id is None and self.task_id is None
        else:
            needs_task = self.kind in {SourceTargetKind.DETAIL, SourceTargetKind.TASK_CAPABILITY}
            valid = (
                self.field is None
                and self.item_id is not None
                and (self.task_id is not None) == needs_task
            )
        if not valid:
            raise InvalidJdSourceError("The source target has missing or unrelated identity fields")


@dataclass(frozen=True, slots=True)
class InterviewSource:
    # Pending current_input retains this identity when the same text becomes formal.
    source_id: UUID


class MemorySourceLayer(StrEnum):
    WORK_SITUATION = "work_situation"
    WORK_UNDERSTANDING = "work_understanding"


@dataclass(frozen=True, slots=True)
class MemorySource:
    layer: MemorySourceLayer
    snapshot_id: UUID
    object_id: UUID
    revision_id: UUID


type JdSource = InterviewSource | MemorySource
type SourceTargetContents = Mapping[JdSourceTarget, tuple[str | None, ...]]


@dataclass(frozen=True, slots=True)
class JdSourceReference:
    citation_id: UUID
    target: JdSourceTarget
    source: JdSource
    needs_review: bool = False
    # None is only an unpersisted addition/alignment; storage binds the new JD revision.
    reviewed_revision_id: UUID | None = None


def same_source_identity(left: JdSource, right: JdSource) -> bool:
    match left, right:
        case InterviewSource(), InterviewSource():
            return left.source_id == right.source_id
        case MemorySource(), MemorySource():
            return left.layer == right.layer and left.object_id == right.object_id
        case _:
            return False


def carry_source_references(
    references: tuple[JdSourceReference, ...],
    before: SourceTargetContents,
    after: SourceTargetContents,
) -> tuple[JdSourceReference, ...]:
    """Retain evidence on surviving targets without silently confirming changed text."""
    carried = []
    for reference in references:
        if reference.target not in before:
            raise InvalidJdSourceError("Existing evidence has no owner in its original JD")
        if reference.target in after:
            carried.append(
                replace(
                    reference,
                    needs_review=(
                        reference.needs_review
                        or before[reference.target] != after[reference.target]
                    ),
                )
            )
    return tuple(carried)


def add_source_reference(
    references: tuple[JdSourceReference, ...], new: JdSourceReference
) -> tuple[JdSourceReference, ...]:
    """Adding the same source again cannot refresh its revision or review status."""
    if any(
        reference.citation_id == new.citation_id and reference != new for reference in references
    ):
        raise InvalidJdSourceError("A citation identity cannot select different evidence")
    for reference in references:
        if reference.target == new.target and same_source_identity(reference.source, new.source):
            return references
    return (*references, new)


def align_source_reference(reference: JdSourceReference, source: JdSource) -> JdSourceReference:
    """The workflow must first resolve a permitted current source for the same identity."""
    if not same_source_identity(reference.source, source):
        raise InvalidJdSourceError("Alignment cannot replace the original source identity")
    if reference.source == source and not reference.needs_review:
        return reference
    return replace(reference, source=source, needs_review=False, reviewed_revision_id=None)


@dataclass(frozen=True, slots=True)
class AddJdSource:
    source: JdSource


@dataclass(frozen=True, slots=True)
class RemoveJdSource:
    citation_id: UUID


@dataclass(frozen=True, slots=True)
class AlignJdSource:
    citation_id: UUID
    source: JdSource


type JdSourceChange = AddJdSource | RemoveJdSource | AlignJdSource


@dataclass(frozen=True, slots=True)
class ReviseJdSources:
    command_id: UUID
    expected_revision_id: UUID
    target: JdSourceTarget
    changes: tuple[JdSourceChange, ...]

    def __post_init__(self) -> None:
        validate_source_changes(self.changes)


def validate_source_changes(changes: tuple[JdSourceChange, ...]) -> None:
    if not changes:
        raise InvalidJdSourceError("Choose at least one source change")
    changed: set[UUID] = set()
    added: list[JdSource] = []
    for change in changes:
        if isinstance(change, AddJdSource):
            if any(same_source_identity(change.source, source) for source in added):
                raise InvalidJdSourceError("Add each source only once")
            added.append(change.source)
        else:
            if change.citation_id in changed:
                raise InvalidJdSourceError("Change each existing citation only once")
            changed.add(change.citation_id)
