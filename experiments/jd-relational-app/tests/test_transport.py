import json

import pytest

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


def test_manual_and_both_model_shapes_map_to_one_command_without_app_fields():
    payload = partial_task()
    expected = {"tool": "jd_create_task", "arguments": payload}
    assert manual_command(expected) == model_command("jd_create_task", payload)
    assert model_command("jd_create_task", json.dumps(payload)) == expected
    payload["document_id"] = "model-must-not-supply"
    with pytest.raises(TransportError, match="invalid_input"):
        model_command("jd_create_task", payload)


@pytest.mark.parametrize("raw", ['{"name":"a","name":"b"}', '{"name":NaN}', '[1]', 'null'])
def test_reject_ambiguous_or_nonobject_json(raw):
    with pytest.raises(TransportError, match="invalid_input"):
        model_command("jd_create_task", raw)


def test_missing_null_and_number_are_not_silently_defaulted_or_coerced():
    payload = partial_task()
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


def test_candidate_or_error_outputs_preserve_call_identity_not_claim_saved():
    result = {"status": "candidate_ready", "persisted": False}
    oa = tool_output("openai", "call-7", result)
    cl = tool_output("anthropic", "toolu-7", result)
    assert oa == {"type": "function_call_output", "call_id": "call-7", "output": json.dumps(result, ensure_ascii=False)}
    assert cl["tool_use_id"] == "toolu-7"
    assert json.loads(cl["content"]) == result
    err = tool_output("anthropic", "toolu-7", {"status": "error", "code": "stale_reference"})
    assert err["is_error"] is True


def test_schema_returned_to_caller_cannot_mutate_future_tool_definition():
    value = tool_definition("openai", "jd_create_task")
    value["parameters"]["properties"].clear()
    assert "name" in tool_definition("openai", "jd_create_task")["parameters"]["properties"]
