"""Document-bound Memory port over the one existing conversation source owner."""
from dataclasses import dataclass
from uuid import UUID

from caliburn_memory.sources import InvalidSourceReference, SourceReader

from .conversation_sources import ConversationSourceError, ConversationSourceService, SourceExcerpt


@dataclass(frozen=True, slots=True, repr=False)
class MemorySourceReader(SourceReader):
    """One document's Memory port over the single conversation source owner.

    `window_references` grants the completed-interview purpose as well. Only
    the background extraction/consolidation path needs it, so that B2 can hold
    a completed window as its published `processed_source`. C repair and the
    turn read tools keep the default and stay source-only.
    """
    service: ConversationSourceService
    document_id: str
    window_references: bool = False

    def __post_init__(self):
        if (not isinstance(self.service, ConversationSourceService)
                or type(self.window_references) is not bool):
            raise ConversationSourceError("source_not_available")
        try:
            if type(self.document_id) is not str or str(UUID(self.document_id)) != self.document_id:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    def validate_reference(self, reference: str) -> None:
        try:
            try:
                self.service.validate_reference(reference, self.document_id)
            except ConversationSourceError as error:
                if not (self.window_references and error.code == "invalid_ref"):
                    raise
                self.service.validate_window_reference(reference, self.document_id)
        except ConversationSourceError as error:
            if error.code == "invalid_ref":
                raise InvalidSourceReference("invalid_source_reference") from error
            raise

    def read(self, reference: str) -> SourceExcerpt:
        try:
            return self.service.read(reference, self.document_id)
        except ConversationSourceError as error:
            if error.code == "invalid_ref":
                raise InvalidSourceReference("invalid_source_reference") from error
            raise
