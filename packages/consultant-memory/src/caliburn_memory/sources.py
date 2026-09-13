"""Source owner port; this package stores no canonical conversation."""
from typing import Protocol


class InvalidSourceReference(ValueError):
    """The caller may correct this address; never use for source storage I/O."""


class SourceReader(Protocol):
    document_id: str

    def validate_reference(self, reference: str) -> None:
        """Validate without I/O; invalid shape/scope raises InvalidSourceReference."""
        ...

    def read(self, reference: str) -> object:
        """Read exact source; invalid address uses InvalidSourceReference, I/O does not."""
        ...

    def validate_pair(self, source_reference: str, context_reference: str) -> None:
        """Prove the context was issued for that source; no storage I/O.

        Only an extraction artifact carries a pair, so a reader that grants no
        context purpose refuses by default rather than accepting an unproven
        combination: such an artifact could not have been saved through it.
        """
        raise InvalidSourceReference("invalid_source_reference")


class ExtractionSourceReader(SourceReader, Protocol):
    """What B1 needs from the source owner, and nothing more.

    The owner still owns planning, paging and admission; this package neither
    stores conversation nor keeps a second cursor. `read` here is the paged
    projection B1 walks to its final page, so it extends the single-shot read
    above rather than replacing it.
    """

    def extraction_windows(self, reference: str, *, max_chars: int, context_chars: int) -> list[dict]:
        """Plan whole completed turns as {source_reference, context_reference} pairs."""
        ...

    def read(self, reference: str, offset: int = 0) -> dict:
        """One page: segments, turns, omitted_content_types, next_offset."""
        ...

    def validate_saved_window(self, source_reference: str, context_reference: str | None,
                              *, max_chars: int, context_chars: int) -> None:
        """Re-check an already planned pair; never widen or replan it."""
        ...

    def require_new_source_after(self, reference: str, previous: str) -> None:
        """Admit a range only after the previous one, by saved conversation order."""
        ...
