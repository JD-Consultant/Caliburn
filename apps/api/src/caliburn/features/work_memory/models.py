"""Internal Memory values and edit intent, independent of storage and model wire."""

from dataclasses import dataclass
from uuid import UUID


class InvalidMemoryChangeError(ValueError):
    """Memory content or an explicit change violates a domain invariant."""


class MemoryTargetNotFoundError(LookupError):
    """No exact title match exists in the caller's visible layer map."""


class MemoryMapInconsistencyError(RuntimeError):
    """The supplied layer map contains multiple entries for the selected title."""


def validate_memory_text(text: str) -> None:
    """Reject blank or unstorable content without changing the supplied string."""
    if not text.strip() or "\x00" in text:
        raise InvalidMemoryChangeError("Memory text must be nonblank without NUL")


@dataclass(frozen=True, slots=True)
class MemoryContent:
    """The three required content fields; references are separate identity sets."""

    title: str
    description: str
    body: str

    def __post_init__(self) -> None:
        for text in (self.title, self.description, self.body):
            validate_memory_text(text)


@dataclass(frozen=True, slots=True)
class MemoryContentChanges:
    """Internal intent: None is omitted; body is the result of a controlled patch.

    This is not a model-wire schema or a whole-body replacement tool.
    """

    title: str | None = None
    description: str | None = None
    body: str | None = None

    def __post_init__(self) -> None:
        supplied = tuple(
            text for text in (self.title, self.description, self.body) if text is not None
        )
        if not supplied:
            raise InvalidMemoryChangeError("Supply at least one content field")
        for text in supplied:
            validate_memory_text(text)


@dataclass(frozen=True, slots=True)
class ReferenceChanges:
    """Internal relationship changes after source choices resolve to stable IDs."""

    add: frozenset[UUID] = frozenset()
    remove: frozenset[UUID] = frozenset()

    def __post_init__(self) -> None:
        if not self.add and not self.remove:
            raise InvalidMemoryChangeError("Supply at least one reference to add or remove")
        if self.add & self.remove:
            raise InvalidMemoryChangeError("A reference cannot be both added and removed")


@dataclass(frozen=True, slots=True)
class MemoryMapEntry:
    """Internal title-to-identity projection for one caller-selected visible layer."""

    object_id: UUID
    title: str
    description: str

    def __post_init__(self) -> None:
        validate_memory_text(self.title)
        validate_memory_text(self.description)
