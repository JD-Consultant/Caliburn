"""Two-process probe: a saved pause cannot generate or deliver until explicit resume."""

import asyncio
import json
import os
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from response_capacity import CapacityProbe, request_fixture

from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.tool_steps import (
    PausedResponseLoop,
    ResponseLoopControls,
    run_response_loop,
)


async def run(mode: str, thread_id: str) -> None:
    require_isolated_test_database(os.environ["CALIBURN_TEST_DATABASE_URL"], environment=os.environ)
    provider = CapacityProbe([100])
    pause_requested = True
    acknowledgements = 0

    async def read_request() -> bool:
        return pause_requested

    async def mark_paused() -> None:
        nonlocal acknowledgements
        acknowledgements += 1

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["CALIBURN_TEST_DATABASE_URL"], serde=create_graph_serializer()
    ) as saver:
        await saver.setup()
        options = dict(
            thread_id=thread_id,
            runtime=provider.runtime(),
            max_tool_calls=2,
            max_model_steps=2,
            controls=ResponseLoopControls(read_request, mark_paused),
        )
        paused = await run_response_loop(
            saver, request=request_fixture() if mode == "write" else None, **options
        )
        assert isinstance(paused, PausedResponseLoop)
        assert acknowledgements == 1
        assert paused.state["completed_steps"] == 1
        assert paused.state["next_action"] == "deliver_answer"
        if mode == "resume":
            assert provider.model_requests == provider.count_requests == []
            pause_requested = False
            resumed = await run_response_loop(
                saver, request=None, resume_interrupt_id=paused.interrupt_id, **options
            )
            assert not isinstance(resumed, PausedResponseLoop)
            assert resumed["input_items"] == paused.state["input_items"]
            assert resumed["completed_steps"] == 1
            assert resumed["next_action"] == "deliver_answer"
            assert await run_response_loop(saver, request=None, **options) == resumed
            assert provider.model_requests == provider.count_requests == []
        elif mode != "write":
            raise ValueError("Unknown probe mode")
    print(
        json.dumps(
            {"mode": mode, "model_calls": len(provider.model_requests), "observation_calls": 0}
        )
    )


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1], sys.argv[2]), loop_factory=asyncio.SelectorEventLoop)
