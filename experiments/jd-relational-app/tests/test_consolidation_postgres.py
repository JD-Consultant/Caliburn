"""B1 -> B2 -> publication over real PostgreSQL, in order, with no provider.

Real PostgresSaver for both stages' progress, real PostgresStore for detail and
staged versions, real publication tables, and the real OpenAI SDK answered in
process. What this file is for is the handover itself: that a batch reaches B2
only after B1 finished it, that the published cursor is the only thing that
moves the work forward, and that an interrupted handover resumes on rebuilt
resources without consolidating or publishing twice.

Run `scripts/init_test_runtime.py` and `scripts/init_test_memory.py`
explicitly first. These tests never setup, clear or drop anything.
"""
from contextlib import contextmanager
import json
import os
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from caliburn_memory import PublicationStore
from jd_relational.consolidation_app import build_consolidation_model, build_consolidation_workflow
from jd_relational.extraction_app import build_extraction_model, build_extraction_workflow

from test_consolidation_app import staged
from test_extraction_postgres import (
    FaultyStore, artifacts_for, interviewed, opened, published_rows, saved_rows,
)
from test_extraction_app import completed
from test_memory_core_postgres import SCHEMA


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@contextmanager
def opened_b2(dataset, document, *, store_class=PostgresStore):
    """The B1 document resources, plus the real publication tables B2 needs."""
    engine = sa.create_engine(sa.URL.create("postgresql+psycopg", username="jd_test",
        password="jd-local-test-only", host="127.0.0.1", port=55436,
        database="caliburn_jd_relational_test"), hide_parameters=True,
        connect_args={"options": f"-csearch_path={SCHEMA},public", "connect_timeout": 5})
    try:
        with opened(dataset, document, store_class=store_class) as (
                native, windows, store, saver, store_conn):
            artifacts = artifacts_for(windows, store, document)
            yield native, windows, store, saver, store_conn, artifacts, \
                PublicationStore(engine, artifacts)
    finally:
        engine.dispose()


@contextmanager
def stages(windows, document, store, saver, publication):
    """One transport for both stages; every request is counted in order."""
    sent, queue = [], []

    def respond(request):
        sent.append(json.loads(request.content))
        answer = queue.pop(0) if queue else completed()
        answer = json.loads(json.dumps(answer))
        answer["id"] = f"resp_{len(sent)}"
        for index, item in enumerate(answer["output"]):
            item["id"] = f"item_{len(sent)}_{index}"
            if item.get("type") == "function_call":
                item["call_id"] = f"call_{len(sent)}_{index}"
        return httpx.Response(200, json=answer)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        b1 = build_extraction_workflow(service=windows, document_id=document, store=store,
            model=build_extraction_model(model="gpt-5.6-luna", api_key="offline",
                                         http_client=client).model_copy(update={"max_retries": 0}),
            checkpointer=saver)
        model = build_consolidation_model(model="gpt-5.6-luna", api_key="offline",
                                          http_client=client).model_copy(update={"max_retries": 0})

        def b2(**options):
            return build_consolidation_workflow(extraction=b1, publication=publication,
                model=model, checkpointer=saver, **options)

        yield b1, b2, sent, queue


def test_two_batches_hand_over_in_order_and_only_publication_moves_the_work():
    """The whole R2 path on durable resources, twice.

    The second batch exists because the first one's publication moved the
    cursor -- not because anything asked again -- and each batch reaches B2
    only after B1 finished it.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        first = windows.plan_saved_batch(target, document, max_windows=2)
        assert first["covers_whole_range"] is False
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(first["source_reference"])
            assert publication.current() is None, "B1 alone never publishes"
            queue.extend(staged(extracted["files"][0]["summary_path"], body="第一批的工作理解。"))
            b2().start()
            head = publication.current()
            assert head.revision == 1 and head.processed_source == first["source_reference"]

            rest = windows.plan_saved_batch(target, document,
                                            after_reference=head.processed_source)
            assert rest["covers_whole_range"] is True
            tail = b1.start(rest["source_reference"])
            queue.extend(staged(tail["files"][0]["summary_path"], body="第二批補上的工作理解。"))
            b2().start()
            final = publication.current()
            assert final.revision == 2 and final.processed_source == rest["source_reference"]
            knowledge = artifacts.reader(final.memory).read("/memory/knowledge.md").file_data["content"]
            assert "第二批補上的工作理解。" in knowledge
            assert windows.plan_saved_batch(target, document,
                                            after_reference=final.processed_source) == {
                "source_reference": None, "covers_whole_range": True}
            assert published_rows(store_conn, document) == 1
            print(f"B1->B2 real PG document={document} batches=2 "
                  f"http={len(sent)} revision={final.revision} "
                  f"rows={saved_rows(store_conn, document)}")


def test_a_finished_b1_batch_waits_durably_until_b2_takes_it():
    """B1 done, B2 not started: the handover survives losing every resource."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn, _, publication):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        with stages(windows, document, store, saver, publication) as (b1, _, sent, _):
            files = b1.start(batch)["files"]
            assert len(sent) == 1
        assert publication.current() is None and published_rows(store_conn, document) == 0
    with opened_b2(dataset, document) as (_, windows, store, saver, store_conn, artifacts, publication):
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            queue.extend(staged(files[0]["summary_path"], body="重開後才整併的理解。"))
            result = b2().start()
            assert result["files"] == files, "B2 must take the batch B1 actually finished"
            head = publication.current()
            assert head.revision == 1 and head.processed_source == batch
            assert "重開後才整併的理解。" in artifacts.reader(head.memory).read(
                "/memory/knowledge.md").file_data["content"]
            assert published_rows(store_conn, document) == 1


def test_a_pending_b2_resumes_on_rebuilt_resources_without_a_second_attempt():
    """The saved attempt is progress; reopening never buys the model again."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document, store_class=FaultyStore) as (
            native, windows, store, saver, _, _, publication):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(batch)
            summary_path = extracted["files"][0]["summary_path"]
            store.pass_writes = 0
            queue.extend(staged(summary_path, body="中斷前已整併的理解。"))
            with pytest.raises(RuntimeError, match="synthetic store fault"):
                b2().start()
            attempts = len(sent)
            assert attempts > 1, "the attempt really reached the model before failing"
        assert publication.current() is None
    with opened_b2(dataset, document) as (_, windows, store, saver, store_conn, artifacts, publication):
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, _):
            result = b2().resume()
            assert sent == [], "a saved attempt is never consolidated a second time"
            head = publication.current()
            assert result["result"]["revision"] == head.revision == 1
            assert head.processed_source == batch
            assert "中斷前已整併的理解。" in artifacts.reader(head.memory).read(
                "/memory/knowledge.md").file_data["content"]
            assert published_rows(store_conn, document) == 1


def test_a_lost_publish_reply_is_recovered_from_the_original_request(monkeypatch):
    """Committed and unanswered is still committed; the job reconciles it."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(batch)
            queue.extend(staged(extracted["files"][0]["summary_path"], body="回覆遺失的整併。"))
            original, lost = PublicationStore.publish, []

            def commit_then_lose_the_reply(self, request):
                result = original(self, request)
                if not lost:
                    lost.append(result)
                    raise ConnectionError("synthetic reply loss after commit")
                return result

            monkeypatch.setattr(PublicationStore, "publish", commit_then_lose_the_reply)
            workflow = b2()
            with pytest.raises(ConnectionError, match="synthetic reply loss"):
                workflow.start()
            attempts = len(sent)
            assert publication.current().revision == 1
            monkeypatch.undo()
            resumed = workflow.resume()
            assert len(sent) == attempts, "a committed publication is never re-consolidated"
            assert resumed["result"]["revision"] == 1
            assert publication.current() == lost[0]
            assert published_rows(store_conn, document) == 1


def test_a_repair_published_mid_job_makes_b2_reload_before_it_publishes(monkeypatch):
    """C corrects while B2 holds a stale base; B2 rereads instead of overwriting."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened_b2(dataset, document) as (native, windows, store, saver, store_conn,
                                          artifacts, publication):
        turns = interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        corrected = windows.capture_window(document, first_run_id=turns[0].record.run_id,
                                           last_run_id=turns[0].record.run_id)
        with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
            extracted = b1.start(batch)
            summary_path = extracted["files"][0]["summary_path"]
            original, intervened = PublicationStore.publish, []

            def repair_first(self, request):
                if not intervened:
                    intervened.append(True)
                    version = artifacts.save_memory(knowledge="更正：權限由客戶自行設定。",
                                                    guide="更正後導覽")
                    original(self, self.prepare(version, expected_revision=0, kind="repair",
                                                repair_sources=(corrected,)))
                return original(self, request)

            monkeypatch.setattr(PublicationStore, "publish", repair_first)
            queue.extend([*staged(summary_path, body="舊基準下的說法。"),
                          *staged(summary_path, body="更正後：權限由客戶自行設定。")])
            result = b2().start()
            # B1 and B2 share one transport here, so select B2's own payloads.
            payloads = [payload for request in sent
                        for payload in [json.loads(request["input"][1]["content"])]
                        if "RECENT_REPAIRS" in payload]
            assert payloads and not payloads[0]["RECENT_REPAIRS"]
            later = next(payload for payload in payloads if payload["RECENT_REPAIRS"])
            assert later["RECENT_REPAIRS"][0]["reference"] == corrected
            assert later["GUIDE"] == "更正後導覽", "the reload seeds from C's new head"
            head = publication.current()
            assert head.revision == result["result"]["revision"] == 2
            assert head.processed_source == batch
            knowledge = artifacts.reader(head.memory).read("/memory/knowledge.md").file_data["content"]
            assert "更正後：權限由客戶自行設定。" in knowledge and "舊基準下的說法。" not in knowledge
            assert published_rows(store_conn, document) == 1
