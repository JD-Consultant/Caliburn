"""Typed evidence boundary; no App, conversation store, or model."""

import pytest

from caliburn_memory.sources import EvidenceExchange, EvidenceExchangePage, EvidenceTextPage


@pytest.mark.parametrize("factory", [
    lambda: EvidenceExchangePage(
        order="oldest_to_newest", exchanges=({"not": "an exchange"},)),
    lambda: EvidenceTextPage(
        reference="conversation:fixed", segments=({"not": "a segment"},)),
])
def test_evidence_pages_reject_untyped_boundary_members(factory):
    """A malformed adapter result must not enter B1/B2 as a typed page."""
    with pytest.raises(ValueError):
        factory()


def test_an_exchange_rejects_untyped_message_metadata():
    with pytest.raises(ValueError):
        EvidenceExchange(
            source_reference="conversation:fixed",
            messages=({"message_id": "m1", "role": "user"},),
        )
