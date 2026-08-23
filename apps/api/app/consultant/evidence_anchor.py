"""Deterministic exact-quote resolution against immutable employee sources."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

from app.consultant.state import QuoteAnchor, SourceValidity
from app.consultant.workspace_resources import WorkspaceCatalog, WorkspaceEvidenceReference


VerbatimText = Annotated[str, StringConstraints(min_length=1)]


class EvidenceAnchorError(ValueError):
    """A model-authored evidence reference cannot be resolved safely."""


class ExactQuoteMatch(BaseModel):
    """A raw-text match before a source ID is attached."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: VerbatimText


# Descriptive aliases make the small resolver result convenient to consume
# without creating another durable authority model.
QuoteMatch = ExactQuoteMatch
ResolvedQuote = ExactQuoteMatch


def resolve_exact_quote(
    raw: str,
    quote: str,
    occurrence: int | None = None,
) -> ExactQuoteMatch:
    """Resolve an exact Python-code-point substring in raw source text.

    No trimming, Unicode normalization, line-gutter removal, or fuzzy matching
    is allowed here.  Occurrences are 1-based and count non-overlapping exact
    matches from left to right.
    """

    if not isinstance(raw, str) or not isinstance(quote, str):
        raise EvidenceAnchorError("raw source and quote must be strings")
    if not quote:
        raise EvidenceAnchorError("quote does not occur")
    if occurrence is not None and (
        isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 1
    ):
        raise EvidenceAnchorError("occurrence must be a positive 1-based integer")

    matches: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = raw.find(quote, cursor)
        if start < 0:
            break
        end = start + len(quote)
        matches.append((start, end))
        cursor = start + 1

    if not matches:
        raise EvidenceAnchorError("quote does not occur")
    if occurrence is None and len(matches) > 1:
        raise EvidenceAnchorError("quote occurs multiple times; occurrence is required")
    if occurrence is None:
        selected = matches[0]
    else:
        try:
            selected = matches[occurrence - 1]
        except IndexError as error:
            raise EvidenceAnchorError("quote occurrence is out of range") from error
    return ExactQuoteMatch(start=selected[0], end=selected[1], quote=quote)


def resolve_evidence_reference(
    reference: WorkspaceEvidenceReference,
    catalog: WorkspaceCatalog,
) -> QuoteAnchor:
    """Resolve a local model reference to the existing durable ``QuoteAnchor``.

    The reference and catalog are deliberately strict application-boundary
    types; provider wire models must be converted before resolution.
    """

    if not isinstance(catalog, WorkspaceCatalog):
        raise EvidenceAnchorError("evidence resolution requires a workspace catalog")
    if not isinstance(reference, WorkspaceEvidenceReference):
        raise EvidenceAnchorError("invalid evidence reference")

    try:
        source = catalog.source_for_handle(reference.source_handle)
    except KeyError as error:
        raise EvidenceAnchorError("unknown source handle") from error
    if source.document_id != catalog.document_id:
        raise EvidenceAnchorError("source belongs to a different document")
    if source.validity is SourceValidity.SUPERSEDED:
        raise EvidenceAnchorError("source is superseded")

    match = resolve_exact_quote(
        raw=source.text,
        quote=reference.quote,
        occurrence=reference.occurrence,
    )
    return QuoteAnchor(
        source_id=source.source_id,
        start=match.start,
        end=match.end,
        quote=match.quote,
    )
