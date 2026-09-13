"""What durable state already answers about background admission, and what not.

Before any admission record is proposed, this establishes by measurement which
facts the existing owners really persist. It asserts the gap rather than
describing it, so a later slice cannot quietly widen or shrink the claim, and
so that if the gap closes on its own these tests fail instead of going stale.

Real PostgresSaver, real PostgresStore, real publication and catalog tables;
zero provider. Nothing here creates a table or proposes a schema.
"""
import os
from uuid import uuid4

import pytest

from test_consolidation_app import staged
from test_consolidation_postgres import opened_b2, stages
from test_extraction_postgres import interviewed
from test_interview_window_source import settled
from langchain_core.messages import AIMessage


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")

# The six responsibilities the verified BackgroundRow carried, per adoption
# mapping section 3.3. This file decides nothing about where they should live.
ADMISSION_FACTS = ("document_id", "status", "target_reference", "source_reference",
                   "error_code", "recovery_count")


def persisted(b1, b2_workflow, publication, store_conn, document):
    """Every fact the existing owners durably hold for one document."""
    extraction = b1.graph.get_state(b1.config).values
    consolidation = b2_workflow.graph.get_state(b2_workflow.config).values
    head = publication.current()
    catalog = store_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='jd_document'").fetchall()
    return {
        "b1_state": set(extraction),
        "b2_state": set(consolidation),
        "publication_head": set() if head is None else {"revision", "memory", "processed_source"},
        "jd_document": {row["column_name"] for row in catalog},
    }


def test_the_admitted_target_is_the_one_fact_no_existing_owner_holds():
    """A batch is a prefix; nothing durable says which target it was cut from.

    Both workflows persist the batch reference they were handed. Neither
    persists the target that bounded it, and the publication head only records
    what was already published. Re-deriving the target from the current head is
    exactly what the source contract forbids, so this cannot be recovered.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=2)
        assert batch["covers_whole_range"] is False, "a target with a tail is the case that matters"
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(batch["source_reference"])
            queue.extend(staged(extracted["files"][0]["summary_path"]))
            workflow = b2()
            workflow.start()
            state = persisted(b1, workflow, publication, store_conn, document)

            everywhere = set().union(*state.values())
            # Document identity is held, under the catalog's own column name.
            assert "id" in state["jd_document"] and "document_id" not in everywhere
            assert "source_reference" in everywhere, "the batch itself is durable"
            missing = {fact for fact in ADMISSION_FACTS if fact not in everywhere}
            assert missing == {"document_id", "target_reference", "status",
                               "error_code", "recovery_count"}

            # The stored batch is not the target and cannot stand in for it.
            assert b1.graph.get_state(b1.config).values["source_reference"] == batch["source_reference"]
            assert batch["source_reference"] != target
            head = publication.current()
            assert head.processed_source == batch["source_reference"] != target
            remaining = windows.plan_saved_batch(target, document,
                                                 after_reference=head.processed_source)
            assert remaining["source_reference"] is not None, "the target still has a tail"


def test_the_tail_is_unreachable_once_the_target_is_forgotten():
    """Without the admitted target, the only thing left is the current head.

    That is a different range: it grows with every later turn, so admitted work
    would widen instead of finishing. This is why the batch reference alone
    cannot replace a durable target.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, _, _, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=2)["source_reference"]
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(batch)
            queue.extend(staged(extracted["files"][0]["summary_path"]))
            b2().start()
        # The employee keeps talking while the tail waits. Distinct ids: this is
        # later speech, not a repeat of the turns already admitted.
        for index in range(2):
            settled(native, [AIMessage(id=f"later-a{index}", content="回" * 1250)],
                    text="問" * 1250)
        head = publication.current()
        widened = windows.capture_window(document, **windows.unprocessed_source(
            document, head.processed_source))
        assert widened != target, "re-deriving from the head is a different, larger range"
        from_target = windows.plan_saved_batch(target, document,
                                               after_reference=head.processed_source)
        from_head = windows.plan_saved_batch(widened, document,
                                             after_reference=head.processed_source)
        assert from_target["covers_whole_range"] is True
        assert from_target["source_reference"] != from_head["source_reference"]
