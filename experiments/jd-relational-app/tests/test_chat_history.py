"""Native fixed chat pages, synthetic messages; no provider, DB or write API."""

from copy import deepcopy
import hashlib
import json
from uuid import uuid4

from itsdangerous import URLSafeSerializer
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
import pytest

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryError, ChatHistoryService, public_chat_text
from jd_relational.references import ReadCursor, ReferenceCodec
from jd_relational.runtime_checkpoints import DocumentState, build_document_graph


KEY = b"synthetic-chat-page-key-32-bytes!!!"


@pytest.fixture
def native():
    replies, paused, calls = [], set(), []
    def model(state):
        calls.append(state["jd_ai_run"]["run_id"])
        return {"messages": deepcopy(replies)}
    def hold(state):
        if state["jd_ai_run"]["run_id"] in paused:
            interrupt("synthetic pause")
        return {}
    child = StateGraph(DocumentState)
    child.add_node("model", model); child.add_node("hold", hold)
    child.add_edge(START, "model"); child.add_edge("model", "hold"); child.add_edge("hold", END)
    graph = build_document_graph(child.compile(), InMemorySaver())
    dataset, document = str(uuid4()), str(uuid4())
    return graph, dataset, document, replies, paused, calls


def append(native, replies, *, text="原話\r\n  空白與😀保留", pause=False):
    graph, dataset, document, pending, paused, _ = native
    pending[:] = replies
    record, human = new_run_record(dataset, document, str(uuid4()), text,
        start_revision_id=str(uuid4()))
    if pause: paused.add(record.run_id)
    graph.invoke({"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None},
        {"configurable": {"thread_id": document}}, durability="sync")
    adapter = AiRunCheckpoints(graph)
    observed = adapter.discover(document, dataset)
    if not pause:
        observed = adapter.close(observed, status="completed", messages=observed.messages,
            bindings=observed.bindings, model_view=observed.model_view, read_binding=observed.read_binding)
    return observed


def service(native, *, key=KEY, dataset=None):
    graph, original_dataset, _, *_ = native
    return ChatHistoryService(AiRunCheckpoints(graph), ChatHistoryCodec(key, dataset or original_dataset))


def test_empty_history_has_exact_empty_wire_shape(native):
    _, dataset, document, *_ = native
    assert service(native).read(document) == {"dataset_id": dataset, "document_id": document,
        "anchor": None, "messages": [], "next_cursor": None}


def test_projection_preserves_original_public_text_without_private_fields(native):
    graph, dataset, document, *_ = native
    ai = AIMessage(id="native-ai-original-id", content=[
        {"type": "thinking", "thinking": "private-thinking", "signature": "private-signature"},
        {"type": "reasoning", "text": "private-nested-text"},
        {"type": "text", "text": "公開第一段\r\n", "citations": [{"title": "not-exported"}]},
        "公開純字串", {"type": "tool_use", "input": {"secret": "private-tool-input"}},
        {"type": "text", "text": "  公開最後一段。"}],
        response_metadata={"private_metadata": "not-exported"},
        usage_metadata={"input_tokens": 3, "output_tokens": 7, "total_tokens": 10})
    tool = ToolMessage(id="tool-original", tool_call_id="synthetic-call", content="private-tool-result")
    blank = AIMessage(id="tool-only", content=[{"type": "thinking", "thinking": "private-only"}])
    observed = append(native, [ai, tool, blank])
    before = graph.get_state(observed.root_config).values
    page = service(native).read(document)
    assert set(page) == {"dataset_id", "document_id", "anchor", "messages", "next_cursor"}
    assert page["dataset_id"] == dataset and page["document_id"] == document
    assert page["messages"] == [
        {"message_id": observed.record.run_id, "run_id": observed.record.run_id,
         "role": "user", "text": observed.messages[0].content},
        {"message_id": ai.id, "run_id": observed.record.run_id, "role": "assistant",
         "text": "公開第一段\r\n公開純字串  公開最後一段。"}]
    encoded = json.dumps(page, ensure_ascii=False)
    assert "private" not in encoded and "signature" not in encoded and "usage" not in encoded
    assert graph.get_state(observed.root_config).values == before


def test_pages_keep_original_anchor_after_new_run_and_new_codec(native):
    _, dataset, document, _, _, calls = native
    old = append(native, [AIMessage(id=f"original-{i}", content=f"完整公開 {i}") for i in range(105)])
    first = service(native).read(document)
    assert len(first["messages"]) == 50 and first["next_cursor"]
    append(native, [AIMessage(id="later-message", content="later-public")], text="later-human")
    second = service(native).read(document, cursor=first["next_cursor"])
    third = service(native).read(document, cursor=second["next_cursor"])
    assert first["anchor"] == second["anchor"] == third["anchor"]
    combined = first["messages"] + second["messages"] + third["messages"]
    assert [row["message_id"] for row in combined] == [message.id for message in old.messages]
    assert len(combined) == 106 and third["next_cursor"] is None and len(calls) == 2
    assert service(native).read(document)["anchor"] != first["anchor"]


def test_active_child_advance_cannot_change_remaining_fixed_page(native):
    graph, _, document, *_ = native
    observed = append(native, [AIMessage(id=f"child-{i}", content=f"before-{i}") for i in range(55)], pause=True)
    first = service(native).read(document)
    assert observed.root_config != observed.source_config and first["next_cursor"]
    # Native fixture advances only the same child, leaving the old root active.
    graph.update_state(observed.source_config,
        {"messages": [AIMessage(id="late-child-message", content="late-child-public")]}, as_node="model")
    second = service(native).read(document, cursor=first["next_cursor"])
    assert first["anchor"] == second["anchor"] and second["next_cursor"] is None
    assert [row["message_id"] for row in first["messages"] + second["messages"]] == [m.id for m in observed.messages]


@pytest.mark.parametrize("limit", [0, 51, True, 1.0, "2", None])
def test_invalid_page_limit_rejected_before_checkpoint_io(native, monkeypatch, limit):
    graph, _, document, *_ = native
    def forbidden(*_args, **_kwargs): raise AssertionError("invalid request must not read")
    monkeypatch.setattr(graph, "get_state", forbidden)
    with pytest.raises(ChatHistoryError, match="^invalid_input$"):
        service(native).read(document, limit=limit)


@pytest.mark.parametrize("fault", ["changed", "dataset", "document", "key", "jd_cursor", "anchor", "oversized", "empty"])
def test_cursor_scope_and_purpose_rejected_without_fallback(native, fault):
    _, dataset, document, *_ = native
    append(native, [AIMessage(id="one", content="one"), AIMessage(id="two", content="two")])
    first = service(native).read(document, limit=1)
    cursor, reader, target = first["next_cursor"], service(native), document
    if fault == "changed": cursor = cursor[:-1] + ("X" if cursor[-1] != "X" else "Y")
    elif fault == "dataset": reader = service(native, dataset=str(uuid4()))
    elif fault == "document": target = str(uuid4())
    elif fault == "key": reader = service(native, key=b"another-synthetic-chat-page-key!!")
    elif fault == "jd_cursor": cursor = ReferenceCodec(KEY, dataset).issue_cursor(ReadCursor(
        document_id=document, view="current", revision_id=str(uuid4()), offset=1))
    elif fault == "anchor": cursor = first["anchor"]
    elif fault == "oversized": cursor = "x" * 4097
    elif fault == "empty": cursor = ""
    with pytest.raises(ChatHistoryError, match="^invalid_cursor$"):
        reader.read(target, cursor=cursor)


def test_cursor_signed_payload_has_only_position_and_no_conversation(native):
    _, dataset, document, *_ = native
    observed = append(native, [AIMessage(id="reply", content="never-place-text-in-token")])
    first = service(native).read(document, limit=1)
    serializer = URLSafeSerializer(KEY, salt="caliburn.jd.chat-history.v1",
        signer_kwargs={"digest_method": hashlib.sha256})
    payload = serializer.loads(first["next_cursor"])
    assert payload["document_id"] == document and payload["dataset_id"] == dataset
    assert payload["run_id"] == observed.record.run_id
    assert set(payload) == {"format_version", "purpose", "dataset_id", "document_id", "run_id",
        "root_checkpoint_id", "source_namespace", "source_checkpoint_id", "offset"}
    assert "never-place-text" not in json.dumps(payload)


def test_large_message_is_not_silently_truncated(native):
    _, _, document, *_ = native
    append(native, [AIMessage(id="too-large", content="文" * 400000)])
    first = service(native).read(document)
    assert len(first["messages"]) == 1 and first["next_cursor"]
    with pytest.raises(ChatHistoryError, match="^history_page_too_large$"):
        service(native).read(document, cursor=first["next_cursor"])


def test_unknown_checkpoint_failure_never_exposes_details(native, monkeypatch):
    graph, _, document, *_ = native
    def broken(*_args, **_kwargs): raise OSError("synthetic-private-dsn-body")
    monkeypatch.setattr(graph, "get_state", broken)
    with pytest.raises(ChatHistoryError, match="^checkpoint_unavailable$") as failure:
        service(native).read(document)
    assert failure.value.__suppress_context__ and "private" not in repr(failure.value)


@pytest.mark.parametrize("fault", ["float_version", "boolean_version", "extra", "negative_offset", "past_end", "missing_root", "missing_source", "wrong_namespace"])
def test_even_signed_invalid_position_never_selects_another_snapshot(native, fault):
    _, dataset, document, *_ = native
    append(native, [AIMessage(id="one", content="one")], pause=True)
    first = service(native).read(document, limit=1)
    serializer = URLSafeSerializer(KEY, salt="caliburn.jd.chat-history.v1",
        signer_kwargs={"digest_method": hashlib.sha256})
    payload = serializer.loads(first["next_cursor"])
    if fault == "float_version": payload["format_version"] = 1.0
    elif fault == "boolean_version": payload["format_version"] = True
    elif fault == "extra": payload["unexpected"] = "must not be accepted"
    elif fault == "negative_offset": payload["offset"] = -1
    elif fault == "past_end": payload["offset"] = 500
    elif fault == "missing_root": payload["root_checkpoint_id"] = str(uuid4())
    elif fault == "missing_source": payload["source_checkpoint_id"] = str(uuid4())
    elif fault == "wrong_namespace": payload["source_namespace"] = "consultant:" + str(uuid4())
    with pytest.raises(ChatHistoryError) as error:
        service(native).read(document, cursor=serializer.dumps(payload))
    assert error.value.code in {"invalid_cursor", "invalid_checkpoint"}


@pytest.mark.parametrize("fault", ["document", "missing_id", "extra", "not_root_or_consultant", "null_namespace"])
def test_explicit_source_input_is_rejected_before_native_io(native, monkeypatch, fault):
    graph, dataset, document, *_ = native
    observed = append(native, [AIMessage(id="one", content="one")], pause=True)
    source = observed.source_config
    if fault == "document": source["configurable"]["thread_id"] = str(uuid4())
    elif fault == "missing_id": del source["configurable"]["checkpoint_id"]
    elif fault == "extra": source["unexpected"] = True
    elif fault == "not_root_or_consultant": source["configurable"]["checkpoint_ns"] = "another-node:1"
    elif fault == "null_namespace": source["configurable"]["checkpoint_ns"] = None
    def forbidden(*_args, **_kwargs): raise AssertionError("invalid source must not read")
    monkeypatch.setattr(graph, "get_state", forbidden)
    with pytest.raises(AiCheckpointError, match="^invalid_input$"):
        AiRunCheckpoints(graph).observe_at(document, observed.record.run_id, dataset,
            observed.root_config, source_config=source)


def test_explicit_source_never_asks_native_root_for_latest_child(native, monkeypatch):
    graph, dataset, document, *_ = native
    observed = append(native, [AIMessage(id="one", content="one")], pause=True)
    original_get, reads = graph.get_state, []
    def tracked(conf, **kwargs):
        reads.append((deepcopy(conf), kwargs.get("subgraphs")))
        return original_get(conf, **kwargs)
    monkeypatch.setattr(graph, "get_state", tracked)
    actual = AiRunCheckpoints(graph).observe_at(document, observed.record.run_id, dataset,
        observed.root_config, source_config=observed.source_config)
    assert actual == observed
    assert reads == [(observed.root_config, False), (observed.source_config, True)]


def test_root_source_pin_retains_pre_child_material_and_cannot_invent_another_root(native):
    graph, dataset, document, *_ = native
    observed = append(native, [AIMessage(id="one", content="one")], pause=True)
    adapter = AiRunCheckpoints(graph)
    root_only = adapter.observe_at(document, observed.record.run_id, dataset,
        observed.root_config, source_config=observed.root_config)
    assert len(root_only.messages) == 1 and root_only.source_config == root_only.root_config
    wrong = deepcopy(observed.root_config)
    wrong["configurable"]["checkpoint_id"] = str(uuid4())
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        adapter.observe_at(document, observed.record.run_id, dataset, observed.root_config, source_config=wrong)


def test_start_history_uses_saved_original_human_and_prior_complete_messages():
    from test_ai_checkpoints import DATASET, DOCUMENT, initial_input_failure
    graph, calls, record, human, previous = initial_input_failure(prior=True, prior_format=1)
    reader = ChatHistoryService(AiRunCheckpoints(graph), ChatHistoryCodec(KEY, DATASET))
    first = reader.read(DOCUMENT, limit=1)
    second = reader.read(DOCUMENT, cursor=first["next_cursor"])
    combined = first["messages"] + second["messages"]
    assert [row["message_id"] for row in combined] == [m.id for m in previous.values["messages"]] + [human.id]
    assert combined[-1] == {"message_id": human.id, "run_id": record.run_id,
                            "role": "user", "text": human.content}
    assert first["anchor"] == second["anchor"] and len(calls) == 1


def test_public_text_function_never_promotes_a_partial_ai_chunk():
    from langchain_core.messages import AIMessageChunk
    with pytest.raises(ChatHistoryError, match="^invalid_checkpoint$"):
        public_chat_text(AIMessageChunk(content="partial-public"))


def test_page_byte_limit_keeps_complete_messages_and_agrees_with_wire_size(native):
    _, _, document, *_ = native
    observed = append(native, [AIMessage(id=f"large-{i}", content="文" * 60000) for i in range(10)])
    reader, cursor, rows, anchor = service(native), None, [], None
    while True:
        page = reader.read(document, cursor=cursor)
        assert len(json.dumps(page, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")) <= 1024 * 1024
        assert 0 < len(page["messages"]) <= 50
        anchor = anchor or page["anchor"]
        assert anchor == page["anchor"]
        rows.extend(page["messages"])
        cursor = page["next_cursor"]
        if cursor is None: break
    assert [row["message_id"] for row in rows] == [m.id for m in observed.messages]
    assert all(row["text"] == "文" * 60000 for row in rows[1:])
