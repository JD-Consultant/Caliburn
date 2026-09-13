"""Native Saver source windows and actual request visibility; zero provider/DB."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import traceback
from uuid import uuid4

from itsdangerous import URLSafeSerializer
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
import pytest

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints
from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryService
from jd_relational.conversation_sources import (
    ConversationSourceCodec, ConversationSourceError, ConversationSourceService,
)
from jd_relational.reads import ReadError
from jd_relational.references import ReferenceCodec, SignedReference
from test_chat_history import append, native


KEY = b"synthetic-conversation-source-key-32"
SALT = "caliburn.jd.conversation-source.v1"


def service(native, *, key=KEY, dataset=None):
    graph, original_dataset, *_ = native
    return ConversationSourceService(AiRunCheckpoints(graph),
        ConversationSourceCodec(key, dataset or original_dataset))


def serializer():
    return URLSafeSerializer(KEY, salt=SALT, signer_kwargs={"digest_method": hashlib.sha256},
        serializer_kwargs={"sort_keys": True, "ensure_ascii": False, "allow_nan": False})


def seed(native, *, pause=True):
    question = AIMessage(id="original-ai-question", content=[
        {"type": "thinking", "thinking": "PRIVATE_THINKING", "signature": "PRIVATE_SIGNATURE"},
        {"type": "text", "text": "請說明你在異常時的工作？\r\n  保留脈絡。"}])
    append(native, [question], text="前一輪原話")
    current = append(native, [
        ToolMessage(id="private-tool", tool_call_id="private-call", content="PRIVATE_TOOL"),
        AIMessage(id="this-run-reply", content="本輪稍後回應，不是來源中的前問句")],
        text="只確認合約內設備。\r\n  未知不補造😀", pause=pause)
    return current, question


def public(excerpt):
    return [{"message_id": item.message_id, "role": item.role, "text": item.text}
            for item in excerpt.messages]


def test_current_saved_human_and_previous_public_ai_are_fixed_immutable_source(native):
    observed, question = seed(native)
    _, dataset, document, *_ = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    assert source.dataset_id == dataset
    assert public(excerpt) == [
        {"message_id": question.id, "role": "assistant", "text": str(question.text)},
        {"message_id": observed.record.run_id, "role": "user", "text": observed.messages[-3].content}]
    assert source.read(excerpt.source_ref, document) == excerpt
    assert service(native).read(excerpt.source_ref, document) == excerpt
    assert source.resolve(excerpt.source_ref, document).document_id == document
    assert source.resolve(excerpt.source_ref, document).readable is True
    assert "PRIVATE" not in json.dumps(public(excerpt)) and "PRIVATE" not in repr(excerpt)
    with pytest.raises(FrozenInstanceError): excerpt.messages[0].text = "cannot change"
    with pytest.raises(FrozenInstanceError): excerpt.source_ref = "cannot replace"


def test_initial_input_needs_no_finished_ai_answer_or_b1_b2(native):
    observed = append(native, [], pause=True)
    _, _, document, *_ = native
    excerpt = service(native).capture(document, observed.record.run_id)
    assert public(excerpt) == [{"message_id": observed.record.run_id, "role": "user",
                                "text": observed.messages[0].content}]


@pytest.mark.parametrize("prior", [False, True])
def test_native_start_input_checkpoint_can_supply_saved_human(prior):
    from test_ai_checkpoints import DATASET, DOCUMENT, initial_input_failure
    graph, calls, record, human, _ = initial_input_failure(prior=prior)
    source = ConversationSourceService(AiRunCheckpoints(graph), ConversationSourceCodec(KEY, DATASET))
    excerpt = source.capture(DOCUMENT, record.run_id)
    assert excerpt.messages[-1].message_id == human.id and excerpt.messages[-1].text == human.content
    assert source.read(excerpt.source_ref, DOCUMENT) == excerpt and len(calls) == int(prior)


def test_source_payload_has_exact_position_and_no_original_text(native):
    observed, _ = seed(native)
    _, dataset, document, *_ = native
    excerpt = service(native).capture(document, observed.record.run_id)
    payload = serializer().loads(excerpt.source_ref.removeprefix("conversation:"))
    assert set(payload) == {"format_version", "purpose", "dataset_id", "document_id", "run_id",
        "root_checkpoint_id", "source_namespace", "source_checkpoint_id", "first", "last"}
    assert payload["format_version"] == 1 and payload["purpose"] == "source"
    assert payload["dataset_id"] == dataset and payload["document_id"] == document
    assert payload["run_id"] == payload["last"] == observed.record.run_id
    assert payload["first"] == excerpt.messages[0].message_id
    assert payload["source_namespace"] == observed.source_config["configurable"]["checkpoint_ns"]
    assert payload["source_checkpoint_id"] == observed.source_config["configurable"]["checkpoint_id"]
    assert payload["root_checkpoint_id"] == observed.root_config["configurable"]["checkpoint_id"]
    assert "合約" not in json.dumps(payload) and len(excerpt.source_ref) <= 4096


@pytest.mark.parametrize("advance", ["same-child", "new-run"])
def test_later_native_changes_do_not_advance_original_source(native, monkeypatch, advance):
    observed, _ = seed(native, pause=advance == "same-child")
    graph, _, document, *_, calls = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    if advance == "same-child":
        graph.update_state(observed.source_config,
            {"messages": [AIMessage(id="later-child", content="later private work")]}, as_node="model")
    else:
        append(native, [AIMessage(id="later-run", content="later reply")], text="later human")
    before_calls = list(calls)
    original_get = graph.get_state
    positions = []
    def pinned(config, **kwargs):
        assert config["configurable"].get("checkpoint_id"), "read must not fall back to latest"
        positions.append(deepcopy(config))
        return original_get(config, **kwargs)
    monkeypatch.setattr(graph, "get_state", pinned)
    assert source.read(excerpt.source_ref, document) == excerpt and calls == before_calls
    expected = [observed.root_config]
    if observed.source_config != observed.root_config:
        expected.append(observed.source_config)
    assert positions == expected


def test_for_turn_captures_once_and_returns_only_metadata_without_mutating_request(native, monkeypatch):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    original_capture, calls = source.capture, []
    def capture(*args): calls.append(args); return original_capture(*args)
    monkeypatch.setattr(source, "capture", capture)
    notice_for = source.for_turn(document, observed.record.run_id)
    assert calls == []
    messages = observed.messages
    before = deepcopy(messages)
    first = notice_for(messages)
    assert set(first) == {"type", "source_ref", "messages", "instruction"}
    assert first["type"] == "conversation_source_notice"
    assert first["messages"] == [{"message_id": row.message_id, "role": row.role}
                                   for row in source.read(first["source_ref"], document).messages]
    assert "合約" not in json.dumps(first) and "PRIVATE" not in json.dumps(first)
    first["messages"].clear()
    again = notice_for([*messages, AIMessage(id="later-loop", content="next model request")])
    assert len(calls) == 1 and len(again["messages"]) == 2 and messages == before
    assert first["source_ref"] == again["source_ref"]


@pytest.mark.parametrize("fault", ["missing-human", "changed-human", "missing-ai", "changed-ai", "wrong-role",
    "reversed", "duplicate-human", "duplicate-ai", "later-human", "extra-human-between", "ai-chunk"])
def test_notice_never_claims_original_source_is_visible_after_request_changes(native, fault):
    from langchain_core.messages import AIMessageChunk
    observed, question = seed(native)
    _, _, document, *_ = native
    notice_for = service(native).for_turn(document, observed.record.run_id)
    original = notice_for(observed.messages)
    messages = observed.messages
    human = next(m for m in messages if m.id == observed.record.run_id)
    if fault == "missing-human": messages.remove(human)
    elif fault == "changed-human": messages = [m.model_copy(update={"content": "改掉原話"}) if m.id == human.id else m for m in messages]
    elif fault == "missing-ai": messages = [m for m in messages if m.id != question.id]
    elif fault == "changed-ai": messages = [m.model_copy(update={"content": "改掉問句"}) if m.id == question.id else m for m in messages]
    elif fault == "wrong-role": messages = [SystemMessage(id=m.id, content=m.content) if m.id == human.id else m for m in messages]
    elif fault == "reversed": messages = list(reversed(messages))
    elif fault == "duplicate-human": messages.append(deepcopy(human))
    elif fault == "duplicate-ai": messages.append(deepcopy(question))
    elif fault == "later-human": messages.append(HumanMessage(id=str(uuid4()), content="另一輪"))
    elif fault == "extra-human-between": messages.insert(messages.index(human), HumanMessage(id=str(uuid4()), content="漏揭露原話"))
    elif fault == "ai-chunk": messages = [AIMessageChunk(id=m.id, content=m.content) if m.id == question.id else m for m in messages]
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        notice_for(messages)
    assert notice_for(observed.messages) == original


def test_private_ai_blocks_are_not_original_fact_and_may_be_omitted_from_request(native):
    observed, question = seed(native)
    _, _, document, *_ = native
    message_view = [AIMessage(id=m.id, content=str(m.text)) if m.id == question.id else m for m in observed.messages]
    assert service(native).for_turn(document, observed.record.run_id)(message_view)["source_ref"]


def test_intervening_human_is_not_silently_swallowed_into_source(native):
    append(native, [AIMessage(id="old-ai", content="too old")], text="old human")
    append(native, [], text="middle answer")
    observed = append(native, [], text="current answer", pause=True)
    _, _, document, *_ = native
    excerpt = service(native).capture(document, observed.record.run_id)
    assert len(excerpt.messages) == 1 and excerpt.messages[0].message_id == observed.record.run_id


@pytest.mark.parametrize("fault", ["tamper", "document", "dataset", "key", "chat-anchor", "jd-ref", "old-conversation", "empty", "too-long"])
def test_foreign_or_invalid_tokens_fail_before_native_source_read(native, monkeypatch, fault):
    observed, _ = seed(native)
    graph, dataset, document, *_ = native
    source, target = service(native), document
    token = source.capture(document, observed.record.run_id).source_ref
    if fault == "tamper": token = token[:-8] + ("A" if token[-8] != "A" else "B") + token[-7:]
    elif fault == "document": target = str(uuid4())
    elif fault == "dataset": source = service(native, dataset=str(uuid4()))
    elif fault == "key": source = service(native, key=b"different-synthetic-source-key-32")
    elif fault == "chat-anchor": token = ChatHistoryService(AiRunCheckpoints(graph), ChatHistoryCodec(KEY, dataset)).read(document)["anchor"]
    elif fault == "jd-ref": token = ReferenceCodec(KEY, dataset).issue(SignedReference(document_id=document,
        revision_id=str(uuid4()), purpose="history", role="revision", kind="revision"))
    elif fault == "old-conversation": token = "conversation:eyJkb2N1bWVudCI6Ingi"
    elif fault == "empty": token = ""
    elif fault == "too-long": token = "x" * 4097
    def never(*args, **kwargs): pytest.fail("invalid source must not read native")
    monkeypatch.setattr(graph, "get_state", never)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"): source.read(token, target)
    with pytest.raises(ReadError, match="^invalid_ref$"): source.resolve(token, target)


@pytest.mark.parametrize("patch", [{"format_version": True}, {"format_version": 1.0}, {"format_version": 2},
    {"purpose": "anchor"}, {"last": "not-current-run"}, {"first": "missing-message"},
    {"first": "private-tool"}, {"first": "this-run-reply"}, {"extra": "PRIVATE_EXTRA"}])
def test_authenticated_bad_source_shape_or_range_is_not_accepted(native, patch):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    payload = serializer().loads(source.capture(document, observed.record.run_id).source_ref.removeprefix("conversation:"))
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        source.read(serializer().dumps(payload | patch), document)


@pytest.mark.parametrize("position", ["root_checkpoint_id", "source_checkpoint_id"])
def test_missing_fixed_native_position_is_unavailable_not_latest(native, position):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    payload = serializer().loads(source.capture(document, observed.record.run_id).source_ref.removeprefix("conversation:"))
    with pytest.raises(ConversationSourceError, match="^source_not_available$"):
        source.read(serializer().dumps(payload | {position: str(uuid4())}), document)


def test_source_failures_hide_input_driver_detail_and_preserve_resolver_failure_code(native, monkeypatch):
    observed, _ = seed(native)
    graph, _, document, *_ = native
    source = service(native)
    token = source.capture(document, observed.record.run_id).source_ref
    def broken(*args, **kwargs): raise OSError("PRIVATE_DSN_AND_ORIGINAL_BODY")
    monkeypatch.setattr(graph, "get_state", broken)
    for call, error_type in [(lambda: source.read(token, document), ConversationSourceError),
                             (lambda: source.resolve(token, document), ReadError)]:
        with pytest.raises(error_type, match="^source_not_available$") as error:
            call()
        assert error.value.__suppress_context__ and error.value.__cause__ is None
        assert "PRIVATE" not in "".join(traceback.format_exception(error.value))


def test_long_allowed_human_and_previous_ai_are_complete_without_pagination(native):
    append(native, [AIMessage(id="long-question", content="問" * 70000)], text="previous")
    observed = append(native, [], text="答" * 43000, pause=True)
    _, _, document, *_ = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    assert [len(row.text) for row in excerpt.messages] == [70000, 43000]
    assert source.read(excerpt.source_ref, document) == excerpt


def test_capture_rejects_absent_or_wrong_current_run_and_invalid_scope(native):
    _, _, document, *_ = native
    source = service(native)
    with pytest.raises(ConversationSourceError, match="^source_not_available$"):
        source.capture(document, str(uuid4()))
    observed = append(native, [], pause=True)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"): source.capture(document, str(uuid4()))
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"): source.capture("wrong", observed.record.run_id)
