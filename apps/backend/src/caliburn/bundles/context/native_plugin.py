"""在完整模型步前執行原生壓縮的插件。"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, TypedDict

from langgraph.func import task
from langgraph.runtime import Runtime
from openai.types.responses import CompactedResponse
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.context.request_compaction import (
    compact_request,
    compaction_input,
    count_request,
)
from caliburn.bundles.context.services import COMPACTION_CLIENT, HISTORY_COMPACTION
from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentLimitError, AgentState, request_items


class NativeCompactionFields(TypedDict):
    native_compaction_item_count: int | None


class NativeCompactionState(AgentState, NativeCompactionFields):
    pass


def create_native_plugin(
    *, threshold_tokens: int = 160000, history_threshold_tokens: int = 96000
) -> AgentPlugin:
    @asynccontextmanager
    async def open_services(
        services: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        client = services.require(COMPACTION_CLIENT)

        async def compact_history(
            request: ResponseCreateParamsBase,
        ) -> CompactedResponse | None:
            return await compact_request(
                client, request, threshold_tokens=history_threshold_tokens
            )

        yield (HISTORY_COMPACTION.bind((compact_history,)),)

    async def initialize(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> NativeCompactionFields:
        return {"native_compaction_item_count": None}

    async def compact(
        state: NativeCompactionState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        request = state["model_request"]
        compacted_size = state["native_compaction_item_count"]
        if compacted_size is not None and len(request_items(request)) <= compacted_size:
            return {}
        client = runtime.context.services.require(COMPACTION_CLIENT)

        @task
        async def prepare() -> CompactedResponse | None:
            return await compact_request(
                client, request, threshold_tokens=threshold_tokens
            )

        response = await prepare()
        if response is None:
            return {}
        output = compaction_input(response)
        return {
            "compaction_response": response,
            "native_compaction_item_count": len(output),
            "model_request": {
                **request,
                "input": output,
            },
        }

    async def check_capacity(
        state: NativeCompactionState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        request = state["model_request"]
        compacted_size = state["native_compaction_item_count"]
        if compacted_size is None or len(request_items(request)) > compacted_size:
            return {}
        client = runtime.context.services.require(COMPACTION_CLIENT)

        @task
        async def recount() -> int:
            return await count_request(client, request)

        if await recount() >= threshold_tokens:
            raise AgentLimitError(
                "Compacted window still reaches the token threshold without new items"
            )
        return {}

    return AgentPlugin(
        name="native_compaction",
        required_services=(COMPACTION_CLIENT,),
        provided_services=(HISTORY_COMPACTION,),
        open_services=open_services,
        state_schema=NativeCompactionFields,
        on_turn_start=(PluginStep("initialize", initialize),),
        before_model_step=(
            PluginStep(
                "compact", compact, input_schema=NativeCompactionState, run_last=True
            ),
            PluginStep(
                "check_capacity",
                check_capacity,
                input_schema=NativeCompactionState,
                run_last=True,
            ),
        ),
    )
