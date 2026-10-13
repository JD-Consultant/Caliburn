"""Routing messages 只留目前 Step；原工具歷史仍可從 PG 原件查讀。"""

from dataclasses import replace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import consistent_read_session
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.context_compaction import bind_window_compaction
from caliburn.agent_execution.tool_observations import read_tool_observations
from tests.fixtures.native_response_runtime import run_response_loop
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at
from tests.unit.test_context_compaction import options as compaction_options

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("compact", [False, True])
def test_routing_reset_keeps_current_step_and_retained_tool_originals(
    client, database_settings, compact
):
    async def scenario():
        thread = f"routing-reset:{uuid4()}"
        config = {"configurable": {"thread_id": thread}}
        probe = LoopProbe(
            [response_at(1, tools=1), response_at(2, tools=1), response_at(3, final=True)]
        )
        output = "synthetic-observation:" + "x" * 100_000
        counts = 0
        events = []

        async def execute(prepared):
            return output

        async def count(request, request_id):
            nonlocal counts
            counts += 1
            return {
                "input_tokens": 160_000 if compact and counts == 3 else 100,
                "attempt_id": uuid4(),
            }

        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            bound_compact = bind_window_compaction(
                saver,
                response_thread_id=thread,
                runtime=compaction_options(events)["runtime"],
                recovery=None,
            )
            result = await run_response_loop(
                saver,
                thread_id=thread,
                request=initial_request(),
                runtime=replace(
                    probe.runtime(),
                    execute_tool=execute,
                    count_input=count,
                    compact_window=bound_compact,
                ),
                max_tool_calls=2,
                max_model_steps=3,
            )
            assert result["completed_steps"] == 3
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert result["messages"][0].id == "response_3"
            saved = await saver.aget_tuple(config)
            assert len(saved.checkpoint["channel_values"]["messages"]) == 1
            assert len(probe.requests) == 3
            assert sum(
                item.get("type") == "function_call_output" for item in probe.requests[-1]["input"]
            ) == (0 if compact else 2)
        async with consistent_read_session(client.app.state.database.sessions) as session:
            tools = await read_tool_observations(session, thread_id=thread)
        assert [tool.call_id for tool in tools] == ["call_1_0", "call_2_0"]
        assert all(tool.output == output and tool.result_state == "recorded" for tool in tools)
        assert bool(events) is compact

    client.portal.call(scenario)
