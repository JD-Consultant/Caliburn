"""Who holds which background fact, measured rather than described.

This began as the evidence for ADR0076: it showed on real PostgreSQL that no
existing owner held the admitted target, the admission status, a blocked
reason or a recovery count. The decision was taken and the row now exists, so
these tests assert the settled split instead of the old absence -- the batch
stays with the workflows, published progress stays with publication, and the
four remaining facts live in exactly one place and survive reopening.

Real PostgresSaver, real PostgresStore, real publication and admission tables;
zero provider.
"""
import os
from uuid import uuid4

from langchain_core.messages import AIMessage
import pytest

from jd_relational.background_admission import BackgroundAdmissions

from test_background_admission_postgres import catalogued
from test_consolidation_app import staged
from test_consolidation_postgres import opened_b2, stages
from test_extraction_postgres import interviewed
from test_interview_window_source import settled
from test_storage_postgres import engine  # noqa: F401


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")

# The six responsibilities the verified BackgroundRow carried, per adoption
# mapping section 3.3 and ADR0076.
ADMISSION_FACTS = ("document_id", "status", "target_reference", "source_reference",
                   "error_code", "recovery_count")


def workflow_state(b1, b2_workflow, publication):
    """Every fact the B workflows and publication durably hold themselves."""
    return {
        "b1_state": set(b1.graph.get_state(b1.config).values),
        "b2_state": set(b2_workflow.graph.get_state(b2_workflow.config).values),
        "publication_head": {"revision", "memory", "processed_source"}
                            if publication.current() is not None else set(),
    }


def test_each_background_fact_has_exactly_one_owner(engine):
    """The workflows keep their batch; the admission row keeps the rest.

    Neither copies the other. In particular the published cursor stays with
    publication alone, so nothing here becomes a second progress record.
    """
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    admissions = BackgroundAdmissions(engine)
    with opened_b2(dataset, document) as (native, windows, store, saver, _, _, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            admissions.admit(document, target_reference=target, extraction=b1,
                             publication=publication)
            batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
            admissions.dispatch(document, source_reference=batch)
            extracted = b1.start(batch)
            queue.extend(staged(extracted["files"][0]["summary_path"]))
            workflow = b2()
            workflow.start()

            held = workflow_state(b1, workflow, publication)
            elsewhere = set().union(*held.values())
            row = admissions.read(document)
            assert {"target_reference", "status", "error_code", "recovery_count"} & elsewhere == set()
            assert all(hasattr(row, fact) for fact in ADMISSION_FACTS)
            # The batch is the one fact both sides legitimately name, because
            # the row says what was dispatched and the workflow says what it ran.
            assert row.source_reference == batch
            assert b1.graph.get_state(b1.config).values["source_reference"] == batch
            assert "processed_source" not in {"target_reference", "source_reference"}
            assert publication.current().processed_source == batch


def test_the_durable_target_keeps_the_tail_reachable_while_speech_continues(engine):
    """Later turns would have widened a rederived range; the stored one holds.

    This is the behaviour the row exists for: the tail of admitted work is
    still reachable after the employee has gone on talking, and it is the same
    tail that was admitted rather than a larger one.
    """
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    admissions = BackgroundAdmissions(engine)
    with opened_b2(dataset, document) as (native, windows, store, saver, _, _, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            admissions.admit(document, target_reference=target, extraction=b1,
                             publication=publication)
            batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
            admissions.dispatch(document, source_reference=batch)
            extracted = b1.start(batch)
            queue.extend(staged(extracted["files"][0]["summary_path"]))
            b2().start()
            admissions.advance(document)
        for index in range(2):
            settled(native, [AIMessage(id=f"later-a{index}", content="回" * 1250)],
                    text="問" * 1250)
        published = publication.current().processed_source
        stored = BackgroundAdmissions(engine).read(document).target_reference
        assert stored == target, "reopening reads back the admitted target, not a new one"
        widened = windows.capture_window(document, **windows.unprocessed_source(document, published))
        assert widened != target, "rederiving from the head would have grown the range"
        tail = windows.plan_saved_batch(target, document, after_reference=published)
        assert tail["covers_whole_range"] is True
        assert tail["source_reference"] != windows.plan_saved_batch(
            widened, document, after_reference=published)["source_reference"]
