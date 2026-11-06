"""真 PG 拒絕保存、非法 terminal 與業務錯誤的恢復界線。"""

import asyncio
from typing import cast
from uuid import UUID

import httpx2
import pytest
from openai.types.responses.response_input_param import ResponseInputParam
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.errors import LockNotAvailable

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.stream_support import consume
from tests.integration.agent.tool_fixture import PROBE, ToolProbe
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

WORKSPACE = UUID(int=1)


def test_invalid_completed_response_remains_retryable_after_cold_read(
    checkpoint_conninfo: str,
) -> None:
    sent: list[dict[str, object]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(response_payload([] if len(sent) == 1 else None))
            )
        )

    async def run() -> None:
        for attempt in (1, 2):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=attempt == 1
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="invalid-terminal",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(),
                    checkpointer=saver,
                ) as agent,
            ):
                if attempt == 1:
                    with pytest.raises(ValueError, match="complete assistant message"):
                        await consume(
                            agent.astream(
                                turn_id=UUID(int=101),
                                workspace_id=WORKSPACE,
                                input=cast(ResponseInputParam, INITIAL),
                            )
                        )
                else:
                    snapshot = await agent.aget_state(workspace_id=WORKSPACE)
                    assert (
                        snapshot.next and snapshot.values.get("model_response") is None
                    )
                    await consume(
                        agent.aresume(turn_id=UUID(int=101), workspace_id=WORKSPACE)
                    )
                    saved = await agent.aget_state(workspace_id=WORKSPACE)
                    assert (
                        saved.values["model_response"].output_text == "Synthetic reply"
                    )
        assert len(sent) == 2 and sent[0] == sent[1]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("stage", ["model", "tool"])
def test_checkpoint_failure_stops_next_node_and_exposes_unsaved_effect_window(
    checkpoint_conninfo: str,
    stage: str,
) -> None:
    async def run() -> None:
        sent: list[dict[str, object]] = []
        probe = ToolProbe()
        options = conninfo_to_dict(checkpoint_conninfo)["options"]
        assert isinstance(options, str)
        saver_conninfo = make_conninfo(
            checkpoint_conninfo, options=options + " -clock_timeout=100ms"
        )
        async with (
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as business,
            await AsyncConnection.connect(checkpoint_conninfo) as blocker,
            open_postgres_checkpointer(saver_conninfo, initialize=True) as saver,
        ):
            await business.execute(
                "CREATE TABLE synthetic_effects (item text NOT NULL)"
            )

            async def block_saves() -> None:
                await blocker.execute(
                    "LOCK TABLE checkpoints, checkpoint_blobs, checkpoint_writes "
                    "IN ACCESS EXCLUSIVE MODE"
                )

            async def commit_effect(item: str) -> None:
                await business.execute(
                    "INSERT INTO synthetic_effects VALUES (%s)", (item,)
                )
                if stage == "tool" and len(probe.effects) == 1:
                    await block_saves()

            probe.after_effect = commit_effect

            async def respond(request: httpx2.Request) -> httpx2.Response:
                body = request_body(request)
                sent.append(body)
                if stage == "model" and len(sent) == 1:
                    await block_saves()
                has_outputs = any(
                    item.get("type") == "function_call_output" for item in body["input"]
                )
                payload = response_payload(
                    None
                    if has_outputs
                    else [
                        call(),
                        call(call_id="call_beta", arguments='{"item":"beta"}'),
                    ]
                )
                return sse_response(EventStream(response_events(payload)))

            async with (
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="failed-save",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(BundleConfig("tests.integration.agent.tool_fixture"),),
                    external_services=(PROBE.bind(probe),),
                    checkpointer=saver,
                ) as agent,
            ):
                with pytest.raises(LockNotAvailable):
                    await consume(
                        agent.astream(
                            turn_id=UUID(int=101),
                            workspace_id=WORKSPACE,
                            input=cast(ResponseInputParam, INITIAL),
                        )
                    )
                assert len(sent) == 1
                assert probe.effects == ([] if stage == "model" else ["alpha"])
                await blocker.rollback()
                snapshot = await agent.aget_state(workspace_id=WORKSPACE)
                assert snapshot.next
                assert not any(
                    isinstance(item, dict)
                    and item.get("type") == "function_call_output"
                    for item in snapshot.values["model_request"]["input"]
                )
                await consume(
                    agent.aresume(turn_id=UUID(int=101), workspace_id=WORKSPACE)
                )
            cursor = await business.execute(
                "SELECT item FROM synthetic_effects ORDER BY ctid"
            )
            committed = [row[0] for row in await cursor.fetchall()]
            assert committed == (
                ["alpha", "beta"] if stage == "model" else ["alpha", "alpha", "beta"]
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_expected_tool_error_is_saved_then_remaining_tools_continue(
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        sent = []
        probe = ToolProbe(business_error=True)

        def respond(request: httpx2.Request) -> httpx2.Response:
            sent.append(request_body(request))
            payload = (
                response_payload(
                    [
                        call(),
                        call(call_id="call_beta", arguments='{"item":"beta"}'),
                    ]
                )
                if len(sent) == 1
                else response_payload()
            )
            return sse_response(EventStream(response_events(payload)))

        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="business-error",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig("tests.integration.agent.tool_fixture"),),
                external_services=(PROBE.bind(probe),),
                checkpointer=saver,
            ) as agent,
        ):
            await consume(
                agent.astream(
                    turn_id=UUID(int=101),
                    workspace_id=WORKSPACE,
                    input=cast(ResponseInputParam, INITIAL),
                )
            )
        assert probe.effects == ["alpha", "beta"]
        assert [
            item["output"]
            for item in sent[1]["input"]
            if item.get("type") == "function_call_output"
        ] == ["Synthetic business rejection", "read beta"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
