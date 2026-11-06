"""同 Workspace 變更組裝版本時重建窗口，保留已完成訪談來源資格。"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx2
from langgraph.types import StateSnapshot

from caliburn.bundles.context.history import (
    completed_window_turns,
    previous_completed_window,
)
from caliburn.bundles.context.services import PREVIOUS_WINDOW
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_reconfigured_workspace_rebuilds_instead_of_reusing_an_older_matching_window(
    checkpoint_conninfo: str,
) -> None:
    requests: list[dict[str, Any]] = []
    workspace_id = uuid4()
    turns = (uuid4(), uuid4(), uuid4())
    context = BundleConfig("caliburn.bundles.context", plugins=("window",))
    provider = BundleConfig("tests.unit.bundles.context.test_window_providers")
    configurations = (
        ("v1", (provider, context), "first"),
        ("v2", (context,), "second"),
        ("v1", (provider, context), "third"),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses"
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
            return await previous_completed_window(
                agent, workspace_id=workspace, turn_id=turn
            )

        for index, (version, bundles, text) in enumerate(configurations):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=index == 0
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="reconfigured-context",
                    resume_version=version,
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=bundles,
                    checkpointer=saver,
                    external_services=(PREVIOUS_WINDOW.bind(previous),),
                ) as agent,
            ):
                await consume(
                    agent.astream(
                        workspace_id=workspace_id,
                        turn_id=turns[index],
                        input=text,
                    )
                )
                assert await completed_window_turns(
                    agent, workspace_id=workspace_id
                ) == frozenset(turns[: index + 1])

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert requests[1]["input"] == [{"role": "user", "content": "second"}]
    assert requests[2]["input"] == [
        {"role": "user", "content": "alternative context"},
        {"role": "user", "content": "third"},
        {"role": "user", "content": "alternative input reference"},
    ]
