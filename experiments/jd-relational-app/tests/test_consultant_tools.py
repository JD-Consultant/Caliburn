"""Native tool/agent control flow with synthetic ports, no DB or provider PASS."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from jd_relational.consultant_tools import (
    AiToolError, AiToolPending, AiToolMiddleware, AiToolSession,
    build_jd_tools, decode_ai_binding, decode_ai_bindings, verify_binding_message,
)
from jd_relational.generated.reads import ReadInput, ChangeReadInput
from jd_relational.reads import ReadService
from jd_relational.references import ReferenceCodec, SignedReference, field_value_digest
from jd_relational.snapshots import empty_domain, snapshot_from_domain
from jd_relational.storage.history import HistoryError
from jd_relational.storage.receipts import SavedOperation, WriteObservation, body_for
from jd_relational.storage.service import CurrentDocument
from jd_relational.transport import MODELS
from test_consultant_context import FixedModel


@pytest.fixture(autouse=True)
def no_remote_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


class Materials:
    def __init__(self, document):
        self.value = empty_domain(document, str(uuid4()))
        self.versions = {self.value["revision"]: deepcopy(self.value)}
        self.reads = []

    def read_current(self, document):
        assert document == self.value["document_id"]
        return CurrentDocument(document, "synthetic", False, 1, UUID(self.value["revision"]),
                               1, snapshot_from_domain(self.value))

    def read_revision(self, document, revision):
        self.reads.append((document, revision))
        if document != self.value["document_id"] or str(revision) not in self.versions:
            raise HistoryError("revision_missing")
        value = self.versions[str(revision)]
        return CurrentDocument(document, "synthetic", False, 1, revision, 1, snapshot_from_domain(value))


class Owner:
    def __init__(self):
        self.calls = []
        self.status = "committed"
        self.error = None
        self.on_execute = lambda _: None

    def execute_foreground(self, permit, intent, confirm_bound):
        confirm_bound(intent.identity)
        self.on_execute(intent)
        self.calls.append(intent)
        if self.status == "unknown":
            observed = WriteObservation(intent.document_id, intent.operation_id, None, "unknown")
        else:
            receipt = SavedOperation(intent.document_id, intent.operation_id, intent.request_digest,
                "ai", permit.identity.run_id, intent.base_revision_id,
                uuid4() if self.status == "committed" else None, self.status,
                body_for(intent.command["tool"], self.status), datetime.now(timezone.utc))
            observed = WriteObservation(intent.document_id, intent.operation_id, receipt)
        return SimpleNamespace(wait=lambda timeout=None: SimpleNamespace(
            observation=observed, checkpoint_closed=False, error=self.error))


def setup():
    document, run, dataset = (str(uuid4()) for _ in range(3))
    permit = SimpleNamespace(identity=SimpleNamespace(document_id=document, run_id=run,
                                                    request_digest="a" * 64), stop_event=Event())
    codec = ReferenceCodec(b"synthetic-ai-tool-signing-key-32!", dataset)
    material = Materials(document)
    reads = ReadService(material, material, codec)
    owner = Owner()
    changes = SimpleNamespace(read=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected change read")))
    session = AiToolSession(owner, permit, material, reads, changes, codec)
    context = SimpleNamespace(tool_session=session, document_id=document, run_id=run, dataset_id=dataset)
    return session, context, owner, material, codec


def call(name, args, *, identity=None, message_id=None):
    return AIMessage(id=message_id or "msg-" + str(uuid4()), content="", tool_calls=[{
        "name": name, "args": args, "id": identity or "call-" + str(uuid4()), "type": "tool_call"}],
        response_metadata={"stop_reason": "tool_use"})


def done():
    return AIMessage(id="msg-" + str(uuid4()), content="synthetic final",
                     response_metadata={"stop_reason": "end_turn"})


def task_args():
    return {"container_ref": "fixture-task-container", "after_ref": None, "name": "合成完整任務", "description": None,
            "outcomes": [{"text": "成果甲", "basis_refs": []}, {"text": "成果乙", "basis_refs": []}],
            "requirements": [{"text": "保留重要要求", "basis_refs": []}],
            "capabilities": [], "basis_refs": []}


def run(context, replies, *, saver=None, initial=None, callbacks=()):
    # Fixed replies use an actual synthetic issued locator. This is not the run's
    # read binding: only the native jd_read ToolMessage can establish that below.
    for reply in replies:
        for request in reply.tool_calls:
            if request["args"].get("container_ref") == "fixture-task-container":
                request["args"]["container_ref"] = context.tool_session.codec.issue(SignedReference(
                    document_id=context.document_id, revision_id=context.tool_session.history.value["revision"],
                    purpose="current", role="container", kind="container", child_kind="task"))
    model = FixedModel(replies=replies)
    context.last_test_model = model
    graph = create_agent(model, tools=build_jd_tools(), middleware=[AiToolMiddleware()],
                         checkpointer=saver or InMemorySaver())
    config = {"configurable": {"thread_id": context.document_id}, "callbacks": list(callbacks)}
    result = graph.invoke(initial or {"messages": [HumanMessage(content="合成原話")],
        "jd_ai_bindings": [], "jd_ai_read": None}, config, context=context, durability="sync")
    return result, graph, model


def results(state):
    return [message for message in state["messages"] if isinstance(message, ToolMessage)]


def test_factory_uses_only_generated_shapes_and_no_runtime_fields():
    schemas = {**MODELS, "jd_read": ReadInput, "jd_change_read": ChangeReadInput}
    tools = build_jd_tools()
    assert {tool.name for tool in tools} == set(schemas)
    for tool in tools:
        assert tool.args_schema == schemas[tool.name].model_json_schema(mode="validation")
        assert tool.args_schema["type"] == "object" and tool.args_schema["additionalProperties"] is False
        assert set(tool.args_schema["required"]) == set(tool.args_schema["properties"])
        assert set(tool.args_schema["properties"]).isdisjoint({"runtime", "config", "document_id", "run_id", "operation_id"})


def test_native_after_model_checkpoint_precedes_writer_and_exact_read_is_bound():
    session, context, owner, material, codec = setup()
    saver = InMemorySaver()
    mutation = call("jd_create_task", task_args())

    def check_saved(intent):
        # Look at actual stored checkpoints before the simulated writer effect.
        persisted = list(saver.list({"configurable": {"thread_id": context.document_id}}))
        matches = [entry for entry in persisted if entry.checkpoint["channel_values"].get("jd_ai_bindings")]
        assert matches
        binding = matches[0].checkpoint["channel_values"]["jd_ai_bindings"][-1]
        decoded = decode_ai_binding(binding, dataset_id=codec.dataset_id,
                                   document_id=context.document_id, run_id=context.run_id)
        assert decoded.identity == intent.identity
        assert decoded.message_id == mutation.id and decoded.tool_call_id == mutation.tool_calls[0]["id"]

    owner.on_execute = check_saved
    state, graph, model = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}), mutation, done()], saver=saver)
    assert len(owner.calls) == 1 and owner.calls[0].base_revision_id == UUID(material.value["revision"])
    assert owner.calls[0].origin == "ai" and owner.calls[0].ai_run_id == context.run_id
    messages = results(state)
    assert [message.status for message in messages] == ["success", "success"]
    assert messages[1].tool_call_id == mutation.tool_calls[0]["id"]
    saved = json.loads(messages[1].content)
    assert saved["status"] == "committed" and saved["receipt_durability"] == "confirmed"
    assert "tool_use_id" not in saved and "content" not in saved
    assert state["jd_ai_read"]["tool_message_id"] == messages[0].id
    assert len(state["jd_ai_bindings"]) == 1 and len(model.requests) == 3


@pytest.mark.parametrize("name,args", [
    ("jd_read", {"view": "current", "target_ref": None, "cursor": {"private": "SYNTHETIC_PRIVATE_MARKER"}}),
    ("jd_create_task", {**task_args(), "runtime": "SYNTHETIC_PRIVATE_MARKER"}),
    ("jd_set_text", {"target_field_ref": "SYNTHETIC_PRIVATE_MARKER", "text": 7, "basis_refs": []}),
])
def test_invalid_arguments_have_fixed_error_and_no_writer_or_history_io(name, args, caplog):
    class Capture(BaseCallbackHandler):
        starts = []
        def on_tool_start(self, serialized, input_str, **kwargs):
            self.starts.append(input_str)
    callback = Capture()
    _, context, owner, material, _ = setup()
    request = call(name, args)
    state, _, _ = run(context, [request, done()], callbacks=[callback])
    reply = results(state)[0]
    assert reply.status == "error" and reply.tool_call_id == request.tool_calls[0]["id"]
    assert "SYNTHETIC_PRIVATE_MARKER" not in reply.content + caplog.text
    assert json.loads(reply.content).get("code", json.loads(reply.content).get("status")) == "invalid_input"
    assert owner.calls == [] and material.reads == []
    assert callback.starts == [], "Invalid original arguments must be intercepted before tool callbacks."
    assert not state.get("jd_ai_bindings")


def test_mutation_without_actual_current_read_requests_reread_without_binding():
    _, context, owner, material, _ = setup()
    state, _, _ = run(context, [call("jd_create_task", task_args()), done()])
    reply = results(state)[0]
    assert reply.status == "error" and json.loads(reply.content)["next_action"] == "reread_current"
    assert json.loads(reply.content)["status"] == "invalid_input"
    assert all(json.loads(reply.content)[key] is None for key in ("operation_ref", "result_revision_ref", "change_ref"))
    assert "type" not in json.loads(reply.content)
    assert owner.calls == [] and material.reads == [] and not state.get("jd_ai_bindings")


def test_history_read_at_head_does_not_become_a_write_binding():
    _, context, owner, material, codec = setup()
    reference = codec.issue(SignedReference(document_id=context.document_id,
        revision_id=material.value["revision"], purpose="history", role="revision", kind="revision"))
    state, _, _ = run(context, [call("jd_read", {"view": "history", "target_ref": reference, "cursor": None}),
                               call("jd_create_task", task_args()), done()])
    assert json.loads(results(state)[0].content)["access"] == "history"
    assert state.get("jd_ai_read") is None
    assert json.loads(results(state)[1].content)["next_action"] == "reread_current"
    assert owner.calls == []


def test_valid_current_read_does_not_authorize_historical_target_ref():
    _, context, owner, material, codec = setup()
    old_ref = codec.issue(SignedReference(document_id=context.document_id,
        revision_id=material.value["revision"], purpose="history", role="field", kind="profile", field="purpose",
        value_digest=field_value_digest(None)))
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        call("jd_set_text", {"target_field_ref": old_ref, "text": "不能套用", "basis_refs": []}), done()])
    assert results(state)[-1].status == "error" and owner.calls == []
    assert not state.get("jd_ai_bindings")


@pytest.mark.parametrize("case", ["source", "selection"])
def test_unavailable_source_and_selection_do_not_fabricate_authority(case):
    _, context, owner, material, codec = setup()
    mutation = call("jd_create_task", {**task_args(), "basis_refs": ["synthetic-not-issued-source"]}) if case == "source" else call(
        "jd_replace_selection", {"selection_ref": "synthetic-not-issued-selection", "replacement_text": "替換", "basis_refs": []})
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}), mutation, done()])
    assert results(state)[-1].status == "error" and owner.calls == [] and not state.get("jd_ai_bindings")


def test_unknown_outcome_stops_before_another_model_response():
    _, context, owner, _, _ = setup()
    owner.status = "unknown"
    with pytest.raises(AiToolPending) as failure:
        run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                      call("jd_create_task", task_args()), done()])
    assert str(failure.value) == "ai_tool_pending" and len(owner.calls) == 1
    assert len(context.last_test_model.requests) == 2


def test_confirmed_domain_rejection_is_a_real_error_tool_result():
    _, context, owner, _, _ = setup()
    owner.status = "stale_view"
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                               call("jd_create_task", task_args()), done()])
    reply = results(state)[-1]
    assert reply.status == "error"
    assert json.loads(reply.content)["receipt_durability"] == "confirmed"
    assert json.loads(reply.content)["next_action"] == "reread_current"


def test_more_than_one_call_and_reused_call_id_with_new_payload_stop():
    _, context, owner, _, _ = setup()
    multiple = call("jd_read", {"view": "current", "target_ref": None, "cursor": None})
    multiple.tool_calls.append(deepcopy(multiple.tool_calls[0]))
    with pytest.raises(AiToolError) as failure:
        run(context, [multiple])
    assert str(failure.value) == "multiple_tool_calls" and not owner.calls
    _, context, owner, _, _ = setup()
    first = call("jd_read", {"view": "current", "target_ref": None, "cursor": None}, identity="same-call")
    second = call("jd_create_task", task_args(), identity="same-call")
    with pytest.raises(AiToolError) as failure:
        run(context, [first, second])
    assert str(failure.value) == "tool_call_conflict" and not owner.calls


def test_failed_after_model_checkpoint_prevents_writer_entry():
    class FailingSaver(InMemorySaver):
        def put(self, config, checkpoint, metadata, versions):
            if checkpoint["channel_values"].get("jd_ai_bindings"):
                raise OSError("synthetic saver ack failure")
            return super().put(config, checkpoint, metadata, versions)
    _, context, owner, _, _ = setup()
    with pytest.raises(OSError):
        run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                      call("jd_create_task", task_args())], saver=FailingSaver())
    assert owner.calls == []


def _completed():
    session, context, owner, material, codec = setup()
    state, graph, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                                   call("jd_create_task", task_args()), done()])
    return session, context, owner, material, codec, state


def test_shared_decoder_and_original_message_verifier_roundtrip():
    session, _, owner, _, _, state = _completed()
    bindings = decode_ai_bindings(state["jd_ai_bindings"], **session.scope)
    assert len(bindings) == 1 and bindings[0].identity == owner.calls[0].identity
    assert bindings[0].command_kind == "jd_create_task"
    assert bindings[0].to_dict() == state["jd_ai_bindings"][0]
    verify_binding_message(bindings[0], state["messages"])
    assert set(state["jd_ai_bindings"][0]).isdisjoint({"arguments", "context", "command_json", "snapshot"})


@pytest.mark.parametrize("field,value", [
    ("format_version", True), ("origin", "manual"), ("command_kind", "arbitrary_sql"),
    ("operation_id", "not-a-uuid"), ("input_digest", "not-a-digest"),
    ("run_id", str(uuid4())), ("dataset_id", str(uuid4())), ("private_extra", "SYNTHETIC_PRIVATE_MARKER"),
])
def test_shared_decoder_rejects_changed_or_foreign_recovery_identity(field, value):
    session, _, _, _, _, state = _completed()
    raw = {**state["jd_ai_bindings"][0], field: value}
    with pytest.raises(AiToolError) as failure:
        decode_ai_binding(raw, **session.scope)
    assert str(failure.value) == "invalid_ai_binding"
    with pytest.raises(AiToolError):
        decode_ai_bindings(state["jd_ai_bindings"] * 2, **session.scope)


@pytest.mark.parametrize("damage", ["arguments", "message_id", "call_id", "name", "missing"])
def test_saved_binding_must_match_the_original_ai_call(damage):
    session, _, _, _, _, state = _completed()
    binding = decode_ai_bindings(state["jd_ai_bindings"], **session.scope)[0]
    messages = deepcopy(state["messages"])
    message = next(item for item in messages if item.id == binding.message_id)
    if damage == "arguments":
        message.tool_calls[0]["args"]["name"] = "SYNTHETIC_PRIVATE_MARKER"
    elif damage == "message_id":
        message.id = "another-message"
    elif damage == "call_id":
        message.tool_calls[0]["id"] = "another-call"
    elif damage == "name":
        message.tool_calls[0]["name"] = "jd_delete_item"
    else:
        messages.remove(message)
    with pytest.raises(AiToolError) as failure:
        verify_binding_message(binding, messages)
    assert str(failure.value) == "invalid_ai_binding"


def test_altered_read_message_cannot_authorize_a_mutation():
    session, context, owner, material, _ = setup()
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}), done()])
    message = next(item for item in state["messages"] if isinstance(item, ToolMessage))
    message.content += "SYNTHETIC_PRIVATE_MARKER"
    final, _, _ = run(context, [call("jd_create_task", task_args()), done()], initial=state)
    reply = results(final)[-1]
    assert reply.status == "error" and json.loads(reply.content)["next_action"] == "reread_current"
    assert "SYNTHETIC_PRIVATE_MARKER" not in reply.content
    assert owner.calls == [] and material.reads == []


def test_later_current_does_not_replace_the_exact_read_base():
    _, context, owner, material, _ = setup()
    original_revision = UUID(material.value["revision"])
    original_read = material.read_current
    def advance_after_read(document):
        read = original_read(document)
        material.value = empty_domain(document, str(uuid4()))
        material.versions[material.value["revision"]] = deepcopy(material.value)
        return read
    material.read_current = advance_after_read
    owner.status = "stale_view"  # The real SQL CAS is verified in the separate PG slice.
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                               call("jd_create_task", task_args()), done()])
    assert owner.calls[0].base_revision_id == original_revision
    assert material.reads == [(context.document_id, original_revision)]
    assert original_revision != UUID(material.value["revision"])
    assert json.loads(results(state)[-1].content)["status"] == "stale_view"


def test_confirmed_result_is_not_downgraded_by_owner_cleanup_error():
    _, context, owner, _, _ = setup()
    owner.error = "checkpoint_unavailable"
    state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
                               call("jd_create_task", task_args()), done()])
    result = json.loads(results(state)[-1].content)
    assert result["status"] == "committed" and result["receipt_durability"] == "confirmed"


def test_reopened_session_cannot_reconstruct_a_missing_bound_command_cache():
    old_session, context, _, material, codec, state = _completed()
    owner = Owner()
    context.tool_session = AiToolSession(owner, old_session.permit, material, old_session.reads, old_session.changes, codec)
    binding = state["jd_ai_bindings"][0]
    original = next(item for item in state["messages"] if item.id == binding["message_id"])
    # The pending state is immediately after after_model; already-completed
    # later messages are not replayed or appended as an artificial latest call.
    state["messages"] = state["messages"][:state["messages"].index(original) + 1]
    material.reads.clear()
    with pytest.raises(AiToolError) as failure:
        run(context, [deepcopy(original)], initial=state)
    assert str(failure.value) == "binding_cache_unavailable"
    assert owner.calls == [] and material.reads == []


@pytest.mark.parametrize("scope", ["document_id", "dataset_id", "run_id"])
def test_runtime_scope_mismatch_stops_before_read_or_binding(scope):
    _, context, owner, material, _ = setup()
    setattr(context, scope, str(uuid4()))
    with pytest.raises(AiToolError) as failure:
        run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None})])
    assert str(failure.value) == "invalid_tool_session"
    assert owner.calls == [] and material.reads == []


@pytest.mark.parametrize("view", ["item", "section"])
def test_successful_current_item_or_section_is_an_exact_run_read(view):
    _, context, owner, material, codec = setup()
    duty = str(uuid4())
    material.value["duties"][duty] = {
        "duty_id": duty, "name": "合成職責", "scope_text": None, "position": 0}
    material.versions[material.value["revision"]] = deepcopy(material.value)
    target = codec.issue(SignedReference(document_id=context.document_id,
        revision_id=material.value["revision"], purpose="current", role=view,
        kind="duty" if view == "item" else "section",
        entity_id=duty if view == "item" else "duties_tasks"))
    state, _, _ = run(context, [call("jd_read", {"view": view, "target_ref": target, "cursor": None}),
                               call("jd_create_task", task_args()), done()])
    assert json.loads(results(state)[0].content)["access"] == "current"
    assert owner.calls[0].base_revision_id == UUID(material.value["revision"])
    assert state["jd_ai_read"]["tool_message_id"] == results(state)[0].id
