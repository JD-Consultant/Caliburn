"""Provider 回應經真 SDK 准入；錯誤正文與空白 final 不成為保存結果。"""

import asyncio
import logging
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.bundles.context.native_plugin import create_native_plugin
from caliburn.bundles.context.services import COMPACTION_CLIENT
from caliburn.modules.agent.application.events import model_event
from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    message,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    run_turn,
    sse_response,
)

PRIVATE_PROVIDER_TEXT = "synthetic-provider-private-body"


@pytest.mark.parametrize(
    "failure", ["model_http", "model_stream", "model_phase", "count", "compact"]
)
def test_provider_failure_does_not_retain_raw_text_in_saved_error(
    failure: str,
    caplog: pytest.LogCaptureFixture,
    recwarn: pytest.WarningsRecorder,
) -> None:
    requests: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request.url.path)
        if failure == "compact" and request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 10}
            )
        if failure == "model_stream":
            return sse_response(
                EventStream(
                    [
                        response_events(response_payload())[0],
                        {
                            "type": "error",
                            "sequence_number": 1,
                            "code": "server_error",
                            "message": PRIVATE_PROVIDER_TEXT,
                            "param": None,
                        },
                    ]
                )
            )
        if failure == "model_phase":
            return sse_response(
                EventStream(
                    response_events(response_payload([message(PRIVATE_PROVIDER_TEXT)]))
                )
            )
        return httpx2.Response(
            500,
            headers={"x-request-id": "req_provider_boundary"},
            json={
                "error": {
                    "message": PRIVATE_PROVIDER_TEXT,
                    "type": "server_error",
                }
            },
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            plugins = (
                (create_native_plugin(threshold_tokens=10),)
                if failure in ("count", "compact")
                else ()
            )
            async with open_agent(
                agent_id="provider-boundary",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(AgentBundle(plugins=plugins),),
                external_services=(COMPACTION_CLIENT.bind(client),),
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:
                with pytest.raises((RuntimeError, ValueError)) as caught:
                    async for part in agent.astream(
                        workspace_id=TEST_WORKSPACE_ID,
                        turn_id=uuid4(),
                        input="synthetic employee input",
                    ):
                        public = model_event(part)
                        if public is not None:
                            assert PRIVATE_PROVIDER_TEXT not in public.model_dump_json()
                saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
                assert saved.next
                assert saved.values["model_response"] is None
                assert saved.values["compaction_response"] is None
                assert any(task.error for task in saved.tasks)
                saved_errors = repr([task.error for task in saved.tasks])
                assert PRIVATE_PROVIDER_TEXT not in saved_errors
                assert PRIVATE_PROVIDER_TEXT not in str(caught.value)
                assert PRIVATE_PROVIDER_TEXT not in repr(caught.value)

    with caplog.at_level(logging.ERROR):
        asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert PRIVATE_PROVIDER_TEXT not in repr(
        [record.__dict__ for record in caplog.records]
    )
    # 鎖定 SDK 對刻意非法 phase 的 parse_response 會先發序列化警告；
    # 這不是公開事件或保存錯誤，不在應用層增加全域 warning 遮蔽。
    if failure != "model_phase":
        assert not recwarn
    assert len(requests) == (2 if failure == "compact" else 1)


@pytest.mark.parametrize("text", [" \n\t", "\u3000"])
def test_whitespace_final_is_not_saved_as_a_completed_turn(text: str) -> None:
    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(
                            response_events(response_payload([message(text=text)]))
                        )
                    )
                )
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            with pytest.raises(ValueError, match="nonempty"):
                await run_turn(agent)
            saved = await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)
            assert saved.values["model_response"] is None
            assert not saved.values["turn_completed"]
            assert saved.next == ("call_model",)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
