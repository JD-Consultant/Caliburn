"""Offline checks for non-destructive, App-side context compaction."""

from copy import deepcopy
from dataclasses import dataclass
import json
from threading import Event

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.consultant_context import ConsultantState
from jd_relational.continuation_compaction import (
    A_COMPACTION_PROFILE,
    B1_COMPACTION_PROFILE,
    B2_COMPACTION_PROFILE,
    CompactionProfile,
    ContinuationCompaction,
    ContinuationCompactionError,
    ContinuationCompactionMiddleware,
    ContinuationCompactionState,
    _summary_prompt,
    build_request_view,
    canonical_prefix_digest,
    select_safe_boundary,
)
from jd_relational.working_state import InterviewWorkingState, WorkingItem


class FixedModel(BaseChatModel):
    replies: list[AIMessage]
    requests: list = []

    @property
    def _llm_type(self):
        return "continuation-compaction-offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def completed(identity, content):
    return AIMessage(
        id=identity,
        content=content,
        response_metadata={"status": "completed", "finish_reason": "stop"},
    )


def conversation():
    return [
        HumanMessage(id="h1", content="案例 A：每週巡檢。"),
        AIMessage(id="a1", content="A 已記錄。"),
        HumanMessage(id="h2", content="請讀取相關案例。"),
        AIMessage(
            id="a2",
            content="我會讀兩份。",
            tool_calls=[
                {"name": "read_case", "args": {"id": "A"}, "id": "call-a"},
                {"name": "read_case", "args": {"id": "B"}, "id": "call-b"},
            ],
        ),
        ToolMessage(id="t1", name="read_case", tool_call_id="call-a", content="A result"),
        ToolMessage(id="t2", name="read_case", tool_call_id="call-b", content="B result"),
        AIMessage(id="a3", content="兩份都已讀完。"),
        HumanMessage(id="h3", content="最新更正：其實是每月。"),
    ]


def test_safe_boundary_never_splits_parallel_tools_or_latest_employee_input():
    messages = conversation()
    assert select_safe_boundary(
        messages,
        A_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1}),
    ) == 7

    shortened = messages[:6]
    assert select_safe_boundary(
        shortened,
        CompactionProfile(trigger_input_tokens=1, keep_messages=2),
    ) == 2


def test_request_only_compaction_does_not_delete_private_tool_artifacts():
    private = {"source_reference": "conversation:PRIVATE", "next_offset": None}
    messages = [
        HumanMessage(id="h1", content="請核對案例原話。"),
        AIMessage(
            id="a1",
            content="",
            tool_calls=[{
                "name": "read_evidence",
                "args": {"evidence_key": "E-safe"},
                "id": "call-evidence",
            }],
        ),
        ToolMessage(
            id="t1",
            name="read_evidence",
            tool_call_id="call-evidence",
            content='{"evidence_key":"E-safe","has_more":false}',
            artifact=private,
        ),
        AIMessage(id="a2", content="已完成原話核對。"),
        HumanMessage(id="h2", content="請繼續。"),
    ]
    profile = A_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1})
    boundary = select_safe_boundary(messages, profile)
    assert boundary == 4
    state = ContinuationCompaction(
        format_version=1,
        summary_text="先前案例原話已核對。",
        covered_through_message_id="a2",
        covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
    )

    view = build_request_view(messages, state, profile)

    assert [message.id for message in view] == [view[0].id, "h2"]
    assert view[0].id.startswith("continuation-summary:")
    assert messages[2].artifact == private
    assert messages[2].content == '{"evidence_key":"E-safe","has_more":false}'


def test_summary_prompt_keeps_visible_tool_wave_and_excludes_private_metadata():
    messages = [
        HumanMessage(id="h1", content="請核對案例原話。"),
        AIMessage(
            id="a1",
            content="我會查證。",
            tool_calls=[{
                "name": "read_evidence",
                "args": {"evidence_key": "E-safe"},
                "id": "call-evidence",
            }],
            additional_kwargs={
                "reasoning_details": [{"data": "PRIVATE-OPAQUE-REASONING"}],
            },
            response_metadata={"private_provider_marker": "PRIVATE-RESPONSE"},
        ),
        ToolMessage(
            id="t1",
            name="read_evidence",
            tool_call_id="call-evidence",
            content='{"evidence_key":"E-safe","has_more":false}',
            artifact={"source_reference": "PRIVATE-SIGNED-REFERENCE"},
            status="success",
        ),
    ]

    prompt = _summary_prompt(None, messages)
    payload = json.loads(prompt.split("\n", 1)[1])

    assert payload == {
        "protected_orientation": [],
        "existing_summary": None,
        "new_completed_messages": [
            {"role": "user", "content": "請核對案例原話。"},
            {
                "role": "assistant",
                "content": "我會查證。",
                "tool_calls": [{
                    "name": "read_evidence",
                    "args": {"evidence_key": "E-safe"},
                    "id": "call-evidence",
                }],
            },
            {
                "role": "tool",
                "content": '{"evidence_key":"E-safe","has_more":false}',
                "name": "read_evidence",
                "tool_call_id": "call-evidence",
                "status": "success",
            },
        ],
    }
    assert "PRIVATE-OPAQUE-REASONING" not in prompt
    assert "PRIVATE-RESPONSE" not in prompt
    assert "PRIVATE-SIGNED-REFERENCE" not in prompt


def test_uncovered_reasoning_details_survive_checkpoint_and_request_view():
    reasoning_details = [{
        "type": "reasoning.encrypted",
        "data": "opaque-recent-reasoning",
    }]
    messages = [
        HumanMessage(id="h-old", content="舊工作"),
        AIMessage(id="a-old", content="舊工作已完成"),
        HumanMessage(id="h-current", content="請繼續目前工作"),
        AIMessage(
            id="a-current",
            content="",
            tool_calls=[{
                "name": "jd_read",
                "args": {"view": "current"},
                "id": "call-current",
            }],
            additional_kwargs={"reasoning_details": reasoning_details},
        ),
        ToolMessage(
            id="t-current",
            tool_call_id="call-current",
            content="目前 JD 已讀取",
        ),
    ]
    restored = messages_from_dict([message_to_dict(message) for message in messages])
    state = ContinuationCompaction(
        format_version=1,
        summary_text="舊工作摘要",
        covered_through_message_id="a-old",
        covered_prefix_digest=canonical_prefix_digest(messages[:2]),
    )

    view = build_request_view(restored, state, A_COMPACTION_PROFILE)
    recent = next(message for message in view if message.id == "a-current")
    prompt = _summary_prompt(None, restored[2:])

    assert recent.additional_kwargs["reasoning_details"] == reasoning_details
    assert "opaque-recent-reasoning" not in prompt


@pytest.mark.parametrize(("profile", "marker"), [
    (A_COMPACTION_PROFILE, "訪談焦點"),
    (B1_COMPACTION_PROFILE, "案例身分與差異"),
    (B2_COMPACTION_PROFILE, "跨案例"),
])
def test_summary_request_uses_role_specific_retention_instructions(profile, marker):
    summary = FixedModel(replies=[completed("summary", "角色摘要")])
    main = FixedModel(replies=[completed("answer", "繼續")])
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=profile.model_copy(update={
                "trigger_input_tokens": 1,
                "keep_messages": 1,
            }),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
    )

    agent.invoke({"messages": conversation()})

    assert marker in summary.requests[0][0].text


def test_b2_summary_reads_fixed_task_as_orientation_without_covering_it():
    summary = FixedModel(replies=[completed("summary", "B2 摘要")])
    main = FixedModel(replies=[completed("answer", "繼續 B2")])
    messages = [
        HumanMessage(id="task", content="固定 B2 任務原文"),
        AIMessage(id="a1", content="開始讀案例"),
        HumanMessage(id="h1", content="繼續"),
        AIMessage(id="a2", content="已完成一段比較"),
        HumanMessage(id="h2", content="目前尾段"),
    ]
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=B2_COMPACTION_PROFILE.model_copy(update={
                "trigger_input_tokens": 1,
                "keep_messages": 1,
            }),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
    )

    agent.invoke({"messages": messages})

    payload = json.loads(summary.requests[0][1].text.split("\n", 1)[1])
    assert payload["protected_orientation"] == [
        {"role": "user", "content": "固定 B2 任務原文"}
    ]
    assert payload["new_completed_messages"][0] == {
        "role": "assistant",
        "content": "開始讀案例",
    }
    assert main.requests[0][0].content == "固定 B2 任務原文"
    assert main.requests[0][1].id.startswith("continuation-summary:")


def test_b1_single_current_window_is_never_a_compaction_boundary():
    messages = [
        HumanMessage(id="window-1", content="尚在處理的完整訪談窗口"),
        AIMessage(
            id="b1-call",
            content="讀取案例",
            tool_calls=[{"name": "read_case", "args": {"id": "A"}, "id": "call-a"}],
        ),
        ToolMessage(id="b1-tool", name="read_case", tool_call_id="call-a", content="A result"),
        AIMessage(id="b1-done", content="完成目前工具 wave"),
    ]
    profile = B1_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1})
    assert select_safe_boundary(messages, profile) is None


def test_b1_previous_processed_window_becomes_compactable_only_after_next_window_arrives():
    messages = [
        HumanMessage(id="window-1", content="已完整處理的第一段訪談"),
        AIMessage(id="window-1-done", content="第一段處理完成"),
        HumanMessage(id="window-2", content="目前尚未完整處理的第二段訪談"),
        AIMessage(id="window-2-work", content="正在處理第二段"),
    ]
    profile = B1_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1})
    boundary = select_safe_boundary(messages, profile)
    assert boundary == 2
    state = ContinuationCompaction(
        format_version=1,
        summary_text="第一段訪談與處理進度的非權威延續摘要。",
        covered_through_message_id="window-1-done",
        covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
    )
    view = build_request_view(messages, state, profile)
    assert view[0].id.startswith("continuation-summary:")
    assert [message.id for message in view[1:]] == ["window-2", "window-2-work"]
    assert messages[0].id == "window-1" and messages[2].content.endswith("第二段訪談")


def test_b2_keeps_initial_task_exact_but_can_compact_completed_tool_waves():
    messages = [
        HumanMessage(id="task", content="整理本文件的工作理解。"),
        AIMessage(
            id="b2-a1",
            content="先讀案例 A。",
            tool_calls=[{"name": "read_case", "args": {"id": "A"}, "id": "b2-call-a"}],
        ),
        ToolMessage(id="b2-t1", name="read_case", tool_call_id="b2-call-a", content="A result"),
        AIMessage(
            id="b2-a2",
            content="再讀案例 B。",
            tool_calls=[{"name": "read_case", "args": {"id": "B"}, "id": "b2-call-b"}],
        ),
        ToolMessage(id="b2-t2", name="read_case", tool_call_id="b2-call-b", content="B result"),
    ]
    boundary = select_safe_boundary(
        messages,
        B2_COMPACTION_PROFILE.model_copy(update={"keep_messages": 2}),
    )
    assert boundary == 3
    state = ContinuationCompaction(
        format_version=1,
        summary_text="已完成案例 A 的讀取；接著讀 B。",
        covered_through_message_id=messages[boundary - 1].id,
        covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
    )
    view = build_request_view(messages, state, B2_COMPACTION_PROFILE)
    assert view[0].model_dump() == messages[0].model_dump()
    assert isinstance(view[1], AIMessage)
    assert "對話延續摘要" in view[1].content
    assert all(message.id != "b2-a1" for message in view)


def test_a_keeps_current_employee_input_exact_while_compacting_completed_tool_waves():
    messages = [
        HumanMessage(id="employee-current", content="請依目前資料完成這份 JD。"),
        AIMessage(
            id="a-read-1",
            content="先讀目前 JD。",
            tool_calls=[{"name": "jd_read", "args": {"view": "current"}, "id": "call-read-1"}],
        ),
        ToolMessage(id="t-read-1", name="jd_read", tool_call_id="call-read-1", content="JD page 1"),
        AIMessage(
            id="a-read-2",
            content="再讀工作理解。",
            tool_calls=[{"name": "read_work_understanding", "args": {}, "id": "call-read-2"}],
        ),
        ToolMessage(
            id="t-read-2",
            name="read_work_understanding",
            tool_call_id="call-read-2",
            content="工作理解結果",
        ),
        AIMessage(
            id="a-recent",
            content="保留近期寫入。",
            tool_calls=[{"name": "jd_insert_item", "args": {}, "id": "call-recent"}],
        ),
        ToolMessage(
            id="t-recent",
            name="jd_insert_item",
            tool_call_id="call-recent",
            content="最近寫入結果",
        ),
    ]
    summary = FixedModel(replies=[completed("summary", "已讀目前 JD 與工作理解。")])
    main = FixedModel(replies=[completed("answer", "繼續完成 JD。")])
    profile = A_COMPACTION_PROFILE.model_copy(update={
        "trigger_input_tokens": 1,
        "keep_messages": 2,
    })
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=profile,
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
    )

    result = agent.invoke({"messages": messages})

    payload = json.loads(summary.requests[0][1].text.split("\n", 1)[1])
    assert payload["protected_orientation"] == [{
        "role": "user",
        "content": "請依目前資料完成這份 JD。",
    }]
    assert all(
        item != {"role": "user", "content": "請依目前資料完成這份 JD。"}
        for item in payload["new_completed_messages"]
    )
    assert [message.id for message in main.requests[0]] == [
        "employee-current",
        main.requests[0][1].id,
        "a-recent",
        "t-recent",
    ]
    saved = ContinuationCompaction.model_validate(
        result["continuation_compaction"], strict=True,
    )
    assert saved.format_version == 2
    assert saved.protected_message_id == "employee-current"
    assert [message.id for message in result["messages"][:-1]] == [
        message.id for message in messages
    ]


def test_a_releases_previous_protected_input_when_the_next_employee_turn_is_compacted():
    messages = [
        HumanMessage(id="employee-1", content="第一輪員工原話。"),
        AIMessage(
            id="a1",
            content="讀取第一輪資料。",
            tool_calls=[{"name": "jd_read", "args": {}, "id": "call-1"}],
        ),
        ToolMessage(id="t1", name="jd_read", tool_call_id="call-1", content="第一輪結果"),
        AIMessage(id="answer-1", content="第一輪回答。"),
        HumanMessage(id="employee-2", content="第二輪需要逐字保留的新原話。"),
        AIMessage(
            id="a2",
            content="讀取第二輪資料。",
            tool_calls=[{"name": "jd_read", "args": {}, "id": "call-2"}],
        ),
        ToolMessage(id="t2", name="jd_read", tool_call_id="call-2", content="第二輪結果 A"),
        AIMessage(
            id="a3",
            content="繼續讀取。",
            tool_calls=[{"name": "read_case", "args": {}, "id": "call-3"}],
        ),
        ToolMessage(id="t3", name="read_case", tool_call_id="call-3", content="第二輪結果 B"),
        AIMessage(
            id="a-recent",
            content="近期工具呼叫。",
            tool_calls=[{"name": "jd_insert_item", "args": {}, "id": "call-recent"}],
        ),
        ToolMessage(
            id="t-recent",
            name="jd_insert_item",
            tool_call_id="call-recent",
            content="近期結果",
        ),
    ]
    previous_boundary = 3
    previous = ContinuationCompaction(
        format_version=2,
        summary_text="第一輪已讀取資料。",
        covered_through_message_id="t1",
        covered_prefix_digest=canonical_prefix_digest(messages[:previous_boundary]),
        protected_message_id="employee-1",
    )
    summary = FixedModel(replies=[completed("summary", "兩輪進度已整合。")])
    main = FixedModel(replies=[completed("answer", "繼續第二輪。")])
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=A_COMPACTION_PROFILE.model_copy(update={
                "trigger_input_tokens": 1,
                "keep_messages": 2,
            }),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
    )

    result = agent.invoke({
        "messages": messages,
        "continuation_compaction": previous.model_dump(mode="json"),
    })

    payload = json.loads(summary.requests[0][1].text.split("\n", 1)[1])
    assert payload["existing_summary"] == "第一輪已讀取資料。"
    assert payload["protected_orientation"] == [{
        "role": "user",
        "content": "第二輪需要逐字保留的新原話。",
    }]
    assert {"role": "user", "content": "第一輪員工原話。"} in payload[
        "new_completed_messages"
    ]
    assert {"role": "user", "content": "第二輪需要逐字保留的新原話。"} not in payload[
        "new_completed_messages"
    ]
    assert [message.id for message in main.requests[0]] == [
        "employee-2",
        main.requests[0][1].id,
        "a-recent",
        "t-recent",
    ]
    saved = ContinuationCompaction.model_validate(
        result["continuation_compaction"], strict=True,
    )
    assert saved.protected_message_id == "employee-2"


def test_a_dynamic_protection_fails_closed_when_it_does_not_name_latest_human_in_prefix():
    messages = [
        HumanMessage(id="employee-1", content="第一輪原話。"),
        AIMessage(id="answer-1", content="第一輪回答。"),
        HumanMessage(id="employee-2", content="第二輪原話。"),
        AIMessage(id="answer-2", content="第二輪回答。"),
    ]
    state = {
        "format_version": 2,
        "summary_text": "無效的保護邊界。",
        "covered_through_message_id": "answer-2",
        "covered_prefix_digest": canonical_prefix_digest(messages),
        "protected_message_id": "employee-1",
    }

    with pytest.raises(
        ContinuationCompactionError,
        match="invalid_compaction_boundary",
    ):
        build_request_view(messages, state, A_COMPACTION_PROFILE)


def test_saved_summary_is_validated_against_immutable_canonical_prefix():
    messages = conversation()
    boundary = 2
    state = ContinuationCompaction(
        format_version=1,
        summary_text="案例 A 原先記錄為每週巡檢。",
        covered_through_message_id="a1",
        covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
    )
    original = deepcopy(messages)
    view = build_request_view(messages, state, A_COMPACTION_PROFILE)
    assert messages == original
    assert isinstance(view[0], AIMessage)
    assert view[1].id == "h2"

    mutated = deepcopy(messages)
    mutated[0].content = "內容遭到改寫"
    with pytest.raises(ContinuationCompactionError, match="invalid_compaction_boundary"):
        build_request_view(mutated, state, A_COMPACTION_PROFILE)


def test_middleware_summarizes_incrementally_and_publishes_with_main_response():
    messages = conversation()
    first_boundary = 2
    previous = ContinuationCompaction(
        format_version=1,
        summary_text="既有摘要：案例 A 原先是每週巡檢。",
        covered_through_message_id="a1",
        covered_prefix_digest=canonical_prefix_digest(messages[:first_boundary]),
    )
    summary = FixedModel(replies=[completed("summary", "新摘要：A 已讀取，仍待確認頻率。")])
    main = FixedModel(replies=[completed("answer", "請問正確頻率是每月嗎？")])
    profile = CompactionProfile(trigger_input_tokens=1, keep_messages=1)
    middleware = ContinuationCompactionMiddleware(
        summary_model=summary,
        profile=profile,
        token_counter=lambda request, view: 100,
    )
    agent = create_agent(
        main,
        tools=[],
        middleware=[middleware],
        state_schema=ContinuationCompactionState,
        checkpointer=InMemorySaver(),
    )
    result = agent.invoke(
        {"messages": messages, "continuation_compaction": previous.model_dump(mode="json")},
        {"configurable": {"thread_id": "incremental-compaction"}},
        durability="sync",
    )

    assert len(summary.requests) == 1
    prompt = summary.requests[0][-1].content
    assert previous.summary_text in prompt
    assert "請讀取相關案例。" in prompt and "兩份都已讀完。" in prompt
    assert "案例 A：每週巡檢。" not in prompt and "A 已記錄。" not in prompt
    assert len(main.requests) == 1
    assert isinstance(main.requests[0][0], AIMessage)
    assert "新摘要" in main.requests[0][0].content
    saved = ContinuationCompaction.model_validate(result["continuation_compaction"], strict=True)
    assert saved.covered_through_message_id == "a3"
    assert [message.id for message in result["messages"][:-1]] == [message.id for message in messages]


def test_compaction_updates_only_its_own_checkpoint_field_and_preserves_working_state():
    working = InterviewWorkingState(
        focus_item_id="wi_" + "1" * 32,
        items=[WorkingItem(
            item_id="wi_" + "1" * 32,
            subject="故障升級",
            known_and_open="已知本人先初判；升級條件仍待確認。",
            information_needed="取得一次實際升級案例。",
            status="open",
            priority="high_jd_impact",
        )],
    )
    summary = FixedModel(replies=[completed("summary", "舊互動已整理；最新更正仍待確認。")])
    main = FixedModel(replies=[completed("answer", "請問正確的升級條件是什麼？")])
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "working-state-compaction"}}
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ConsultantState,
        checkpointer=saver,
    )
    result = agent.invoke({
        "messages": conversation(),
        "interview_working_state": working.model_dump(mode="json"),
    }, config, durability="sync")

    assert result["interview_working_state"] == working.model_dump(mode="json")
    assert agent.get_state(config).values["interview_working_state"] == working.model_dump(mode="json")
    assert ContinuationCompaction.model_validate(
        result["continuation_compaction"], strict=True,
    ).summary_text == "舊互動已整理；最新更正仍待確認。"


def test_effective_request_size_prevents_recompacting_a_small_saved_view():
    messages = conversation()
    boundary = 7
    previous = ContinuationCompaction(
        format_version=1,
        summary_text="已完成的舊工作摘要。",
        covered_through_message_id="a3",
        covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
    )
    summary = FixedModel(replies=[])
    main = FixedModel(replies=[completed("answer", "收到更正。")])
    seen = []

    def count(request, view):
        seen.append([message.id for message in view])
        return len(view)

    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=4, keep_messages=1),
            token_counter=count,
        )],
        state_schema=ContinuationCompactionState,
    )
    agent.invoke({"messages": messages, "continuation_compaction": previous.model_dump(mode="json")})

    assert len(seen) == 1
    assert seen[0][0].startswith("continuation-summary:")
    assert seen[0][1:] == ["h3"]
    assert not summary.requests
    assert [message.id for message in main.requests[0]] == seen[0]


def test_main_failure_does_not_publish_new_summary():
    class FailingModel(FixedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.requests.append(deepcopy(messages))
            raise RuntimeError("synthetic main failure")

    messages = conversation()
    summary = FixedModel(replies=[completed("summary", "暫時摘要")])
    agent = create_agent(
        FailingModel(replies=[]),
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "failed-main"}}
    with pytest.raises(RuntimeError, match="synthetic main failure"):
        agent.invoke({"messages": messages}, config, durability="sync")
    state = agent.get_state(config).values
    assert state.get("continuation_compaction") is None


def test_saved_summary_survives_graph_rebuild_and_next_chat_turn():
    messages = conversation()
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "reopened-chat"}}
    summary = FixedModel(replies=[completed("summary", "已整理舊訪談；最新更正尚待確認。")])
    first_main = FixedModel(replies=[completed("answer-1", "我先確認這項更正。")])
    profile = CompactionProfile(trigger_input_tokens=1, keep_messages=1)
    first = create_agent(
        first_main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=profile,
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
        checkpointer=saver,
    )
    first.invoke({"messages": messages}, config, durability="sync")

    second_summary = FixedModel(replies=[])
    second_main = FixedModel(replies=[completed("answer-2", "繼續訪談。")])
    reopened = create_agent(
        second_main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=second_summary,
            profile=CompactionProfile(trigger_input_tokens=20, keep_messages=1),
            token_counter=lambda request, view: len(view),
        )],
        state_schema=ContinuationCompactionState,
        checkpointer=saver,
    )
    reopened.invoke(
        {"messages": [HumanMessage(id="h4", content="對，是每月一次。")]},
        config,
        durability="sync",
    )

    assert not second_summary.requests
    request = second_main.requests[0]
    assert request[0].id.startswith("continuation-summary:")
    assert [message.id for message in request[1:]] == ["h3", "answer-1", "h4"]
    canonical = reopened.get_state(config).values["messages"]
    assert [message.id for message in canonical[:-1]] == [
        *(message.id for message in messages),
        "answer-1",
        "h4",
    ]


@dataclass
class StopContext:
    stop_event: Event


@pytest.mark.parametrize("cancel_after_summary", [False, True])
def test_cancellation_stops_before_the_next_paid_model_call(cancel_after_summary):
    stop = Event()

    class CancellingSummary(FixedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            context_stop.set()
            return result

    context_stop = stop
    if not cancel_after_summary:
        stop.set()
    summary_type = CancellingSummary if cancel_after_summary else FixedModel
    summary = summary_type(replies=[completed("summary", "不應發布的摘要")])
    main = FixedModel(replies=[completed("answer", "不應送出")])
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
        context_schema=StopContext,
    )

    with pytest.raises(ContinuationCompactionError, match="compaction_cancelled"):
        agent.invoke({"messages": conversation()}, context=StopContext(stop))
    assert len(summary.requests) == int(cancel_after_summary)
    assert not main.requests


def test_invalid_saved_boundary_fails_closed_only_at_configured_hard_limit():
    bad = {
        "format_version": 1,
        "summary_text": "損壞摘要",
        "covered_through_message_id": "a1",
        "covered_prefix_digest": "sha256:" + "0" * 64,
    }
    main = FixedModel(replies=[completed("answer", "不應送出")])
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=FixedModel(replies=[]),
            profile=CompactionProfile(
                trigger_input_tokens=10,
                keep_messages=1,
                hard_input_tokens=50,
            ),
            token_counter=lambda request, view: 50,
        )],
        state_schema=ContinuationCompactionState,
    )
    with pytest.raises(ContinuationCompactionError, match="invalid_compaction_boundary"):
        agent.invoke({"messages": conversation(), "continuation_compaction": bad})
    assert not main.requests


def test_truncated_summary_is_not_published_or_sent_to_the_main_model():
    summary = FixedModel(replies=[AIMessage(
        id="summary",
        content="被截斷的摘要",
        response_metadata={"status": "incomplete", "finish_reason": "length"},
    )])
    main = FixedModel(replies=[completed("answer", "不應送出")])
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
    )
    with pytest.raises(ContinuationCompactionError, match="invalid_compaction_summary"):
        agent.invoke({"messages": conversation()})
    assert len(summary.requests) == 1
    assert not main.requests


def test_incomplete_main_response_does_not_publish_a_completed_summary():
    summary = FixedModel(replies=[completed("summary", "暫時摘要")])
    main = FixedModel(replies=[AIMessage(
        id="answer",
        content="被截斷的主回答",
        response_metadata={"status": "incomplete", "finish_reason": "length"},
    )])
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "incomplete-main"}}
    agent = create_agent(
        main,
        tools=[],
        middleware=[ContinuationCompactionMiddleware(
            summary_model=summary,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )],
        state_schema=ContinuationCompactionState,
        checkpointer=saver,
    )
    with pytest.raises(
        ContinuationCompactionError,
        match="incomplete_compacted_model_response",
    ):
        agent.invoke({"messages": conversation()}, config, durability="sync")
    assert agent.get_state(config).values.get("continuation_compaction") is None
