"""完整成功原件與取消／失敗的界線，經真 SDK 及公開 Agent 驗證。"""

import asyncio

import httpx2
import pytest
from langgraph.errors import NodeCancelledError

from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from tests.unit.modules.agent.offline_openai import (
    TEST_WORKSPACE_ID,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    run_turn,
    sse_response,
)
from tests.unit.modules.agent.terminal_stream import TerminalStream


@pytest.mark.parametrize("status", ["missing", "failed", "incomplete", "invalid"])
@pytest.mark.parametrize("close_fails", [False, True])
def test_non_successful_terminal_never_becomes_a_saved_response(
    status: str, close_fails: bool
) -> None:
    payload = response_payload(
        [] if status == "invalid" else None,
        status=status if status in ("failed", "incomplete") else "completed",
    )
    events = response_events(payload)
    if status == "missing":
        events = events[:-1]

    async def run() -> None:
        wire = TerminalStream(
            events,
            close_error=RuntimeError("synthetic close error") if close_fails else None,
        )
        async with (
            offline_client(
                httpx2.MockTransport(lambda _: sse_response(wire))
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            with pytest.raises((RuntimeError, ValueError)) as caught:
                await run_turn(agent, input="合成失敗回應")
            if not close_fails and status in ("failed", "incomplete"):
                assert isinstance(caught.value, ModelResponseError)
                assert caught.value.response.status == status
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None
            assert saved.next == ("call_model",)
            assert wire.closed

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("masked", [False, True])
def test_read_cancellation_is_not_replaced_by_an_ordinary_close_error(
    masked: bool,
) -> None:
    async def run() -> None:
        wire = TerminalStream(
            response_events(response_payload())[:-1],
            read_error=asyncio.CancelledError("synthetic read cancellation"),
            close_error=RuntimeError("synthetic close error") if masked else None,
        )
        async with (
            offline_client(
                httpx2.MockTransport(lambda _: sse_response(wire))
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            with pytest.raises(NodeCancelledError):
                await run_turn(agent, input="合成讀取取消")
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None
            assert not saved.values["turn_completed"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_sdk_connection_wrapper_does_not_hide_transport_cancellation() -> None:
    async def respond(request: httpx2.Request) -> httpx2.Response:
        try:
            raise asyncio.CancelledError("synthetic transport cancellation")
        finally:
            raise httpx2.ReadError("synthetic transport cleanup", request=request)

    async def run() -> None:
        async with (
            offline_client(httpx2.MockTransport(respond)) as client,
            open_test_agent(client=client) as agent,
        ):
            with pytest.raises(NodeCancelledError):
                await run_turn(agent, input="合成連線取消")
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None
            assert not saved.values["turn_completed"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("close_fails", [False, True])
def test_task_cancellation_during_close_remains_cancelled(close_fails: bool) -> None:
    async def run() -> None:
        wire = TerminalStream(
            response_events(response_payload()),
            block_close=True,
            close_error=RuntimeError("synthetic close error") if close_fails else None,
        )
        async with (
            offline_client(
                httpx2.MockTransport(lambda _: sse_response(wire))
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            invocation = asyncio.create_task(run_turn(agent, input="合成關閉取消"))
            await asyncio.wait_for(wire.close_started.wait(), timeout=5)
            invocation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await invocation
            assert invocation.cancelled()
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None
            assert not saved.values["turn_completed"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


class FatalStreamError(BaseException):
    """模擬必須傳出的程序級中斷，不終止測試 runner。"""


def test_base_exception_after_terminal_is_not_accepted_as_success() -> None:
    async def run() -> None:
        wire = TerminalStream(
            response_events(response_payload()), close_error=FatalStreamError()
        )
        async with (
            offline_client(
                httpx2.MockTransport(lambda _: sse_response(wire))
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            with pytest.raises(FatalStreamError):
                await run_turn(agent, input="合成程序中斷")
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
