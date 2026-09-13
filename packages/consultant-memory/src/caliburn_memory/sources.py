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
