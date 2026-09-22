"""Management inputs keep product meaning while sharing the strict wire subset."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from jd_relational.generated import models


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts/jd-work.schema.json").read_text(encoding="utf-8"))
ROOTS = {
    "create_task": "CreateTaskInput", "revise_work": "ReviseWorkInput",
    "set_text": "SetTextInput", "insert_item": "InsertItemInput",
    "delete_item": "DeleteItemInput", "move_item": "MoveItemInput",
    "set_task_capability": "SetTaskCapabilityInput",
    "replace_selection": "ReplaceSelectionInput",
    # Manual-only, and generated from the same SSOT so its shape is not
    # hand-written; it is deliberately not offered to the model.
    "restore_revision": "RestoreRevisionInput",
    "undo_ai_turn": "UndoAiTurnInput",
}
KINDS = ("duty", "collaborator", "knowledge", "skill", "outcome", "requirement", "condition")


def item(kind):
    value = {"kind": kind, "container_ref": "issued-container", "after_ref": None,
             "basis_refs": []}
    if kind in {"duty", "collaborator"}:
        value.update(name=None, scope_text="已知的合作或職責範圍。\n未確認部分不補造。")
    elif kind in {"knowledge", "skill"}:
        value.update(name=None, description="理解介面狀態並據以辨識前端問題。")
    else:
        value["text"] = "僅依已約定範圍處理；超出範圍先確認。"
    return value


def content_changes():
    return [
        {"kind": "set_field", "target_field_ref": "issued-task-description",
         "text": "只對包含月檢約定的專案按月檢查。", "basis_refs": []},
        {"kind": "add_task_detail", "task_ref": "issued-task", "detail_kind": "requirement",
         "after_ref": None, "text": "缺陷修正約定不自動擴大為月檢。", "basis_refs": []},
    ]


def management_input(name):
    return {
        "SetTextInput": {"target_field_ref": "issued-field", "text": None, "basis_refs": []},
        "InsertItemInput": {"item": item("knowledge")},
        "DeleteItemInput": {"target_ref": "issued-duty", "content_changes": content_changes()},
        "MoveItemInput": {"target_ref": "issued-task", "destination_container_ref": "issued-destination",
                          "after_ref": None, "content_changes": content_changes()},
        "SetTaskCapabilityInput": {"task_ref": "issued-task", "capability_ref": "issued-shared-skill",
                                   "mode": "unlink", "basis_refs": []},
        "ReplaceSelectionInput": {"selection_ref": "issued-selection", "replacement_text": "每季🔎\n依約定",
                                  "basis_refs": []},
        "RestoreRevisionInput": {"target_revision_id": "issued-revision"},
        "UndoAiTurnInput": {"ai_run_id": "issued-run", "expected_result_revision_id": "issued-revision"},
    }[name]


MANAGEMENT_ROOTS = tuple(name for name in ROOTS.values() if name not in {"CreateTaskInput", "ReviseWorkInput"})
# The model never sees the manual-only entries, so App-context rules that exist
# to stop a model stating what the App owns do not apply to them.
MANUAL_ONLY_ROOTS = ("RestoreRevisionInput", "UndoAiTurnInput")
MODEL_ROOTS = tuple(name for name in MANAGEMENT_ROOTS if name not in MANUAL_ONLY_ROOTS)


def accepted_by_both(name, payload, expected):
    oracle = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})
    assert oracle.is_valid(payload) is expected
    model = getattr(models, name)
    published = Draft202012Validator(model.model_json_schema(mode="validation"))
    assert published.is_valid(payload) is expected
    try:
        parsed = model.model_validate(payload, strict=True)
    except ValidationError:
        assert expected is False
    else:
        assert expected is True
        assert parsed.model_dump(mode="json") == payload


def nested_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_objects(child)


def test_catalog_has_named_closed_roots_for_every_command():
    assert SCHEMA["properties"] == {key: {"$ref": f"#/$defs/{name}"} for key, name in ROOTS.items()}
    assert set(SCHEMA["required"]) == set(ROOTS)
    Draft202012Validator.check_schema(SCHEMA)
    for name in ROOTS.values():
        root = SCHEMA["$defs"][name]
        assert root["type"] == "object" and "anyOf" not in root and "oneOf" not in root
        model = getattr(models, name)
        assert model.model_config["extra"] == "forbid"
        published = model.model_json_schema(mode="validation")
        Draft202012Validator.check_schema(published)
        assert published["type"] == "object" and "anyOf" not in published and "oneOf" not in published
        assert set(published["properties"]) == set(root["properties"])
        assert "WorkCommandCatalog" not in published.get("$defs", {})
        assert set(ROOTS.values()).isdisjoint(published.get("$defs", {}))
        for node in nested_objects(published):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
    for node in nested_objects(SCHEMA):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


@pytest.mark.parametrize("name", MANAGEMENT_ROOTS)
def test_management_payload_round_trips_without_defaults_or_coercion(name):
    accepted_by_both(name, management_input(name), True)


@pytest.mark.parametrize("kind", KINDS)
def test_insert_has_exactly_seven_distinct_item_shapes(kind):
    value = item(kind)
    accepted_by_both("InsertItemInput", {"item": value}, True)
    for key in value:
        missing = deepcopy(value)
        del missing[key]
        accepted_by_both("InsertItemInput", {"item": missing}, False)
    wrong = deepcopy(value)
    wrong["description" if kind in {"duty", "collaborator"} else "scope_text"] = None
    accepted_by_both("InsertItemInput", {"item": wrong}, False)


@pytest.mark.parametrize("name", MANAGEMENT_ROOTS)
def test_every_root_key_is_required(name):
    payload = management_input(name)
    for key in payload:
        missing = deepcopy(payload)
        del missing[key]
        accepted_by_both(name, missing, False)


@pytest.mark.parametrize("name", MODEL_ROOTS)
def test_app_context_is_rejected_in_every_model_input(name):
    """What the App owns is never something a model may state.

    The manual-only commands are excluded because they are the App's own
    entries: undoing a turn names that turn, which is what it is for, and no
    model can ask for it at all.
    """
    payload = management_input(name)
    for key in ("document_id", "base_revision", "operation_id", "ai_run_id", "position"):
        accepted_by_both(name, {**payload, key: "App owns this"}, False)


@pytest.mark.parametrize("name", ("DeleteItemInput", "MoveItemInput"))
def test_structural_adjustments_accept_only_existing_two_change_variants(name):
    payload = management_input(name)
    assert SCHEMA["$defs"][name]["properties"]["content_changes"]["items"] == {
        "anyOf": [{"$ref": "#/$defs/SetFieldChange"}, {"$ref": "#/$defs/AddTaskDetailChange"}]}
    for change in payload["content_changes"]:
        for key in change:
            missing = deepcopy(change)
            del missing[key]
            accepted_by_both(name, {**payload, "content_changes": [missing]}, False)
    forbidden = [
        {"kind": "remove_task_detail", "detail_ref": "issued-detail"},
        {"kind": "set_task_capability", "task_ref": "issued-task", "capability_ref": "issued-skill",
         "mode": "unlink", "basis_refs": []},
        {"kind": "add_condition", "container_ref": "issued-condition-container", "after_ref": None,
         "text": "不能夾帶新增全職位条件", "basis_refs": []},
        {"kind": "remove_condition", "condition_ref": "issued-condition"},
        {"kind": "jd_revise_work", "changes": content_changes()},
    ]
    for change in forbidden:
        accepted_by_both(name, {**payload, "content_changes": [change]}, False)
    accepted_by_both(name, {**payload, "content_changes": []}, True)


@pytest.mark.parametrize("kind", ("duty", "collaborator", "knowledge", "skill"))
def test_insert_nullable_does_not_make_name_or_body_mandatory(kind):
    value = item(kind)
    body = "scope_text" if kind in {"duty", "collaborator"} else "description"
    value.update(name="已知名稱", **{body: None})
    accepted_by_both("InsertItemInput", {"item": value}, True)
    value["name"] = None
    # Final meaningful-content validation belongs to the shared domain.
    accepted_by_both("InsertItemInput", {"item": value}, True)


@pytest.mark.parametrize("kind", ("outcome", "requirement", "condition"))
def test_text_items_cannot_claim_nullable_text_or_extra_name(kind):
    value = item(kind)
    accepted_by_both("InsertItemInput", {"item": {**value, "text": None}}, False)
    accepted_by_both("InsertItemInput", {"item": {**value, "name": None}}, False)


@pytest.mark.parametrize("kind", ("task", "profile", "unknown", None, 1))
def test_insert_cannot_create_task_shell_or_invent_item_kind(kind):
    value = item("knowledge")
    value["kind"] = kind
    accepted_by_both("InsertItemInput", {"item": value}, False)


def test_condition_kind_comes_from_issued_container_not_model_choice():
    value = item("condition")
    accepted_by_both("InsertItemInput", {"item": {**value, "condition_kind": "qualification"}}, False)


def test_selection_has_only_issued_selection_replacement_and_sources():
    payload = management_input("ReplaceSelectionInput")
    accepted_by_both("ReplaceSelectionInput", {**payload, "replacement_text": ""}, True)
    accepted_by_both("ReplaceSelectionInput", {**payload, "replacement_text": None}, False)
    for key in ("target_field_ref", "field_ref", "old_text", "start", "end", "offset", "block_id"):
        accepted_by_both("ReplaceSelectionInput", {**payload, key: "not model input"}, False)
    wrong = deepcopy(payload)
    wrong["target_field_ref"] = wrong.pop("selection_ref")
    accepted_by_both("ReplaceSelectionInput", wrong, False)
    text = management_input("SetTextInput")
    text["selection_ref"] = text.pop("target_field_ref")
    accepted_by_both("SetTextInput", text, False)


@pytest.mark.parametrize("mode", ("link", "unlink", "toggle", None, 1, True))
def test_relation_has_two_literal_modes(mode):
    payload = management_input("SetTaskCapabilityInput")
    payload["mode"] = mode
    accepted_by_both("SetTaskCapabilityInput", payload, mode in ("link", "unlink"))


@pytest.mark.parametrize("wrong", (1, True, {}, [], ["not text"]))
def test_management_text_refs_and_sources_do_not_coerce(wrong):
    for name, field in (("SetTextInput", "text"), ("SetTextInput", "target_field_ref"),
                        ("MoveItemInput", "after_ref"), ("ReplaceSelectionInput", "replacement_text")):
        payload = management_input(name)
        payload[field] = wrong
        accepted_by_both(name, payload, False)
    payload = management_input("SetTaskCapabilityInput")
    payload["basis_refs"] = [wrong]
    accepted_by_both("SetTaskCapabilityInput", payload, False)
