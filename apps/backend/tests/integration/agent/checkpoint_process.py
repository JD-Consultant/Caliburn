"""獨立 writer／reader 程序：只透過公開組裝及官方 saver 接續。"""

import asyncio
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx2
from langchain_core.tools import StructuredTool
from openai.types.responses import (
    ParsedResponse,
    ParsedResponseFunctionToolCall,
    ParsedResponseOutputMessage,
    ParsedResponseOutputText,
    ResponseReasoningItem,
)
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
)
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    EventStream,
    call,
    message,
    offline_client,
    reasoning,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    effects = Path(str(config["effects"]))

    async def read_alpha(item: str) -> str:
        with effects.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        if item == "beta" and config["fail"]:
            raise RuntimeError("Synthetic tool failure")
        return "read " + item

    return AgentBundle(
        (
            AgentPlugin(
                "tools",
                tools=(
                    StructuredTool.from_function(
                        coroutine=read_alpha, description="Read synthetic data."
                    ),
                ),
            ),
        )
    )


async def run(mode: str, conninfo: str, directory: Path) -> None:
    sent: list[dict[str, object]] = []
    calls = [
        call(call_id=f"call_{item}", arguments=json.dumps({"item": item}))
        for item in ("alpha", "beta", "gamma")
    ]
    opaque = reasoning()
    opaque.pop("status")
    # 省略值與顯式 null 不可在 checkpoint 後互換。
    first_payload = response_payload([opaque, *calls, message(phase=None)])

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        payload = (
            first_payload if mode != "reader" and len(sent) == 1 else response_payload()
        )
        return sse_response(EventStream(response_events(payload)))

    async with (
        open_postgres_checkpointer(conninfo, initialize=mode != "reader") as saver,
        offline_client(httpx2.MockTransport(respond)) as client,
        open_agent(
            agent_id="uninterrupted-control" if mode == "control" else "cold-recovery",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig(
                    __name__,
                    {
                        "effects": str(
                            directory
                            / (
                                "control-effects.jsonl"
                                if mode == "control"
                                else "effects.jsonl"
                            )
                        ),
                        "fail": mode == "writer",
                    },
                ),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        if mode == "reader":
            snapshot = await agent.aget_state(workspace_id=UUID(int=1))
            response = snapshot.values["model_response"]
            assert type(response) is ParsedResponse
            assert response.model_extra == {"future_response_field": {"retained": True}}
            assert response.usage is not None and response.usage.total_tokens == 21
            assert type(response.output[1]) is ParsedResponseFunctionToolCall
            assert response.output[1].parsed_arguments == {"item": "alpha"}
            assert response.output[1].__api_exclude__ == {"parsed_arguments"}
            assert type(response.output[-1]) is ParsedResponseOutputMessage
            assert type(response.output[-1].content[0]) is ParsedResponseOutputText
            assert response.output[-1].content[0].__api_exclude__ == {"parsed"}
            items = snapshot.values["model_request"]["input"]
            assert isinstance(items[1], ResponseReasoningItem)
            assert items[1].encrypted_content == "synthetic-opaque-content"
            assert items[-1] == {
                "type": "function_call_output",
                "call_id": "call_alpha",
                "output": "read alpha",
            }
            history = [
                item
                async for item in agent.aget_state_history(workspace_id=UUID(int=1))
            ]
            assert history and snapshot.next
            assert sent == []
        try:
            events = (
                agent.astream(
                    turn_id=UUID(int=101),
                    workspace_id=UUID(int=1),
                    input=cast(ResponseInputParam, INITIAL),
                )
                if mode != "reader"
                else agent.aresume(turn_id=UUID(int=101), workspace_id=UUID(int=1))
            )
            async for _ in events:
                pass
        except RuntimeError as error:
            if mode != "writer" or str(error) != "Synthetic tool failure":
                raise
        else:
            assert mode in ("reader", "control")
            result = await agent.aget_state(workspace_id=UUID(int=1))
            assert result.values["model_step"] == 2
            assert result.values["model_response"].output_text == "Synthetic reply"
        (directory / f"{mode}.json").write_text(json.dumps(sent), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3])),
        loop_factory=asyncio.SelectorEventLoop,
    )
