"""One entry point for a document's background work, on real PostgreSQL.

Waking is cheap and repeatable; what may actually run is decided by durable
state, never by how often something knocked. A new target needs a real saved
consolidation request -- there is no word-count fallback -- and work already
admitted continues in its own order rather than being restarted.

Real Saver, Store, publication and admission tables, real SDK answered in
process. Nothing here loops or schedules: each wake admits at most one bounded
batch and returns.
"""
import os
from uuid import uuid4

from langchain_core.messages import AIMessage
import pytest

from jd_relational.background_admission import BackgroundAdmissions
from jd_relational.background_dispatch import BackgroundDispatcher

from test_background_admission_postgres import catalogued
from test_consolidation_app import staged
from test_consolidation_postgres import opened_b2, stages
from test_extraction_postgres import interviewed
from test_interview_window_source import asked, settled
from test_manual_runtime import Checkpoints, Storage  # noqa: F401
from test_storage_postgres import engine  # noqa: F401


pytestmark = [
    pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                       reason="explicit isolated PostgreSQL test opt-in required"),
    pytest.mark.skip(reason="historical two-stage contract; superseded by layered background tests"),
]


def requested(native, index):
    """One settled turn that really asked for background consolidation."""
    return settled(native, [*asked(f"req{index}"),
                            AIMessage(id=f"req-a{index}", content="回" * 1250)],
                   text="問" * 1250)


class DirectWorker:
    """Runs an admitted batch inline: this file is about deciding, not threading.

    The host's own bounded worker and its shutdown drain are covered by
    `test_background_host_postgres.py`; using it here would only add threads to
    assertions about durable state.
    """

    def admit_background(self, document_id, work):
        from concurrent.futures import Future
        future = Future()
        future.set_result(work())
        return future


@pytest.fixture
def dispatch(engine):
    """A catalogued document with real B resources and one dispatcher over them."""
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    admissions = BackgroundAdmissions(engine)
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            consolidation = b2()
            dispatcher = BackgroundDispatcher(DirectWorker(), admissions, windows, document,
                                              extraction=b1, consolidation=consolidation,
                                              publication=publication, max_windows=2)
            yield dispatcher, admissions, document, native, windows, b1, consolidation, \
                publication, sent, queue


def test_a_wakeup_without_a_saved_request_starts_nothing(dispatch):
    """Quiet turns are not a reason to consolidate, however often we wake."""
    dispatcher, admissions, document, native, *_ , publication, sent, _ = dispatch
    interviewed(native, 3)
    assert dispatcher.wake() == "wait"
    assert dispatcher.wake() == "wait"
    assert admissions.read(document).status == "idle"
    assert sent == [] and publication.current() is None


def test_a_saved_request_admits_a_target_and_runs_exactly_one_batch(dispatch):
    """The request decides when to start; the target then bounds the work."""
    dispatcher, admissions, document, native, windows, b1, _, publication, sent, _ = dispatch
    interviewed(native, 3)
    requested(native, 1)
    assert dispatcher.wake() == "next_batch"
    row = admissions.read(document)
    assert row.status == "running" and row.target_reference and row.source_reference
    assert b1.graph.get_state(b1.config).values["source_reference"] == row.source_reference
    assert len(sent) == 2, "one bounded batch of two windows, not the whole target"
    assert publication.current() is None, "B1 never publishes"


def test_the_next_wakeup_hands_the_finished_batch_to_b2_and_publishes(dispatch):
    """B1 done, B2 not started: the handover is what the next wake does."""
    dispatcher, admissions, document, native, windows, b1, _, publication, sent, queue = dispatch
    interviewed(native, 3)
    requested(native, 1)
    dispatcher.wake()
    handed_over = admissions.read(document)
    files = b1.graph.get_state(b1.config).values["files"]
    queue.extend(staged(files[0]["summary_path"], body="背景整理出的理解。"))
    assert dispatcher.wake() == "consolidate"
    head = publication.current()
    assert head.revision == 1 and head.processed_source == handed_over.source_reference
    # The published batch is done with, so the row keeps only its target.
    after = admissions.read(document)
    assert after.status == "queued" and after.source_reference is None
    assert after.target_reference == handed_over.target_reference


def test_a_wakeup_after_publication_takes_the_tail_without_a_new_request(dispatch):
    """The published cursor moves the work on; no second notification needed."""
    dispatcher, admissions, document, native, windows, b1, _, publication, sent, queue = dispatch
    interviewed(native, 5)
    requested(native, 1)
    dispatcher.wake()
    queue.extend(staged(b1.graph.get_state(b1.config).values["files"][0]["summary_path"]))
    dispatcher.wake()
    target = admissions.read(document).target_reference
    assert dispatcher.wake() == "next_batch"
    row = admissions.read(document)
    assert row.target_reference == target, "the same admitted target, not a new one"
    assert row.source_reference != publication.current().processed_source


def test_a_wakeup_on_blocked_work_changes_nothing(dispatch):
    """A named block is a decision, not something a wakeup may override."""
    dispatcher, admissions, document, native, windows, b1, _, publication, sent, _ = dispatch
    interviewed(native, 3)
    requested(native, 1)
    dispatcher.wake()
    before = admissions.block(document, error_code="source_unavailable")
    assert dispatcher.wake() == "blocked"
    assert admissions.read(document) == before


class PendingWorker(DirectWorker):
    """Admits the batch but leaves its Future running, as a real worker would."""

    def __init__(self):
        self.admitted = []

    def admit_background(self, document_id, work):
        from concurrent.futures import Future
        self.admitted.append(work)
        return Future()


def test_waking_again_while_a_batch_runs_is_not_a_second_batch(dispatch, engine):
    """Repeated wakeups are cheap and idempotent, not repeated work."""
    dispatcher, admissions, document, native, windows, b1, consolidation, publication, sent, _ = dispatch
    interviewed(native, 3)
    requested(native, 1)
    worker = PendingWorker()
    busy = BackgroundDispatcher(worker, admissions, windows, document, extraction=b1,
                                consolidation=consolidation, publication=publication,
                                max_windows=2)
    assert busy.wake() == "next_batch"
    admitted = admissions.read(document)
    assert admitted.status == "queued" and admitted.target_reference
    assert admitted.source_reference is None, "the batch is cut by the work, not by waking"
    for _ in range(3):
        assert busy.wake() == "busy"
    assert len(worker.admitted) == 1 and sent == []
    assert admissions.read(document) == admitted, "the wakeups changed nothing"
