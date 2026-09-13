"""One in-flight B batch per document, decided from what is already durable.

B1's own admission only compares a new range with its previous range, so two
adjacent batches look legal to it even when the first was never published.
This guard asks the publication head instead, which is the one authority for
what has actually been handed over. It needs no new state of its own.
"""
import pytest

from caliburn_memory.extraction import ExtractionWorkflow
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.extraction_app import accepted
from jd_relational.background_admission import (
    BackgroundAdmissionError, require_handed_over,
)

from test_chat_history import native  # noqa: F401
from test_consolidation_app import b2, staged  # noqa: F401
from test_interview_window_source import interview  # noqa: F401


def test_a_document_that_has_never_extracted_admits_its_first_batch(b2):
    """Nothing has been handed over because nothing has been taken."""
    build, _, publication, _, _, _, _, _ = b2
    extraction = build().extraction
    untouched = ExtractionWorkflow(extraction.reader, extraction.artifacts,
                                   extraction.structured, accepted, InMemorySaver())
    assert publication.current() is None
    require_handed_over(untouched, publication)


def test_a_finished_batch_that_b2_has_not_published_blocks_the_next_one(b2):
    """The reproduced hazard: adjacent ranges hide an unpublished batch.

    Without this, B1 would accept the next range, overwrite the files B2 was
    going to take, and the cursor would then move past detail nothing ever
    consolidated. Scanning the Store for those orphans is not a remedy.
    """
    build, _, publication, _, extracted, _, _, _ = b2
    workflow = build()
    assert extracted["files"], "B1 finished a batch in the fixture"
    assert publication.current() is None
    with pytest.raises(BackgroundAdmissionError, match="^handover_incomplete$"):
        require_handed_over(workflow.extraction, publication)


def test_publishing_that_batch_admits_the_next_one(b2):
    """Only the published cursor reopens admission."""
    build, _, publication, batch, extracted, _, _, queue = b2
    workflow = build()
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    workflow.start()
    assert publication.current().processed_source == batch
    require_handed_over(workflow.extraction, publication)


def test_a_pending_extraction_blocks_admission_before_anything_else(b2, monkeypatch):
    """An unfinished B1 job is continued, never replaced by a new range."""
    build, _, publication, _, _, store, _, _ = b2
    workflow = build()
    snapshot = workflow.extraction.graph.get_state(workflow.extraction.config)
    monkeypatch.setattr(type(snapshot), "next", property(lambda self: ("save",)))
    with pytest.raises(BackgroundAdmissionError, match="^extraction_pending$"):
        require_handed_over(workflow.extraction, publication)
