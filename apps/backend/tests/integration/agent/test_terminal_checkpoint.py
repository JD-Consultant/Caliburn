"""成功 terminal 不被普通收尾否決；真 PG 冷重開仍保留唯一原件。"""

import asyncio
from uuid import uuid4

import httpx2
import pytest

from caliburn.modules.agent.agent import AgentExecutionError
from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    message,
    offline_client,
    reasoning,
    response_events,
    response_payload,
    sse_response,
)
from tests.unit.modules.agent.terminal_stream import TerminalStream


@pytest.mark.parametrize("fault", ["none", "close", "tail"])
def test_completed_original_survives_cleanup_and_cold_resume(
    checkpoint_conninfo: str, fault: str
) -> None:
    workspace, turn = uuid4(), uuid4()
    payload = response_payload([reasoning(), message()])
    request_count = 0

    async def run() -> None:
        nonlocal request_count
        wire = TerminalStream(
            response_events(payload),
            read_error=OSError("synthetic tail error") if fault == "tail" else None,
            close_error=RuntimeError("synthetic close error")
            if fault == "close"
            else None,
        )

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal request_count
            request_count += 1
            return sse_response(wire)

        for attempt in (1, 2):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=attempt == 1
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="terminal-checkpoint",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(),
                    checkpointer=saver,
                ) as agent,
            ):
                if attempt == 1:
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=turn, input="合成完整回應"
                        )
                    )
                else:
                    with pytest.raises(AgentExecutionError, match="completed"):
                        await consume(
                            agent.aresume(workspace_id=workspace, turn_id=turn)
                        )
                saved = await agent.aget_state(workspace_id=workspace)
                response = saved.values["model_response"]
                assert response.id == payload["id"]
                assert response.usage.total_tokens == 21
                assert response.model_extra["future_response_field"] == {
                    "retained": True
                }
                assert (
                    response.output[0].encrypted_content == "synthetic-opaque-content"
                )
                assert saved.values["model_request"]["input"][-2:] == response.output
                assert saved.values["turn_completed"]
                assert not saved.next
        assert wire.closed
        assert not wire.tail_read

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert request_count == 1
