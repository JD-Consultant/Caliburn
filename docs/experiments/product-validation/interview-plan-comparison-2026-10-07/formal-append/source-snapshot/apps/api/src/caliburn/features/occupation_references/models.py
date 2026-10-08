"""Reference choices and explicit work exclusions, without answer or Memory copies."""

from dataclasses import dataclass, replace
from uuid import UUID


class ReferenceStateError(ValueError):
    """Invalid or unavailable reference candidate state."""


class ReferenceStateConflictError(ReferenceStateError):
    """An original operation identity was reused with different intent."""


class StaleReferenceStateError(ReferenceStateError):
    """The candidate revision or generation no longer permits this operation."""


@dataclass(frozen=True, slots=True)
class OccupationReferenceState:
    selected_reference_ids: tuple[str, ...] | None = None
    excluded_work: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.selected_reference_ids is not None:
            if not isinstance(self.selected_reference_ids, tuple):
                raise ReferenceStateError("Reference selections must be an immutable tuple")
            for reference in self.selected_reference_ids:
                _require_text(reference, "Reference identity")
        _require_excluded_work(self.excluded_work)
        if len(set(self.excluded_work)) != len(self.excluded_work):
            raise ReferenceStateError("Each exact excluded work description must be unique")


@dataclass(frozen=True, slots=True)
class ReferenceStatePosition:
    execution_id: UUID
    generation_id: UUID
    revision_id: UUID
    state: OccupationReferenceState


def select_references(
    state: OccupationReferenceState, references: tuple[str, ...]
) -> OccupationReferenceState:
    return replace(state, selected_reference_ids=tuple(dict.fromkeys(references)))


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ReferenceStateError(f"{label} must contain non-whitespace text without NUL")


def _require_excluded_work(values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise ReferenceStateError("Excluded work must be an immutable tuple")
    for value in values:
        _require_text(value, "Excluded work")


def update_excluded_work(
    state: OccupationReferenceState, add: tuple[str, ...], remove: tuple[str, ...]
) -> OccupationReferenceState:
    """Apply exact list edits; determining non-responsibility belongs to the caller."""
    _require_excluded_work(add)
    _require_excluded_work(remove)
    if not add and not remove:
        raise ReferenceStateError("An excluded work update must add or remove at least one item")
    removed = set(remove)
    if removed.intersection(add):
        raise ReferenceStateError("The same excluded work cannot be added and removed together")
    if removed.difference(state.excluded_work):
        raise ReferenceStateError("Every removed work description must match an existing exclusion")
    retained = tuple(item for item in state.excluded_work if item not in removed)
    return replace(state, excluded_work=tuple(dict.fromkeys((*retained, *add))))
