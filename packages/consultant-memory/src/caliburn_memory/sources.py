"""Source owner port; this package stores no canonical conversation."""
from dataclasses import dataclass
from typing import Literal, Protocol


MAX_EVIDENCE_EXCHANGES = 50


class InvalidSourceReference(ValueError):
    """The caller may correct this address; never use for source storage I/O."""


@dataclass(frozen=True, slots=True)
class EvidenceMessage:
    message_id: str
    role: Literal["user", "assistant"]

    def __post_init__(self):
        if (type(self.message_id) is not str or not self.message_id.strip()
                or "\0" in self.message_id or self.role not in {"user", "assistant"}):
            raise ValueError("invalid_evidence_message")


@dataclass(frozen=True, slots=True)
class EvidenceExchange:
    source_reference: str
    messages: tuple[EvidenceMessage, ...]

    def __post_init__(self):
        if (type(self.messages) is not tuple
                or any(not isinstance(message, EvidenceMessage) for message in self.messages)):
            raise ValueError("invalid_evidence_exchange")
        roles = tuple(message.role for message in self.messages)
        if (type(self.source_reference) is not str or not self.source_reference.strip()
                or "\0" in self.source_reference
                or roles not in {("user",), ("assistant", "user")}):
            raise ValueError("invalid_evidence_exchange")


@dataclass(frozen=True, slots=True)
class EvidenceExchangePage:
    order: Literal["oldest_to_newest"]
    exchanges: tuple[EvidenceExchange, ...]
    next_offset: int | None = None

    def __post_init__(self):
        if (self.order != "oldest_to_newest" or type(self.exchanges) is not tuple
                or any(not isinstance(exchange, EvidenceExchange)
                       for exchange in self.exchanges)
                or (self.next_offset is not None
                    and (type(self.next_offset) is not int or self.next_offset <= 0))):
            raise ValueError("invalid_evidence_exchange_page")


@dataclass(frozen=True, slots=True)
class EvidenceSegment:
    message_id: str
    role: Literal["user", "assistant"]
    text: str
    text_offset: int

    def __post_init__(self):
        if (type(self.message_id) is not str or not self.message_id.strip()
                or "\0" in self.message_id or self.role not in {"user", "assistant"}
                or type(self.text) is not str or not self.text
                or type(self.text_offset) is not int or self.text_offset < 0):
            raise ValueError("invalid_evidence_segment")


@dataclass(frozen=True, slots=True)
class EvidenceTextPage:
    reference: str
    segments: tuple[EvidenceSegment, ...]
    next_offset: int | None = None

    def __post_init__(self):
        if (type(self.reference) is not str or not self.reference.strip()
                or "\0" in self.reference or type(self.segments) is not tuple
                or any(not isinstance(segment, EvidenceSegment)
                       for segment in self.segments)
                or (self.next_offset is not None
                    and (type(self.next_offset) is not int or self.next_offset <= 0))):
            raise ValueError("invalid_evidence_text_page")


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

    The owner still owns canonical order, page contents and admission.  A B1
    attempt may checkpoint the opaque numeric position returned by this port,
    but this package stores neither a second conversation nor a second source
    index. `read` remains the legacy window/context projection; exact turn
    evidence uses `read_source_page` and is never selected by model offset.
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

    def window_exchanges(self, reference: str) -> EvidenceExchangePage:
        """All evidence exchanges inside one fixed window, in canonical order."""
        ...

    def history_exchanges(self, through_reference: str, *, offset: int = 0,
                          limit: int = MAX_EVIDENCE_EXCHANGES) -> EvidenceExchangePage:
        """A bounded page of safe history fixed by `through_reference`."""
        ...

    def read_source_page(self, reference: str, offset: int = 0) -> EvidenceTextPage:
        """Read one exact source page; Runtime owns the next offset."""
        ...
