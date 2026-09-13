"""Document-bound Memory port over the one existing conversation source owner."""
from dataclasses import dataclass
from uuid import UUID

from caliburn_memory.sources import InvalidSourceReference, SourceReader

from .conversation_sources import ConversationSourceError, ConversationSourceService, SourceExcerpt


@dataclass(frozen=True, slots=True, repr=False)
class MemorySourceReader(SourceReader):
    """One document's Memory port over the single conversation source owner.

    The extra purposes are granted one at a time, because they are not needed
    together: B2 holds a completed window as its published `processed_source`
    and must never store a disambiguation range there, while B1's extraction
    artifact validates both of its own references. C repair and the turn read
    tools keep the defaults and stay source-only.
    """
    service: ConversationSourceService
    document_id: str
    window_references: bool = False
    context_references: bool = False

    def __post_init__(self):
        if (not isinstance(self.service, ConversationSourceService)
                or type(self.window_references) is not bool
                or type(self.context_references) is not bool):
            raise ConversationSourceError("source_not_available")
        try:
            if type(self.document_id) is not str or str(UUID(self.document_id)) != self.document_id:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    def validate_reference(self, reference: str) -> None:
        try:
            granted = ([self.service.validate_window_reference] if self.window_references else []) \
                + ([self.service.validate_context_reference] if self.context_references else [])
            try:
                self.service.validate_reference(reference, self.document_id)
            except ConversationSourceError as error:
                if error.code != "invalid_ref" or not granted:
                    raise
                for index, accepts in enumerate(granted):
                    try:
                        accepts(reference, self.document_id)
                        break
                    except ConversationSourceError:
                        if index == len(granted) - 1:
                            raise
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

    def validate_pair(self, source_reference: str, context_reference: str) -> None:
        """The owner proves the two were planned together; no storage I/O.

        Only a reader granted the context purpose can hold a planned pair, and
        that is B1's artifact reader: there the owner has to prove the two were
        issued together, so a window cannot be recombined with a neighbouring
        window's prefix. A source-only reader holds no context purpose at all —
        both of its addresses are turn sources, already validated one by one,
        and it keeps the behaviour the read tools and C repair were verified on.
        """
        if not self.context_references:
            return
        try:
            self.service.validate_window_pair(source_reference, context_reference, self.document_id)
        except ConversationSourceError as error:
            if error.code == "invalid_ref":
                raise InvalidSourceReference("invalid_source_reference") from error
            raise
