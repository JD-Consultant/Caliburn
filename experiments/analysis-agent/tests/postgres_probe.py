"""Subprocess worker for the opt-in, dedicated-DB persistence test.

All provider responses are synthetic. Only PostgreSQL is real. This is test
support, not a product command or a general database cleanup interface.
"""

import json
import os
import sys

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.postgres import PostgresSaver
from openai import BadRequestError

from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from test_agent_runtime import compacted_response, tool_response
from test_native_continuity import assistant_text, response_body


def probe(mode: str, thread_id: str) -> None:
    dsn = os.environ["Q019_TEST_DATABASE_URL"]
    config = {"configurable": {"thread_id": thread_id}}
    calls = []
    payloads = []

    @tool
    def read_case(name: str) -> str:
        """Return a synthetic case without any external side effects."""
        calls.append(name)
        assert mode == "write", "Recovery must reuse the committed tool result"
        return "A 使用單次付款"

    def respond(request):
        payloads.append(json.loads(request.content))
        if mode == "write":
            # A different DB connection must see the employee message BEFORE
            # the first model response, not only when the run eventually exits.
            with PostgresSaver.from_conn_string(dsn) as observer:
                saved = observer.get(config)
                assert saved is not None
                messages = saved["channel_values"]["messages"]
                assert [m.content for m in messages if isinstance(m, HumanMessage)] == ["A 是一次付費的網站。"]
            if len(payloads) == 1:
                return httpx.Response(200, json=tool_response())
            return httpx.Response(400, json={"error": {"message": "synthetic provider failure", "type": "invalid_request_error"}})
        if len(payloads) == 1:
            return httpx.Response(200, json=compacted_response())
        return httpx.Response(200, json=response_body([assistant_text("接著談 B。", "msg_b")]))

    with PostgresSaver.from_conn_string(dsn) as saver, httpx.Client(transport=httpx.MockTransport(respond)) as client:
        agent = build_agent(
            model=build_model(model="gpt-5.6-luna", api_key="offline", http_client=client),
            checkpointer=saver, instructions="固定訪談規則", tools=[read_case],
        )
        if mode == "write":
            try:
                agent.invoke({"messages": [HumanMessage("A 是一次付費的網站。", id="employee-a")]}, config, durability="sync")
            except BadRequestError:
                pass
            else:
                raise AssertionError("Fixture should stop at a failed model step")
            assert calls == ["A"]
            assert agent.get_state(config).next
        else:
            assert mode == "resume"
            snapshot = agent.get_state(config)
            assert snapshot.next
            assert isinstance(snapshot.values["messages"][-1], ToolMessage)
            assert snapshot.values["messages"][-1].content == "A 使用單次付款"
            # Resume across actual process exit; do not append the input again.
            agent.invoke(None, config, durability="sync")
            agent.invoke({"messages": [HumanMessage("B 是月租。", id="employee-b")]}, config, durability="sync")
            canonical = agent.get_state(config).values["messages"]
            assert agent.get_state(config).next == ()
            assert calls == []
            resumed_wire = payloads[0]["input"]
            assert next(x for x in resumed_wire if x.get("id") == "rs_tool")["encrypted_content"] == "opaque-before"
            assert next(x for x in resumed_wire if x.get("role") == "assistant")["phase"] == "commentary"
            assert [(x["type"], x["call_id"]) for x in resumed_wire if "call_id" in x] == [
                ("function_call", "call_a"), ("function_call_output", "call_a")]
            next_wire = payloads[1]["input"]
            assert next_wire[0]["content"] == "固定訪談規則"
            assert [x["type"] for x in next_wire[1:]] == ["compaction", "reasoning", "message", "message"]
            assert next_wire[1]["encrypted_content"] == "opaque-compact"
            assert next_wire[2]["encrypted_content"] == "opaque-after"
            assert next_wire[-1]["content"] == "B 是月租。"
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
            assert agent.get_state({"configurable": {"thread_id": thread_id + "-empty"}}).values == {}
    print(json.dumps({"mode": mode, "ok": True}))


if __name__ == "__main__":
    probe(sys.argv[1], sys.argv[2])
