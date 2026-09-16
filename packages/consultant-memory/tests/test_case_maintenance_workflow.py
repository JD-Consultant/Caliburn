"""B1 case Agent over fixed canonical windows; zero provider/publication."""

from copy import deepcopy
import json
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field

from caliburn_memory import (
    CASE_MAINTENANCE_INSTRUCTIONS,
    CaseArtifact,
    CaseMaintenanceSession,
    CaseMaintenanceWorkflow,
    MemoryArtifacts,
)
from test_extraction import WindowSource


class FixedModel(BaseChatModel):
    """Queue native Agent replies or one synthetic transport failure."""

    replies: list[Any]
    requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "b1-case-maintenance-offline-test"

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
    return AIMessage("本窗口已處理。", id=identity,
                     response_metadata={"status": "completed", "finish_reason": "stop"})


def _workflow(replies, *, generated=(), **options):
    source = WindowSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    iterator = iter(generated)
    session = CaseMaintenanceSession(
        artifacts, id_factory=(lambda: next(iterator)) if generated else None,
    )
    model = FixedModel(replies=list(replies))
    options.setdefault("max_model_steps", 16)
    options.setdefault("max_tool_calls", 15)
    workflow = CaseMaintenanceWorkflow(
        source, session, model, InMemorySaver(), **options,
    )
    return source, session, model, workflow


def _one_window(source, *, text="甲案原話：本人先做故障初判。", context="顧問問：誰負責？"):
    batch = source.window("batch", text)
    window = source.window("window", text)
    context_reference = source.window("context", context)
    source.plan(batch, [{
        "source_reference": window,
        "context_reference": context_reference,
    }])
    return batch, window, context_reference


def test_all_planned_windows_share_one_stage_and_only_outer_batch_becomes_evidence():
    first_id, second_id = str(uuid4()), str(uuid4())
    source, session, model, workflow = _workflow([
        _call("create_case", {
            "content": "## 甲案\n本人先做故障初判。",
            "route_note": "甲案、故障初判",
        }, "create-first"),
        _done("first-window-done"),
        _call("create_case", {
            "content": "## 乙案\n本人核對付款條件。",
            "route_note": "乙案、付款條件",
        }, "create-second"),
        _call("finish_case_maintenance", {"outcome": "changed"}, "finish"),
        _done("all-done"),
    ], generated=[first_id, second_id])
    batch = source.window("batch", "甲案與乙案整批原話")
    first = source.window("first", "甲案原話：本人先做故障初判。")
    second = source.window("second", "乙案原話：本人核對付款條件。")
    context = source.window("context", "顧問問：請分別說明兩個案例。")
    source.plan(batch, [
        {"source_reference": first, "context_reference": context},
        {"source_reference": second, "context_reference": None},
    ])

    result = workflow.start(
        batch, base_publication_revision=0, base_version=None,
    )

    stage = session.load(result["case_stage"])
    assert stage.completed and stage.outcome == "changed"
    assert stage.current_case_ids == tuple(sorted((first_id, second_id)))
    assert all(item.source_references == (batch,) for item in session.current_cases(stage))
    first_payload = json.loads(next(
        message.content for message in model.requests[0] if isinstance(message, HumanMessage)
    ))
    assert first_payload["WINDOW"]["position"] == 1
    assert first_payload["WINDOW"]["count"] == 2
    assert "甲案原話" in json.dumps(first_payload["NEW_SOURCE"], ensure_ascii=False)
    assert "請分別說明" in json.dumps(first_payload["CONTEXT_ONLY"], ensure_ascii=False)
    assert first_payload["CASE_GUIDE"] == ""
    assert isinstance(model.requests[0][0], SystemMessage)
    assert model.requests[0][0].content == CASE_MAINTENANCE_INSTRUCTIONS
    assert result["thread_model_call_count"] == 5
    assert result["thread_tool_call_count"] == {"__all__": 3}


def test_finish_is_rejected_before_the_final_window_then_allowed_on_the_final_window():
    source, session, _model, workflow = _workflow([
        _call("finish_case_maintenance", {"outcome": "no_op"}, "too-early"),
        _done("first-window-done"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("all-done"),
    ])
    batch = source.window("batch", "兩個沒有新工作資訊的回合")
    first = source.window("first", "寒暄一")
    second = source.window("second", "寒暄二")
    source.plan(batch, [
        {"source_reference": first, "context_reference": None},
        {"source_reference": second, "context_reference": None},
    ])

    result = workflow.start(batch, base_publication_revision=0, base_version=None)

    stage = session.load(result["case_stage"])
    assert stage.completed and stage.outcome == "no_op"
    early = next(message for message in result["messages"]
                 if isinstance(message, ToolMessage) and message.tool_call_id == "too-early")
    assert early.status == "error"
    assert json.loads(early.content)["error"] == "source_windows_remaining"


def test_agent_reads_the_current_case_before_revising_and_keeps_both_sources():
    source, session, model, workflow = _workflow([])
    case_id = str(uuid4())
    base_source = source.window("base", "使用者原先說：本人先做故障初判。")
    guide = f"- [故障處理](/memory/cases/items/{case_id}.md) — 故障初判"
    base = session.artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=guide,
        cases=(CaseArtifact(case_id, "## 故障處理\n本人先做故障初判。", (base_source,)),),
        understanding_guide="",
        understandings=(),
    )
    batch, _window, _context = _one_window(
        source, text="使用者補充：初判後也會留存紀錄。",
    )
    # Queue replies after the real base has been created so the workflow keeps
    # the same graph/session while exercising the normal read-before-write path.
    model.replies.extend([
        _call("read_case", {"case_id": case_id}, "read"),
        _call("revise_case", {
            "case_id": case_id,
            "diff": "@@\n-本人先做故障初判。\n+本人先做故障初判並留存紀錄。",
            "route_note": None,
        }, "revise"),
        _call("finish_case_maintenance", {"outcome": "changed"}, "finish"),
        _done("done"),
    ])

    result = workflow.start(batch, base_publication_revision=1, base_version=base)

    stage = session.load(result["case_stage"])
    revised = session.current_cases(stage)[0]
    assert revised.case_id == case_id
    assert "並留存紀錄" in revised.content
    assert revised.source_references == (base_source, batch)
    assert [change.kind for change in stage.changes] == ["revise"]


def test_transport_failure_after_a_tool_checkpoint_resumes_without_repeating_the_tool():
    case_id = str(uuid4())
    source, session, model, workflow = _workflow([
        _call("create_case", {
            "content": "## 故障處理\n本人先做故障初判。",
            "route_note": "故障處理、初判",
        }, "create"),
        RuntimeError("synthetic transport fault"),
        _call("finish_case_maintenance", {"outcome": "changed"}, "finish"),
        _done("done-after-resume"),
    ], generated=[case_id])
    batch, _window, _context = _one_window(source)

    with pytest.raises(RuntimeError, match="synthetic transport fault"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    result = workflow.resume()
    stage = session.load(result["case_stage"])
    assert stage.completed and stage.current_case_ids == (case_id,)
    # The prior call/result remains visible in later model requests, but its
    # semantic effect and Runtime-assigned identity occur exactly once.
    assert [change.kind for change in stage.changes] == ["create"]
    assert len(model.requests) == 4


def test_window_evidence_registry_is_checkpointed_without_copying_interview_text():
    source, session, model, workflow = _workflow([
        RuntimeError("synthetic transport fault"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("done-after-resume"),
    ])
    batch = source.window("batch", "固定批次")
    first = source.evidence("firstevidence", [
        ("assistant", "請說明誰負責初判？"),
        ("user", "我負責初判。"),
    ])
    second = source.evidence("secondevidence", [
        ("assistant", "接著如何處理？"),
        ("user", "我會留存紀錄。"),
    ])
    window = source.window("window", "我負責初判，接著留存紀錄。")
    source.set_window_evidence(window, first, second)
    source.plan(batch, [{"source_reference": window, "context_reference": None}])

    with pytest.raises(RuntimeError, match="synthetic transport fault"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    saved = workflow.graph.get_state(workflow.config)
    checkpointed = session.load(saved.values["case_stage"])
    assert [(item.evidence_key, item.source_reference) for item in checkpointed.evidence] == [
        ("E1", first), ("E2", second),
    ]
    serialized = json.dumps(checkpointed.to_dict(), ensure_ascii=False)
    assert "我負責初判" not in serialized and "留存紀錄" not in serialized
    payload = json.loads(next(
        message.content for message in model.requests[0] if isinstance(message, HumanMessage)
    ))
    assert payload["NEW_SOURCE"]["evidence"]["order"] == "oldest_to_newest"
    assert [item["evidence_key"] for item in payload["NEW_SOURCE"]["evidence"]["blocks"]] == [
        "E1", "E2",
    ]

    result = workflow.resume()
    resumed = session.load(result["case_stage"])
    assert [(item.evidence_key, item.source_reference) for item in resumed.evidence] == [
        ("E1", first), ("E2", second),
    ]


def test_read_case_uses_owner_history_order_instead_of_artifact_tuple_order():
    source, session, model, workflow = _workflow([])
    case_id = str(uuid4())
    older = source.evidence("olderevidence", [("user", "較早：本人先確認告警。")])
    newer = source.evidence("newerevidence", [("user", "較晚：補充夜間先隔離設備。")])
    guide = f"- [故障處理](/memory/cases/items/{case_id}.md) — 故障與夜間例外"
    base = session.artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=guide,
        cases=(CaseArtifact(case_id, "## 故障處理\n本人確認告警；夜間先隔離設備。",
                            (newer, older)),),
        understanding_guide="",
        understandings=(),
    )
    batch, _window, _context = _one_window(source, text="沒有新的工作資訊。")
    source.set_history(older, newer)
    model.replies.extend([
        _call("read_case", {"case_id": case_id}, "read"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("done"),
    ])

    result = workflow.start(batch, base_publication_revision=1, base_version=base)

    stage = session.load(result["case_stage"])
    assert [item.source_reference for item in sorted(stage.evidence, key=lambda item: item.order_key)] == [
        older, newer, _window,
    ]
    read_result = next(message for message in result["messages"]
                       if isinstance(message, ToolMessage) and message.tool_call_id == "read")
    payload = json.loads(read_result.content)
    blocks = payload["case"]["evidence"]["blocks"]
    assert [block["evidence_key"] for block in blocks] == ["E2", "E3"]
    assert "較早" in json.dumps(blocks[0], ensure_ascii=False)
    assert "較晚" in json.dumps(blocks[1], ensure_ascii=False)


def test_history_and_exact_evidence_paging_use_only_checkpointed_runtime_cursors():
    source, session, model, workflow = _workflow([])
    older = source.evidence("olderevidence", [(
        "user", "這是一段超過單頁的較早訪談原話，必須由 Runtime 接續讀取。",
    )])
    batch, _window, _context = _one_window(source, text="本次沒有新增工作資訊。")
    source.set_history(older)
    model.replies.extend([
        _call("browse_interview_history", {}, "browse"),
        _call("read_more_evidence", {"evidence_key": "E2"}, "more"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("done"),
    ])

    result = workflow.start(batch, base_publication_revision=0, base_version=None)

    stage = session.load(result["case_stage"])
    assert stage.history_next_offset is None and stage.history_order_count == 1
    older_entry = next(item for item in stage.evidence if item.source_reference == older)
    assert older_entry.evidence_key == "E2" and older_entry.next_offset == 24
    assert source.history_reads == [(batch, 0, 8)]
    assert (older, 0) in source.source_reads and (older, 12) in source.source_reads
    browse_result = next(message for message in result["messages"]
                         if isinstance(message, ToolMessage) and message.tool_call_id == "browse")
    browse_payload = json.loads(browse_result.content)
    assert browse_payload["evidence"]["blocks"][0]["evidence_key"] == "E2"
    assert "source_reference" not in browse_result.content and "offset" not in browse_result.content


def test_history_cursor_and_evidence_keys_resume_at_the_next_owner_page():
    source, session, model, workflow = _workflow([])
    history = tuple(source.evidence(f"history{letter}", [("user", f"歷史訪談 {letter}")])
                    for letter in "abcdefghi")
    batch, current_window, _context = _one_window(source, text="本次沒有新增工作資訊。")
    source.set_history(*history)
    model.replies.extend([
        _call("browse_interview_history", {}, "browse-first"),
        RuntimeError("synthetic transport fault"),
        _call("browse_interview_history", {}, "browse-second"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("done"),
    ])

    with pytest.raises(RuntimeError, match="synthetic transport fault"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    # The outer snapshot still shows the agent-node input while its pending
    # writes are retained internally.  Actual resume behaviour is the proof:
    # it must not ask the owner for offset 0 again.
    assert source.history_reads == [(batch, 0, 8)]

    result = workflow.resume()
    resumed = session.load(result["case_stage"])
    assert resumed.history_next_offset is None and resumed.history_order_count == 9
    assert [(item.evidence_key, item.source_reference) for item in resumed.evidence] == [
        ("E1", current_window),
        *((f"E{index}", reference) for index, reference in enumerate(history, 2)),
    ]
    assert resumed.evidence[-1].evidence_key == "E10"
    assert resumed.evidence[-1].source_reference == history[-1]
    assert source.history_reads == [(batch, 0, 8), (batch, 8, 8)]


def test_read_case_fails_closed_when_owner_cannot_prove_every_citation_order():
    source, session, model, workflow = _workflow([])
    case_id = str(uuid4())
    proven = source.evidence("provenevidence", [("user", "可證明順序的原話。")])
    missing = source.evidence("missingevidence", [("user", "未出現在固定歷史的原話。")])
    guide = f"- [故障處理](/memory/cases/items/{case_id}.md) — 故障處理"
    base = session.artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=guide,
        cases=(CaseArtifact(case_id, "## 故障處理\n本人確認告警。", (proven, missing)),),
        understanding_guide="",
        understandings=(),
    )
    batch, _window, _context = _one_window(source, text="沒有新的工作資訊。")
    source.set_history(proven)
    model.replies.extend([
        _call("read_case", {"case_id": case_id}, "read"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish"),
        _done("done"),
    ])

    result = workflow.start(batch, base_publication_revision=1, base_version=base)

    stage = session.load(result["case_stage"])
    assert stage.read_case_ids == ()
    read_result = next(message for message in result["messages"]
                       if isinstance(message, ToolMessage) and message.tool_call_id == "read")
    assert read_result.status == "error"
    assert json.loads(read_result.content)["error"] == "case_evidence_order_unavailable"


def test_final_window_gets_one_bounded_completion_correction_not_a_fresh_job():
    source, session, model, workflow = _workflow([
        _done("forgot-to-finish"),
        _done("ignored-runtime-feedback"),
    ], max_completion_corrections=1)
    batch, _window, _context = _one_window(source)

    with pytest.raises(ValueError, match="completion allowance exhausted"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    assert len(model.requests) == 2
    assert any("Runtime validation feedback" in message.content
               for message in model.requests[1] if isinstance(message, SystemMessage))
    with pytest.raises(ValueError, match="completion allowance exhausted"):
        workflow.resume()
    assert len(model.requests) == 2
    assert not session.load(workflow.graph.get_state(workflow.config).values["case_stage"]).completed


def test_model_step_limit_survives_resume_instead_of_resetting():
    source, _session, model, workflow = _workflow([
        _done("forgot-to-finish"),
    ], max_model_steps=1, max_completion_corrections=1)
    batch, _window, _context = _one_window(source)

    with pytest.raises(ModelCallLimitExceededError, match="Model call limit"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    assert len(model.requests) == 1
    with pytest.raises(ModelCallLimitExceededError, match="Model call limit"):
        workflow.resume()
    assert len(model.requests) == 1


@pytest.mark.parametrize("reply, reason", [
    (AIMessage("輸出被截斷", id="incomplete", response_metadata={"status": "incomplete"}),
     "not complete"),
    (AIMessage("", id="refused", response_metadata={"status": "completed"},
               additional_kwargs={"refusal": "synthetic refusal"}),
     "refused"),
])
def test_incomplete_or_refused_model_response_never_completes_the_stage(reply, reason):
    source, session, _model, workflow = _workflow([reply])
    batch, _window, _context = _one_window(source)

    with pytest.raises(ValueError, match=reason):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    saved = workflow.graph.get_state(workflow.config)
    assert saved.next
    assert not session.load(saved.values["case_stage"]).completed


def test_incomplete_response_cannot_execute_its_proposed_case_tool():
    reply = _call("create_case", {
        "content": "不完整輸出不得寫入。", "route_note": "不完整",
    }, "incomplete-tool")
    reply.response_metadata["status"] = "incomplete"
    source, session, _model, workflow = _workflow([reply], generated=[str(uuid4())])
    batch, _window, _context = _one_window(source)

    with pytest.raises(ValueError, match="not complete"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    saved = workflow.graph.get_state(workflow.config)
    stage = session.load(saved.values["case_stage"])
    assert stage.changes == () and stage.upserts == ()


def test_next_fixed_batch_clears_old_messages_and_gets_its_own_bounded_attempt():
    source, session, model, workflow = _workflow([
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish-first"),
        _done("done-first"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish-second"),
        _done("done-second"),
    ])
    first = source.window("firstbatch", "第一批專屬內容")
    first_window = source.window("firstwindow", "第一批專屬內容")
    source.plan(first, [{"source_reference": first_window, "context_reference": None}])
    second = source.window("secondbatch", "第二批專屬內容")
    second_window = source.window("secondwindow", "第二批專屬內容")
    source.plan(second, [{"source_reference": second_window, "context_reference": None}])

    original = workflow.start(first, base_publication_revision=0, base_version=None)
    calls_after_first = len(model.requests)
    assert workflow.start(first, base_publication_revision=0, base_version=None) == original
    assert len(model.requests) == calls_after_first

    result = workflow.start(second, base_publication_revision=0, base_version=None)

    stage = session.load(result["case_stage"])
    assert stage.completed and stage.source_reference == second
    assert result["thread_model_call_count"] == 2
    second_request = model.requests[calls_after_first]
    contents = "\n".join(str(message.content) for message in second_request)
    assert "第二批專屬內容" in contents
    assert "第一批專屬內容" not in contents


def test_same_source_with_a_new_base_is_a_fresh_semantic_attempt_after_stale():
    source, session, model, workflow = _workflow([
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish-v0"),
        _done("done-v0"),
        _call("finish_case_maintenance", {"outcome": "no_op"}, "finish-v1"),
        _done("done-v1"),
    ])
    batch, _window, _context = _one_window(source)
    first = workflow.start(batch, base_publication_revision=0, base_version=None)
    calls_after_first = len(model.requests)
    base = session.artifacts.save_bundle(
        base_publication_revision=0,
        case_guide="",
        cases=(),
        understanding_guide="",
        understandings=(),
    )

    second = workflow.start(batch, base_publication_revision=1, base_version=base)

    assert len(model.requests) == calls_after_first + 2
    assert first["case_stage"]["base_publication_revision"] == 0
    assert second["case_stage"]["base_publication_revision"] == 1
    assert second["case_stage"]["base_memory_version_id"] == base.version_id
    assert second["thread_model_call_count"] == 2


def test_too_many_windows_stop_before_source_read_or_model_call():
    source, _session, model, workflow = _workflow([], max_windows=1)
    batch = source.window("batch", "整批")
    first = source.window("first", "甲案")
    second = source.window("second", "乙案")
    source.plan(batch, [
        {"source_reference": first, "context_reference": None},
        {"source_reference": second, "context_reference": None},
    ])
    source.reads.clear()

    with pytest.raises(ValueError, match="Too many case-maintenance windows"):
        workflow.start(batch, base_publication_revision=0, base_version=None)

    assert source.reads == [] and model.requests == []
