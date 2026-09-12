"""Compare source schema, published schema and generated DTO acceptance."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from jd_relational.generated.models import CreateTaskInput, ReviseWorkInput


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "jd-work.schema.json").read_text(encoding="utf-8"))
MODELS = {"CreateTaskInput": CreateTaskInput, "ReviseWorkInput": ReviseWorkInput}


def oracle(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    )


def create_task() -> dict:
    return {
        "container_ref": "container-1", "after_ref": None,
        "name": "異常診斷", "description": "在約定範圍內診斷異常。\n超出範圍轉交窗口。",
        "basis_refs": ["source-task"],
        "outcomes": [{"text": "可回查的診斷結果", "basis_refs": ["source-outcome"]}],
        "requirements": [{"text": "區分觀察與待驗假設", "basis_refs": []}],
        "capabilities": [{"capability_ref": "skill-1", "basis_refs": ["source-relation"]}],
    }


def revise_work() -> dict:
    return {"changes": [
        {"kind": "set_field", "target_field_ref": "task-description", "text": "只提供技術診斷", "basis_refs": ["source-correction"]},
        {"kind": "add_task_detail", "task_ref": "task-1", "detail_kind": "requirement", "after_ref": None, "text": "保留診斷資料", "basis_refs": []},
        {"kind": "remove_task_detail", "detail_ref": "outcome-1"},
        {"kind": "set_task_capability", "task_ref": "task-1", "capability_ref": "skill-1", "mode": "unlink", "basis_refs": []},
        {"kind": "add_condition", "container_ref": "condition-container-1", "after_ref": None, "text": "僅處理合約內系統", "basis_refs": []},
        {"kind": "remove_condition", "condition_ref": "condition-1"},
    ]}


def accepted_by_both(name: str, payload: dict, expected: bool) -> None:
    schema_accepts = oracle(name).is_valid(payload)
    published_accepts = Draft202012Validator(
        MODELS[name].model_json_schema(mode="validation")
    ).is_valid(payload)
    try:
        parsed = MODELS[name].model_validate(payload, strict=True)
    except ValidationError as exc:
        model_accepts = False
        model_errors = str(exc)
    else:
        model_accepts = True
        # A generated DTO must not coerce values or silently inject omitted input.
        assert parsed.model_dump(mode="json") == payload
    assert schema_accepts == expected
    assert published_accepts == expected
    assert model_accepts == expected, model_errors if not model_accepts else payload


@pytest.mark.parametrize("name,factory", [("CreateTaskInput", create_task), ("ReviseWorkInput", revise_work)])
def test_complete_payload_round_trips_without_loss(name, factory):
    accepted_by_both(name, factory(), True)


def test_explicit_null_is_accepted_for_nullable_fields():
    task = create_task()
    task["name"] = None
    accepted_by_both("CreateTaskInput", task, True)
    task["name"] = "只知名稱"
    task["description"] = None
    accepted_by_both("CreateTaskInput", task, True)
    correction = revise_work()
    correction["changes"][0]["text"] = None
    accepted_by_both("ReviseWorkInput", correction, True)


def objects_with_paths(value, path=()):
    if isinstance(value, dict):
        yield path, value
        for key, item in value.items():
            yield from objects_with_paths(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from objects_with_paths(item, (*path, index))


def at_path(value, path):
    for key in path:
        value = value[key]
    return value


def missing_required_cases():
    for name, factory in [("CreateTaskInput", create_task), ("ReviseWorkInput", revise_work)]:
        base = factory()
        for path, obj in objects_with_paths(base):
            for key in obj:
                changed = deepcopy(base)
                del at_path(changed, path)[key]
                yield pytest.param(name, changed, id=f"{name}:{path}:{key}")


@pytest.mark.parametrize("name,payload", list(missing_required_cases()))
def test_every_required_key_is_required_in_generated_model(name, payload):
    accepted_by_both(name, payload, False)


@pytest.mark.parametrize("name,factory", [("CreateTaskInput", create_task), ("ReviseWorkInput", revise_work)])
def test_extra_properties_are_rejected_at_every_object_level(name, factory):
    base = factory()
    for path, _ in objects_with_paths(base):
        changed = deepcopy(base)
        at_path(changed, path)["unexpected"] = "ignored data would be an error"
        accepted_by_both(name, changed, False)


@pytest.mark.parametrize("wrong", [1, 1.5, True, False, {}, []])
def test_text_and_references_do_not_accept_numbers_or_other_types(wrong):
    for key in ("container_ref", "after_ref", "name", "description"):
        task = create_task()
        task[key] = wrong
        accepted_by_both("CreateTaskInput", task, False)
    correction = revise_work()
    correction["changes"][0]["text"] = wrong
    accepted_by_both("ReviseWorkInput", correction, False)


@pytest.mark.parametrize("wrong", ["source-1", [1], [None], [True], [{}]])
def test_sources_are_arrays_of_strings(wrong):
    for name, factory, path in [
        ("CreateTaskInput", create_task, ()),
        ("CreateTaskInput", create_task, ("outcomes", 0)),
        ("CreateTaskInput", create_task, ("capabilities", 0)),
        ("ReviseWorkInput", revise_work, ("changes", 0)),
    ]:
        payload = factory()
        at_path(payload, path)["basis_refs"] = wrong
        accepted_by_both(name, payload, False)


@pytest.mark.parametrize("kind", ["move_task", "create_duty", "replace_selection", "set_field_typo", None, 1])
def test_unlisted_variants_are_rejected(kind):
    payload = revise_work()
    payload["changes"][0]["kind"] = kind
    accepted_by_both("ReviseWorkInput", payload, False)


def test_each_variant_accepts_only_its_declared_keys():
    for change in revise_work()["changes"]:
        accepted_by_both("ReviseWorkInput", {"changes": [change]}, True)
    payload = revise_work()
    payload["changes"][2]["basis_refs"] = []
    accepted_by_both("ReviseWorkInput", payload, False)
    payload = revise_work()
    payload["changes"][1]["detail_kind"] = "condition"
    accepted_by_both("ReviseWorkInput", payload, False)
    payload = revise_work()
    payload["changes"][3]["mode"] = "toggle"
    accepted_by_both("ReviseWorkInput", payload, False)


def test_nullable_is_not_optional_and_domain_validation_is_separate():
    # Semantically invalid empty content stays representable; domain owns that error.
    task = create_task()
    task.update(name=None, description=None, outcomes=[], requirements=[], capabilities=[])
    accepted_by_both("CreateTaskInput", task, True)
    accepted_by_both("ReviseWorkInput", {"changes": []}, True)


def test_ssot_is_valid_and_tool_roots_are_closed_objects():
    Draft202012Validator.check_schema(SCHEMA)
    for name in MODELS:
        root = SCHEMA["$defs"][name]
        assert root["type"] == "object"
        assert "anyOf" not in root
    for _, obj in objects_with_paths(SCHEMA):
        if obj.get("type") == "object":
            assert obj["additionalProperties"] is False
            assert set(obj["required"]) == set(obj["properties"])
