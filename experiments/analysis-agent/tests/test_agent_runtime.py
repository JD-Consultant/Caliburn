"""Real compiled-agent boundary checks, synthetic provider responses only."""

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from openai import BadRequestError

from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from test_native_continuity import assistant_text, response_body


def tool_response():
    return response_body([
        {"type": "reasoning", "id": "rs_tool", "summary": [], "encrypted_content": "opaque-before"},
        assistant_text("先讀案例。", "msg_comment", "commentary"),
        {"type": "function_call", "id": "fc_a", "call_id": "call_a", "name": "read_case", "arguments": '{"name":"A"}', "status": "completed"},
    ], "resp_tool")


def compacted_response():
    return response_body([
        {"type": "compaction", "id": "cmp_a", "encrypted_content": "opaque-compact"},
        {"type": "reasoning", "id": "rs_tail", "summary": [], "encrypted_content": "opaque-after"},
        assistant_text("A 使用單次付款，交付後還有哪些工作？", "msg_tail"),
    ], "resp_compacted")


def test_agent_keeps_canonical_tool_history_but_compacts_only_next_request():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "interview-a"}}
    payloads = []
    calls = []
    bodies = [tool_response(), compacted_response(), response_body([assistant_text("接著談 B。", "msg_b")])]

    @tool
    def read_case(name: str) -> str:
        """Read a synthetic previously recorded case for this offline test."""
        calls.append(name)
        return "A 使用單次付款"

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=bodies[len(payloads) - 1])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client)
        agent = build_agent(model=model, checkpointer=saver, instructions="固定訪談規則", tools=[read_case])
        agent.invoke({"messages": [HumanMessage("A 是一次付費的網站。", id="employee-a")]}, config, durability="sync")
        # Re-create the compiled graph; InMemory here is not a process/DB proof.
        agent = build_agent(model=model, checkpointer=saver, instructions="固定訪談規則", tools=[read_case])
        agent.invoke({"messages": [HumanMessage("B 是月租。", id="employee-b")]}, config, durability="sync")
        canonical = agent.get_state(config).values["messages"]

    assert calls == ["A"]
    tool_wire = payloads[1]["input"]
    assert [(x["type"], x["call_id"]) for x in tool_wire if "call_id" in x] == [
        ("function_call", "call_a"), ("function_call_output", "call_a")]
    # In store=False the adapter intentionally omits server message lookup IDs
    # from outgoing assistant text. It must preserve the content and phase.
    commentary = next(x for x in tool_wire if x.get("role") == "assistant")
    assert commentary["phase"] == "commentary"
    assert commentary["content"][0]["text"] == "先讀案例。"
    assert next(x for x in tool_wire if x.get("id") == "rs_tool")["encrypted_content"] == "opaque-before"
    next_wire = payloads[2]["input"]
    assert next_wire[0]["content"] == "固定訪談規則"
    assert [x["type"] for x in next_wire[1:]] == ["compaction", "reasoning", "message", "message"]
    assert next_wire[1]["encrypted_content"] == "opaque-compact"
    assert next_wire[2]["encrypted_content"] == "opaque-after"
    assert next_wire[3]["phase"] == "final_answer"
    assert next_wire[4]["content"] == "B 是月租。"
    assert [m.content for m in canonical if isinstance(m, HumanMessage)] == ["A 是一次付費的網站。", "B 是月租。"]
    assert [m.content for m in canonical if isinstance(m, ToolMessage)] == ["A 使用單次付款"]
    original_ai = canonical[1]
    assert original_ai.content[0] == {"type": "reasoning", "id": "rs_tool", "summary": [], "encrypted_content": "opaque-before"}
    assert original_ai.content[1]["text"] == "先讀案例。"
    assert original_ai.content[1]["phase"] == "commentary"
    assert original_ai.content[1]["id"] == "msg_comment"
    assert original_ai.content[2]["call_id"] == "call_a"
    assert original_ai.content[2]["arguments"] == '{"name":"A"}'
    assert original_ai.tool_calls[0]["id"] == "call_a"
    assert not any(m.type == "system" for m in canonical)


def test_resume_after_provider_failure_reuses_saved_input_and_tool_result():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "failed-interview"}}
    payloads = []
    calls = []

    @tool
    def read_case(name: str) -> str:
        """Read an offline case; not an external side-effectful operation."""
        calls.append(name)
        return "A 使用單次付款"

    def respond(request):
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return httpx.Response(200, json=tool_response())
        if len(payloads) == 2:
            return httpx.Response(400, json={"error": {"message": "synthetic bad request", "type": "invalid_request_error"}})
        return httpx.Response(200, json=response_body([assistant_text("請補充驗收工作。", "msg_recovered")]))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client)
        agent = build_agent(model=model, checkpointer=saver, instructions="訪談規則", tools=[read_case])
        with pytest.raises(BadRequestError):
            agent.invoke({"messages": [HumanMessage("查看 A。", id="employee-a")]}, config, durability="sync")
        snapshot = agent.get_state(config)
        assert snapshot.next
        assert isinstance(snapshot.values["messages"][-1], ToolMessage)
        # Official retry input is None, not another copy of the employee input.
        agent = build_agent(model=model, checkpointer=saver, instructions="訪談規則", tools=[read_case])
        result = agent.invoke(None, config, durability="sync")
        assert agent.get_state(config).next == ()

    assert calls == ["A"]
    assert len(payloads) == 3
    assert [m.content for m in result["messages"] if isinstance(m, HumanMessage)] == ["查看 A。"]
    assert result["messages"][-1].text == "請補充驗收工作。"
    assert next(x for x in payloads[2]["input"] if x["type"] == "function_call_output")["output"] == "A 使用單次付款"


def test_new_document_cannot_receive_another_documents_conversation():
    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=response_body([assistant_text("請繼續。", "msg_" + str(len(payloads)))]))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        agent = build_agent(
            model=build_model(model="gpt-5.6-luna", api_key="offline", http_client=client),
            checkpointer=InMemorySaver(), instructions="訪談規則", tools=[],
        )
        agent.invoke({"messages": [HumanMessage("A 的獨有內容")]}, {"configurable": {"thread_id": "a"}}, durability="sync")
        agent.invoke({"messages": [HumanMessage("B 的獨有內容")]}, {"configurable": {"thread_id": "b"}}, durability="sync")

    assert [x["content"] for x in payloads[1]["input"]] == ["訪談規則", "B 的獨有內容"]
