"""An observed write result must not invent durability or permission to replay."""

from copy import deepcopy
import json
from pathlib import Path
import traceback

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest
from result_fixtures import observed_result

from jd_relational.generated.results import MutationResult
from jd_relational.transport import TransportError, tool_output


CATALOG = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-result.schema.json").read_text(encoding="utf-8"))
SCHEMA = {"$defs": CATALOG["$defs"], "$ref": "#/$defs/MutationResult"}


def committed():
    return {"status": "committed", "effect": "changed", "receipt_durability": "confirmed",
            "operation_ref": "issued-operation", "result_revision_ref": "issued-result",
            "change_ref": "issued-change", "error": None, "next_action": "continue"}


@pytest.mark.parametrize("patch", [
    {"effect": "unchanged"}, {"receipt_durability": "unconfirmed"}, {"operation_ref": None},
    {"result_revision_ref": None}, {"change_ref": None}, {"next_action": "reconcile_operation"},
    {"status": "no_change"}, {"status": "save_failed"}, {"unknown_field": "must reject"},
])
def test_inconsistent_success_never_reaches_either_provider(patch):
    value = {**committed(), **patch}
    for provider in ("openai", "anthropic"):
        with pytest.raises(TransportError, match="invalid_result"):
            tool_output(provider, "call", value)


def test_preparation_cannot_be_returned_as_a_saved_mutation():
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("openai", "call", {"status": "candidate_ready", "persisted": False})


def test_bound_unconfirmed_unchanged_must_reconcile_before_any_new_write():
    value = {"status": "save_failed", "effect": "unchanged", "receipt_durability": "unconfirmed",
             "operation_ref": "issued-operation", "result_revision_ref": None, "change_ref": None,
             "error": {"code": "save_failed", "message": "尚未確認回執，先查回原操作。", "related_refs": []},
             "next_action": "stop"}
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("anthropic", "call", value)
    value["next_action"] = "reconcile_operation"
    assert json.loads(tool_output("anthropic", "call", value)["content"]) == value


def test_output_preserves_actual_observation_without_mutating_it():
    value = committed()
    original = deepcopy(value)
    assert json.loads(tool_output("openai", "call", value)["output"]) == original
    assert value == original


@pytest.mark.parametrize("status,phase", [
    ("committed", None), ("no_change", None), ("outcome_unknown", None),
    *[(status, phase) for status in ("invalid_input", "target_missing", "stale_view", "relationship_conflict", "dependent_items", "save_failed")
      for phase in ("confirmed", "unconfirmed")],
    *[(status, "unbound") for status in ("invalid_input", "busy", "archived", "operation_conflict", "save_failed")],
])
def test_observation_matrix_matches_ssot_generated_dto_and_published_shape(status, phase):
    value = observed_result(status, phase)
    Draft202012Validator(SCHEMA).validate(value)
    Draft202012Validator(MutationResult.model_json_schema()).validate(value)
    assert MutationResult.model_validate(value, strict=True).model_dump(mode="json") == value
    # Removing any fact cannot silently default it to a claim of durability.
    for key in value:
        incomplete = {name: item for name, item in value.items() if name != key}
        assert not Draft202012Validator(SCHEMA).is_valid(incomplete)
        with pytest.raises(ValidationError):
            MutationResult.model_validate(incomplete, strict=True)


@pytest.mark.parametrize("patch", [
    {"effect": "changed"}, {"receipt_durability": "confirmed"}, {"operation_ref": None},
    {"result_revision_ref": "guessed-revision"}, {"change_ref": "guessed-change"}, {"next_action": "continue"},
    {"error": {"code": "save_failed", "message": "wrong category", "related_refs": []}},
])
def test_commit_uncertainty_is_not_a_terminal_or_a_guessed_revision(patch):
    value = {**observed_result("outcome_unknown"), **patch}
    assert not Draft202012Validator(SCHEMA).is_valid(value)
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("openai", "call", value)


@pytest.mark.parametrize("call_id", [None, "", "  ", 7, "x" * 4097])
def test_missing_or_unbounded_provider_identity_is_rejected(call_id):
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("openai", call_id, committed())


def test_output_validation_does_not_echo_raw_error_payload_in_traceback():
    value = observed_result("invalid_input")
    value["error"]["message"] = {"secret": "SensitiveY"}
    with pytest.raises(TransportError) as error:
        tool_output("anthropic", "call", value)
    assert "SensitiveY" not in "".join(traceback.format_exception(error.value))


def test_invalid_unicode_is_rejected_before_the_sdk_serializes_it():
    value = observed_result("invalid_input")
    value["error"]["message"] = "broken \ud800 content"
    with pytest.raises(TransportError, match="invalid_result"):
        tool_output("anthropic", "call", value)
