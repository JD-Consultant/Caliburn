"""失敗診斷只輸出定位與安全摘要，不受 handler 故障影響。"""

import asyncio
import logging

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.types import interrupt

from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    offline_client,
    reasoning,
    response_events,
    response_payload,
    run_test_agent,
    sse_response,
)


def test_model_failure_logs_once_without_response_text_or_opaque(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = response_payload(
        [reasoning(), call(arguments='{"secret":"employee-private"}')], status="failed"
    )

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(payload)))
            )
        ) as client:
            with pytest.raises(ModelResponseError):
                await run_test_agent(client=client)

    asyncio.run(run())
    records = [
        record
        for record in caplog.records
        if record.name.startswith("caliburn.modules.agent")
    ]
    assert len(records) == 1
    fields = records[0].__dict__
    assert fields["event"] == "agent.model.failed"
    assert fields["response_id"] == "resp_offline"
    assert fields["error_type"] == "ModelResponseError"
    assert fields["execution"]["run_id"]
    rendered = repr(fields)
    assert (
        "employee-private" not in rendered
        and "synthetic-opaque-content" not in rendered
    )


def test_logging_failure_preserves_original_failure() -> None:
    class BrokenHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("diagnostic output failed")

    logger = logging.getLogger(
        "caliburn.modules.agent.infrastructure.openai.call_model"
    )
    handler = BrokenHandler()
    logger.addHandler(handler)

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(
                    EventStream(response_events(response_payload(status="failed")))
                )
            )
        ) as client:
            with pytest.raises(ModelResponseError):
                await run_test_agent(client=client)

    try:
        asyncio.run(run())
    finally:
        logger.removeHandler(handler)


def test_tool_interrupt_is_not_logged_as_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def read_alpha(item: str) -> str:
        return str(interrupt({"approve": item}))

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Approve.")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(
                    EventStream(response_events(response_payload([call()])))
                )
            )
        ) as client:
            await run_test_agent(client=client, tools=(tool,))

    asyncio.run(run())
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("caliburn.modules.agent")
    ]
