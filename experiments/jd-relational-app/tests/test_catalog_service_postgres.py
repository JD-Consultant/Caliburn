"""Real catalog SQL and native Saver/manual ownership; no provider or OS host.

Uses only the explicitly initialized 55436 synthetic test database. Persisted
evidence is retained. Run only with JD_RELATIONAL_TEST_DB=1.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from threading import Event
import traceback
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage
import pytest
import sqlalchemy as sa

from jd_relational.catalog_service import CatalogError, CatalogService
from jd_relational.domain import COLLECTIONS, PROFILE_FIELDS
from jd_relational.storage import schema as db
from test_manual_runtime_postgres import config, counts, engine, prepare, runtime_factory


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


def catalog(runtime_factory):
    owner, graph, observed, calls = runtime_factory()
    return CatalogService(owner, str(uuid4())), owner, graph, observed, calls


def request(service, *, title="合成員工完整工作", key=None):
    return {"request_key": str(key or uuid4()), "dataset_id": service.dataset_id, "title": title}


def create(service, **kwargs):
    value = request(service, **kwargs)
    return service.create(value)["document_id"], value


def change(service, document, value, *, kind):
    return service.update(document, service.etag(service.get(document)), value, kind=kind)


def before(document):
    return str(UUID(int=UUID(document).int - 1))


def test_create_empty_document_persists_initial_jd_without_consultant(runtime_factory, engine):
    service, owner, graph, observed, calls = catalog(runtime_factory)
    document, envelope = create(service)
    current = owner.storage.read_current(document)
    assert current.title == envelope["title"] and current.revision_number == 1
    assert current.metadata_version == 1 and current.archived is False
    assert all(current.domain["profile"][field] is None for field in PROFILE_FIELDS)
    assert all(current.domain[name] == {} for name in COLLECTIONS.values())
    assert current.domain["task_capabilities"] == current.domain["source_links"] == []
    assert counts(engine, document) == (1, 0)
    assert calls == [] and observed.updates == []
    assert service.lookup(envelope)["document_id"] == document


def test_list_pagination_and_archive_restore_use_the_persisted_catalog(runtime_factory, engine):
    service, owner, _, _, calls = catalog(runtime_factory)
    document, _ = create(service)
    create(service, title="合成另一份工作")
    create(service, title="合成第三份工作")
    page = service.list(limit=2)
    with engine.connect() as conn:
        expected = conn.execute(sa.select(db.jd_document.c.id).where(
            db.jd_document.c.archived.is_(False)).order_by(db.jd_document.c.id).limit(3)).scalars().all()
    assert [item["document_id"] for item in page["documents"]] == expected[:2]
    assert page["dataset_id"] == service.dataset_id and page["next_after"] == expected[1]
    continuation = service.list(limit=1, after=page["next_after"])
    assert continuation["documents"][0]["document_id"] == expected[2]
    changed = change(service, document, {"title": "更名後的完整工作"}, kind="title")
    assert changed["metadata_version"] == 2 and changed["title"] == "更名後的完整工作"
    archived = change(service, document, {"archived": True}, kind="archive")
    assert archived["metadata_version"] == 3 and archived["archived"] is True
    assert all(item["document_id"] != document for item in service.list(after=before(document), limit=1)["documents"])
    assert service.list(archived=True, after=before(document), limit=1)["documents"][0]["document_id"] == document
    restored = change(service, document, {"archived": False}, kind="archive")
    assert restored["metadata_version"] == 4 and restored["archived"] is False
    assert service.list(after=before(document), limit=1)["documents"][0]["document_id"] == document
    assert counts(engine, document) == (1, 0) and calls == []
    assert owner.storage.read_current(document).title == "更名後的完整工作"


def test_metadata_after_jd_edit_preserves_original_messages_and_all_jd_history(runtime_factory, engine):
    service, owner, graph, _, calls = catalog(runtime_factory)
    document, _ = create(service)
    messages = [HumanMessage(content="合成原始訪談\n每月核對報表，不設績效目標。", id="human-original"),
                AIMessage(content="保留訪談依據並整理真實工作。", id="ai-original")]
    graph.update_state(config(document), {"messages": messages}, as_node="consultant")
    original_messages = [item.model_dump() for item in graph.get_state(config(document)).values["messages"]]
    result = owner.submit(prepare(owner, document=document, text="每月核對營運報表，指出資料異常。" )).wait(5)
    assert result.checkpoint_closed and result.observation.status == "committed"
    current = owner.storage.read_current(document)
    original_snapshot = deepcopy(current.snapshot)
    with engine.connect() as conn:
        revisions = conn.execute(sa.select(db.jd_revision).where(db.jd_revision.c.document_id == document)
            .order_by(db.jd_revision.c.revision_number)).mappings().all()
        receipts = conn.execute(sa.select(db.jd_operation).where(db.jd_operation.c.document_id == document)).mappings().all()
    change(service, document, {"title": "已訪談合成 JD"}, kind="title")
    change(service, document, {"archived": True}, kind="archive")
    change(service, document, {"archived": False}, kind="archive")
    after = owner.storage.read_current(document)
    assert after.snapshot == original_snapshot and after.revision_id == current.revision_id
    assert after.revision_number == 2 and counts(engine, document) == (2, 1)
    with engine.connect() as conn:
        assert conn.execute(sa.select(db.jd_revision).where(db.jd_revision.c.document_id == document)
            .order_by(db.jd_revision.c.revision_number)).mappings().all() == revisions
        assert conn.execute(sa.select(db.jd_operation).where(db.jd_operation.c.document_id == document)).mappings().all() == receipts
    assert [item.model_dump() for item in graph.get_state(config(document)).values["messages"]] == original_messages
    assert calls == []


def test_live_jd_writer_blocks_same_document_metadata_but_not_another_document(runtime_factory, monkeypatch):
    service, owner, _, _, calls = catalog(runtime_factory)
    one, _ = create(service)
    two, _ = create(service)
    entered, release = Event(), Event()
    original = owner.storage.execute
    def wait_for_write(intent):
        if intent.document_id == one:
            entered.set()
            assert release.wait(5)
        return original(intent)
    monkeypatch.setattr(owner.storage, "execute", wait_for_write)
    handle = owner.submit(prepare(owner, document=one))
    try:
        assert entered.wait(3)
        with pytest.raises(CatalogError, match="^busy$"):
            change(service, one, {"archived": True}, kind="archive")
        changed = change(service, two, {"title": "另一份仍可更名"}, kind="title")
        assert changed["metadata_version"] == 2
        assert service.get(one)["metadata_version"] == 1
    finally:
        release.set()
    assert handle.wait(5).checkpoint_closed and calls == []


def test_catalog_io_holds_only_its_document_slot(runtime_factory, monkeypatch):
    service, owner, _, _, calls = catalog(runtime_factory)
    one, _ = create(service)
    two, _ = create(service)
    entered, release = Event(), Event()
    original = owner.storage.update_catalog
    def wait_for_catalog(document, *args, **kwargs):
        if document == one:
            entered.set()
            assert release.wait(5)
        return original(document, *args, **kwargs)
    monkeypatch.setattr(owner.storage, "update_catalog", wait_for_catalog)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(change, service, one, {"title": "第一份較慢更名"}, kind="title")
        try:
            assert entered.wait(3)
            assert change(service, two, {"archived": True}, kind="archive")["archived"] is True
        finally:
            release.set()
        assert pending.result(5)["metadata_version"] == 2
    assert calls == []


def test_original_creation_key_and_title_survive_rename_and_archive(runtime_factory, engine):
    service, owner, _, _, calls = catalog(runtime_factory)
    document, envelope = create(service, title="原始建立名稱，保留空格 ")
    change(service, document, {"title": "後來更名"}, kind="title")
    change(service, document, {"archived": True}, kind="archive")
    assert service.lookup(envelope)["document_id"] == document
    assert service.create(envelope)["document_id"] == document
    with pytest.raises(CatalogError, match="^creation_conflict$"):
        service.create({**envelope, "title": "後來更名"})
    with pytest.raises(CatalogError, match="^creation_conflict$"):
        service.lookup({**envelope, "title": "原始建立名稱，保留空格"})
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.jd_document).where(
            db.jd_document.c.create_request_key == envelope["request_key"])).scalar_one() == 1
    current = service.get(document)
    assert (current["title"], current["archived"], current["metadata_version"]) == ("後來更名", True, 3)
    assert counts(engine, document) == (1, 0) and calls == []


def test_new_dataset_blocks_creation_and_old_dataset_etag_before_metadata_write(runtime_factory, monkeypatch):
    service, owner, _, _, calls = catalog(runtime_factory)
    document, envelope = create(service)
    old_tag = service.etag(service.get(document))
    current_dataset = CatalogService(owner, str(uuid4()))
    mutations = []
    def forbidden(*args, **kwargs):
        mutations.append(True)
        raise AssertionError("Old dataset must be rejected before any writer admission")
    monkeypatch.setattr(owner, "create_document", forbidden)
    monkeypatch.setattr(owner, "update_catalog", forbidden)
    with pytest.raises(CatalogError, match="^dataset_changed$"):
        current_dataset.create(envelope)
    with pytest.raises(CatalogError, match="^dataset_changed$"):
        current_dataset.lookup(envelope)
    with pytest.raises(CatalogError, match="^metadata_changed$"):
        current_dataset.update(document, old_tag, {"title": "舊頁不准寫"}, kind="title")
    assert mutations == [] and service.get(document)["metadata_version"] == 1 and calls == []


def test_sql_cas_rejects_metadata_changed_after_service_etag_check(runtime_factory, engine, monkeypatch):
    service, owner, _, _, calls = catalog(runtime_factory)
    document, _ = create(service)
    old_tag = service.etag(service.get(document))
    original = owner.update_catalog
    injected = []
    def change_between_read_and_lock(doc, version, **values):
        injected.append(original(doc, version, title="先完成的另一個操作"))
        return original(doc, version, **values)
    monkeypatch.setattr(owner, "update_catalog", change_between_read_and_lock)
    with pytest.raises(CatalogError, match="^metadata_changed$"):
        service.update(document, old_tag, {"title": "過時操作不得覆蓋"}, kind="title")
    current = service.get(document)
    assert len(injected) == 1 and current["title"] == "先完成的另一個操作"
    assert current["metadata_version"] == 2 and counts(engine, document) == (1, 0) and calls == []


@pytest.mark.parametrize("kind", ["create", "metadata"])
def test_real_commit_with_lost_ack_returns_unknown_then_read_only_reconciliation(runtime_factory, engine, monkeypatch, kind):
    service, owner, _, _, calls = catalog(runtime_factory)
    envelope = request(service)
    document = None
    if kind == "metadata":
        document = service.create(envelope)["document_id"]
        old_tag = service.etag(service.get(document))
    lost = []
    native_commit = engine.dialect.do_commit
    method = "create_document" if kind == "create" else "update_catalog"
    original = getattr(owner.storage, method)
    def lose_ack(dbapi_connection):
        native_commit(dbapi_connection)
        if not lost:
            lost.append(True)
            raise OSError("SyntheticPrivateCommitAcknowledgementSentinel")
    def operation_with_lost_ack(*args, **kwargs):
        with monkeypatch.context() as scope:
            scope.setattr(engine.dialect, "do_commit", lose_ack)
            return original(*args, **kwargs)
    monkeypatch.setattr(owner.storage, method, operation_with_lost_ack)
    with pytest.raises(CatalogError, match="^write_unconfirmed$") as caught:
        if kind == "create":
            service.create(envelope)
        else:
            service.update(document, old_tag, {"title": "確實已提交，回覆遺失"}, kind="title")
    assert lost == [True]
    assert "SyntheticPrivateCommitAcknowledgementSentinel" not in "".join(traceback.format_exception(caught.value))
    def forbidden(*args, **kwargs):
        raise AssertionError("Lookup must not replay an unknown write")
    monkeypatch.setattr(owner.storage, method, forbidden)
    found = service.lookup(envelope)
    assert found["state"] == "found"
    document = found["document_id"]
    state = service.get(document)
    assert state["metadata_version"] == (1 if kind == "create" else 2)
    if kind == "metadata":
        assert state["title"] == "確實已提交，回覆遺失"
        with pytest.raises(CatalogError, match="^metadata_changed$"):
            service.update(document, old_tag, {"title": "確實已提交，回覆遺失"}, kind="title")
    assert counts(engine, document) == (1, 0) and calls == []
