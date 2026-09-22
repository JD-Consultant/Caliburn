"""Chat wire facts separate run closure, original input and actual JD receipts."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
import pytest

from jd_relational.generated import chat_http, manual_http, results
from result_fixtures import observed_result


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
SCHEMA = json.loads((CONTRACTS / "jd-chat-http.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(json.loads((CONTRACTS / name).read_text(encoding="utf-8"))))
    for name in ("jd-work.schema.json", "jd-result.schema.json", "jd-manual-http.schema.json", "jd-read.schema.json")
)
DATASET = "12345678-90ab-cdef-1234-567890abcdef"
DOCUMENT = "22345678-90ab-cdef-1234-567890abcdef"
RUN = "32345678-90ab-cdef-1234-567890abcdef"
ROOTS = ("ChatStartInput", "ChatRunState", "ChatHistoryPage", "ChatMessage", "ChatProblem", "ChatRunChangePage")


def write_state(blocked=False):
    return {"ready": True, "archived": False, "write_blocked": blocked,
            "running": False, "operation_id": None, "error": None}


def start():
    return {"run_id": RUN, "text": "原話\r\n  每月處理異常。😀",
            "expected_jd_revision_ref": "original-signed-revision"}


def run(status="not_found"):
    terminal = status in ("completed", "cancelled", "failed")
    return {"dataset_id": DATASET, "document_id": DOCUMENT, "run_id": RUN,
            "write_state": write_state(status in ("running", "closing", "recovery_required")),
            "run_status": status, "input_state": "saved" if terminal else "unconfirmed",
            "response_message_id": None, "stop_requested": False if status == "running" else None,
            "jd_effects": {"state": "settled" if terminal else "unconfirmed", "results": []}}


def message():
    return {"message_id": "native-ai-message-id", "run_id": RUN,
            "role": "assistant", "text": "請說明這項工作的實際範圍。"}


def history():
    return {"dataset_id": DATASET, "document_id": DOCUMENT,
            "anchor": "fixed-checkpoint-anchor", "anchor_run_id": RUN, "messages": [message()], "next_cursor": None}


def problem():
    return {"type": "about:blank", "title": "Conflict", "status": 409,
            "detail": "請查回原回合。", "instance": f"urn:uuid:{RUN}",
            "code": "run_conflict", "next_action": "lookup_run"}


def run_changes():
    return {"format_version": 1, "view": "run_change", "access": "history", "dataset_id": DATASET,
            "document_id": DOCUMENT, "run_id": RUN, "capture_ref": "signed-original-capture",
            "effects_state": "settled", "continuity": "none", "captured_operation_count": 0,
            "base_revision_ref": None, "result_revision_ref": None, "records": [], "start_index": 0,
            "total_records": 0, "total_changes": 0, "has_more": False, "next_cursor": None,
            "oversized_unit": False}


FACTORIES = dict(zip(ROOTS, (start, run, history, message, problem, run_changes), strict=True))


def oracle(name):
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
                                 registry=REGISTRY)


def accepts(name, payload, expected):
    model = getattr(chat_http, name)
    assert oracle(name).is_valid(payload) is expected
    assert Draft202012Validator(model.model_json_schema(mode="validation")).is_valid(payload) is expected
    try:
        parsed = model.model_validate(payload, strict=True)
    except ValidationError:
        assert expected is False
    else:
        assert expected is True
        assert parsed.model_dump(mode="json") == payload


def test_only_named_endpoint_roots_are_published():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["properties"] == {name: {"$ref": f"#/$defs/{name}"} for name in ROOTS}
    assert SCHEMA["required"] == list(ROOTS)
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize("name", ROOTS)
def test_required_fields_round_trip_and_unknown_fields_fail(name):
    payload = FACTORIES[name]()
    accepts(name, payload, True)
    for key in payload:
        missing = deepcopy(payload)
        del missing[key]
        accepts(name, missing, False)
    accepts(name, {**payload, "unexpected": "not a contract field"}, False)


@pytest.mark.parametrize("wrong", [RUN.upper(), RUN.replace("-", ""), "{" + RUN + "}",
                                  RUN + "\n", "", None, 1, True])
def test_scoped_identities_are_canonical_uuid_strings(wrong):
    accepts("ChatStartInput", {**start(), "run_id": wrong}, False)
    accepts("ChatMessage", {**message(), "run_id": wrong}, False)
    for key in ("dataset_id", "document_id", "run_id"):
        accepts("ChatRunState", {**run(), key: wrong}, False)
    for key in ("dataset_id", "document_id"):
        accepts("ChatHistoryPage", {**history(), key: wrong}, False)


@pytest.mark.parametrize("wrong", ["", " \r\n\t", "\u3000\u00a0", "\x00", "工\x00作",
                                  "\x1c", "\x1d", "\x1e", "\x1f", None, 1, True])
def test_start_rejects_empty_whitespace_nul_and_non_text(wrong):
    accepts("ChatStartInput", {**start(), "text": wrong}, False)


def test_start_preserves_original_text_and_leaves_utf8_byte_limit_to_app():
    for text in (start()["text"], "  工作  ", "\n工作\n", "😀", "工" * 44000):
        accepts("ChatStartInput", {**start(), "text": text}, True)
    for key in ("document_id", "dataset_id", "start_revision_id", "request_digest", "messages"):
        accepts("ChatStartInput", {**start(), key: RUN}, False)


@pytest.mark.parametrize("wrong", ["", "r" * 4097, None, True, 1])
def test_original_revision_ref_is_required_and_bounded(wrong):
    accepts("ChatStartInput", {**start(), "expected_jd_revision_ref": wrong}, False)


@pytest.mark.parametrize("status", ["not_found", "running", "closing", "recovery_required",
                                   "completed", "cancelled", "failed"])
def test_run_states_preserve_three_independent_facts(status):
    payload = run(status)
    accepts("ChatRunState", payload, True)
    for key in payload:
        missing = deepcopy(payload)
        del missing[key]
        accepts("ChatRunState", missing, False)
    accepts("ChatRunState", {**payload, "success": True}, False)


@pytest.mark.parametrize("status", ["running", "closing", "recovery_required"])
def test_unresolved_run_is_blocked_and_never_advertises_settled_effects(status):
    payload = run(status)
    for saved in ("saved", "unconfirmed"):
        accepts("ChatRunState", {**payload, "input_state": saved}, True)
    accepts("ChatRunState", {**payload, "input_state": "not_saved"}, False)
    accepts("ChatRunState", {**payload, "write_state": write_state(False)}, False)
    accepts("ChatRunState", {**payload, "jd_effects": {"state": "settled", "results": []}}, False)
    for stopped in (False, True, None):
        accepts("ChatRunState", {**payload, "stop_requested": stopped}, status != "running" or stopped is not None)


@pytest.mark.parametrize("status", ["completed", "cancelled", "failed"])
def test_terminal_saved_runs_can_include_committed_jd_even_if_failed(status):
    payload = run(status)
    payload["jd_effects"]["results"] = [observed_result("committed")]
    accepts("ChatRunState", payload, True)
    accepts("ChatRunState", {**payload, "write_state": write_state(True)}, True)
    accepts("ChatRunState", {**payload, "response_message_id": "native-saved-response"}, True)
    accepts("ChatRunState", {**payload, "stop_requested": False}, False)
    accepts("ChatRunState", {**payload, "input_state": "unconfirmed"}, False)
    payload["jd_effects"] = {"state": "unconfirmed", "results": []}
    accepts("ChatRunState", payload, False)


def test_not_found_is_unknown_and_has_no_invented_response_or_effects():
    payload = run()
    accepts("ChatRunState", {**payload, "write_state": write_state(True)}, True)
    for key, value in (("input_state", "not_saved"), ("input_state", "saved"),
                       ("response_message_id", "native-id"), ("stop_requested", False),
                       ("jd_effects", {"state": "settled", "results": []}),
                       ("jd_effects", {"state": "unconfirmed", "results": [observed_result("committed")]})):
        accepts("ChatRunState", {**payload, key: value}, False)


def test_known_unsaved_input_only_allows_failed_and_empty_settled_effects():
    payload = {**run("failed"), "input_state": "not_saved"}
    accepts("ChatRunState", payload, True)
    for status in ("completed", "cancelled", "running", "not_found"):
        accepts("ChatRunState", {**payload, "run_status": status}, False)
    accepts("ChatRunState", {**payload, "response_message_id": "native-id"}, False)
    for status in ("committed", "no_change", "outcome_unknown"):
        accepts("ChatRunState", {**payload, "jd_effects": {"state": "settled", "results": [observed_result(status)]}}, False)


@pytest.mark.parametrize("status,phase", [
    ("committed", None), ("no_change", None), ("outcome_unknown", None),
    *[(status, phase) for status in ("invalid_input", "target_missing", "stale_view",
                                   "relationship_conflict", "dependent_items", "save_failed")
      for phase in ("confirmed", "unconfirmed")],
    *[(status, "unbound") for status in ("invalid_input", "busy", "archived", "operation_conflict", "save_failed")],
])
def test_effects_reuse_only_original_bound_results_and_respect_durability(status, phase):
    result = observed_result(status, phase)
    for run_status in ("running", "failed"):
        payload = run(run_status)
        payload["jd_effects"]["results"] = [result]
        expected = phase != "unbound" and (run_status == "running" or result["receipt_durability"] == "confirmed")
        accepts("ChatRunState", payload, expected)
        if expected:
            item = chat_http.ChatRunState.model_validate(payload, strict=True).root.jd_effects.results[0]
            while hasattr(item, "root"):
                item = item.root
            assert type(item) is getattr(results, type(item).__name__)


def test_external_write_state_is_not_a_second_local_copy():
    parsed = chat_http.ChatRunState.model_validate(run("running"), strict=True)
    assert isinstance(parsed.root.write_state, manual_http.ManualBlockedState)
    parsed = chat_http.ChatRunState.model_validate(run("failed"), strict=True)
    assert isinstance(parsed.root.write_state, manual_http.ManualDocumentState)


def test_effect_results_are_bounded_without_silently_truncating():
    for status in ("running", "failed"):
        for size in (0, 96, 97):
            payload = run(status)
            payload["jd_effects"]["results"] = [observed_result("no_change")] * size
            accepts("ChatRunState", payload, size <= 96)


@pytest.mark.parametrize("wrong", [0, 1, 0.0, 1.0, "true", "false"])
def test_stop_request_is_a_real_boolean_not_a_truthy_value(wrong):
    for status in ("running", "closing", "recovery_required"):
        accepts("ChatRunState", {**run(status), "stop_requested": wrong}, False)


def test_output_literal_boolean_limit_is_explicit_and_raw_contract_remains_strict():
    # Existing Pydantic Literal[bool] accepts equal 0/1. The App projection must
    # check the four flags with type(value) is bool before validating this DTO.
    payload = run("running")
    payload["write_state"]["write_blocked"] = 1
    assert not oracle("ChatRunState").is_valid(payload)
    assert not Draft202012Validator(chat_http.ChatRunState.model_json_schema()).is_valid(payload)
    parsed = chat_http.ChatRunState.model_validate(payload, strict=True).model_dump(mode="json")
    assert parsed["write_state"]["write_blocked"] is True


def test_history_empty_state_cannot_invent_an_anchor_cursor_or_message():
    empty = {**history(), "anchor": None, "anchor_run_id": None, "messages": [], "next_cursor": None}
    accepts("ChatHistoryPage", empty, True)
    accepts("ChatHistoryPage", {**empty, "messages": [message()]}, False)
    accepts("ChatHistoryPage", {**empty, "next_cursor": "later-page"}, False)
    accepts("ChatHistoryPage", {**empty, "anchor": "fixed-anchor", "anchor_run_id": RUN}, True)
    accepts("ChatHistoryPage", {**empty, "anchor_run_id": RUN}, False)
    accepts("ChatHistoryPage", {**empty, "anchor": "fixed-anchor"}, False)


def test_history_keeps_native_message_ids_roles_and_exact_public_text_only():
    for role in ("user", "assistant", "system", "tool", "developer"):
        payload = {**message(), "role": role, "text": "逐字\r\n  保留。😀"}
        accepts("ChatMessage", payload, role in ("user", "assistant"))
    for key in ("timestamp", "tool_calls", "tool_args", "thinking", "signature", "usage", "provider"):
        accepts("ChatMessage", {**message(), key: "private or unproven"}, False)
    for wrong in ("", None, 1):
        accepts("ChatMessage", {**message(), "message_id": wrong}, False)
        accepts("ChatMessage", {**message(), "text": wrong}, False)


def test_history_page_is_at_most_fifty_messages_with_a_fixed_bounded_anchor():
    for size in (0, 50, 51):
        accepts("ChatHistoryPage", {**history(), "messages": [message()] * size}, size <= 50)
    for key in ("anchor", "next_cursor"):
        for wrong in ("", "r" * 4097, 1, True):
            accepts("ChatHistoryPage", {**history(), key: wrong}, False)


@pytest.mark.parametrize("status", [403, 404, 409, 422, 500, 503, 200, 202, "409", True])
def test_problem_status_is_not_a_success_or_an_original_run_outcome(status):
    accepts("ChatProblem", {**problem(), "status": status},
            type(status) is int and status in (403, 404, 409, 422, 500, 503))


def test_problem_has_fixed_app_codes_and_no_rollback_or_private_exception_claim():
    for code in ("invalid_input", "invalid_ref", "document_missing", "dataset_changed", "stale_view",
                 "run_conflict", "busy", "recovery_required", "service_unavailable", "origin_not_allowed"):
        accepts("ChatProblem", {**problem(), "code": code}, True)
    for action in ("correct_input", "reread", "lookup_run", "wait", "recover", "stop"):
        accepts("ChatProblem", {**problem(), "next_action": action}, True)
    for key, value in (("type", "https://invented.invalid"), ("instance", RUN),
                       ("code", "provider_error"), ("next_action", "retry")):
        accepts("ChatProblem", {**problem(), key: value}, False)
    for key in ("input_saved", "jd_result", "rolled_back", "raw_error", "traceback"):
        accepts("ChatProblem", {**problem(), key: "not proven"}, False)


def test_disabled_ai_has_a_distinct_stop_problem_while_manual_work_remains_available():
    accepts("ChatProblem", {**problem(), "status": 503, "title": "Service Unavailable",
        "code": "ai_unavailable", "next_action": "stop",
        "detail": "AI 訪談尚未啟用；請保留輸入。目前仍可查看原有對話及編輯 JD。"}, True)


def test_anchored_history_exposes_its_required_canonical_run_identity():
    payload = {**history(), "anchor_run_id": RUN}
    accepts("ChatHistoryPage", payload, True)
    for wrong in (None, "", RUN.upper(), RUN + "\n", 1, True):
        accepts("ChatHistoryPage", {**payload, "anchor_run_id": wrong}, False)
