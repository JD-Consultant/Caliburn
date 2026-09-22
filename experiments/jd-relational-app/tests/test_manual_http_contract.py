"""Manual HTTP shapes reuse the named business commands and exact write results."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
import pytest
from result_fixtures import observed_result
from test_contract import create_task, revise_work
from test_management_contract import management_input

from jd_relational.generated import manual_http, models, results


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
SCHEMA = json.loads((CONTRACTS / "jd-manual-http.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(json.loads((CONTRACTS / name).read_text(encoding="utf-8"))))
    for name in ("jd-work.schema.json", "jd-result.schema.json")
)
OPERATION = "12345678-90ab-cdef-1234-567890abcdef"
ROOTS = ("ManualSaveInput", "ManualDocumentState", "ManualOperationState", "ManualProblem")
INPUTS = {
    "jd_create_task": "CreateTaskInput", "jd_revise_work": "ReviseWorkInput",
    "jd_set_text": "SetTextInput", "jd_insert_item": "InsertItemInput",
    "jd_delete_item": "DeleteItemInput", "jd_move_item": "MoveItemInput",
    "jd_set_task_capability": "SetTaskCapabilityInput",
    "jd_replace_selection": "ReplaceSelectionInput",
}


def save(tool="jd_set_text"):
    name = INPUTS[tool]
    arguments = (create_task() if name == "CreateTaskInput" else revise_work()
                 if name == "ReviseWorkInput" else management_input(name))
    return {"operation_id": OPERATION, "base_revision_ref": "issued-current-revision",
            "command": {"tool": tool, "arguments": arguments}}


def state():
    return {"ready": True, "archived": False, "write_blocked": False,
            "running": False, "operation_id": None, "error": None}


def operation():
    return {"operation_id": OPERATION, "presence": "not_found", "result": None,
            "write_state": state()}


def problem():
    return {"type": "about:blank", "title": "Conflict", "status": 409,
            "detail": "請先查回原操作。", "instance": f"urn:uuid:{OPERATION}",
            "code": "operation_conflict", "next_action": "lookup_operation"}


FACTORIES = dict(zip(ROOTS, (save, state, operation, problem), strict=True))


def accepts(name, payload, expected):
    oracle = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
                                 registry=REGISTRY)
    model = getattr(manual_http, name)
    published = Draft202012Validator(model.model_json_schema(mode="validation"))
    assert oracle.is_valid(payload) is expected
    assert published.is_valid(payload) is expected
    try:
        parsed = model.model_validate(payload, strict=True)
    except ValidationError:
        assert expected is False
    else:
        assert expected is True
        assert parsed.model_dump(mode="json") == payload


def test_catalog_has_only_the_four_transport_roots():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["properties"] == {name: {"$ref": f"#/$defs/{name}"} for name in ROOTS}
    assert SCHEMA["required"] == list(ROOTS)
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize("tool", INPUTS)
def test_all_eight_business_effects_reuse_the_existing_input_model(tool):
    payload = save(tool)
    accepts("ManualSaveInput", payload, True)
    value = manual_http.ManualSaveInput.model_validate(payload, strict=True)
    assert isinstance(value.command.root.arguments, getattr(models, INPUTS[tool]))
    for key in ("tool", "arguments"):
        changed = deepcopy(payload)
        del changed["command"][key]
        accepts("ManualSaveInput", changed, False)
    changed = deepcopy(payload)
    changed["command"]["commands"] = [deepcopy(payload["command"])]
    accepts("ManualSaveInput", changed, False)
    # HTTP metadata must not be copied into the shared business arguments.
    changed = deepcopy(payload)
    changed["command"]["arguments"]["operation_id"] = OPERATION
    accepts("ManualSaveInput", changed, False)


@pytest.mark.parametrize("tool", INPUTS)
def test_each_named_command_rejects_unmatched_arguments(tool):
    payload = save(tool)
    payload["command"]["arguments"] = ({"changes": []} if tool != "jd_revise_work"
                                        else management_input("SetTextInput"))
    accepts("ManualSaveInput", payload, False)


@pytest.mark.parametrize("name", ROOTS)
def test_transport_fields_are_required_and_unknown_fields_rejected(name):
    payload = FACTORIES[name]()
    accepts(name, payload, True)
    for key in payload:
        changed = deepcopy(payload)
        del changed[key]
        accepts(name, changed, False)
    accepts(name, {**payload, "unexpected": "must not silently ignore"}, False)


@pytest.mark.parametrize("wrong", [OPERATION.upper(), OPERATION.replace("-", ""),
                                  "{" + OPERATION + "}", OPERATION + "\n", "", None, 7])
def test_operation_identity_requires_canonical_uuid_string(wrong):
    for name, factory in (("ManualSaveInput", save), ("ManualOperationState", operation)):
        accepts(name, {**factory(), "operation_id": wrong}, False)
    accepts("ManualDocumentState", {**state(), "operation_id": wrong}, wrong is None)


@pytest.mark.parametrize("wrong", ["", "r" * 4097, None, True, 7])
def test_base_revision_is_a_bounded_issued_string(wrong):
    accepts("ManualSaveInput", {**save(), "base_revision_ref": wrong}, False)


@pytest.mark.parametrize("command", [[], {}, {"tool": "jd_batch", "arguments": []},
                                    {"tool": "jd_set_text", "arguments": {}, "commands": []},
                                    {"commands": [save()["command"]]}])
def test_manual_save_cannot_embed_a_generic_batch(command):
    accepts("ManualSaveInput", {**save(), "command": command}, False)


@pytest.mark.parametrize("wrong", ["true", "false", None])
def test_document_flags_are_strict_booleans(wrong):
    for key in ("ready", "archived", "write_blocked", "running"):
        accepts("ManualDocumentState", {**state(), key: wrong}, False)


@pytest.mark.parametrize("wrong", [0, 1, 0.0, 1.0])
def test_pydantic_boolean_literal_limitation_is_explicit(wrong):
    # The authoritative and published schemas reject numeric flags. Pydantic
    # 2.13.5 Literal[bool] still accepts equal 0/1, even with strict=True.
    # These output-only flags require the narrow App projection type guard;
    # this regression documents the raw generator limitation, not acceptance
    # by the service or permission to silently coerce an HTTP response.
    oracle = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/ManualDocumentState"},
                                 registry=REGISTRY)
    published = Draft202012Validator(manual_http.ManualDocumentState.model_json_schema(mode="validation"))
    for key in ("ready", "archived", "write_blocked", "running"):
        payload = {**state(), key: wrong}
        assert not oracle.is_valid(payload)
        assert not published.is_valid(payload)
        coerces = key in ({"archived", "write_blocked", "running"} if wrong == 0
                          else {"ready", "write_blocked"})
        if coerces:
            result = manual_http.ManualDocumentState.model_validate(payload, strict=True).model_dump(mode="json")
            assert type(result[key]) is bool
            assert result == {**payload, key: bool(wrong)}
        else:
            with pytest.raises(ValidationError):
                manual_http.ManualDocumentState.model_validate(payload, strict=True)


@pytest.mark.parametrize("error", [None, "busy", "recovery_required", "service_unavailable", "failed", 1])
def test_document_state_error_is_a_closed_nullable_code(error):
    accepts("ManualDocumentState", {**state(), "write_blocked": True, "error": error},
            error in (None, "busy", "recovery_required", "service_unavailable"))


def test_archived_state_can_be_ready_without_an_error():
    accepts("ManualDocumentState", {**state(), "archived": True, "write_blocked": True}, True)


@pytest.mark.parametrize("presence", ["not_found", "pending", "observed", "complete", None, 1])
def test_operation_presence_is_not_a_new_mutation_result(presence):
    accepts("ManualOperationState", {**operation(), "presence": presence},
            presence == "not_found")


@pytest.mark.parametrize("status,phase", [("committed", None), ("no_change", None),
                                        ("outcome_unknown", None), ("save_failed", "unconfirmed"),
                                        ("invalid_input", "confirmed"), ("busy", "unbound")])
def test_observed_operation_preserves_the_original_result_contract(status, phase):
    result = observed_result(status, phase)
    presence = "pending" if result["receipt_durability"] == "unconfirmed" else "observed"
    value = {**operation(), "presence": presence, "result": result}
    accepted = phase != "unbound"
    accepts("ManualOperationState", value, accepted)
    if not accepted:
        return
    parsed = manual_http.ManualOperationState.model_validate(value, strict=True)
    original = parsed.root.result.root
    assert type(original) is getattr(results, type(original).__name__)
    changed = deepcopy(value)
    changed["result"]["receipt_durability"] = "guessed"
    accepts("ManualOperationState", changed, False)


@pytest.mark.parametrize("status", [403, 404, 409, 422, 500, 503, 200, 202, "409", True])
def test_problem_status_does_not_claim_a_success_or_pending_result(status):
    accepts("ManualProblem", {**problem(), "status": status},
            type(status) is int and status in (403, 404, 409, 422, 500, 503))


def test_manual_problem_has_no_mutation_durability_or_rollback_claim():
    for key in ("result", "jd_result", "receipt_durability", "rolled_back", "effect"):
        accepts("ManualProblem", {**problem(), key: "not established by this failure"}, False)
    for key, value in (("type", "https://invented.example/problem"), ("instance", OPERATION),
                       ("code", "save_failed"), ("next_action", "retry")):
        accepts("ManualProblem", {**problem(), key: value}, False)


@pytest.mark.parametrize("patch", [{"archived": True}, {"ready": False},
                                  {"running": True}, {"operation_id": OPERATION},
                                  {"error": "busy"}])
def test_document_cannot_advertise_unblocked_when_its_state_disallows_writes(patch):
    accepts("ManualDocumentState", {**state(), **patch}, False)


@pytest.mark.parametrize("presence,result", [
    ("observed", None), ("not_found", observed_result("committed")),
    ("pending", observed_result("committed")),
    ("observed", observed_result("busy", "unbound")),
    ("observed", observed_result("outcome_unknown")),
    ("pending", None),
])
def test_operation_presence_cannot_contradict_receipt_facts(presence, result):
    accepts("ManualOperationState", {**operation(), "presence": presence, "result": result}, False)


@pytest.mark.parametrize("status,phase", [
    ("committed", None), ("no_change", None), ("outcome_unknown", None),
    *[(status, phase) for status in ("invalid_input", "target_missing", "stale_view",
                                   "relationship_conflict", "dependent_items", "save_failed")
      for phase in ("confirmed", "unconfirmed")],
    *[(status, "unbound") for status in ("invalid_input", "busy", "archived",
                                        "operation_conflict", "save_failed")],
])
def test_every_original_result_is_permitted_only_with_matching_presence(status, phase):
    result = observed_result(status, phase)
    expected = (None if phase == "unbound" else "pending"
                if result["receipt_durability"] == "unconfirmed" else "observed")
    for presence in ("not_found", "pending", "observed"):
        value = {**operation(), "presence": presence, "result": result}
        accepts("ManualOperationState", value, presence == expected)
