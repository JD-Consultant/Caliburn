import json
import traceback

import pytest
from result_fixtures import observed_result

from jd_relational.transport import (
    TransportError,
    manual_command,
    model_command,
    tool_definition,
    tool_output,
)


def partial_task():
    return {
        "container_ref": "unassigned-ref",
        "after_ref": None,
        "name": None,
        "description": "收到異常後釐清問題；其他條件仍待確認。\r\n保留原意。",
        "basis_refs": [],
        "outcomes": [],
        "requirements": [],
        "capabilities": [],
    }


def model_partial_task():
    value = partial_task()
    value["basis_evidence_keys"] = value.pop("basis_refs")
    return value


def test_manual_and_both_model_shapes_map_to_one_command_without_app_fields():
    manual_payload = partial_task()
    model_payload = model_partial_task()
    expected = {"tool": "jd_create_task", "arguments": manual_payload}
    assert manual_command(expected) == model_command("jd_create_task", model_payload)
    assert model_command("jd_create_task", json.dumps(model_payload)) == expected
    model_payload["document_id"] = "model-must-not-supply"
    with pytest.raises(TransportError, match="invalid_input"):
        model_command("jd_create_task", model_payload)


@pytest.mark.parametrize("raw", ['{"name":"a","name":"b"}', '{"name":NaN}', '[1]', 'null'])
def test_reject_ambiguous_or_nonobject_json(raw):
    with pytest.raises(TransportError, match="invalid_input"):
        model_command("jd_create_task", raw)


def test_missing_null_and_number_are_not_silently_defaulted_or_coerced():
    payload = model_partial_task()
    del payload["name"]
    with pytest.raises(TransportError):
        model_command("jd_create_task", payload)
    payload["name"] = 123
    with pytest.raises(TransportError):
        model_command("jd_create_task", payload)


def test_unknown_tool_and_manual_envelope_fields_rejected():
    with pytest.raises(TransportError, match="unknown_tool"):
        model_command("write_file", {})
    with pytest.raises(TransportError):
        manual_command({"tool": "jd_create_task", "arguments": partial_task(), "force": True})


def test_request_limit_applies_before_parsing_including_whitespace():
    raw = " " * (1024 * 1024) + "{}"
    with pytest.raises(TransportError, match="request_too_large"):
        model_command("jd_create_task", raw)
    with pytest.raises(TransportError, match="invalid_input"):
        model_command("jd_create_task", '{"name":"\ud800"}')


def test_provider_roots_are_objects_with_required_nullable_not_catalog_union():
    for tool in ("jd_create_task", "jd_revise_work"):
        oa = tool_definition("openai", tool)
        cl = tool_definition("anthropic", tool)
        assert isinstance(oa["description"], str)
        assert oa["parameters"] == cl["input_schema"]
        assert oa["strict"] is cl["strict"] is True
        assert oa["parameters"]["type"] == "object"
        assert "anyOf" not in oa["parameters"]
        assert oa["parameters"]["additionalProperties"] is False
        assert set(oa["parameters"]["required"]) == set(oa["parameters"]["properties"])
        assert "operation_id" not in json.dumps(oa)
        assert "revision" not in oa["parameters"]["properties"]


def test_insert_container_refs_require_exact_latest_current_read_values():
    """Opaque write refs are copied from the latest current view, never reconstructed."""
    schema = tool_definition("openai", "jd_insert_item")["parameters"]
    descriptions = []

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "container_ref" and isinstance(item, dict):
                    descriptions.append(item.get("description", ""))
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(schema)

    assert len(descriptions) == 7
    for description in descriptions:
        normalized = description.lower()
        assert "latest successful jd_read current" in normalized
        assert "verbatim" in normalized
        assert "derive" in normalized
        assert "older read" in normalized


def test_synthetic_observation_outputs_preserve_call_identity():
    result = observed_result()
    oa = tool_output("openai", "call-7", result)
    cl = tool_output("anthropic", "toolu-7", result)
    assert oa == {"type": "function_call_output", "call_id": "call-7", "output": json.dumps(result, ensure_ascii=False)}
    assert cl["tool_use_id"] == "toolu-7"
    assert json.loads(cl["content"]) == result
    err = tool_output("anthropic", "toolu-7", observed_result("stale_view"))
    assert err["is_error"] is True


def test_schema_returned_to_caller_cannot_mutate_future_tool_definition():
    value = tool_definition("openai", "jd_create_task")
    value["parameters"]["properties"].clear()
    assert "name" in tool_definition("openai", "jd_create_task")["parameters"]["properties"]


def test_create_task_schema_explains_the_exact_issued_child_container():
    definition = tool_definition("openai", "jd_create_task")
    description = definition["parameters"]["properties"]["container_ref"]["description"]

    assert "type=container" in description
    assert "child_kind is task" in description
    assert "owner_ref equals the duty item_ref" in description
    assert "type=item record's container_ref" in description


@pytest.mark.parametrize("status", ["invalid_input", "target_missing", "stale_view", "relationship_conflict",
                                  "dependent_items", "save_failed", "outcome_unknown", "operation_conflict", "busy", "archived"])
def test_every_known_failure_status_sets_anthropic_error_flag(status):
    assert tool_output("anthropic", "toolu", observed_result(status))["is_error"] is True


@pytest.mark.parametrize("status", ["committed", "no_change"])
def test_nonerror_status_preserves_anthropic_success_flag(status):
    assert tool_output("anthropic", "toolu", observed_result(status))["is_error"] is False


def test_unknown_result_status_is_not_silently_misreported_as_success():
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("anthropic", "toolu", {"status": "typo-status"})


def test_invalid_payload_does_not_leak_through_standard_exception_traceback():
    payload = model_partial_task()
    payload["name"] = {"private": "SensitiveX"}
    with pytest.raises(TransportError) as error:
        model_command("jd_create_task", payload)
    rendered = "".join(traceback.format_exception(error.value))
    assert "SensitiveX" not in rendered
