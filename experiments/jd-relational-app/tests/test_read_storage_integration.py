"""Opt-in real PostgreSQL read/ref/command/history integration, no providers."""

import os
from uuid import UUID, uuid4

import pytest

from jd_relational.domain import COLLECTIONS, FIELDS, Source, source_target
from jd_relational.intents import bind_edit
from jd_relational.observation_projection import project_observation
from jd_relational.reads import ReadError, ReadService, command_context
from jd_relational.references import ReferenceCodec
from jd_relational.storage.history import HistoryReader
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine  # public, isolated, explicitly opted-in fixture
from test_storage_service import FakeAuthority, change, insert_item, task_args


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                               reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def codec():
    return ReferenceCodec(b"synthetic-read-storage-signing-key-only", "read-storage-test-dataset")


@pytest.fixture
def reads(store, engine, codec):
    return ReadService(store, HistoryReader(engine), codec, page_bytes=4096)


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成讀取接合"))


def request(view="current", target=None, cursor=None):
    return {"view": view, "target_ref": target, "cursor": cursor}


def pages(reads, document, view="current", target=None, first=None):
    page = first or reads.read(document, request(view, target))
    result, received, cursors = [], [], set()
    while True:
        assert page["format_version"] == 2
        received.append(page)
        result.extend(page["records"])
        assert page["has_more"] == (page["next_cursor"] is not None)
        assert len(received) < 500
        if not page["has_more"]:
            return result, received
        assert page["next_cursor"] not in cursors
        cursors.add(page["next_cursor"])
        page = reads.read(document, request(view, target, page["next_cursor"]))


def records(reads, current):
    return pages(reads, current.document_id)[0]


def item(rows, kind):
    return next(row for row in rows if row["type"] == "item" and row["kind"] == kind)


def field(rows, name, item_ref=None):
    return next(row for row in rows if row["type"] == "field" and row["name"] == name and row["item_ref"] == item_ref)


def container(rows, kind, owner=None):
    return next(row for row in rows if row["type"] == "container" and row["child_kind"] == kind and row["owner_ref"] == owner)


def apply_issued(store, codec, current, tool, arguments, resolver=None):
    command = {"tool": tool, "arguments": arguments}
    context = command_context(current.domain, command, codec, resolver or (lambda token, doc: Source(doc)),
                              lambda: str(uuid4()))
    intent = bind_edit(operation_id=uuid4(), origin="manual", ai_run_id=None, command=command, context=context)
    store.authority.admit(intent)
    result = store.execute(intent)
    assert result.confirmed and result.status == "committed"
    return store.read_current(current.document_id), intent, result


@pytest.fixture
def rich(store, current):
    # Existing tested command helper is setup only. Assertions below use refs
    # issued by the real read projection and immutable PostgreSQL material.
    for kind, values in (
        ("collaborator", {"name": "客服窗口", "scope_text": "對外承諾由窗口處理"}),
        ("duty", {"name": "維運", "scope_text": "只處理合約內系統"}),
        ("knowledge", {"name": "合約範圍", "description": "辨識服務涵蓋項目"}),
        ("skill", {"name": "異常診斷", "description": "區分事實與假設"}),
        ("qualification", {"text": "須依現場安全程序取得操作資格"}),
    ):
        arguments = insert_item("condition" if kind == "qualification" else kind, **values)
        if kind == "qualification":
            arguments["item"]["container_ref"] = "container:qualification"
        current, _, _ = change(store, current, "jd_insert_item", arguments)
    duty = next(iter(current.domain["duties"]))
    args = task_args(f"tasks:{duty}")
    args["description"] = "辨識合約內異常；不能确认根因時轉交。\n" * 70
    args["outcomes"].append({"text": "清楚標示未確認的觀察資訊", "basis_refs": []})
    args["requirements"].append({"text": "完成隔離後才進行檢查", "basis_refs": ["qa:2"]})
    args["capabilities"] = [{"capability_ref": f"capability:{identity}", "basis_refs": ["qa:1"]}
                            for identity in current.domain["capabilities"]]
    current, _, _ = change(store, current, "jd_create_task", args, origin="ai", ai_run_id="synthetic-read-integration")
    current, _, _ = change(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": "忠實呈現員工的工作", "basis_refs": []})
    return current


def decode(codec, token, doc, role):
    return codec.resolve(token, document_id=doc, roles={role}, purposes={"current", "history", "observation"})


def assert_complete_projection(rows, current, codec, *, purpose):
    """Reassemble stable fields/ownership/relations from all issued pages."""
    value, doc = current.domain, current.document_id
    expected_fields = {("profile", None, name): text for name, text in value["profile"].items()}
    expected_items = {}
    for kind, collection in COLLECTIONS.items():
        for identity, row in value[collection].items():
            expected_fields.update({(kind, identity, name): row[name] for name in FIELDS[kind]})
            detail_kind = row["kind"] if kind in {"detail", "capability", "condition"} else kind
            parent = row["duty_id"] if kind == "task" else row["task_id"] if kind == "detail" else None
            expected_items[(kind, identity)] = (detail_kind, parent, row["position"])
    actual_fields, actual_items, actual_relations, actual_sources = {}, {}, set(), set()
    for row in rows:
        if row["type"] == "field":
            ref = decode(codec, row["field_ref"], doc, "field")
            assert ref.purpose == purpose and ref.revision_id == str(current.revision_id)
            key = (ref.kind, ref.entity_id, ref.field)
            assert key not in actual_fields
            actual_fields[key] = row["value"]
        elif row["type"] == "item":
            ref = decode(codec, row["item_ref"], doc, "item")
            assert row["item_id"] == ref.entity_id
            owner = decode(codec, row["container_ref"], doc, "container")
            assert ref.purpose == owner.purpose == purpose
            actual_items[(ref.kind, ref.entity_id)] = (row["kind"], owner.entity_id, row["position"])
        elif row["type"] == "task_capability":
            task = decode(codec, row["task_ref"], doc, "item")
            cap = decode(codec, row["capability_ref"], doc, "item")
            actual_relations.add((task.entity_id, cap.entity_id, row["position"]))
        elif row["type"] == "source":
            ref = codec.resolve(row["target_ref"], document_id=doc, roles={"item", "field"}, purposes={purpose})
            cap = decode(codec, row["related_capability_ref"], doc, "item").entity_id if row["related_capability_ref"] else None
            target = ("relation", ref.entity_id, cap) if cap else (ref.kind, ref.field if ref.kind == "profile" else ref.entity_id)
            actual_sources.add((target, row["source_ref"]))
            assert row["readability"] == "not_checked"
    assert actual_fields == expected_fields and actual_items == expected_items
    assert actual_relations == {(r["task_id"], r["capability_id"], r["position"]) for r in value["task_capabilities"]}
    assert actual_sources == {(source_target(row), row["source_ref"]) for row in value["source_links"]}
    assert len([row for row in rows if row["type"] == "section"]) == 6
    assert {row["section_key"] for row in rows if row["type"] == "section"} == {
        "profile", "purpose", "duties_tasks", "knowledge", "skills", "conditions"}


def test_issued_container_item_and_field_reach_the_same_real_save(reads, store, codec, current):
    rows = records(reads, current)
    current, _, _ = apply_issued(store, codec, current, "jd_insert_item", {"item": {
        "kind": "duty", "container_ref": container(rows, "duty")["container_ref"], "after_ref": None,
        "name": "維運", "scope_text": "合約內系統", "basis_refs": []}})
    rows = records(reads, current)
    duty = item(rows, "duty")
    args = task_args(container(rows, "task", duty["item_ref"])["container_ref"])
    current, _, saved = apply_issued(store, codec, current, "jd_create_task", args)
    assert saved.receipt.base_revision_id != saved.receipt.result_revision_id
    rows = records(reads, current)
    task = item(rows, "task")
    initial_task = task
    current, _, _ = apply_issued(store, codec, current, "jd_set_text", {
        "target_field_ref": field(rows, "description", task["item_ref"])["field_ref"],
        "text": "只檢查授權範圍；未知不補造。", "basis_refs": []})
    rows = records(reads, current)
    task = item(rows, "task")
    assert task["item_id"] == initial_task["item_id"]
    assert task["item_ref"] != initial_task["item_ref"]
    before = current.domain
    current, _, _ = apply_issued(store, codec, current, "jd_move_item", {
        "target_ref": task["item_ref"], "destination_container_ref": container(rows, "task")["container_ref"],
        "after_ref": None, "content_changes": []})
    identity = decode(codec, task["item_ref"], current.document_id, "item").entity_id
    assert current.domain["tasks"][identity]["duty_id"] is None
    assert current.domain["tasks"][identity]["description"] == "只檢查授權範圍；未知不補造。"
    assert current.domain["details"] == before["details"] and current.domain["duties"] == before["duties"]
    moved = item(records(reads, current), "task")
    assert moved["item_id"] == task["item_id"] == identity
    assert moved["item_ref"] != task["item_ref"]
    assert moved["container_ref"] != task["container_ref"]
    assert_complete_projection(records(reads, current), current, codec, purpose="current")


def test_history_pages_reassemble_old_fields_and_original_producer_refs(reads, store, codec, rich):
    index, index_pages = pages(reads, rich.document_id, "history")
    assert len(index_pages) > 1
    assert [row["revision_number"] for row in index] == list(range(rich.revision_number, 0, -1))
    head_entry = index[0]
    old_rows, old_pages = pages(reads, rich.document_id, "history", head_entry["revision_ref"])
    assert len(old_pages) > 1 and all(page["access"] == "history" for page in old_pages)
    assert_complete_projection(old_rows, rich, codec, purpose="history")
    rows = records(reads, rich)
    newer, new_intent, new_saved = apply_issued(store, codec, rich, "jd_set_text", {
        "target_field_ref": field(rows, "purpose")["field_ref"], "text": "新的目的", "basis_refs": []})
    original = reads.history.read_revision(rich.document_id, rich.revision_id)
    operation = decode(codec, head_entry["operation_ref"], rich.document_id, "operation")
    change_ref = decode(codec, head_entry["change_ref"], rich.document_id, "change")
    revision_ref = decode(codec, head_entry["revision_ref"], rich.document_id, "revision")
    assert operation.entity_id == change_ref.entity_id == str(original.producer_operation_id)
    assert change_ref.revision_id == revision_ref.revision_id == str(rich.revision_id)
    pair = reads.history.read_change(rich.document_id, UUID(operation.entity_id))
    assert pair.result.revision_id == rich.revision_id != newer.revision_id
    assert pair.receipt.result_revision_id == rich.revision_id
    fresh_index, _ = pages(reads, rich.document_id, "history")
    new_operation = decode(codec, fresh_index[0]["operation_ref"], rich.document_id, "operation")
    new_change = decode(codec, fresh_index[0]["change_ref"], rich.document_id, "change")
    assert new_operation.entity_id == new_change.entity_id == str(new_intent.operation_id)
    assert new_change.revision_id == str(new_saved.receipt.result_revision_id) == str(newer.revision_id)
    assert new_operation.entity_id != operation.entity_id
    again, _ = pages(reads, rich.document_id, "history", head_entry["revision_ref"])
    assert_complete_projection(again, rich, codec, purpose="history")
    initial = index[-1]
    assert initial["origin"] == "initial" and initial["operation_ref"] is None and initial["change_ref"] is None


@pytest.mark.parametrize("status", ["committed", "no_change"])
def test_original_receipt_revision_normalizes_through_history_without_writable_scope(reads, store, codec, current, status):
    """Observation refs differ textually; ordinary history reads normalize them."""
    initial_rows = records(reads, current)
    text = "自己的工作與必要範圍" if status == "committed" else None
    command = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": field(initial_rows, "purpose")["field_ref"], "text": text, "basis_refs": []}}
    context = command_context(current.domain, command, codec, lambda *_: None, lambda: str(uuid4()))
    intent = bind_edit(operation_id=uuid4(), origin="manual", ai_run_id=None, command=command, context=context)
    store.authority.admit(intent)
    saved = store.execute(intent)
    assert saved.confirmed and saved.status == status
    result = project_observation(saved, codec)
    current = store.read_current(current.document_id)
    current_page = reads.read(current.document_id, request())
    # The browser's former direct-token comparison reports a false conflict.
    assert result["result_revision_ref"] != current_page["revision_ref"]
    historical_rows, historical_pages = pages(reads, current.document_id, "history", result["result_revision_ref"])
    canonical = historical_pages[0]["revision_ref"]
    assert all(page["revision_ref"] == canonical == current_page["revision_ref"]
               and page["access"] == "history" for page in historical_pages)
    assert field(historical_rows, "purpose")["value"] == text
    forbidden = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": field(historical_rows, "purpose")["field_ref"], "text": "不能用歷史寫", "basis_refs": []}}
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(current.domain, forbidden, codec, lambda *_: None, lambda: str(uuid4()))
    current_rows = records(reads, current)
    newer, _, _ = apply_issued(store, codec, current, "jd_set_text", {
        "target_field_ref": field(current_rows, "purpose")["field_ref"], "text": "後來補充的不同版本", "basis_refs": []})
    later_rows, later_pages = pages(reads, current.document_id, "history", result["result_revision_ref"])
    assert field(later_rows, "purpose")["value"] == text
    assert all(page["revision_ref"] == canonical for page in later_pages)
    assert reads.read(current.document_id, request())["revision_ref"] != canonical
    assert reads.history.read_change(current.document_id, intent.operation_id).receipt.result_revision_id == current.revision_id
    assert newer.revision_id != current.revision_id
    assert project_observation(saved, codec) == result


@pytest.mark.parametrize("role", ["field", "item", "container"])
def test_history_references_cannot_write_even_when_the_revision_is_current(reads, store, codec, rich, role):
    index, _ = pages(reads, rich.document_id, "history")
    rows, _ = pages(reads, rich.document_id, "history", index[0]["revision_ref"])
    if role == "field":
        ref = field(rows, "purpose")["field_ref"]
        command = {"tool": "jd_set_text", "arguments": {"target_field_ref": ref, "text": "不應保存", "basis_refs": []}}
    elif role == "item":
        ref = item(rows, "task")["item_ref"]
        command = {"tool": "jd_delete_item", "arguments": {"target_ref": ref, "content_changes": []}}
    else:
        ref = container(rows, "task")["container_ref"]
        command = {"tool": "jd_create_task", "arguments": task_args(ref)}
    assert decode(codec, ref, rich.document_id, role).revision_id == str(rich.revision_id)
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(rich.domain, command, codec, lambda token, doc: Source(doc), lambda: str(uuid4()))
    assert store.read_current(rich.document_id).snapshot == rich.snapshot


def test_new_head_stales_current_cursor_but_history_index_item_section_and_cursor_continue(reads, store, codec, rich):
    current_first = reads.read(rich.document_id, request())
    index_first = reads.read(rich.document_id, request("history"))
    assert current_first["has_more"] and index_first["has_more"]
    revision = index_first["records"][0]["revision_ref"]
    historical_rows, _ = pages(reads, rich.document_id, "history", revision)
    task_ref = item(historical_rows, "task")["item_ref"]
    section_ref = next(row["section_ref"] for row in historical_rows
                       if row["type"] == "section" and row["title"] == "職責與任務")
    historical_first = {view: reads.read(rich.document_id, request(view, target))
                        for view, target in (("history", revision), ("item", task_ref), ("section", section_ref))}
    assert all(page["has_more"] for page in historical_first.values())
    rows = records(reads, rich)
    newer, _, _ = apply_issued(store, codec, rich, "jd_set_text", {
        "target_field_ref": field(rows, "purpose")["field_ref"], "text": "新 head", "basis_refs": []})
    with pytest.raises(ReadError, match="stale_view"):
        reads.read(rich.document_id, request(cursor=current_first["next_cursor"]))
    with pytest.raises(ReadError, match="stale_view"):
        command_context(newer.domain, {"tool": "jd_set_text", "arguments": {
            "target_field_ref": field(rows, "purpose")["field_ref"], "text": "過時引用不可重送", "basis_refs": []}},
            codec, lambda token, doc: Source(doc), lambda: str(uuid4()))
    for view, target in (("history", revision), ("item", task_ref), ("section", section_ref)):
        old, received = pages(reads, rich.document_id, view, target, historical_first[view])
        assert all(decode(codec, page["revision_ref"], rich.document_id, "revision").revision_id == str(rich.revision_id)
                   for page in received)
        assert all(page["access"] == "history" for page in received)
        if view == "history":
            assert_complete_projection(old, rich, codec, purpose="history")
        else:
            assert item(old, "task") and len([row for row in old if row["type"] == "task_capability"]) == 2
    old_index, _ = pages(reads, rich.document_id, "history", first=index_first)
    assert [row["revision_number"] for row in old_index] == list(range(rich.revision_number, 0, -1))
    fresh_index, _ = pages(reads, rich.document_id, "history")
    assert fresh_index[0]["revision_number"] == newer.revision_number


def test_other_document_tokens_are_rejected_before_write_and_history_read(reads, store, codec, rich):
    other = store.read_current(store.create_document(uuid4(), "不同文件"))
    rows = records(reads, rich)
    command = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": field(rows, "purpose")["field_ref"], "text": "不可跨文件", "basis_refs": []}}
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(other.domain, command, codec, lambda token, doc: Source(doc), lambda: str(uuid4()))
    with pytest.raises(ReadError, match="invalid_ref"):
        reads.read(other.document_id, request("item", item(rows, "task")["item_ref"]))
    index = reads.read(rich.document_id, request("history"))
    with pytest.raises(ReadError, match="invalid_ref"):
        reads.read(other.document_id, request("history", index["records"][0]["revision_ref"]))
    with pytest.raises(ReadError, match="invalid_ref"):
        reads.read(other.document_id, request("history", cursor=index["next_cursor"]))
    assert store.read_current(other.document_id).snapshot == other.snapshot


@pytest.mark.parametrize("source", [Source("another-document"), None, "unavailable"])
def test_source_owner_rejection_cannot_create_a_bound_operation(reads, store, codec, rich, source):
    rows = records(reads, rich)
    command = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": field(rows, "purpose")["field_ref"], "text": "不能以錯誤來源保存", "basis_refs": ["qa:private"]}}
    before = dict(store.authority.bound)
    resolved = Source(rich.document_id, readable=False) if source == "unavailable" else source
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(rich.domain, command, codec, lambda token, doc: resolved, lambda: str(uuid4()))
    assert store.authority.bound == before
    assert store.read_current(rich.document_id).snapshot == rich.snapshot


def test_saved_basis_becomes_needs_recheck_after_manual_edit_without_rewriting_history(reads, store, codec, rich, engine):
    rows = records(reads, rich)
    task = item(rows, "task")
    task_sources = [row for row in rows if row["type"] == "source" and row["target_ref"] == task["item_ref"]]
    assert task_sources and all(row["basis_status"] == "current" for row in task_sources)
    original_links = rich.domain["source_links"]
    seen = []
    def resolver(token, doc):
        assert engine.pool.checkedout() == 0, "The JD read transaction must end before source-owner I/O."
        seen.append((token, doc))
        return Source(doc)
    newer, _, _ = apply_issued(store, codec, rich, "jd_set_text", {
        "target_field_ref": field(rows, "description", task["item_ref"])["field_ref"],
        "text": "人工更正：只在安全隔離後檢查。", "basis_refs": []}, resolver)
    assert seen == [] and newer.domain["source_links"] == original_links
    after = records(reads, newer)
    task_after = item(after, "task")
    after_sources = [row for row in after if row["type"] == "source" and row["target_ref"] == task_after["item_ref"]]
    assert all(row["basis_status"] == "needs_recheck" and row["readability"] == "not_checked" for row in after_sources)
    historical = reads.history.read_revision(rich.document_id, rich.revision_id)
    assert historical.snapshot == rich.snapshot
    # Explicit source refresh happens only after materialization; history stays immutable.
    refreshed, _, _ = apply_issued(store, codec, newer, "jd_set_text", {
        "target_field_ref": field(after, "description", task_after["item_ref"])["field_ref"],
        "text": "人工更正：只在安全隔離後檢查。", "basis_refs": ["qa:1"]}, resolver)
    assert seen == [("qa:1", rich.document_id)]
    refreshed_rows = records(reads, refreshed)
    refreshed_task = item(refreshed_rows, "task")
    refreshed_source = next(row for row in refreshed_rows if row["type"] == "source"
                            and row["target_ref"] == refreshed_task["item_ref"] and row["related_capability_ref"] is None)
    assert refreshed_source["basis_status"] == "current"
    assert reads.history.read_revision(rich.document_id, rich.revision_id).snapshot == rich.snapshot
