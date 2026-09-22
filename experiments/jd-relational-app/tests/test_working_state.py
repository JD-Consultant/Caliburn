"""Working State is one checkpoint field, not a second Memory or source owner."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.consultant_context import ConsultantContext, ConsultantState, JdNoticeMiddleware
from jd_relational.runtime_checkpoints import build_document_graph
from jd_relational.working_state import (
    InterviewWorkingState, WorkingEvidence, WorkingStateError,
    WorkingStateUpdateInput, _apply_update, _model_working_state_to_domain,
    build_working_state_tools, model_working_state_schema,
    checked_working_state, sanitized_source_notice, working_state_notice,
)
from test_consultant_context import FixedModel, setup


def scope():
    dataset, document, run = (str(uuid4()) for _ in range(3))
    context = SimpleNamespace(
        dataset_id=dataset, document_id=document, run_id=run,
        memory_session=None, source_notice=None,
    )
    runtime = SimpleNamespace(state={"messages": []})
    return context, runtime


def apply(current, operations, *, context=None, runtime=None, catalog=None, source=None):
    context, runtime = (scope() if context is None else (context, runtime))
    parsed = WorkingStateUpdateInput.model_validate({"operations": operations}, strict=True)
    return _apply_update(
        parsed, runtime=runtime, context=context, current=current,
        raw_source_notice=source, session=None, catalog=catalog or {},
    )


def create_operation(**extra):
    return {"op": "create", "subject": "故障升級",
            "known_and_open": "已知本人先做初判；升級條件仍不清楚。",
            "information_needed": "取得一次實際升級案例與決定者。", **extra}


def test_create_patch_and_lifecycle_are_local_atomic_state_changes():
    state = InterviewWorkingState()
    created, receipt = apply(state, [create_operation(make_focus=True)])
    identity = receipt[0]["item_id"]
    assert identity.startswith("wi_") and created.focus_item_id == identity
    assert created.items[0].status == "open" and created.items[0].priority == "normal"

    revised, _ = apply(created, [{"op": "revise", "item_id": identity,
        "known_and_open": "已確認本人會通知主管；跨部門對象仍不清楚。"}])
    assert revised.items[0].subject == created.items[0].subject
    assert revised.items[0].information_needed == created.items[0].information_needed
    assert revised.items[0].known_and_open != created.items[0].known_and_open

    parked, _ = apply(revised, [{"op": "park", "item_id": identity}])
    assert parked.focus_item_id is None and parked.items[0].status == "parked"
    reopened, _ = apply(parked, [{"op": "reopen", "item_id": identity},
                                 {"op": "set_focus", "item_id": identity}])
    assert reopened.focus_item_id == identity and reopened.items[0].status == "open"


def test_invalid_batch_has_no_partial_effect_and_cannot_mix_lifecycle_operations():
    original, receipt = apply(InterviewWorkingState(),
                              [create_operation(make_focus=True)])
    identity = receipt[0]["item_id"]
    with pytest.raises(WorkingStateError, match="duplicate_working_item_operation"):
        apply(original, [{"op": "park", "item_id": identity},
                         {"op": "mark_captured", "item_id": identity}])
    assert original.items[0].status == "open" and original.focus_item_id == identity


def test_revise_and_mark_captured_can_share_one_atomic_batch():
    original, receipt = apply(InterviewWorkingState(),
                              [create_operation(make_focus=True)])
    identity = receipt[0]["item_id"]
    updated, _ = apply(original, [
        {"op": "revise", "item_id": identity,
         "known_and_open": "已取得本次案例，暫時不需繼續追問。"},
        {"op": "mark_captured", "item_id": identity},
    ])
    assert updated.items[0].status == "captured_pending_memory"
    assert updated.items[0].known_and_open.startswith("已取得")
    assert updated.focus_item_id is None


def test_remove_guards_require_real_read_proof_and_superseded_keeps_replacement():
    state, receipt = apply(InterviewWorkingState(),
                           [create_operation(), create_operation(subject="主管交接")])
    first, second = [entry["item_id"] for entry in receipt]
    with pytest.raises(WorkingStateError, match="working_memory_not_read"):
        apply(state, [{"op": "remove", "item_id": first,
                       "reason": "memory_reconciled", "memory_handle": "case:unknown"}])
    with pytest.raises(WorkingStateError, match="working_source_not_read"):
        apply(state, [{"op": "remove", "item_id": first,
                       "reason": "no_longer_relevant", "source_evidence_key": "E-unknown"}])
    kept, _ = apply(state, [{"op": "remove", "item_id": first,
                             "reason": "superseded", "replacement_item_id": second}])
    assert [item.item_id for item in kept.items] == [second]


def test_source_key_resolves_to_private_reference_and_projection_never_returns_it():
    context, runtime = scope()
    source_ref = "conversation:private-signed-reference"
    key = "E-current-visible"
    source = {"type": "conversation_source_notice", "source_ref": source_ref,
              "messages": [{"message_id": context.run_id, "role": "user"}],
              "instruction": "synthetic"}
    catalog = {key: WorkingEvidence(
        key, source_ref, "current_turn", context.run_id, "visible", 0)}
    state, _ = apply(
        InterviewWorkingState(),
        [create_operation(source_evidence_keys=[key], make_focus=True)],
        context=context, runtime=runtime, catalog=catalog, source=source,
    )
    assert state.items[0].source_refs == [source_ref]
    projected = working_state_notice(state.model_dump(mode="json"), context)
    encoded = json.dumps(projected, ensure_ascii=False)
    assert source_ref not in encoded
    assert "memory_basis_revision" not in projected
    assert "current_memory_revision" not in projected
    assert projected["expanded_items"][0]["evidence_keys"][0].startswith("E-")
    source_view = sanitized_source_notice(source, context)
    assert source_ref not in json.dumps(source_view) and source_view["evidence_key"].startswith("E-")


def test_prior_available_source_must_be_read_before_reuse_elsewhere():
    context, runtime = scope()
    key, source_ref = "E-prior", "conversation:prior"
    catalog = {key: WorkingEvidence(
        key, source_ref, "working_item", "wi_" + "1" * 32, "available", 0)}
    with pytest.raises(WorkingStateError, match="working_source_not_read"):
        apply(InterviewWorkingState(),
              [create_operation(source_evidence_keys=[key])],
              context=context, runtime=runtime, catalog=catalog)


def test_model_schema_cannot_supply_runtime_owned_fields():
    payload = create_operation(item_id="wi_" + "1" * 32, status="open",
                               source_refs=["conversation:forbidden"])
    with pytest.raises(Exception):
        WorkingStateUpdateInput.model_validate({"operations": [payload]}, strict=True)


def test_tool_schema_exposes_only_model_owned_working_state_arguments():
    tools = {tool.name: tool for tool in build_working_state_tools()}
    assert set(tools) == {
        "read_interview_working_item", "update_interview_working_state",
    }
    read_schema = tools["read_interview_working_item"].tool_call_schema.model_json_schema()
    assert set(read_schema["properties"]) == {"item_id"}

    update_schema = tools["update_interview_working_state"].args_schema
    assert update_schema == model_working_state_schema()
    assert set(update_schema["properties"]) == {"operations"}
    variants = update_schema["properties"]["operations"]["items"]["anyOf"]
    create_schema = next(item for item in variants
                         if item["properties"]["op"]["enum"] == ["create"])
    revise_schema = next(item for item in variants
                         if item["properties"]["op"]["enum"] == ["revise"])
    assert set(create_schema["properties"]) == {
        "op", "subject", "known_and_open", "information_needed",
        "why_it_matters", "priority", "source_evidence_keys",
        "related_handles", "make_focus",
    }
    assert set(revise_schema["properties"]) == {"op", "item_id", "changes"}
    change_schema = revise_schema["properties"]["changes"]["items"]
    assert set(change_schema["properties"]) == {
        "field", "action", "text", "priority", "evidence_keys", "related_handles",
    }
    for field in ("field", "action", "text", "priority", "evidence_keys", "related_handles"):
        assert change_schema["properties"][field].get("description")
    encoded = json.dumps(update_schema, ensure_ascii=False)
    for runtime_owned in (
        '"source_refs"', '"document_id"', '"run_id"',
        '"memory_basis_revision"', '"checkpoint_revision"',
        '"created_at"', '"updated_at"', '"receipt"', '"offset"',
    ):
        assert runtime_owned not in encoded


def test_model_revise_adapter_preserves_omitted_fields_and_distinguishes_clear():
    model_input = {
        "operations": [{
            "op": "revise", "item_id": "wi_" + "1" * 32,
            "changes": [
                {"field": "subject", "action": "set", "text": "新主題",
                 "priority": None, "evidence_keys": None, "related_handles": None},
                {"field": "why_it_matters", "action": "clear", "text": None,
                 "priority": None, "evidence_keys": None, "related_handles": None},
            ],
        }],
    }
    domain = _model_working_state_to_domain(model_input)
    parsed = WorkingStateUpdateInput.model_validate(domain, strict=True)
    operation = parsed.operations[0]
    assert operation.model_fields_set == {"op", "item_id", "subject", "why_it_matters"}
    assert operation.subject == "新主題" and operation.why_it_matters is None


@pytest.mark.parametrize("changes", [
    [
        {"field": "subject", "action": "set", "text": "A", "priority": None,
         "evidence_keys": None, "related_handles": None},
        {"field": "subject", "action": "set", "text": "B", "priority": None,
         "evidence_keys": None, "related_handles": None},
    ],
    [{"field": "subject", "action": "clear", "text": None, "priority": None,
      "evidence_keys": None, "related_handles": None}],
])
def test_model_revise_adapter_rejects_ambiguous_mutations(changes):
    with pytest.raises(ValueError):
        _model_working_state_to_domain({"operations": [{
            "op": "revise", "item_id": "wi_" + "1" * 32, "changes": changes,
        }]})


def test_update_tool_command_is_saved_in_the_existing_document_checkpoint():
    context, final = setup()
    human = HumanMessage(id=context.run_id, content="我會先判斷故障，但還沒說升級條件。")
    call = AIMessage(id="working-call", content="", tool_calls=[{
        "name": "update_interview_working_state",
        "args": {"operations": [create_operation(make_focus=True)]},
        "id": "working-call-id", "type": "tool_call",
    }], response_metadata={"stop_reason": "tool_use", "status": "completed"})
    model = FixedModel(replies=[call, final])
    child = create_agent(
        model, tools=build_working_state_tools(), system_prompt="synthetic",
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState,
        context_schema=ConsultantContext,
    )
    saver = InMemorySaver()
    root = build_document_graph(child, saver)
    config = {"configurable": {"thread_id": context.document_id}}
    result = root.invoke({"messages": [human]}, config, context=context, durability="sync")
    state = checked_working_state(result["interview_working_state"])
    assert state is not None and len(state.items) == 1
    assert state.focus_item_id == state.items[0].item_id
    assert [message.type for message in result["messages"]] == ["human", "ai", "tool", "ai"]

    reopened_child = create_agent(
        FixedModel(replies=[]), tools=build_working_state_tools(), system_prompt="synthetic",
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState,
        context_schema=ConsultantContext,
    )
    reopened = build_document_graph(reopened_child, saver)
    saved = reopened.get_state(config, subgraphs=True)
    assert checked_working_state(saved.values["interview_working_state"]) == state


def test_current_turn_key_round_trip_saves_only_resolved_source_in_private_state():
    context, final = setup()
    source_ref = "conversation:private-current-turn"
    human = HumanMessage(id=context.run_id, content="我會先判斷故障，再決定是否升級。")
    context = replace(context, source_notice=lambda messages: {
        "type": "conversation_source_notice", "source_ref": source_ref,
        "messages": [{"message_id": context.run_id, "role": "user"}],
        "instruction": "synthetic",
    })

    class SourceSelectingModel(FixedModel):
        def _generate(self, messages, *args, **kwargs):
            if not self.requests:
                blocks = [json.loads(block["text"]) for block in messages[0].content
                          if block["text"].startswith("{")]
                notice = next(block for block in blocks
                              if block.get("type") == "conversation_source_notice")
                assert source_ref not in json.dumps(messages, ensure_ascii=False, default=str)
                self.replies.append(AIMessage(
                    id="working-source-call", content="", tool_calls=[{
                        "name": "update_interview_working_state",
                        "args": {"operations": [create_operation(
                            source_evidence_keys=[notice["evidence_key"]], make_focus=True)]},
                        "id": "working-source-call-id", "type": "tool_call",
                    }], response_metadata={"stop_reason": "tool_use", "status": "completed"},
                ))
            else:
                self.replies.append(final)
            return super()._generate(messages, *args, **kwargs)

    model = SourceSelectingModel(replies=[], requests=[])
    child = create_agent(
        model, tools=build_working_state_tools(), system_prompt="synthetic",
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState,
        context_schema=ConsultantContext,
    )
    root = build_document_graph(child, InMemorySaver())
    result = root.invoke(
        {"messages": [human]}, {"configurable": {"thread_id": context.document_id}},
        context=context, durability="sync",
    )
    state = checked_working_state(result["interview_working_state"])
    assert state.items[0].source_refs == [source_ref]
    assert all(source_ref not in json.dumps(request, ensure_ascii=False, default=str)
               for request in model.requests)
    second_blocks = [json.loads(block["text"]) for block in model.requests[1][0].content
                     if block["text"].startswith("{")]
    working = next(block for block in second_blocks
                   if block.get("type") == "interview_working_state")
    assert working["expanded_items"][0]["evidence_keys"]
