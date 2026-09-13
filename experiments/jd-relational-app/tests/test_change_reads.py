"""Original-operation change pages, with exact historical fields and no writable refs."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID
from pathlib import Path
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from jd_relational.change_reads import ChangeReadService
from jd_relational.generated.reads import ChangeReadPage
from jd_relational.domain import CommandContext, Ref, build_candidate
from jd_relational.references import ReferenceCodec, SignedReference, ReadCursor
from jd_relational.reads import ReadError, command_context, read_json
from jd_relational.snapshots import snapshot_from_domain, snapshot_digest, empty_domain
from jd_relational.storage.history import ChangeMaterial, HistoricalRevision, HistoryError
from jd_relational.storage.receipts import SavedOperation, body_for
from test_snapshots import complete_domain, uid
from test_changes import ordered_tasks

DOC, BASE, RESULT, OP = "document-a", uid(900), uid(901), uid(950)
NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


@pytest.fixture
def codec():
    return ReferenceCodec(b"change-projection-synthetic-key-0000", "dataset")


def material(before=None, after=None, status="committed"):
    before = complete_domain() if before is None else before
    if after is None:
        after = deepcopy(before)
        after["tasks"][uid(3)]["description"] = "更正繁中😀\n完整說明與 e\u0301  "
    left, right = snapshot_from_domain(before), snapshot_from_domain(after)
    base = HistoricalRevision(DOC, UUID(BASE), 1, None, "initial", NOW, None, 3, "jd-relational-v1", snapshot_digest(left), left)
    result = HistoricalRevision(DOC, UUID(RESULT), 2, UUID(BASE), "manual", NOW, UUID(OP), 3, "jd-relational-v1", snapshot_digest(right), right)
    receipt = SavedOperation(DOC, UUID(OP), "a" * 64, "manual", None, UUID(BASE),
        UUID(RESULT) if status == "committed" else UUID(BASE) if status == "no_change" else None,
        status, body_for("jd_revise_work", status), NOW)
    return ChangeMaterial(receipt, base if status in {"committed", "no_change"} else None,
                          result if status == "committed" else base if status == "no_change" else None)


class History:
    def __init__(self, value):
        self.value, self.calls = value, []

    def read_change(self, document_id, operation_id):
        self.calls.append((document_id, operation_id))
        assert document_id == DOC and operation_id == UUID(OP)
        return self.value


def change_ref(codec, revision=RESULT, operation=OP):
    return codec.issue(SignedReference(document_id=DOC, revision_id=revision, purpose="observation",
        role="change", kind="change", entity_id=operation))


def all_pages(service, token):
    result, pages, cursor = [], [], None
    while True:
        page = service.read(DOC, {"change_ref": token, "cursor": cursor})
        assert page["start_index"] == len(result)
        pages.append(page)
        result.extend(page["records"])
        assert page["has_more"] == (page["next_cursor"] is not None)
        if not page["has_more"]:
            assert len(result) == page["total_records"]
            return result, pages
        cursor = page["next_cursor"]
        assert len(pages) < 2000


def test_changed_item_full_before_after_fields_use_original_history_only_refs(codec):
    history = History(material())
    rows, pages = all_pages(ChangeReadService(history, codec, page_bytes=6000), change_ref(codec))
    assert pages[0]["total_changes"] == 1 and len(pages) > 1
    headers = [row for row in rows if row["type"] == "change"]
    assert headers == [{"type": "change", "change_index": 0, "kind": "update", "entity_kind": "task",
                        "before_exists": True, "after_exists": True, "changed_fields": ["description"]}]
    fields = [row for row in rows if row["type"] == "value" and row["record"]["type"] == "field"]
    assert len(fields) == 4
    assert next(row["record"]["value"] for row in fields if row["side"] == "after" and row["record"]["name"] == "description") == "更正繁中😀\n完整說明與 e\u0301  "
    for row in fields:
        ref = codec.resolve(row["record"]["field_ref"], document_id=DOC, roles={"field"}, purposes={"history"})
        assert ref.revision_id == (BASE if row["side"] == "before" else RESULT)
        with pytest.raises(ReadError, match="invalid_ref"):
            command_context(history.value.result.domain,
                {"tool": "jd_set_text", "arguments": {"target_field_ref": row["record"]["field_ref"], "text": "不得寫歷史", "basis_refs": []}},
                codec, lambda *_: None, lambda: uid(980))
    assert all(call == (DOC, UUID(OP)) for call in history.calls)
    items = [row for row in rows if row["type"] == "value" and row["record"]["type"] == "item"]
    assert len(items) == 2 and {row["record"]["item_id"] for row in items} == {uid(3)}
    assert len({row["record"]["item_ref"] for row in items}) == 2
    assert all(page["format_version"] == 2 for page in pages)


@pytest.mark.parametrize("version", [1, True, 3])
def test_change_v2_source_and_generated_schemas_refuse_old_or_invalid_versions(codec, version):
    page = ChangeReadService(History(material()), codec).read(DOC, {"change_ref": change_ref(codec), "cursor": None})
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-read.schema.json").read_text(encoding="utf-8"))
    source = {"$defs": schema["$defs"], "$ref": "#/$defs/ChangeReadPage"}
    assert Draft202012Validator(source).is_valid(page)
    page["format_version"] = version
    assert not Draft202012Validator(source).is_valid(page)
    assert not Draft202012Validator(ChangeReadPage.model_json_schema()).is_valid(page)
    with pytest.raises(ValidationError):
        ChangeReadPage.model_validate(page, strict=True)


def test_long_fields_are_never_truncated_and_affected_tasks_are_individually_paged(codec):
    before = complete_domain()
    after = deepcopy(before)
    after["capabilities"][uid(10)]["description"] = "繁" * (65536 // 3)
    for number in range(100, 160):
        identity = uid(number)
        after["tasks"][identity] = {"task_id": identity, "duty_id": None, "name": "同名任務", "description": None, "position": number}
        after["task_capabilities"].append({"task_id": identity, "capability_id": uid(10), "position": 0})
    rows, pages = all_pages(ChangeReadService(History(material(before, after)), codec, page_bytes=4096), change_ref(codec))
    assert any(page["oversized_unit"] for page in pages)
    assert all(len(page["records"]) == 1 if page["oversized_unit"] else len(read_json(page).encode()) <= 4096 for page in pages)
    header = next(row for row in rows if row["type"] == "change" and row["entity_kind"] == "capability")
    impact = [row for row in rows if row["type"] == "affected_task" and row["change_index"] == header["change_index"]]
    assert len(impact) == 62
    texts = [row["record"]["value"] for row in rows if row["type"] == "value" and row["record"]["type"] == "field"]
    assert after["capabilities"][uid(10)]["description"] in texts


def test_source_basis_digest_and_position_changes_are_explicit_even_if_status_stays_same(codec):
    before = complete_domain()
    after = deepcopy(before)
    after["source_links"][7]["basis_digest"] = "b" * 64
    rows, _ = all_pages(ChangeReadService(History(material(before, after)), codec), change_ref(codec))
    sources = [row for row in rows if row["type"] == "source_value"]
    assert [(row["side"], row["basis_digest"], row["position"]) for row in sources] == [("before", "a" * 64, 0), ("after", "b" * 64, 0)]
    assert all(row["record"]["basis_status"] == "needs_recheck" and row["record"]["readability"] == "not_checked" for row in sources)


def test_d01_move_retains_owned_content_and_exposes_both_parent_contexts(codec):
    before = complete_domain()
    context = CommandContext(DOC, BASE, {"duty": Ref(DOC, BASE, "duty", uid(2))}, {}, lambda: uid(990))
    after = build_candidate(before, {"tool": "jd_delete_item", "arguments": {"target_ref": "duty", "content_changes": []}}, context)
    rows, _ = all_pages(ChangeReadService(History(material(before, after)), codec), change_ref(codec))
    moved = next(row for row in rows if row["type"] == "change" and row["kind"] == "move")
    placements = [row for row in rows if row["type"] == "item_placement" and row["change_index"] == moved["change_index"]]
    assert len(placements) == 2
    parents = [codec.resolve(row["container_ref"], document_id=DOC, roles={"container"}, purposes={"history"}).entity_id for row in placements]
    assert parents == [uid(2), None]
    assert not any(row["type"] == "change" and row["entity_kind"] == "detail" for row in rows)


def test_reorder_with_same_raw_position_has_actual_neighbor_context(codec):
    before = ordered_tasks(3)
    after = deepcopy(before)
    for row in after["tasks"].values():
        row["position"] = 2 - row["position"]
    rows, _ = all_pages(ChangeReadService(History(material(before, after)), codec), change_ref(codec))
    middle = next(row for row in rows if row["type"] == "change" and row["changed_fields"] == [])
    context = [row for row in rows if row["type"] == "item_placement" and row["change_index"] == middle["change_index"]]
    resolved = [[codec.resolve(row[key], document_id=DOC, roles={"item"}, purposes={"history"}).entity_id
                 for key in ("previous_item_ref", "next_item_ref")] for row in context]
    assert resolved == [[uid(100), uid(102)], [uid(102), uid(100)]]


def test_position_renumber_only_is_not_fabricated_content_change(codec):
    before = ordered_tasks(3)
    after = deepcopy(before)
    for row in after["tasks"].values():
        row["position"] += 20
    rows, pages = all_pages(ChangeReadService(History(material(before, after)), codec), change_ref(codec))
    assert rows == [] and len(pages) == 1 and pages[0]["total_changes"] == 0


@pytest.mark.parametrize("status", ["no_change", "invalid_input", "save_failed"])
def test_nonchanging_operations_never_gain_a_public_change_page(codec, status):
    with pytest.raises(ReadError, match="invalid_ref"):
        ChangeReadService(History(material(status=status)), codec).read(DOC, {"change_ref": change_ref(codec), "cursor": None})


@pytest.mark.parametrize("bad", [{"change_ref": "x"}, {"change_ref": "x", "cursor": None, "document_id": DOC}, {"change_ref": None, "cursor": None}])
def test_closed_two_argument_input_rejects_model_context(codec, bad):
    history = History(material())
    with pytest.raises(ReadError, match="invalid_input"):
        ChangeReadService(history, codec).read(DOC, bad)
    assert history.calls == []


def test_cursor_binds_original_operation_and_result_and_does_not_consult_current(codec):
    history = History(material())
    service = ChangeReadService(history, codec, page_bytes=4096)
    first = service.read(DOC, {"change_ref": change_ref(codec), "cursor": None})
    cursor = codec.resolve_cursor(first["next_cursor"], document_id=DOC, view="change", operation_id=OP, revision_id=RESULT)
    second = service.read(DOC, {"change_ref": change_ref(codec), "cursor": first["next_cursor"]})
    assert second["start_index"] == cursor.offset
    bad = codec.issue_cursor(ReadCursor(document_id=DOC, view="change", revision_id=RESULT, operation_id=uid(951), offset=cursor.offset))
    with pytest.raises(ReadError, match="invalid_ref"):
        service.read(DOC, {"change_ref": change_ref(codec), "cursor": bad})


@pytest.mark.parametrize("failure", ["codec", "dto", "stored"])
def test_internal_projection_or_history_fault_is_not_mislabeled_as_bad_caller_input(codec, monkeypatch, failure):
    import jd_relational.change_reads as implementation
    history = History(material())
    token = change_ref(codec)
    if failure == "codec":
        monkeypatch.setattr(ReferenceCodec, "issue", lambda *_: (_ for _ in ()).throw(ValueError("private signer error")))
    elif failure == "dto":
        monkeypatch.setattr(implementation.ChangeReadPage, "model_validate", lambda *_a, **_kw: (_ for _ in ()).throw(ValueError("private DTO error")))
    else:
        history.read_change = lambda *_: (_ for _ in ()).throw(HistoryError("stored_content_mismatch"))
    with pytest.raises(ReadError, match="^read_failed$") as error:
        ChangeReadService(history, codec).read(DOC, {"change_ref": token, "cursor": None})
    assert error.value.__suppress_context__


@pytest.mark.parametrize("direction", ["create", "delete"])
def test_all_entity_fields_and_associations_are_complete_across_pages(codec, direction):
    from jd_relational.domain import COLLECTIONS, FIELDS
    blank, full = empty_domain(DOC, BASE), complete_domain()
    before, after = (blank, full) if direction == "create" else (full, blank)
    rows, pages = all_pages(ChangeReadService(History(material(before, after)), codec, page_bytes=8192), change_ref(codec))
    assert len(pages) > 2
    for side_name, expected in (("before", before), ("after", after)):
        values = [r["record"] for r in rows if r["type"] == "value" and r["side"] == side_name]
        fields = [r for r in values if r["type"] == "field"]
        actual = {}
        for field in fields:
            target = codec.resolve(field["field_ref"], document_id=DOC, roles={"field"}, purposes={"history"})
            actual[(target.kind, target.entity_id, target.field)] = field["value"]
        expected_fields = {("profile", None, name): value for name, value in expected["profile"].items()}
        expected_fields.update({(kind, identity, name): row[name] for kind, collection in COLLECTIONS.items()
                               for identity, row in expected[collection].items() for name in FIELDS[kind]})
        assert actual == expected_fields
        assert len([r for r in values if r["type"] == "task_capability"]) == len(expected["task_capabilities"])
        sources = [r for r in rows if r["type"] == "source_value" and r["side"] == side_name]
        assert len(sources) == len(expected["source_links"])
        assert {r["record"]["source_ref"] for r in sources} == {r["source_ref"] for r in expected["source_links"]}
    assert {r["entity_kind"] for r in rows if r["type"] == "change"} == {
        "profile", "collaborator", "duty", "task", "detail", "capability", "condition", "task_capability", "source_link"}
    assert all(not field.endswith("_id") for r in rows if r["type"] == "change" for field in r["changed_fields"])


@pytest.mark.parametrize("kind", ["relation", "source"])
def test_relation_and_source_reorder_with_equal_position_retains_exact_neighbors(codec, kind):
    before = complete_domain()
    if kind == "relation":
        before["capabilities"][uid(11)] = {"capability_id": uid(11), "kind": "skill", "name": "同名", "description": None, "position": 1}
        before["task_capabilities"].append({"task_id": uid(3), "capability_id": uid(11), "position": 2})
        group = [r for r in before["task_capabilities"] if r["task_id"] == uid(3)]
        field, identity, type_name = "capability_id", uid(10), "relation_placement"
    else:
        original = before["source_links"][3]
        before["source_links"] += [{**original, "source_link_id": uid(60 + i), "source_ref": f"source-extra-{i}", "position": i + 1} for i in range(2)]
        group = [r for r in before["source_links"] if r["task_id"] == uid(3)]
        field, identity, type_name = "source_link_id", uid(60), "source_placement"
    after = deepcopy(before)
    target_group = after["task_capabilities"] if kind == "relation" else after["source_links"]
    keys = {r[field] for r in group}
    for row in target_group:
        if row[field] in keys and row.get("task_id") == uid(3):
            row["position"] = 2 - row["position"]
    rows, _ = all_pages(ChangeReadService(History(material(before, after)), codec, page_bytes=8192), change_ref(codec))
    header = next(r for r in rows if r["type"] == "change" and r["kind"] == "reorder" and r["changed_fields"] == [])
    placements = [r for r in rows if r["type"] == type_name and r["change_index"] == header["change_index"]]
    if kind == "relation":
        neighbors = [[codec.resolve(r[k], document_id=DOC, roles={"item"}, purposes={"history"}).entity_id
                      for k in ("previous_capability_ref", "next_capability_ref")] for r in placements]
        assert neighbors == [[uid(9), uid(11)], [uid(11), uid(9)]]
    else:
        assert [[r["previous_source_ref"], r["next_source_ref"]] for r in placements] == [
            ["issued-source-3", "source-extra-1"], ["source-extra-1", "issued-source-3"]]


def test_text_change_does_not_invent_source_link_mutation(codec):
    from jd_relational.domain import source_basis_digest, source_target
    before = complete_domain()
    link = before["source_links"][3]
    link["basis_digest"] = source_basis_digest(before, source_target(link))
    after = deepcopy(before)
    after["tasks"][uid(3)]["description"] = "更正正文而未重申來源"
    rows, _ = all_pages(ChangeReadService(History(material(before, after)), codec), change_ref(codec))
    assert not any(r["type"] == "source_value" or r["type"] == "change" and r["entity_kind"] == "source_link" for r in rows)


@pytest.mark.parametrize("wrong", ["document", "dataset", "role", "revision", "end_cursor"])
def test_wrong_scope_and_out_of_range_cursor_never_resolve_to_current(codec, wrong):
    history = History(material())
    service = ChangeReadService(history, codec)
    token, document, cursor = change_ref(codec), DOC, None
    if wrong == "document":
        document = "other-document"
    elif wrong == "dataset":
        token = change_ref(ReferenceCodec(b"change-projection-synthetic-key-0000", "other-dataset"))
    elif wrong == "role":
        token = codec.issue(SignedReference(document_id=DOC, revision_id=RESULT, purpose="history", role="revision", kind="revision"))
    elif wrong == "revision":
        token = change_ref(codec, revision=uid(902))
    else:
        first = service.read(DOC, {"change_ref": token, "cursor": None})
        cursor = codec.issue_cursor(ReadCursor(document_id=DOC, view="change", revision_id=RESULT, operation_id=OP, offset=first["total_records"]))
    with pytest.raises(ReadError, match="^invalid_ref$"):
        service.read(document, {"change_ref": token, "cursor": cursor})
    if wrong in {"document", "dataset", "role"}:
        assert not history.calls


def test_repeated_locator_signing_is_reused_only_inside_one_projection(codec, monkeypatch):
    from jd_relational.reads import content_projection
    original, issued = ReferenceCodec.issue, []
    def counted(self, ref):
        issued.append(ref)
        return original(self, ref)
    monkeypatch.setattr(ReferenceCodec, "issue", counted)
    snapshot = complete_domain()
    projection = content_projection(snapshot, codec, "history")
    token = projection.token("field", "task", uid(3), "description")
    assert projection.token("field", "task", uid(3), "description") == token
    assert len(issued) == 1
    # Neither another request nor another version/text shares retained tokens.
    changed = deepcopy(snapshot)
    changed["revision"] = RESULT
    changed["tasks"][uid(3)]["description"] = "另一版文字"
    other = content_projection(changed, codec, "history")
    assert other.token("field", "task", uid(3), "description") != token
    assert len(issued) == 2
