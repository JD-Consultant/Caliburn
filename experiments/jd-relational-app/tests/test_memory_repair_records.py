"""Pure original-call/result contracts; no Store, source, DB, or model calls."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from caliburn_memory.memory import MemoryVersion
from caliburn_memory.publication import PublishedHead, PublishRequest

from jd_relational.memory_repair_records import (
    REPAIR_NAME, LayeredRepairInput, MemoryRepairError, decode_repair_bindings,
    make_repair_binding, make_repair_message, make_unbound_repair_message,
    parse_layered_repair_input, parse_repair_input, validate_repair_message,
    validate_unbound_repair_message,
    verify_repair_binding_message,
)

DATASET = "aaaaaaaa-1111-4222-8333-444444444444"
DOCUMENT = "bbbbbbbb-1111-4222-8333-444444444444"
RUN = "cccccccc-1111-4222-8333-444444444444"
VERSION = "dddddddd-1111-4222-8333-444444444444"
NEXT_VERSION = "eeeeeeee-1111-4222-8333-444444444444"
LATER_VERSION = "ffffffff-1111-4222-8333-444444444444"
SOURCE = "conversation:opaque-current-source"
BASE = PublishedHead(1, MemoryVersion(DOCUMENT, VERSION), "conversation:background-source")
SCOPE = dict(dataset_id=DATASET, document_id=DOCUMENT, run_id=RUN)
EDIT = {"path": "/memory/knowledge.md", "diff": "@@\n-主管\n+處長"}
CASE = "11111111-1111-4111-8111-111111111111"
UNDERSTANDING = "22222222-2222-4222-8222-222222222222"
LAYERED_ARGS = {
    "case_id": CASE,
    "case_diff": "@@\n-本人負責維修。\n+本人只負責通報；維修由外包負責。",
    "case_route_note": None,
    "remove_evidence_keys": ["E1"],
    "understanding_updates": [{
        "understanding_id": UNDERSTANDING,
        "action": "revalidate",
        "diff": None,
        "supporting_case_ids": [CASE],
        "route_note": None,
    }],
}
LAYERED_REPAIR = {
    "case_id": CASE,
    "case_diff": LAYERED_ARGS["case_diff"],
    "case_route_note": None,
    "remove_source_references": ["conversation:old-source"],
    "understanding_updates": LAYERED_ARGS["understanding_updates"],
}


def model_message(args=None):
    return AIMessage(id="msg-original", content=[], tool_calls=[{
        "name": REPAIR_NAME, "id": "call-original", "args": {"edits": [EDIT]} if args is None else args,
    }])


def test_current_layered_input_exposes_only_model_owned_fields():
    parsed = parse_layered_repair_input(LAYERED_ARGS)
    assert parsed == LAYERED_ARGS
    properties = LayeredRepairInput.model_json_schema(mode="validation")["properties"]
    assert set(properties) == {
        "case_id", "case_diff", "case_route_note", "remove_evidence_keys",
        "understanding_updates",
    }
    encoded = json.dumps(properties, ensure_ascii=False)
    for runtime_owned in ("source_reference", "revision", "version_id", "digest",
                          "offset", "operation_id", "remove_source_references"):
        assert runtime_owned not in encoded
    with pytest.raises(MemoryRepairError, match="^invalid_repair_input$"):
        parse_layered_repair_input({**LAYERED_ARGS, "revision": 1})


def test_layered_binding_and_request_preserve_exact_runtime_resolved_repair():
    message = model_message(LAYERED_ARGS)
    bound = make_repair_binding(
        message, **SCOPE, base=asdict(BASE), source_reference=SOURCE,
        repair=LAYERED_REPAIR, layered=True,
    )
    assert bound.format_version == 2 and bound.repair == LAYERED_REPAIR
    verify_repair_binding_message(bound, [message])
    request = PublishRequest(
        bound.operation_id, MemoryVersion(DOCUMENT, NEXT_VERSION), 1, "repair", "a" * 64,
        repair_sources=(SOURCE,), bundle_base_revision=1,
        bundle_base_version_id=VERSION,
    )
    saved = PublishedHead(2, request.memory, BASE.processed_source)
    outcome = {"status": "applied", "detail": "已保存", "head": asdict(saved),
        "guide": "分層導覽", "applied_head": asdict(saved),
        "source_reference": SOURCE}
    result = make_repair_message(bound, outcome, request)
    assert result.artifact["format_version"] == 2
    assert "read_paths" not in json.loads(result.content)
    assert validate_repair_message(result, bound) == (outcome, request)


def test_unbound_current_call_never_exposes_retired_two_file_read_paths():
    original = model_message(LAYERED_ARGS)

    result = make_unbound_repair_message(original)

    assert result.artifact["format_version"] == 2
    assert "read_paths" not in json.loads(result.content)
    validate_unbound_repair_message(result, original)


def test_unbound_current_legacy_shaped_call_is_closed_with_the_current_format():
    original = model_message()

    result = make_unbound_repair_message(original)

    assert result.artifact["format_version"] == 2
    assert "read_paths" not in json.loads(result.content)
    validate_unbound_repair_message(result, original)


def test_a_saved_legacy_unbound_result_remains_validatable_for_recovery():
    original = model_message()

    result = make_unbound_repair_message(original, format_version=1)

    assert result.artifact["format_version"] == 1
    assert "read_paths" in json.loads(result.content)
    validate_unbound_repair_message(result, original)


def binding(message=None, **kwargs):
    return make_repair_binding(message or model_message(), **SCOPE,
        base=kwargs.pop("base", asdict(BASE)), source_reference=SOURCE, **kwargs)


def applied(bound, *, later=False):
    request = PublishRequest(bound.operation_id, MemoryVersion(DOCUMENT, NEXT_VERSION),
        1, "repair", "a" * 64, repair_sources=(SOURCE,))
    saved = PublishedHead(2, request.memory, BASE.processed_source)
    current = PublishedHead(3, MemoryVersion(DOCUMENT, LATER_VERSION), SOURCE) if later else saved
    outcome = {"status": "applied", "detail": "已保存", "head": asdict(current),
        "guide": "新導覽", "applied_head": asdict(saved), "source_reference": SOURCE,
        "read_paths": ["/memory/knowledge.md", "/memory/guide.md"], "changes": [EDIT]}
    return outcome, request


def test_exact_patch_input_preserves_text_and_bounds():
    args = {"edits": [EDIT, {"path": "/memory/guide.md", "diff": "x" * (12000 - len(EDIT["diff"]))}]}
    assert parse_repair_input(args) == args["edits"]
    assert parse_repair_input(args) is not args["edits"]


@pytest.mark.parametrize("args", [None, [], {}, {"edits": []}, {"edits": [EDIT] * 9},
    {"edits": [EDIT], "base": 1}, {"edits": ({**EDIT},)},
    {"edits": [{"path": EDIT["path"], "old_text": "主管", "new_text": "處長"}]},
    {"edits": [{**EDIT, "unknown": True}]}, {"edits": [{**EDIT, "diff": 1}]},
    {"edits": [{**EDIT, "diff": " "}]}, {"edits": [{**EDIT, "diff": "x" * 12001}]},
    {"edits": [{**EDIT, "path": "/interviews/other/summary.md"}]}])
def test_bad_input_is_safe_and_does_not_coerce(args):
    with pytest.raises(MemoryRepairError, match="^invalid_repair_input$"):
        parse_repair_input(args)


def test_binding_owns_identity_but_preserves_invalid_original_args_for_feedback():
    message = model_message({"edits": "PRIVATE_INPUT_MARKER"})
    first, second = binding(message), binding(message)
    assert str(UUID(first.operation_id)) == first.operation_id != second.operation_id
    assert first.input_digest == second.input_digest
    assert "PRIVATE_INPUT_MARKER" not in first.model_dump_json()
    verify_repair_binding_message(first, [HumanMessage(content="原話", id=RUN), message])
    assert decode_repair_bindings([first.model_dump(mode="json")], **SCOPE) == (first,)
    assert decode_repair_bindings(None, **SCOPE) == ()


@pytest.mark.parametrize("fault", ["args", "name", "call", "message", "duplicate", "missing", "extra_call"])
def test_binding_cannot_be_rebound_to_another_original_call(fault):
    bound = binding()
    msg = model_message()
    if fault == "args": msg.tool_calls[0]["args"] = {"edits": [{**EDIT, "diff": "other"}]}
    elif fault == "name": msg.tool_calls[0]["name"] = "jd_read"
    elif fault == "call": msg.tool_calls[0]["id"] = "other"
    elif fault == "message": msg.id = "other"
    elif fault == "extra_call": msg.tool_calls.append(deepcopy(msg.tool_calls[0]))
    messages = [] if fault == "missing" else [msg, msg] if fault == "duplicate" else [msg]
    with pytest.raises(MemoryRepairError):
        verify_repair_binding_message(bound, messages)


@pytest.mark.parametrize("field,value", [("format_version", True), ("format_version", 1.0),
    ("dataset_id", DOCUMENT), ("document_id", DATASET), ("run_id", DATASET),
    ("operation_id", VERSION.upper()), ("input_digest", "invalid"),
    ("source_reference", ""), ("base", {**asdict(BASE), "revision": True})])
def test_binding_decoder_rejects_wrong_scope_and_strict_shape(field, value):
    data = binding().model_dump(mode="json")
    data[field] = value
    with pytest.raises(MemoryRepairError):
        decode_repair_bindings([data], **SCOPE)


def test_duplicate_bindings_are_not_separate_attempts():
    data = binding().model_dump(mode="json")
    with pytest.raises(MemoryRepairError):
        decode_repair_bindings([data, deepcopy(data)], **SCOPE)


def test_applied_tool_artifact_keeps_original_request_and_later_b_separate():
    bound = binding()
    outcome, request = applied(bound, later=True)
    message = make_repair_message(bound, outcome, request)
    content = json.loads(message.content)
    assert set(content) == {"status", "detail", "guide", "read_paths", "retryable"}
    assert message.status == "success" and message.name == REPAIR_NAME
    assert message.tool_call_id == bound.tool_call_id
    assert "operation_id" not in content and "head" not in content and "changes" not in message.artifact["outcome"]
    assert EDIT["diff"] not in message.content
    assert outcome["changes"] == [EDIT]  # construction does not mutate caller outcome
    decoded, saved = validate_repair_message(message, bound)
    assert saved == request and decoded["head"]["revision"] == 3
    assert decoded["applied_head"]["revision"] == 2
    serializer = JsonPlusSerializer()
    restored = serializer.loads_typed(serializer.dumps_typed(message))
    assert validate_repair_message(restored, bound) == (decoded, request)


def test_legacy_repair_artifact_accepts_both_pre_bundle_and_additive_empty_request_shapes():
    bound = binding()
    outcome, request = applied(bound)
    current = make_repair_message(bound, outcome, request)
    assert current.artifact["request"]["bundle_base_revision"] is None
    assert current.artifact["request"]["bundle_base_version_id"] is None
    assert validate_repair_message(current, bound)[1] == request

    historical = deepcopy(current)
    historical.artifact["request"].pop("bundle_base_revision")
    historical.artifact["request"].pop("bundle_base_version_id")
    assert validate_repair_message(historical, bound)[1] == request

    unsupported_layered = deepcopy(current)
    unsupported_layered.artifact["request"]["bundle_base_revision"] = 1
    unsupported_layered.artifact["request"]["bundle_base_version_id"] = VERSION
    with pytest.raises(MemoryRepairError, match="^invalid_repair_message$"):
        validate_repair_message(unsupported_layered, bound)


def test_native_anthropic_projection_excludes_artifact_but_keeps_tool_identity():
    # Exact installed adapter's normal projection, without client/provider use.
    from langchain_anthropic.chat_models import _format_messages
    bound = binding()
    outcome, request = applied(bound)
    message = make_repair_message(bound, outcome, request)
    _, wire = _format_messages([model_message(), message])
    result = wire[-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == bound.tool_call_id
    assert result["content"] == message.content
    encoded = json.dumps(wire, ensure_ascii=False)
    assert bound.operation_id not in encoded and bound.input_digest not in encoded
    assert request.artifact_digest not in encoded and "applied_head" not in encoded


def test_stale_after_prepare_retains_the_original_request_without_claiming_publication():
    bound = binding()
    _, request = applied(bound)
    later = PublishedHead(2, MemoryVersion(DOCUMENT, LATER_VERSION), SOURCE)
    outcome = {"status": "stale", "detail": "版本已更新，需重讀", "head": asdict(later), "guide": "新導覽"}
    message = make_repair_message(bound, outcome, request)
    assert message.status == "error" and json.loads(message.content)["retryable"] is True
    assert validate_repair_message(message, bound) == (outcome, request)


@pytest.mark.parametrize("status", ["invalid_edit", "stale", "no_memory", "repair_limit",
    "not_executed", "not_published"])
@pytest.mark.parametrize("failures_before", [0, 1, 2])
def test_failure_retry_projection_only_counts_correctable_status(status, failures_before):
    bound = binding(base=None if status == "no_memory" else asdict(BASE))
    outcome = {"status": status, "detail": "安全提示", "read_paths": [EDIT["path"]]}
    if status in ("stale", "no_memory"):
        outcome.update(head=asdict(BASE) if status == "stale" else None, guide="目前導覽" if status == "stale" else "")
    message = make_repair_message(bound, outcome, failures_before=failures_before)
    assert message.status == "error"
    assert json.loads(message.content)["retryable"] is (status in {"invalid_edit", "stale", "no_memory"} and failures_before < 1)
    assert validate_repair_message(message, bound, failures_before=failures_before) == (outcome, None)


@pytest.mark.parametrize("fault", ["op", "digest", "call", "name", "status", "content", "content_extra",
    "request_missing", "artifact_extra", "artifact_format", "changes", "unknown_outcome", "different_counter"])
def test_tool_projection_and_saved_artifact_cannot_disagree(fault):
    bound = binding()
    outcome = {"status": "invalid_edit", "detail": "安全提示"}
    request = None
    if fault == "request_missing": outcome, request = applied(bound)
    message = make_repair_message(bound, outcome, request)
    if fault == "op": message.artifact["operation_id"] = VERSION
    elif fault == "digest": message.artifact["input_digest"] = "b" * 64
    elif fault == "call": message.tool_call_id = "wrong"
    elif fault == "name": message.name = "jd_read"
    elif fault == "status": message.status = "success"
    elif fault == "content": message.content = '{"status":"applied"}'
    elif fault == "content_extra": message.content = json.dumps({**json.loads(message.content), "head": 1})
    elif fault == "request_missing": message.artifact["request"] = None
    elif fault == "artifact_extra": message.artifact["extra"] = True
    elif fault == "artifact_format": message.artifact["format_version"] = True
    elif fault == "changes": message.artifact["outcome"]["changes"] = [EDIT]
    elif fault == "unknown_outcome": message.artifact["outcome"]["status"] = "database_failed"
    with pytest.raises(MemoryRepairError, match="^invalid_repair_message$"):
        validate_repair_message(message, bound, failures_before=1 if fault == "different_counter" else 0)


@pytest.mark.parametrize("fault", ["op", "doc", "base", "source", "kind", "cursor", "digest",
    "applied_memory", "applied_revision", "applied_cursor", "current_doc", "current_behind", "head_missing",
    "guide_large", "guide_type", "unknown_key"])
def test_applied_requires_exact_original_request_and_nonregressing_same_document_head(fault):
    bound = binding()
    outcome, request = applied(bound)
    if fault == "op": request = replace(request, operation_id=VERSION)
    elif fault == "doc": request = replace(request, memory=MemoryVersion(DATASET, NEXT_VERSION))
    elif fault == "base": request = replace(request, expected_revision=0)
    elif fault == "source": request = replace(request, repair_sources=("different",))
    elif fault == "kind": request = replace(request, kind="consolidation")
    elif fault == "cursor": request = replace(request, processed_source=SOURCE)
    elif fault == "digest": request = replace(request, artifact_digest="invalid")
    elif fault == "applied_memory": outcome["applied_head"]["memory"]["version_id"] = VERSION
    elif fault == "applied_revision": outcome["applied_head"]["revision"] = 3
    elif fault == "applied_cursor": outcome["applied_head"]["processed_source"] = SOURCE
    elif fault == "current_doc": outcome["head"]["memory"]["document_id"] = DATASET
    elif fault == "current_behind": outcome["head"]["revision"] = 1
    elif fault == "head_missing": outcome["head"] = None
    elif fault == "guide_large": outcome["guide"] = "x" * 4001
    elif fault == "guide_type": outcome["guide"] = 1
    elif fault == "unknown_key": outcome["raw_exception"] = "PRIVATE_INPUT_MARKER"
    with pytest.raises(MemoryRepairError, match="^invalid_repair_message$"):
        make_repair_message(bound, outcome, request)


@pytest.mark.parametrize("count", [-1, True, 1.0, "1", 3])
def test_invalid_failure_count_is_not_coerced(count):
    with pytest.raises(MemoryRepairError):
        make_repair_message(binding(), {"status": "invalid_edit", "detail": "bad input"}, failures_before=count)


def test_no_message_helper_can_turn_unknown_io_into_a_correctable_result():
    with pytest.raises(MemoryRepairError):
        make_repair_message(binding(), {"status": "source_unavailable", "detail": "PRIVATE_INPUT_MARKER"})


@pytest.mark.parametrize("fault", ["extra", "boolean_revision", "tuple_sources", "extra_memory", "wrong_source"])
def test_persisted_request_decoder_rejects_loose_shapes(fault):
    bound = binding()
    outcome, request = applied(bound)
    message = make_repair_message(bound, outcome, request)
    value = message.artifact["request"]
    if fault == "extra": value["extra"] = 1
    elif fault == "boolean_revision": value["expected_revision"] = True
    elif fault == "tuple_sources": value["repair_sources"] = (SOURCE,)
    elif fault == "extra_memory": value["memory"]["extra"] = 1
    elif fault == "wrong_source": message.artifact["outcome"]["source_reference"] = "other"
    with pytest.raises(MemoryRepairError, match="^invalid_repair_message$"):
        validate_repair_message(message, bound)


def test_same_published_revision_cannot_name_a_different_memory():
    bound = binding()
    outcome, request = applied(bound)
    outcome["head"]["memory"]["version_id"] = LATER_VERSION
    with pytest.raises(MemoryRepairError):
        make_repair_message(bound, outcome, request)
