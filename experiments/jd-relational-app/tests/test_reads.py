"""Real generated read projection and signed locators; no model or HTTP host."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4
import json
import pytest

from test_snapshots import complete_domain, uid
from jd_relational.references import ReferenceCodec, SignedReference
from jd_relational.snapshots import empty_domain, snapshot_from_domain
from jd_relational.reads import ReadService, ReadError, command_context
from jd_relational.domain import Source, build_candidate
from jd_relational.intents import bind_edit


class CurrentReader:
    def __init__(self, value):
        self.value = value

    def read_current(self, document_id):
        assert document_id == self.value["document_id"]
        return SimpleNamespace(
            snapshot=snapshot_from_domain(self.value), revision_id=UUID(self.value["revision"])
        )


@pytest.fixture
def codec():
    return ReferenceCodec(b"synthetic-only-signing-material-0000", "test-dataset")


def reader(value, codec, size=12000):
    current = CurrentReader(value)
    return ReadService(current, None, codec, page_bytes=size), current


def all_pages(service, doc, view="current", target=None):
    records, cursor, pages = [], None, []
    while True:
        page = service.read(doc, {"view": view, "target_ref": target, "cursor": cursor})
        pages.append(page)
        records.extend(page["records"])
        assert page["has_more"] == (page["next_cursor"] is not None)
        if not page["has_more"]:
            return records, pages
        cursor = page["next_cursor"]
        assert len(pages) < 1000


def test_complete_read_preserves_fields_relations_sources_and_display_identity(codec):
    value = complete_domain()
    service, _ = reader(value, codec)
    records, pages = all_pages(service, value["document_id"])
    assert len([r for r in records if r["type"] == "section"]) == 6
    assert len([r for r in records if r["type"] == "task_capability"]) == 3
    sources = [r for r in records if r["type"] == "source"]
    assert len(sources) == 8 and all(r["readability"] == "not_checked" for r in sources)
    expected = list(value["profile"].values())
    from jd_relational.domain import COLLECTIONS, FIELDS

    for kind, collection in COLLECTIONS.items():
        expected += [row[name] for row in value[collection].values() for name in FIELDS[kind]]
    actual = [r["value"] for r in records if r["type"] == "field"]
    assert sorted(map(repr, expected)) == sorted(map(repr, actual))
    assert len(pages) > 1
    assert all(
        len(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode()) <= 12000
        for p in pages
    )
    items = [r for r in records if r["type"] == "item"]
    assert {r["item_id"] for r in items} == {
        identity for collection in COLLECTIONS.values() for identity in value[collection]
    }
    assert all(set(r).isdisjoint({"item_id", "section_key"}) for r in records
               if r["type"] not in {"item", "section"})


def test_display_identity_survives_real_task_move_and_field_edit_but_refs_do_not(codec):
    value = complete_domain()
    service, current = reader(value, codec)
    original, _ = all_pages(service, "document-a")
    task = next(r for r in original if r["type"] == "item" and r["item_id"] == uid(3))
    unassigned = next(r for r in original if r["type"] == "container"
                      and r["child_kind"] == "task" and r["owner_ref"] is None)
    move = {"tool": "jd_move_item", "arguments": {
        "target_ref": task["item_ref"], "destination_container_ref": unassigned["container_ref"],
        "after_ref": None, "content_changes": []}}
    current.value = build_candidate(value, move, command_context(value, move, codec, lambda *_: None, lambda: str(uuid4())))
    current.value["revision"] = uid(902)
    moved, _ = all_pages(service, "document-a")
    moved_task = next(r for r in moved if r["type"] == "item" and r["item_id"] == uid(3))
    name = next(r for r in moved if r["type"] == "field" and r["item_ref"] == moved_task["item_ref"] and r["name"] == "name")
    edit = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": name["field_ref"], "text": "更正後名稱", "basis_refs": []}}
    current.value = build_candidate(current.value, edit, command_context(current.value, edit, codec, lambda *_: None, lambda: str(uuid4())))
    current.value["revision"] = uid(903)
    edited, _ = all_pages(service, "document-a")
    for rows in (moved, edited):
        assert {r["item_id"] for r in rows if r["type"] == "item"} == {
            r["item_id"] for r in original if r["type"] == "item"}
        assert {r["section_key"] for r in rows if r["type"] == "section"} == {
            "profile", "purpose", "duties_tasks", "knowledge", "skills", "conditions"}
        assert {r["item_ref"] for r in rows if r["type"] == "item"}.isdisjoint(
            r["item_ref"] for r in original if r["type"] == "item")
    assert moved_task["container_ref"] != task["container_ref"]
    assert current.value["tasks"][uid(3)]["duty_id"] is None
    assert current.value["tasks"][uid(3)]["name"] == "更正後名稱"
    with pytest.raises(ReadError, match="invalid_ref"):
        bad = {**move, "arguments": {**move["arguments"], "target_ref": uid(3)}}
        command_context(current.value, bad, codec, lambda *_: None, lambda: str(uuid4()))


def test_empty_document_exposes_all_sections_profile_fields_and_root_containers(codec):
    value = empty_domain("document-a", uid(901))
    service, _ = reader(value, codec)
    records, _ = all_pages(service, "document-a")
    assert len([r for r in records if r["type"] == "field"]) == 5
    containers = [r["child_kind"] for r in records if r["type"] == "container"]
    assert set(containers) == {
        "duty",
        "task",
        "collaborator",
        "knowledge",
        "skill",
        "work_environment",
        "schedule_travel",
        "shared_authority",
        "shared_collaboration",
        "qualification",
    }


def test_long_allowed_field_is_complete_on_explicit_oversized_page(codec):
    value = empty_domain("document-a", uid(901))
    value["profile"]["purpose"] = "繁" * (65536 // 3)
    service, _ = reader(value, codec, size=5000)
    records, pages = all_pages(service, "document-a")
    oversize = [p for p in pages if p["oversized_unit"]]
    assert len(oversize) == 1 and len(oversize[0]["records"]) == 1
    assert [r["value"] for r in records if r["type"] == "field" and r["name"] == "purpose"] == [
        value["profile"]["purpose"]
    ]


def test_current_cursor_refuses_new_head_and_invalid_shape(codec):
    service, source = reader(complete_domain(), codec, 5000)
    first = service.read("document-a", {"view": "current", "target_ref": None, "cursor": None})
    source.value = deepcopy(source.value)
    source.value["revision"] = uid(999)
    with pytest.raises(ReadError, match="stale_view"):
        service.read(
            "document-a", {"view": "current", "target_ref": None, "cursor": first["next_cursor"]}
        )
    with pytest.raises(ReadError, match="invalid_input"):
        service.read("document-a", {"view": "current", "target_ref": None})


@pytest.mark.parametrize("fault", ["ref_issuer", "output_schema"])
def test_internal_projection_failure_does_not_blame_caller(codec, monkeypatch, fault):
    from jd_relational import reads
    from jd_relational.references import ReferenceValidationError

    service, _ = reader(complete_domain(), codec)
    if fault == "ref_issuer":

        def broken_issuer(*args, **kwargs):
            raise ReferenceValidationError("invalid_ref")

        monkeypatch.setattr(ReferenceCodec, "issue", broken_issuer)
    else:
        monkeypatch.setattr(reads._Projection, "records", lambda *args: [{"type": "field"}])
    with pytest.raises(ReadError, match="^read_failed$"):
        service.read("document-a", {"view": "current", "target_ref": None, "cursor": None})


def test_task_item_view_includes_parent_details_shared_definitions_and_sources(codec):
    value = complete_domain()
    service, _ = reader(value, codec)
    target = codec.issue(
        SignedReference(
            document_id="document-a",
            revision_id=value["revision"],
            purpose="current",
            role="item",
            kind="task",
            entity_id=uid(3),
        )
    )
    records, _ = all_pages(service, "document-a", "item", target)
    kinds = [r["kind"] for r in records if r["type"] == "item"]
    assert kinds.count("task") == 1
    assert (
        kinds.count("duty") == 1 and kinds.count("outcome") == 2 and kinds.count("requirement") == 2
    )
    assert kinds.count("knowledge") == 1 and kinds.count("skill") == 1


def test_issued_manual_and_ai_contexts_reach_same_domain_without_exposing_context_input(codec):
    value = complete_domain()
    service, _ = reader(value, codec)
    records, _ = all_pages(service, "document-a")
    field = next(
        r
        for r in records
        if r["type"] == "field"
        and r["name"] == "description"
        and r["value"] == value["tasks"][uid(3)]["description"]
    )
    command = {
        "tool": "jd_set_text",
        "arguments": {
            "target_field_ref": field["field_ref"],
            "text": "僅於停機時檢查。",
            "basis_refs": [],
        },
    }
    context = command_context(
        value, command, codec, lambda token, doc: Source(doc), lambda: str(uuid4())
    )
    candidate = build_candidate(value, command, context)
    assert candidate["tasks"][uid(3)]["description"] == "僅於停機時檢查。"
    assert (
        bind_edit(
            operation_id=uuid4(), origin="manual", ai_run_id=None, command=command, context=context
        ).command
        == command
    )
    bad = deepcopy(command)
    ref = codec.resolve(
        field["field_ref"], document_id="document-a", roles={"field"}, purposes={"current"}
    )
    bad["arguments"]["target_field_ref"] = codec.issue(
        SignedReference(**{**ref.model_dump(), "purpose": "history"})
    )
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(value, bad, codec, lambda token, doc: Source(doc), lambda: str(uuid4()))


def test_source_owner_scope_and_saved_field_digest_are_required(codec):
    value = complete_domain()
    service, _ = reader(value, codec)
    records, _ = all_pages(service, "document-a")
    field = next(r for r in records if r["type"] == "field" and r["name"] == "purpose")
    command = {
        "tool": "jd_set_text",
        "arguments": {
            "target_field_ref": field["field_ref"],
            "text": "新內容",
            "basis_refs": ["source"],
        },
    }
    with pytest.raises(ReadError, match="invalid_ref"):
        command_context(
            value, command, codec, lambda token, doc: Source("wrong"), lambda: str(uuid4())
        )
    value["profile"]["purpose"] = "同版材料被改壞"
    with pytest.raises(ReadError, match="stale_view"):
        command_context(value, command, codec, lambda token, doc: Source(doc), lambda: str(uuid4()))
