"""The admission row on real PostgreSQL: what it holds, and what it decides.

Real table, real constraints, real Saver and publication. The row records what
was admitted; every decision still reads the Saver's checkpoints and the
publication head, so a stale row never causes a second consolidation and a
`running` row never stands in as proof that the model ran.

Run `scripts/init_test_database.py` (migration 20260914_0002) first. These
tests never create, clear or drop a table.
"""
from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.background_admission import (
    Admission, BackgroundAdmissionError, BackgroundAdmissions, reconcile,
)
from jd_relational.storage import schema as db

from test_consolidation_app import staged
from test_consolidation_postgres import opened_b2, stages
from test_extraction_postgres import interviewed
from test_storage_postgres import engine  # noqa: F401


pytestmark = [
    pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                       reason="explicit isolated PostgreSQL test opt-in required"),
    pytest.mark.skip(reason="historical two-stage contract; superseded by layered background tests"),
]


def catalogued(engine, document_id):
    """The admission row points at a real document, so create one to point at."""
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(db.jd_document.insert().values(
            id=document_id, title="合成背景准入", metadata_version=1,
            create_request_key=str(uuid4()), create_payload_digest="b" * 64,
            created_at=now, updated_at=now))
    return document_id


def archive(engine, document_id):
    with engine.begin() as connection:
        connection.execute(db.jd_document.update().where(
            db.jd_document.c.id == document_id).values(archived=True))


@pytest.fixture
def admitted(engine):
    """One catalogued document, its resources, and an admission store on them."""
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    admissions = BackgroundAdmissions(engine)
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            yield (admissions, document, windows, target, b1, b2, publication, sent, queue)


def test_an_absent_row_reads_as_idle_rather_than_as_missing(engine):
    """No admission is a real answer, not an error the caller has to handle."""
    document = catalogued(engine, str(uuid4()))
    assert BackgroundAdmissions(engine).read(document) == Admission(document)


@pytest.mark.parametrize("bad", [
    Admission("x", status="queued"),
    Admission("x", status="running", target_reference="t"),
    Admission("x", status="blocked"),
    Admission("x", status="idle", target_reference="t"),
])
def test_the_table_refuses_a_state_that_does_not_describe_real_work(engine, bad):
    """queued needs a target, running needs its batch, blocked needs a reason."""
    document = catalogued(engine, str(uuid4()))
    with pytest.raises(sa.exc.IntegrityError):
        BackgroundAdmissions(engine).save(
            Admission(document, bad.status, bad.target_reference,
                      bad.source_reference, bad.error_code))


def test_a_committed_batch_that_never_started_is_asked_to_start(admitted):
    """The batch is recorded before B1 is invoked, so a crash between the two
    is visible as work to begin, not as work already done."""
    admissions, document, windows, target, b1, b2, publication, sent, _ = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    row = admissions.dispatch(document, source_reference=batch)
    assert row.status == "running" and sent == []
    assert reconcile(admissions.read(document), extraction=b1, consolidation=b2(),
                     publication=publication, windows=windows, document_id=document) == "start_batch"


def test_a_finished_batch_that_b2_has_not_taken_is_asked_to_consolidate(admitted):
    """B1 done, B2 not started: the handover is what is owed."""
    admissions, document, windows, target, b1, b2, publication, sent, _ = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    admissions.dispatch(document, source_reference=batch)
    b1.start(batch)
    assert publication.current() is None
    assert reconcile(admissions.read(document), extraction=b1, consolidation=b2(),
                     publication=publication, windows=windows, document_id=document) == "consolidate"


def test_a_published_batch_is_recognised_even_when_the_row_is_stale(admitted):
    """Publication succeeded but the row still says running. Never redo it.

    The head is the authority on what was handed over, so reconciliation moves
    on to the target's tail instead of consolidating the same batch twice.
    """
    admissions, document, windows, target, b1, b2, publication, sent, queue = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    admissions.dispatch(document, source_reference=batch)
    extracted = b1.start(batch)
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    b2().start()
    stale = admissions.read(document)
    assert stale.status == "running" and stale.source_reference == batch
    assert publication.current().processed_source == batch
    assert reconcile(stale, extraction=b1, consolidation=b2(), publication=publication,
                     windows=windows, document_id=document) == "next_batch"


def test_later_interview_turns_never_widen_the_admitted_target(admitted, engine):
    """The target is what was admitted, whatever the employee says afterwards."""
    admissions, document, windows, target, b1, b2, publication, sent, queue = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    admissions.dispatch(document, source_reference=batch)
    extracted = b1.start(batch)
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    b2().start()
    queued = admissions.advance(document)
    assert queued.status == "queued" and queued.target_reference == target
    assert queued.source_reference is None
    # A later valid notification is not written here and does not replace it.
    assert admissions.read(document).target_reference == target
    tail = windows.plan_saved_batch(target, document,
                                    after_reference=publication.current().processed_source)
    assert tail["covers_whole_range"] is True and tail["source_reference"] is not None


def test_repeated_wakeups_neither_re_execute_nor_reset_the_recovery_budget(admitted):
    """Waking twice is not two jobs, and never buys a fresh allowance."""
    admissions, document, windows, target, b1, b2, publication, sent, _ = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    admissions.dispatch(document, source_reference=batch)
    admissions.recovered(document)
    before = admissions.read(document)
    for _ in range(3):
        again = admissions.dispatch(document, source_reference=batch)
    assert again == before and again.recovery_count == 1
    assert sent == [], "deciding what is owed never invokes the model"
    with pytest.raises(BackgroundAdmissionError, match="^admission_in_flight$"):
        admissions.admit(document, target_reference=target, extraction=b1, publication=publication)


def test_a_blocked_reason_and_its_recovery_budget_survive_reopening(admitted, engine):
    """Reopening the program is not a reason to try again or start the count over."""
    admissions, document, windows, target, b1, b2, publication, _, _ = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
    admissions.dispatch(document, source_reference=batch)
    admissions.recovered(document)
    admissions.recovered(document)
    admissions.block(document, error_code="source_unavailable")
    reopened = BackgroundAdmissions(engine).read(document)
    assert reopened.status == "blocked" and reopened.error_code == "source_unavailable"
    assert reopened.recovery_count == 2 and reopened.target_reference == target
    assert reconcile(reopened, extraction=b1, consolidation=b2(), publication=publication,
                     windows=windows, document_id=document) == "blocked"


def test_archiving_stops_new_admission_and_keeps_what_was_already_admitted(admitted, engine):
    """Archiving is not a Memory withdrawal: the row and its budget stay."""
    admissions, document, windows, target, b1, b2, publication, _, _ = admitted
    admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
    admissions.recovered(document)
    archive(engine, document)
    kept = admissions.read(document)
    assert kept.status == "queued" and kept.target_reference == target and kept.recovery_count == 1
    admissions.settle(document)
    with pytest.raises(BackgroundAdmissionError, match="^document_archived$"):
        admissions.admit(document, target_reference=target, extraction=b1, publication=publication)
