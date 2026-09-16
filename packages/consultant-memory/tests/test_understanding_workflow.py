"""Durable B2 Agent over one fixed completed B1 candidate; zero provider/publication."""

from copy import deepcopy
import json
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field

from caliburn_memory import (
    CaseArtifact, CaseMaintenanceSession, EvidenceExchange, EvidenceMessage, MemoryArtifacts,
    UNDERSTANDING_MAINTENANCE_INSTRUCTIONS,
    UnderstandingMaintenanceError,
    UnderstandingMaintenanceSession, UnderstandingMaintenanceWorkflow,
    WorkUnderstandingArtifact,
)
from test_extraction import WindowSource


class FixedModel(BaseChatModel):
    replies: list[Any]
    requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "b2-understanding-maintenance-offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


def _call(name, arguments, identity):
    return AIMessage("", id=f"message-{identity}", tool_calls=[{
        "name": name, "args": arguments, "id": identity, "type": "tool_call",
    }], response_metadata={"status": "completed", "finish_reason": "tool_calls"})


def _done(identity="done"):
    return AIMessage(
        "本次工作理解整理已完成。", id=identity,
        response_metadata={"status": "completed", "finish_reason": "stop"},
    )


def _register_case_evidence(session, stage, *references):
    updated = stage
    for index, reference in enumerate(references):
        updated, _item = session.register_evidence(
            updated,
            EvidenceExchange(reference, (EvidenceMessage(reference, "user"),)),
            order_key=(0, index, 0),
            next_offset=None,
        )
    return updated


def _harness(replies, **options):
    source = WindowSource()
    base_source = source.window(
        "base", "員工原話：本人只負責故障初判與蒐集紀錄；後續跨部門協調由主管負責。",
    )
    batch_source = source.window(
        "batch", "員工補充：夜間故障時本人會先隔離設備，再把紀錄交給主管。",
    )
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_a, case_b, understanding_x = (str(uuid4()) for _ in range(3))
    version = artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=(
            f"- [故障案例](/memory/cases/items/{case_a}.md) — 故障初判與交接\n"
            f"- [交付案例](/memory/cases/items/{case_b}.md) — 交付內容核對"
        ),
        cases=(
            CaseArtifact(case_a, "## 故障案例\n本人先做故障初判並蒐集紀錄。", (base_source,)),
            CaseArtifact(case_b, "## 交付案例\n本人核對交付內容。", (base_source,)),
        ),
        understanding_guide=(
            f"- [事件與交付處理](/memory/understanding/items/{understanding_x}.md)"
        ),
        understandings=(WorkUnderstandingArtifact(
            understanding_x,
            "本人負責事件初判與交付前核對。",
            (case_a, case_b),
        ),),
    )
    case_session = CaseMaintenanceSession(artifacts)
    case_stage = case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=batch_source,
    )
    case_stage = _register_case_evidence(
        case_session, case_stage, base_source, batch_source)
    case_stage, _case = case_session.observe_case(case_stage, case_a)
    case_stage = case_session.revise_case(
        case_stage,
        case_id=case_a,
        diff=("@@\n-本人先做故障初判並蒐集紀錄。\n"
              "+本人先做故障初判、蒐集紀錄；夜間先隔離設備後交給主管。"),
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    case_stage = case_session.finish(case_stage)
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    model = FixedModel(replies=list(replies))
    options.setdefault("max_model_steps", 16)
    options.setdefault("max_tool_calls", 15)
    workflow = UnderstandingMaintenanceWorkflow(
        source, session, model, InMemorySaver(), **options,
    )
    return source, session, model, workflow, case_stage, {
        "base_source": base_source,
        "batch_source": batch_source,
        "case_a": case_a,
        "case_b": case_b,
        "understanding_x": understanding_x,
        "version": version,
    }


def _no_op_replies(ids, prefix):
    return [
        _call("read_case", {"case_id": ids["case_a"]}, f"{prefix}-read-a"),
        _call("read_case", {"case_id": ids["case_b"]}, f"{prefix}-read-b"),
        _call("read_work_understanding", {
            "understanding_id": ids["understanding_x"],
        }, f"{prefix}-read-understanding"),
        _call("revalidate_work_understanding", {
            "understanding_id": ids["understanding_x"],
            "supporting_case_ids": [ids["case_a"], ids["case_b"]],
        }, f"{prefix}-revalidate"),
        _call("finish_understanding_maintenance", {"outcome": "no_op"},
              f"{prefix}-finish"),
        _done(f"{prefix}-done"),
    ]


def test_agent_revises_stable_understanding_without_preloading_case_or_raw_text():
    source, session, model, workflow, case_stage, ids = _harness([])
    model.replies.extend([
        _call("read_case", {"case_id": ids["case_a"]}, "read-a"),
        _call("read_case", {"case_id": ids["case_b"]}, "read-b"),
        _call("read_work_understanding", {
            "understanding_id": ids["understanding_x"],
        }, "read-understanding"),
        _call("revise_work_understanding", {
            "understanding_id": ids["understanding_x"],
            "diff": ("@@\n-本人負責事件初判與交付前核對。\n"
                     "+本人負責事件初判、夜間設備隔離與交付前核對；"
                     "故障後續跨部門協調由主管負責。"),
            "supporting_case_ids": [ids["case_a"], ids["case_b"]],
            "route_note": "事件初判、夜間隔離與交付核對；主管負責後續協調",
        }, "revise"),
        _call("finish_understanding_maintenance", {"outcome": "changed"}, "finish"),
        _done(),
    ])
    source.reads.clear()

    result = workflow.start(case_stage)

    stage = session.load(result["understanding_stage"])
    assert stage.completed and stage.outcome == "changed"
    assert "跨部門協調由主管負責" in session.current_understandings(stage)[0].content
    first_request = model.requests[0]
    assert isinstance(first_request[0], SystemMessage)
    assert first_request[0].content == UNDERSTANDING_MAINTENANCE_INSTRUCTIONS
    payload = json.loads(next(
        item.content for item in first_request if isinstance(item, HumanMessage)
    ))
    assert payload["REQUIRED_CASE_IDS"] == [ids["case_a"]]
    assert payload["DIRECTLY_AFFECTED_UNDERSTANDING_IDS"] == [ids["understanding_x"]]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "夜間先隔離設備後交給主管" not in serialized
    assert "員工原話" not in serialized


def test_agent_reads_only_case_owned_source_then_returns_nonpublishable_rework():
    source, session, model, workflow, case_stage, ids = _harness([])
    model.replies.extend([
        _call("read_case", {"case_id": ids["case_a"]}, "read-case"),
        _call("read_case_source", {
            "case_id": ids["case_a"],
            "source_reference": ids["base_source"],
            "offset": 0,
        }, "read-source"),
        _call("request_case_rework", {"issues": [{
            "case_id": ids["case_a"],
            "source_reference": ids["base_source"],
            "reason": "原話明確說跨部門協調由主管負責，案例不可把它列為本人責任。",
        }]}, "rework"),
        _done("rework-done"),
    ])
    source.reads.clear()

    result = workflow.start(case_stage)

    stage = session.load(result["understanding_stage"])
    assert stage.completed and stage.outcome == "case_rework_required"
    assert [(item.case_id, item.source_reference)
            for item in stage.read_source_references] == [
        (ids["case_a"], ids["base_source"]),
    ]
    assert source.reads == [(ids["base_source"], 0)]
    source_result = next(
        item for item in result["messages"]
        if isinstance(item, ToolMessage) and item.tool_call_id == "read-source"
    )
    payload = json.loads(source_result.content)
    assert payload["source"]["reference"] == ids["base_source"]
    assert payload["source"]["next_offset"] is not None
    with pytest.raises(UnderstandingMaintenanceError, match="not publishable"):
        session.current_understandings(stage)


def test_semantic_no_op_revalidates_the_complete_support_set():
    _source, session, model, workflow, case_stage, ids = _harness([])
    model.replies.extend(_no_op_replies(ids, "no-op"))

    result = workflow.start(case_stage)

    stage = session.load(result["understanding_stage"])
    assert stage.completed and stage.outcome == "no_op"
    assert stage.binding_updates[0].understanding_id == ids["understanding_x"]
    assert set(stage.binding_updates[0].supporting_case_ids) == {
        ids["case_a"], ids["case_b"],
    }


def test_same_completed_b1_input_is_idempotent_but_changed_b1_starts_clean_attempt():
    source, session, model, workflow, case_stage, ids = _harness([])
    model.replies.extend(_no_op_replies(ids, "first"))

    first = workflow.start(case_stage)
    calls_after_first = len(model.requests)
    assert workflow.start(case_stage) == first
    assert len(model.requests) == calls_after_first

    later_source = source.window(
        "later", "員工更正：夜間也只隔離設備，交接與跨部門協調仍由主管處理。",
    )
    later_stage = session.case_session.open(
        base_publication_revision=1,
        base_version=ids["version"],
        source_reference=later_source,
    )
    later_stage = _register_case_evidence(
        session.case_session, later_stage, ids["base_source"], later_source)
    later_stage, _case = session.case_session.observe_case(later_stage, ids["case_a"])
    later_stage = session.case_session.revise_case(
        later_stage,
        case_id=ids["case_a"],
        diff=("@@\n-本人先做故障初判並蒐集紀錄。\n"
              "+本人先做故障初判並蒐集紀錄；夜間只隔離設備，"
              "交接與跨部門協調仍由主管處理。"),
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    later_stage = session.case_session.finish(later_stage)
    model.replies.extend(_no_op_replies(ids, "second"))

    second = workflow.start(later_stage)

    assert session.load(second["understanding_stage"]).completed
    assert len(model.requests) == calls_after_first + 6
    first_new_request = model.requests[calls_after_first]
    assert not any(isinstance(item, ToolMessage) for item in first_new_request)
    payload = json.loads(next(
        item.content for item in first_new_request if isinstance(item, HumanMessage)
    ))
    assert payload["REQUIRED_CASE_IDS"] == [ids["case_a"]]
    assert second["thread_model_call_count"] == 6


def test_transport_failure_resumes_same_attempt_without_replaying_checkpointed_read():
    source, session, model, workflow, case_stage, ids = _harness([])
    model.replies.extend([
        _call("read_case", {"case_id": ids["case_a"]}, "read-case"),
        RuntimeError("synthetic B2 transport fault"),
        _call("read_case_source", {
            "case_id": ids["case_a"],
            "source_reference": ids["base_source"],
            "offset": 0,
        }, "read-source"),
        _call("request_case_rework", {"issues": [{
            "case_id": ids["case_a"],
            "source_reference": ids["base_source"],
            "reason": "原話與 B1 的責任邊界不一致。",
        }]}, "rework"),
        _done(),
    ])

    with pytest.raises(RuntimeError, match="synthetic B2 transport fault"):
        workflow.start(case_stage)

    result = workflow.resume()
    stage = session.load(result["understanding_stage"])
    assert stage.outcome == "case_rework_required"
    assert len(stage.read_case_ids) == 1
    assert sum(
        isinstance(item, ToolMessage) and item.tool_call_id == "read-case"
        for item in result["messages"]
    ) == 1
    assert sum(
        isinstance(item, ToolMessage) and item.tool_call_id == "read-source"
        for item in result["messages"]
    ) == 1


def test_final_response_gets_one_bounded_completion_correction_and_resume_does_not_reset_it():
    _source, session, model, workflow, case_stage, _ids = _harness([
        _done("forgot-to-finish"),
        _done("ignored-runtime-feedback"),
    ], max_completion_corrections=1)

    with pytest.raises(ValueError, match="completion allowance exhausted"):
        workflow.start(case_stage)

    assert len(model.requests) == 2
    assert any("Runtime validation feedback" in item.content
               for item in model.requests[1] if isinstance(item, SystemMessage))
    with pytest.raises(ValueError, match="completion allowance exhausted"):
        workflow.resume()
    assert len(model.requests) == 2
    assert not session.load(
        workflow.graph.get_state(workflow.config).values["understanding_stage"],
    ).completed


def test_model_step_limit_survives_resume_instead_of_allocating_a_new_attempt():
    _source, _session, model, workflow, case_stage, _ids = _harness([
        _done("forgot-to-finish"),
    ], max_model_steps=1, max_completion_corrections=1)

    with pytest.raises(ModelCallLimitExceededError, match="Model call limit"):
        workflow.start(case_stage)
    with pytest.raises(ModelCallLimitExceededError, match="Model call limit"):
        workflow.resume()
    assert len(model.requests) == 1


def test_tool_call_limit_survives_resume_instead_of_allocating_a_new_attempt():
    _source, _session, model, workflow, case_stage, ids = _harness(
        [], max_tool_calls=1,
    )
    model.replies.extend([
        _call("read_case", {"case_id": ids["case_a"]}, "first-tool"),
        _call("read_case", {"case_id": ids["case_b"]}, "over-limit-tool"),
    ])

    with pytest.raises(ToolCallLimitExceededError, match="Tool call limit"):
        workflow.start(case_stage)
    with pytest.raises(ToolCallLimitExceededError, match="Tool call limit"):
        workflow.resume()
    assert len(model.requests) == 2


@pytest.mark.parametrize("reply, reason", [
    (AIMessage("輸出被截斷", id="incomplete", response_metadata={"status": "incomplete"}),
     "not complete"),
    (AIMessage("", id="refused", response_metadata={"status": "completed"},
               additional_kwargs={"refusal": "synthetic refusal"}),
     "refused"),
])
def test_incomplete_or_refused_model_response_cannot_complete_or_mutate_stage(reply, reason):
    _source, session, _model, workflow, case_stage, _ids = _harness([reply])

    with pytest.raises(ValueError, match=reason):
        workflow.start(case_stage)

    saved = workflow.graph.get_state(workflow.config)
    stage = session.load(saved.values["understanding_stage"])
    assert not stage.completed
    assert stage.read_case_ids == () and stage.changes == ()
