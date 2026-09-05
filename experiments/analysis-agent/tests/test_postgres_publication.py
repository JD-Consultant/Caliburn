"""Real PG metadata contention with official Store artifacts; no model calls."""

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.publication import HeadRow, ReceiptRow, PublicationStore, PublicationUncertain, StalePublication


@pytest.fixture
def pg_publications():
    dsn = os.environ.get("Q019_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Dedicated q019_agent_test DSN required; not a concurrency pass")
    params = conninfo_to_dict(dsn)
    assert params.get("dbname") == "q019_agent_test"
    assert params.get("host") in ("127.0.0.1", "localhost")
    assert 1 <= int(params.get("connect_timeout", "0")) <= 10
    dsn = make_conninfo(dsn, options="-c statement_timeout=10000 -c lock_timeout=5000")
    # libpq DSN stays out of logs / SQLAlchemy URL representation.
    engine = create_engine(URL.create("postgresql+psycopg"), connect_args=conninfo_to_dict(dsn), hide_parameters=True)
    document = "q019-test-" + str(uuid4())
    with PostgresStore.from_conn_string(dsn) as store:
        store.setup()
        artifacts = MemoryArtifacts(store, document)
        pub = PublicationStore(engine, artifacts)
        pub.setup()
        try:
            yield pub, artifacts
        finally:
            # Explicit random test document only, ORM deletes; not drop_all/DB.
            with Session(engine) as session, session.begin():
                for row in session.scalars(select(ReceiptRow).where(ReceiptRow.document_id == document)):
                    session.delete(row)
                head = session.get(HeadRow, document)
                if head:
                    session.delete(head)
            items, offset = [], 0
            while page := store.search(("q019-memory", document), limit=100, offset=offset):
                items.extend(page)
                offset += len(page)
            for item in items:
                store.delete(item.namespace, item.key)
            engine.dispose()


@pytest.mark.parametrize("existing_head", [False, True])
@pytest.mark.parametrize("same_operation", [False, True])
def test_pg_competing_writers_do_not_lose_updates(pg_publications, existing_head, same_operation):
    pub, artifacts = pg_publications
    old = artifacts.save_memory(knowledge="舊", guide="舊導覽")
    base = pub.publish(pub.prepare(old, expected_revision=0, kind="repair")).revision if existing_head else 0
    versions = [artifacts.save_memory(knowledge=text, guide=text + "導覽") for text in ["背景整理", "即時修補"]]
    requests = [pub.prepare(v, expected_revision=base, kind="repair") for v in versions]
    if same_operation:
        requests[1] = requests[0]
    barrier = Barrier(2, timeout=5)

    def before_write(conn, cursor, statement, parameters, context, executemany):
        prefix = "UPDATE q019_document_memory_head" if existing_head else "INSERT INTO q019_document_memory_head"
        if statement.startswith(prefix):
            barrier.wait()  # both already read the same base; database decides winner

    def publish(req):
        try:
            return pub.publish(req)
        except StalePublication:
            return "stale"

    event.listen(pub.engine, "before_cursor_execute", before_write)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(publish, req) for req in requests]
            results = [f.result(timeout=15) for f in futures]
    finally:
        event.remove(pub.engine, "before_cursor_execute", before_write)
    successes = [r for r in results if r != "stale"]
    assert len(successes) == (2 if same_operation else 1)
    assert all(r.revision == base + 1 for r in successes)
    assert pub.current().revision == base + 1
    assert all(r == pub.current() for r in successes)
    with Session(pub.engine) as session:
        receipts = list(session.scalars(select(ReceiptRow).where(ReceiptRow.document_id == artifacts.document_id)))
        assert len(receipts) == base + 1


def test_pg_lost_commit_reply_and_new_clients_recover_exact_version(pg_publications):
    pub, artifacts = pg_publications
    version = artifacts.save_memory(knowledge="主管核准例外", guide="核准權限導覽")
    request = pub.prepare(version, expected_revision=0, kind="repair")

    def lose_reply(session):
        raise OperationalError("COMMIT", {}, ConnectionError("synthetic lost reply"))

    event.listen(pub.sessions, "after_commit", lose_reply)
    try:
        with pytest.raises(PublicationUncertain):
            pub.publish(request)
    finally:
        event.remove(pub.sessions, "after_commit", lose_reply)
    pub.engine.dispose()  # all future metadata reads establish new DB connections
    reopened = PublicationStore(pub.engine, artifacts)
    first = reopened.receipt(request.operation_id).result
    assert first.revision == 1
    second_version = artifacts.save_memory(knowledge="另一工作", guide="新版導覽")
    second = reopened.publish(reopened.prepare(second_version, expected_revision=1, kind="repair"))
    assert second.revision == 2
    assert reopened.publish(request) == first
    assert reopened.current() == second
    assert artifacts.guide(first.memory) == "核准權限導覽"
    assert artifacts.reader(first.memory).read("/memory/knowledge.md").file_data["content"] == "主管核准例外"
