"""Whether a document may admit a new background batch, from durable facts only.

This decides nothing about scheduling and owns no state. B1 progress belongs to
the Saver, published understanding and the one processed-source cursor belong
to the publication store, and this reads both rather than keeping a third copy.

B1's own `require_new_source_after` compares a candidate range with B1's
previous range. That is the right rule for B1, but it cannot see whether that
previous range was ever handed over: two adjacent batches look legal even when
the first was never published. Starting the second overwrites the files B2 was
going to take, and the cursor then moves past detail nothing consolidated.
Scanning the Store for those orphans is explicitly not a remedy, so the check
belongs before the batch is started, here.
"""

from caliburn_memory import PublicationStore
from caliburn_memory.extraction import ExtractionWorkflow


class BackgroundAdmissionError(ValueError):
    """A bounded, safe reason a new batch may not start right now."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require_handed_over(extraction: ExtractionWorkflow, publication: PublicationStore) -> None:
    """Admit a new batch only when the last one reached the published cursor.

    An unfinished B1 job is continued rather than replaced, so it blocks first
    and on its own terms. Otherwise the last range B1 accepted must be exactly
    what publication now names as processed: anything else means a batch is
    still in flight between the two stages.
    """
    if not isinstance(extraction, ExtractionWorkflow) or not isinstance(publication, PublicationStore):
        raise BackgroundAdmissionError("invalid_admission_input")
    snapshot = extraction.graph.get_state(extraction.config)
    if snapshot.next:
        raise BackgroundAdmissionError("extraction_pending")
    previous = snapshot.values.get("source_reference") if snapshot.values else None
    if previous is None:
        return
    head = publication.current()
    if head is None or head.processed_source != previous:
        raise BackgroundAdmissionError("handover_incomplete")
