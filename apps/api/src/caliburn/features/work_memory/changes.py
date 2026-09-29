"""Pure Memory edits and exact title selection, without I/O, revisions or model wire."""

from uuid import UUID

from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemoryContentChanges,
    MemoryMapEntry,
    MemoryMapInconsistencyError,
    MemoryTargetNotFoundError,
    ReferenceChanges,
    validate_memory_text,
)


def apply_content_changes(current: MemoryContent, changes: MemoryContentChanges) -> MemoryContent:
    """Compute content after an edit; body must already be the controlled patch result.

    None preserves a field in this internal value, not in the model-wire contract.
    This does not apply V4A, save content or allocate a revision.
    """
    return MemoryContent(
        title=current.title if changes.title is None else changes.title,
        description=current.description if changes.description is None else changes.description,
        body=current.body if changes.body is None else changes.body,
    )


def apply_reference_changes(
    current: frozenset[UUID], changes: ReferenceChanges, allowed: frozenset[UUID]
) -> frozenset[UUID]:
    """Compute relationship membership; allowed IDs come from the source/scope owner.

    Only additions require membership in allowed; removals must exist in current.
    No database eligibility check, source deletion or revision alignment occurs here.
    An empty result is valid and unmentioned relationships remain untouched.
    """
    if not changes.add <= allowed:
        raise InvalidMemoryChangeError("Added references must belong to the allowed source set")
    if not changes.remove <= current:
        raise InvalidMemoryChangeError(
            "Removed references must belong to the current reference set"
        )
    return (current - changes.remove) | changes.add


def resolve_title(entries: tuple[MemoryMapEntry, ...], target_title: str) -> UUID:
    """Select a new request's exact title within the supplied visible layer map.

    Existing relationships and replayed operations retain their already-bound IDs.
    Duplicate matches are a map inconsistency, never a first-match selection.
    """
    validate_memory_text(target_title)
    matches = tuple(entry.object_id for entry in entries if entry.title == target_title)
    if not matches:
        raise MemoryTargetNotFoundError("The selected title is absent from the supplied layer map")
    if len(matches) > 1:
        raise MemoryMapInconsistencyError(
            "The selected title has multiple entries in the layer map"
        )
    return matches[0]


def require_unique_title(
    target_id: UUID, content: MemoryContent, entries: tuple[MemoryMapEntry, ...]
) -> None:
    """Check exact title uniqueness excluding self in the caller's single-layer map.

    The owner supplies the current scope and protects it against concurrent writes.
    This check neither reads another layer nor guarantees uniqueness at commit time.
    """
    if any(entry.object_id != target_id and entry.title == content.title for entry in entries):
        raise InvalidMemoryChangeError(
            "Another object in the supplied layer already has this title"
        )
