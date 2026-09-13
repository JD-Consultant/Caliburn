"""Source owner port; this package stores no canonical conversation."""
from typing import Protocol


class SourceReader(Protocol):
    document_id: str

    def validate_reference(self, reference: str) -> None:
        """Validate address shape and document scope only, without storage I/O."""
        ...

    def read(self, reference: str) -> object:
        """Read the exact saved source or raise; never substitute latest content."""
        ...
