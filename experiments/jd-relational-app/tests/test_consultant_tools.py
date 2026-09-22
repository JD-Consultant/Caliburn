"""Native tool/agent control flow with synthetic ports, no DB or provider PASS."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage, message_to_dict,
    messages_from_dict,
)
from langgraph.checkpoint.memory import InMemorySaver
import pytest
from caliburn_memory.requests import REQUEST_KIND, REQUEST_TOOL_NAME, request_memory_consolidation

from jd_relational.consultant_tools import (
    AiToolError, AiToolPending, AiToolMiddleware, AiToolSession, RuntimeEvidence,
    _error_result, _jd_read_message, _project_jd_read_result, _resolve_model_evidence,
    jd_evidence_catalog, reproject_active_evidence_catalog,
    build_jd_tools, decode_ai_binding, decode_ai_bindings, verify_binding_message,
)
from jd_relational.memory_context import evidence_read_projection
from jd_relational.continuation_compaction import (
    A_COMPACTION_PROFILE, ContinuationCompaction, build_request_view,
    canonical_prefix_digest,
)
from jd_relational.consultant_execution import ConsultantExecutionMiddleware
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
                uuid4() if self.status == "committed" else intent.base_revision_id if self.status == "no_change" else None,
                self.status, body_for(intent.command["tool"], self.status), datetime.now(timezone.utc))
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
            "outcomes": [{"text": "成果甲", "basis_evidence_keys": []}, {"text": "成果乙", "basis_evidence_keys": []}],
            "requirements": [{"text": "保留重要要求", "basis_evidence_keys": []}],
            "capabilities": [], "basis_evidence_keys": []}


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


def run_with_execution(context, replies, *, saver=None, initial=None, callbacks=()):
    """Run the native tools with the production A execution guard enabled."""
    for reply in replies:
        for request in reply.tool_calls:
            if request["args"].get("container_ref") == "fixture-task-container":
                request["args"]["container_ref"] = context.tool_session.codec.issue(SignedReference(
                    document_id=context.document_id, revision_id=context.tool_session.history.value["revision"],
                    purpose="current", role="container", kind="container", child_kind="task"))
    model = FixedModel(replies=replies)
    context.last_test_model = model
    graph = create_agent(model, tools=build_jd_tools(), middleware=[
        AiToolMiddleware(),
        ModelCallLimitMiddleware(thread_limit=64, exit_behavior="error"),
        ToolCallLimitMiddleware(thread_limit=63, exit_behavior="error"),
        ConsultantExecutionMiddleware(),
    ], checkpointer=saver or InMemorySaver())
    config = {"configurable": {"thread_id": context.document_id}, "callbacks": list(callbacks)}
    result = graph.invoke(initial or {"messages": [HumanMessage(id=context.run_id, content="合成原話")],
        "jd_ai_bindings": [], "jd_ai_read": None}, config, context=context, durability="sync")
    return result, graph, model


def test_consolidation_notification_executes_and_returns_to_the_model():
    """The pure background notice must not terminate the consultant loop."""
    session, context, _, _, _ = setup()
    notice = AIMessage(id="notice-message", content="", tool_calls=[{
        "name": REQUEST_TOOL_NAME, "args": {}, "id": "notice-call", "type": "tool_call",
    }], response_metadata={"stop_reason": "tool_use"})
    model = FixedModel(replies=[notice, done()])
    graph = create_agent(model, tools=[request_memory_consolidation], middleware=[AiToolMiddleware()],
                         checkpointer=InMemorySaver())
    result = graph.invoke({"messages": [HumanMessage(id=context.run_id, content="合成原話")],
        "jd_ai_bindings": [], "jd_ai_read": None},
        {"configurable": {"thread_id": context.document_id}}, context=context, durability="sync")

    messages = result["messages"]
    assert [message.type for message in messages] == ["human", "ai", "tool", "ai"]
    tool = messages[2]
    assert isinstance(tool, ToolMessage) and tool.name == REQUEST_TOOL_NAME
    assert tool.status == "success" and tool.artifact == {"kind": REQUEST_KIND}
    assert messages[3].content == "synthetic final"
    assert len(model.requests) == 2


def results(state):
    return [message for message in state["messages"] if isinstance(message, ToolMessage)]


def test_invalid_ref_error_teaches_exact_safe_recovery_without_echoing_input():
    result = _error_result(SimpleNamespace(
        code="invalid_ref",
        message="model supplied PRIVATE_BAD_REFERENCE",
    ))

    message = result["error"]["message"]
    assert result["next_action"] == "reread_current"
    assert "最新一次成功的 jd_read current" in message
    assert "原樣複製" in message
    assert "不可推測" in message
    assert "PRIVATE_BAD_REFERENCE" not in message


def test_factory_uses_only_generated_shapes_and_no_runtime_fields():
    schemas = {**MODELS, "jd_read": ReadInput, "jd_change_read": ChangeReadInput}
    tools = build_jd_tools()
    assert {tool.name for tool in tools} == set(schemas)
    for tool in tools:
        assert tool.args_schema == schemas[tool.name].model_json_schema(mode="validation")
        assert tool.args_schema["type"] == "object" and tool.args_schema["additionalProperties"] is False
        assert set(tool.args_schema["required"]) == set(tool.args_schema["properties"])
        assert set(tool.args_schema["properties"]).isdisjoint({"runtime", "config", "document_id", "run_id", "operation_id"})


def test_jd_source_projection_is_private_until_the_source_is_read():
    projected, evidence = _project_jd_read_result({
        "access": "current",
        "view": "current",
        "records": [{
            "type": "source",
            "section_ref": "section-1",
            "target_ref": "task-1",
            "related_capability_ref": None,
            "source_ref": "private-source-reference",
            "basis_status": "current",
            "readability": "not_checked",
        }],
    }, dataset_id="dataset-1", document_id="document-1", run_id="run-1")

    projected_json = json.dumps(projected, ensure_ascii=False)
    assert "private-source-reference" not in projected_json
    assert projected["records"][0]["read_status"] == "available"
    assert projected["records"][0]["basis_status"] == "current"
    assert len(evidence) == 1

    key = evidence[0].evidence_key
    catalog = {key: evidence[0]}
    with pytest.raises(AiToolError, match="source_not_read"):
        _resolve_model_evidence({"basis_refs": [key]}, catalog)

    catalog[key] = RuntimeEvidence(
        key, evidence[0].source_reference, evidence[0].scope_kind,
        evidence[0].scope_id, "read_complete", None,
    )
    assert _resolve_model_evidence({"basis_refs": [key]}, catalog) == {
        "basis_refs": ["private-source-reference"]
    }


def test_jd_model_projection_keeps_durable_item_shape_unchanged():
    projected, evidence = _project_jd_read_result({
        "access": "current",
        "view": "current",
        "records": [
            {
                "type": "container",
                "container_ref": "issued-task-container",
                "section_ref": "section-1",
                "owner_ref": "issued-duty-item",
                "child_kind": "task",
            },
            {
                "type": "item",
                "item_ref": "issued-duty-item",
                "item_id": "00000000-0000-0000-0000-000000000001",
                "section_ref": "section-1",
                "kind": "duty",
                "container_ref": "issued-duty-list-container",
                "position": "a0",
            },
        ],
    }, dataset_id="dataset-1", document_id="document-1", run_id="run-1")

    duty = projected["records"][1]
    assert duty["container_ref"] == "issued-duty-list-container"
    assert "parent_container_ref" not in duty
    assert "child_container_refs" not in duty
    assert projected["records"][0]["container_ref"] == "issued-task-container"
    assert evidence == ()


def test_active_evidence_catalog_reprojects_after_compaction_and_checkpoint_restore():
    """Compaction may change the request view, never the source-key authority."""
    dataset_id, document_id, run_id = "dataset-1", "document-1", "run-1"
    runtime = SimpleNamespace(context=SimpleNamespace(
        dataset_id=dataset_id, document_id=document_id, run_id=run_id,
    ))
    read_call = AIMessage(
        id="read-ai",
        content="",
        tool_calls=[{
            "name": "jd_read", "args": {}, "id": "read-call", "type": "tool_call",
        }],
    )
    read_result = _jd_read_message(
        "jd_read", "read-call", {
            "format_version": 2,
            "view": "current",
            "access": "current",
            "revision_ref": "revision-ref",
            "records": [{
                "type": "source",
                "section_ref": "section-ref",
                "target_ref": "task-ref",
                "related_capability_ref": None,
                "source_ref": "private-source-reference",
                "basis_status": "current",
                "readability": "available",
            }],
            "start_index": 0,
            "total_records": 1,
            "has_more": False,
            "next_cursor": None,
            "oversized_unit": False,
        },
        dataset_id=dataset_id, document_id=document_id, run_id=run_id,
    )
    canonical = {
        "messages": [HumanMessage(id=run_id, content="目前 JD 要保留這項工作。"),
                     read_call, read_result],
    }
    before = reproject_active_evidence_catalog(runtime, canonical)
    assert len(before) == 1
    key = next(iter(before))

    compaction = ContinuationCompaction(
        format_version=1,
        summary_text=f"已讀取 JD 來源；不可把 {key} 當成新來源。",
        covered_through_message_id=read_result.id,
        covered_prefix_digest=canonical_prefix_digest(canonical["messages"]),
    )
    request_view = build_request_view(
        canonical["messages"], compaction, A_COMPACTION_PROFILE,
    )
    assert any(compaction.summary_text in str(message.content) for message in request_view)

    restored_messages = messages_from_dict([
        message_to_dict(message) for message in canonical["messages"]
    ])
    restored = {
        "messages": restored_messages,
        "continuation_compaction": compaction.model_dump(mode="json"),
    }
    after = reproject_active_evidence_catalog(runtime, restored)
    assert after == before
    assert jd_evidence_catalog(runtime, restored) == {
        key: before[key],
    }

    # A summary mentioning a key is still not an authority source.  It is only
    # present in the detached request view, never in the canonical projection.
    summary_only = {
        "messages": [
            HumanMessage(id=run_id, content="目前 JD 要保留這項工作。"),
            AIMessage(id="summary-only", content=f"摘要提到 {key}。"),
        ],
        "continuation_compaction": compaction.model_dump(mode="json"),
    }
    assert reproject_active_evidence_catalog(runtime, summary_only) == {}

    tampered = deepcopy(restored_messages)
    tampered[-1].artifact["canonical_result"]["records"][0]["source_ref"] = "tampered"
    with pytest.raises(AiToolError, match="invalid_jd_evidence"):
        reproject_active_evidence_catalog(runtime, {"messages": tampered})


def test_jd_catalog_does_not_claim_another_owner_s_successful_evidence_read():
    """The shared read_evidence tool can serve a case before its next call."""
    dataset_id, document_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    context = SimpleNamespace(dataset_id=dataset_id, document_id=document_id, run_id=run_id)
    session = SimpleNamespace(**context.__dict__, head=SimpleNamespace(
        revision=1, memory=SimpleNamespace(version_id=str(uuid4()))))
    content, artifact = evidence_read_projection(
        session, case_id=str(uuid4()), evidence_key="E-case-source",
        source_reference="synthetic-case-source",
        page={"segments": [{"role": "user", "text": "合成原話", "text_offset": 0}],
              "read_offset": 0, "next_offset": None},
    )
    call = AIMessage(id="case-evidence-call", content="", tool_calls=[{
        "name": "read_evidence", "args": {"evidence_key": "E-case-source"},
        "id": "case-evidence-1", "type": "tool_call",
    }])
    result = ToolMessage(id="case-evidence-result", name="read_evidence",
                         tool_call_id="case-evidence-1", status="success",
                         content=content, artifact=artifact)
    runtime = SimpleNamespace(context=context, state={"messages": [
        HumanMessage(id=run_id, content="核對兩筆案例原話"), call, result,
    ]})
    assert jd_evidence_catalog(runtime) == {}
    result.artifact = {**artifact, "kind": "unknown_evidence_kind"}
    with pytest.raises(AiToolError, match="invalid_jd_evidence"):
        jd_evidence_catalog(runtime)


def test_active_evidence_projection_uses_hook_state_for_memory_validation(monkeypatch):
    """Node hooks receive state separately; projection must not read runtime.state."""
    captured = []

    def memory_reader(runtime):
        captured.append(runtime)
        assert isinstance(runtime.state, dict)
        return None

    monkeypatch.setattr("jd_relational.memory_context.memory_session", memory_reader)
    runtime = SimpleNamespace(
        context=SimpleNamespace(
            dataset_id="dataset-1", document_id="document-1", run_id="run-1",
            memory_session=object(), source_notice=None,
        ),
        store=object(),
    )
    state = {"messages": []}

    assert reproject_active_evidence_catalog(runtime, state) == {}
    assert len(captured) == 1 and captured[0].state is state


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
    ("jd_set_text", {"target_field_ref": "SYNTHETIC_PRIVATE_MARKER", "text": 7, "basis_evidence_keys": []}),
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
        call("jd_set_text", {"target_field_ref": old_ref, "text": "不能套用", "basis_evidence_keys": []}), done()])
    assert results(state)[-1].status == "error" and owner.calls == []
    assert not state.get("jd_ai_bindings")


@pytest.mark.parametrize("case", ["source", "selection"])
def test_unavailable_source_and_selection_do_not_fabricate_authority(case):
    _, context, owner, material, codec = setup()
    mutation = call("jd_create_task", {**task_args(), "basis_evidence_keys": ["synthetic-not-issued-source"]}) if case == "source" else call(
        "jd_replace_selection", {"selection_ref": "synthetic-not-issued-selection", "replacement_text": "替換", "basis_evidence_keys": []})
    if case == "source":
        state, _, _ = run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}), mutation, done()])
        reply = results(state)[-1]
        assert reply.status == "error" and json.loads(reply.content)["next_action"] == "correct_arguments"
        assert owner.calls == [] and len(context.last_test_model.requests) == 3
        return
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


def _named_task(name):
    arguments = task_args()
    arguments["name"] = name
    return call("jd_create_task", arguments)


def _mutation_results(state):
    return [message for message in results(state) if message.name == "jd_create_task"]


def _has_finalization_instruction(model):
    return any(isinstance(message, SystemMessage) and "不能再呼叫工具" in str(message.content)
               for request in model.requests for message in request)


def test_invalid_input_can_be_corrected_twice_but_not_submitted_a_third_time():
    _, context, owner, _, _ = setup()
    state, _, model = run_with_execution(context, [
        _named_task("任務甲"), _named_task("任務乙"), _named_task("任務丙"), done()])

    mutations = _mutation_results(state)
    assert len(model.requests) == 4
    assert len(mutations) == 3
    assert [message.status for message in mutations] == ["error"] * 3
    assert all(json.loads(message.content)["status"] == "invalid_input" for message in mutations)
    assert owner.calls == []
    assert _has_finalization_instruction(model)


def test_relationship_conflict_uses_reads_without_resetting_the_episode():
    _, context, owner, _, _ = setup()
    owner.status = "relationship_conflict"
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("關係甲"),
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("關係乙"), _named_task("關係丙"), done()])

    mutations = _mutation_results(state)
    assert len(model.requests) == 6
    assert len(owner.calls) == 3
    assert len([message for message in results(state) if message.name == "jd_read"]) == 2
    assert [json.loads(message.content)["status"] for message in mutations] == [
        "relationship_conflict", "relationship_conflict", "relationship_conflict"]
    assert _has_finalization_instruction(model)


def test_stale_view_requires_current_read_before_replanned_submission():
    _, context, owner, _, _ = setup()
    owner.status = "stale_view"
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("過期甲"), _named_task("沒有重讀"),
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("過期乙"), done()])

    mutations = _mutation_results(state)
    assert len(model.requests) == 6
    assert len(owner.calls) == 2
    assert [json.loads(message.content)["status"] for message in mutations] == [
        "stale_view", "invalid_input", "stale_view"]
    assert len([message for message in results(state) if message.name == "jd_read"]) == 2
    assert state.get("jd_ai_read") is None
    assert _has_finalization_instruction(model)


@pytest.mark.parametrize("success_status", ["committed", "no_change"])
def test_committed_or_no_change_closes_the_active_episode(success_status):
    _, context, owner, _, _ = setup()
    owner.status = "stale_view"

    def switch_after_first_attempt(_):
        if owner.calls:
            owner.status = success_status

    owner.on_execute = switch_after_first_attempt
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("第一次過期"),
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("第二次成功"), done()])

    mutations = _mutation_results(state)
    assert len(model.requests) == 5
    assert len(owner.calls) == 2
    assert [json.loads(message.content)["status"] for message in mutations] == [
        "stale_view", success_status]
    assert not _has_finalization_instruction(model)


def test_save_and_read_failures_finalize_without_replaying():
    _, context, owner, _, _ = setup()
    owner.status = "save_failed"
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("不重送"), done()])
    assert len(model.requests) == 3
    assert len(owner.calls) == 1
    assert json.loads(_mutation_results(state)[0].content)["status"] == "save_failed"
    assert _has_finalization_instruction(model)

    _, context, owner, material, _ = setup()
    original_read = material.read_current

    def failed_read(document):
        raise HistoryError("read_failed")

    material.read_current = failed_read
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}), done()])
    assert len(model.requests) == 2
    assert owner.calls == []
    assert json.loads(results(state)[0].content)["code"] == "read_failed"
    assert _has_finalization_instruction(model)
    material.read_current = original_read


def test_unknown_outcome_stops_before_another_model_response_with_guard():
    _, context, owner, _, _ = setup()
    owner.status = "unknown"
    with pytest.raises(AiToolPending, match="^ai_tool_pending"):
        run_with_execution(context, [
            call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
            _named_task("結果不明")])
    assert len(context.last_test_model.requests) == 2
    assert len(owner.calls) == 1


def test_dependent_items_never_implies_cascade_or_set_null_command():
    _, context, owner, _, _ = setup()
    owner.status = "dependent_items"
    state, _, model = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("需要明確處理關係"), done()])

    assert len(model.requests) == 3
    assert len(owner.calls) == 1
    assert [message.name for message in results(state)] == ["jd_read", "jd_create_task"]
    assert json.loads(_mutation_results(state)[0].content)["next_action"] == "resolve_dependencies"


def test_recovered_intermediate_tool_errors_remain_private_tool_messages():
    _, context, owner, _, _ = setup()
    owner.status = "stale_view"

    def switch_after_first_attempt(_):
        if owner.calls:
            owner.status = "committed"

    owner.on_execute = switch_after_first_attempt
    state, _, _ = run_with_execution(context, [
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("先失敗"),
        call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
        _named_task("後成功"), done()])

    messages = results(state)
    assert any(message.status == "error" for message in messages)
    final = state["messages"][-1]
    assert isinstance(final, AIMessage) and not final.tool_calls
    assert "stale_view" not in final.content
