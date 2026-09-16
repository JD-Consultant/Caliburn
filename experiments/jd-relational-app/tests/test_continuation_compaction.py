"""Offline checks for non-destructive, App-side context compaction."""

from copy import deepcopy
from dataclasses import dataclass
from threading import Event

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.continuation_compaction import (
    A_COMPACTION_PROFILE,
    B2_COMPACTION_PROFILE,
    CompactionProfile,
    ContinuationCompaction,
    ContinuationCompactionError,
    ContinuationCompactionMiddleware,
    ContinuationCompactionState,
    build_request_view,
    canonical_prefix_digest,
    select_safe_boundary,
)


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
    assert "h2" in prompt and "a3" in prompt
    assert "h1" not in prompt and "a1" not in prompt
    assert len(main.requests) == 1
    assert isinstance(main.requests[0][0], AIMessage)
    assert "新摘要" in main.requests[0][0].content
    saved = ContinuationCompaction.model_validate(result["continuation_compaction"], strict=True)
    assert saved.covered_through_message_id == "a3"
    assert [message.id for message in result["messages"][:-1]] == [message.id for message in messages]


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
