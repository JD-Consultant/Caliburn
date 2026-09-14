"""Read back the saved interview behind one JD source marker.

This projects what the one source owner already holds; it opens no second
store, keeps no cursor, parses no reference and never writes. A marker on the
JD says which interviews a piece of content rests on, and this is how the
employee reads those words again.

An assistant message is the consultant's own wording at the time. It is
returned with its role so the page can say so, and is never presented as
something the employee stated.
"""

from .conversation_sources import ConversationSourceError
from .generated.reads import SourceReadInput, SourceReadPage
from .reads import ReadError


class SourceReadService:
    """One owner, read only. Codes stay inside the shared read vocabulary."""

    def __init__(self, sources):
        self.sources = sources

    def read(self, document_id: str, arguments: dict) -> dict:
        try:
            request = SourceReadInput.model_validate(arguments, strict=True)
        except Exception:
            raise ReadError("invalid_input") from None
        try:
            excerpt = self.sources.read(request.source_ref, document_id)
        except ConversationSourceError as error:
            # A source this document cannot claim is a bad reference. Anything
            # else the owner reports is `source_not_available`, which covers
            # BOTH a run that is genuinely gone and any failure while reading
            # -- the owner normalises every other code and catches every other
            # exception. Since the two cannot be told apart here, this must not
            # claim the interview is missing and invite the employee onward; an
            # unconfirmed read is reported as unconfirmed, and says stop.
            raise ReadError("invalid_ref" if error.code == "invalid_ref"
                            else "read_failed") from None
        except Exception:
            # Defensive: the owner raises nothing else, but a driver exception
            # must never carry a connection string to the employee.
            raise ReadError("read_failed") from None
        return SourceReadPage(
            format_version=2, view="source_read", access="history",
            source_ref=excerpt.source_ref,
            messages=[{"message_id": message.message_id, "role": message.role,
                       "text": message.text} for message in excerpt.messages],
        ).model_dump(mode="json")
