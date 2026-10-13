"""Native pending writes and acknowledgement loss keep complete originals exactly once."""

import asyncio

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.tool_steps import read_completed_response_history
from tests.fixtures.native_response_runtime import read_response_state, run_response_loop
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at

pytestmark = pytest.mark.postgres


class WindowBoundaryFault(AsyncPostgresSaver):
    mode = "finish_pending"

    async def aput(self, config, checkpoint, metadata, new_versions):
        state = checkpoint["channel_values"]
        if (
            not config["configurable"].get("checkpoint_ns")
            and state.get("completed_steps") == 1
            and (bool(state.get("response_snapshot")) == (self.mode == "finish_pending"))
        ):
            if self.mode == "next_after":
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic window boundary confirmation lost")
        return await super().aput(config, checkpoint, metadata, new_versions)


@pytest.mark.parametrize("mode", ["finish_pending", "next_before", "next_after"])
def test_reopen_uses_original_step_without_duplicate_append_or_outbound(
    empty_database_settings, mode
):
    async def scenario():
        settings = empty_database_settings
        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        first_final = mode == "finish_pending"
        probe = LoopProbe(
            [response_at(1, final=True)]
            if first_final
            else [response_at(1, tools=1), response_at(2, final=True)]
        )
        options = dict(
            thread_id="window-boundary",
            runtime=probe.runtime(),
            max_tool_calls=4,
            max_model_steps=2,
        )
        config = {"configurable": {"thread_id": options["thread_id"]}}
        serde = create_graph_serializer()
        async with WindowBoundaryFault.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            saver.mode = mode
            with pytest.raises(ConnectionError, match="window boundary"):
                await run_response_loop(saver, request=initial_request(), **options)
            assert len(probe.requests) == 1
            original = await saver.aget_tuple(config)
            assert original is not None
            if mode != "next_after":
                assert original.pending_writes  # Native node result survived the failed full save.
            saved = await read_response_state(saver, config)
            prepared_id = saved.values["request_id"]
            with pytest.raises(ValueError, match="completed"):
                await read_completed_response_history(saver, thread_id=options["thread_id"])

        # Fresh physical connection; latest only, never historical replay.
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            result = await run_response_loop(saver, request=None, **options)
            assert "input_items" not in result
            window = await read_completed_response_history(saver, thread_id=options["thread_id"])
            assert window.items[:2] == initial_request().create_payload()["input"]
            assert len(window.items) == (4 if first_final else 8)
            assert len(probe.requests) == (1 if first_final else 2)
            if not first_final:
                assert probe.request_ids[1] == prepared_id
            assert probe.effects == ([] if first_final else ["call_1_0"])
            assert [
                item["call_id"]
                for item in window.items
                if item.get("type") == "function_call_output"
            ] == probe.effects
            assert await run_response_loop(saver, request=None, **options) == result
            assert len(probe.requests) == (1 if first_final else 2)
            assert all(
                [
                    "input_items" not in saved.checkpoint["channel_values"]
                    async for saved in saver.alist(config)
                ]
            )

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
