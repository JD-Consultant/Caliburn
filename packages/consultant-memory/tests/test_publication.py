"""Contract tests of the application publication seam, not model quality."""

from dataclasses import replace
import importlib.util
from uuid import uuid4

import pytest
from langgraph.store.memory import InMemoryStore

from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from conftest import ExampleSource


@pytest.fixture
def publications():
    assert importlib.util.find_spec("caliburn_memory.publication"), "Missing atomic publication seam"
    from sqlalchemy import create_engine
    from caliburn_memory.publication import PublicationStore
    engine = create_engine("sqlite+pysqlite:///:memory:")
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a", source=ExampleSource())
    pub = PublicationStore(engine, artifacts)
    pub.setup()
    try:
        yield pub, artifacts
    finally:
        engine.dispose()


def request(pub, artifacts, revision=0, text="案例A", **kwargs):
    version = artifacts.save_memory(knowledge=text, guide=text + "導覽")
    return pub.prepare(version, expected_revision=revision, kind="repair", **kwargs)


def test_publish_and_replay_after_later_version_return_original_receipt(publications):
    pub, artifacts = publications
    first_request = request(pub, artifacts)
    assert pub.current() is None
    first = pub.publish(first_request)
    assert first.revision == 1
    second = pub.publish(request(pub, artifacts, 1, "案例B"))
    assert second.revision == 2
    assert pub.publish(first_request) == first
    assert pub.receipt(first_request.operation_id).result == first
    assert pub.current() == second
    assert artifacts.guide(second.memory) == "案例B導覽"
    assert pub.receipt(str(uuid4())) is None


def test_stale_background_cannot_overwrite_repair_or_advance_cursor(publications):
    from caliburn_memory.publication import StalePublication
    pub, artifacts = publications
    source = artifacts.source.reference
    original = request(pub, artifacts)
    b_request = pub.prepare(original.memory, expected_revision=0, kind="consolidation", processed_source=source)
    repaired = pub.publish(request(pub, artifacts, text="例外由主管核准", repair_sources=(source,)))
    with pytest.raises(StalePublication) as error:
        pub.publish(b_request)
    assert error.value.current == repaired
    assert pub.current().processed_source is None
    assert pub.receipt(b_request.operation_id) is None
    assert artifacts.reader(pub.current().memory).read("/memory/knowledge.md").file_data["content"] == "例外由主管核准"


def test_no_content_change_still_versions_cursor_and_repairs_preserve_it(publications):
    pub, artifacts = publications
    source = artifacts.source.reference
    first = pub.publish(request(pub, artifacts))
    noop = pub.prepare(first.memory, expected_revision=1, kind="consolidation", processed_source=source)
    second = pub.publish(noop)
    assert second.revision == 2 and second.memory == first.memory
    assert second.processed_source == source
    third = pub.publish(pub.prepare(first.memory, expected_revision=2, kind="repair"))
    assert third.revision == 3 and third.processed_source == source


def test_same_operation_with_changed_payload_is_rejected(publications):
    pub, artifacts = publications
    req = request(pub, artifacts)
    first = pub.publish(req)
    other = replace(request(pub, artifacts, 1, "另一內容"), operation_id=req.operation_id)
    with pytest.raises(ValueError, match="operation"):
        pub.publish(other)
    assert pub.current() == first


def test_missing_or_modified_artifacts_never_become_current(publications):
    pub, artifacts = publications
    with pytest.raises(ValueError, match="unavailable"):
        pub.prepare(MemoryVersion("document-a", str(uuid4())), expected_revision=0, kind="repair")
    req = request(pub, artifacts)
    # Simulate an out-of-contract writer/partial storage failure through public
    # Store API. Publication must catch differing prepared bytes before SQL.
    ns = ("q019-memory", "document-a", "versions", req.memory.version_id)
    item = artifacts.store.search(ns, limit=100)[0]
    artifacts.store.put(ns, item.key, dict(item.value, content="被改掉"))
    with pytest.raises(ValueError, match="changed|content|fingerprint"):
        pub.publish(req)
    assert pub.current() is None and pub.receipt(req.operation_id) is None


def test_runtime_scope_and_request_validation(publications):
    from caliburn_memory.publication import PublicationStore
    pub, artifacts = publications
    req = request(pub, artifacts)
    other = PublicationStore(pub.engine, MemoryArtifacts(artifacts.store, "document-b"))
    with pytest.raises(ValueError, match="document"):
        other.publish(req)
    assert other.current() is None and other.receipt(req.operation_id) is None
    for options in [{"expected_revision": -1, "kind": "repair"},
                    {"expected_revision": 0, "kind": "invented"},
                    {"expected_revision": 0, "kind": "consolidation"},
                    {"expected_revision": 0, "kind": "repair", "processed_source": "invented"}]:
        with pytest.raises(ValueError):
            pub.prepare(req.memory, **options)


def test_repair_receipts_can_be_read_in_bounded_revision_order(publications):
    pub, artifacts = publications
    source = artifacts.source.reference
    for revision in range(3):
        pub.publish(request(pub, artifacts, revision, f"更正{revision}", repair_sources=(source,)))
    page = pub.repair_receipts(after_revision=0, through_revision=2, limit=1)
    assert len(page) == 1 and page[0].result.revision == 1
    assert page[0].repair_sources == (source,)
    following = pub.repair_receipts(after_revision=1, through_revision=2)
    assert [r.result.revision for r in following] == [2]
    assert pub.repair_receipts(after_revision=2, through_revision=2) == []


def test_failure_before_commit_rolls_back_head_and_receipt(publications):
    from sqlalchemy import event
    pub, artifacts = publications
    first = pub.publish(request(pub, artifacts))
    req = request(pub, artifacts, 1, "未完成版本")

    def fail(session):
        session.flush()
        raise RuntimeError("synthetic failure before commit")

    event.listen(pub.sessions, "before_commit", fail)
    try:
        with pytest.raises(RuntimeError, match="before commit"):
            pub.publish(req)
    finally:
        event.remove(pub.sessions, "before_commit", fail)
    assert pub.current() == first and pub.receipt(req.operation_id) is None


def test_lost_commit_response_can_be_reconciled_without_republishing(publications):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    from caliburn_memory.publication import PublicationStore, PublicationUncertain
    pub, artifacts = publications
    req = request(pub, artifacts)

    def lose_response(session):
        raise OperationalError("COMMIT", {}, ConnectionError("synthetic lost reply"))

    event.listen(pub.sessions, "after_commit", lose_response)
    try:
        with pytest.raises(PublicationUncertain):
            pub.publish(req)
    finally:
        event.remove(pub.sessions, "after_commit", lose_response)
    reopened = PublicationStore(pub.engine, artifacts)
    assert reopened.receipt(req.operation_id).result.revision == 1
    assert reopened.publish(req).revision == 1
    assert reopened.current().revision == 1


@pytest.mark.parametrize("failure_point", ["initial-receipt", "rollback-receipt", "rollback-head"])
def test_reconciliation_connection_failure_preserves_uncertain_contract(publications, failure_point):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    from caliburn_memory.publication import PublicationUncertain, StalePublication
    pub, artifacts = publications
    committed = request(pub, artifacts)
    first = pub.publish(committed)
    attempt = committed if failure_point == "initial-receipt" else request(pub, artifacts, 0, "已過期")
    receipt_reads, head_reads = 0, 0

    def disconnect(conn, cursor, statement, parameters, context, executemany):
        nonlocal receipt_reads, head_reads
        if not statement.startswith("SELECT"):
            return
        if "q019_memory_publication_receipt" in statement:
            receipt_reads += 1
            if ((failure_point == "initial-receipt" and receipt_reads == 1)
                    or (failure_point == "rollback-receipt" and receipt_reads == 3)):
                raise OperationalError("SELECT", {}, ConnectionError("synthetic reconciliation disconnect"))
        if "q019_document_memory_head" in statement:
            head_reads += 1
            if failure_point == "rollback-head" and head_reads == 2:
                raise OperationalError("SELECT", {}, ConnectionError("synthetic current-head disconnect"))

    event.listen(pub.engine, "before_cursor_execute", disconnect)
    try:
        with pytest.raises(PublicationUncertain):
            pub.publish(attempt)
    finally:
        event.remove(pub.engine, "before_cursor_execute", disconnect)
    assert pub.current() == first
    assert pub.publish(committed) == first
    if failure_point != "initial-receipt":
        with pytest.raises(StalePublication):
            pub.publish(attempt)


def test_original_receipt_precedes_artifact_and_source_read_after_later_publication(publications):
    pub, artifacts = publications
    source = artifacts.source
    original = request(pub, artifacts, text=f"[原話]({source.reference})", repair_sources=(source.reference,))
    first = pub.publish(original)
    latest = pub.publish(request(pub, artifacts, revision=1, text="後續工作內容"))
    source.unavailable = True
    source.reads.clear()
    assert pub.publish(original) == first
    assert source.reads == []  # source shape validation must not reach storage
    assert pub.current() == latest
    assert pub.receipt(original.operation_id).result == first
    with pytest.raises(ValueError, match="reference"):
        artifacts.verify_version(original.memory)  # a new verification really reads


def test_publication_validates_source_scope_without_io(publications):
    pub, artifacts = publications
    source = artifacts.source
    req = request(pub, artifacts, repair_sources=(source.reference,))
    source.reads.clear()
    source.unavailable = True
    first = pub.publish(req)
    assert first.revision == 1 and source.reads == []
    assert source.validations.count(source.reference) >= 2
    with pytest.raises(ValueError, match="source|Source|document"):
        pub.publish(replace(req, repair_sources=("conversation:document-b:original",)))
    assert pub.current() == first
