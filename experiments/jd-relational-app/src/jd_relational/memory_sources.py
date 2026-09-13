"""Document-bound Memory port over the one existing conversation source owner."""
from dataclasses import dataclass
from uuid import UUID

from caliburn_memory.sources import SourceReader

from .conversation_sources import ConversationSourceError, ConversationSourceService, SourceExcerpt


@dataclass(frozen=True, slots=True, repr=False)
class MemorySourceReader(SourceReader):
    service: ConversationSourceService
    document_id: str

    def __post_init__(self):
        if not isinstance(self.service, ConversationSourceService):
            raise ConversationSourceError("source_not_available")
        try:
            if type(self.document_id) is not str or str(UUID(self.document_id)) != self.document_id:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    def validate_reference(self, reference: str) -> None:
        self.service.validate_reference(reference, self.document_id)

    def read(self, reference: str) -> SourceExcerpt:
        return self.service.read(reference, self.document_id)
