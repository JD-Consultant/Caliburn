"""共享來源在啟動取得；本輪讀版由插件 State 固定。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import TypedDict, cast
from uuid import UUID

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceKey,
)
from caliburn.modules.agent.state import (
    AgentState,
    request_items,
)


@dataclass
class SnapshotSource:
    published: dict[UUID, str]
    events: list[str] = field(default_factory=list)
    reads: list[UUID] = field(default_factory=list)
    cleanup_error: RuntimeError | None = None


SNAPSHOT_SOURCE = ServiceKey[SnapshotSource]("snapshots")


class SnapshotChannels(TypedDict):
    snapshot_version: str
    snapshot_tool_context: str


class SnapshotState(AgentState, SnapshotChannels):
    pass


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    label = str(config.get("label", "snapshot"))

    async def read(item: str, runtime: ToolRuntime[AgentContext]) -> str:
        if config.get("fail_tool"):
            raise RuntimeError("tool failed")
        return f"{runtime.state['snapshot_tool_context']}/{item}"

    tools = (
        (
            StructuredTool.from_function(
                coroutine=read, name="read_alpha", description="Read item."
            ),
        )
        if config.get("tools")
        else ()
    )

    @asynccontextmanager
    async def open_services(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[object], ...]]:
        source = dependencies.require(SNAPSHOT_SOURCE)

        @asynccontextmanager
        async def acquire() -> AsyncIterator[None]:
            source.events.append(f"{label}:enter")
            try:
                yield
            finally:
                await asyncio.sleep(0)
                source.events.append(f"{label}:exit")
                if source.cleanup_error is not None:
                    raise source.cleanup_error

        # yield 前的部分取得也由此 Bundle 自己清理。
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(acquire())
            if config.get("fail_setup"):
                raise RuntimeError("setup failed")

            yield ()

    async def pin_snapshot(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> dict[str, str]:
        source = runtime.context.services.require(SNAPSHOT_SOURCE)
        workspace_id = state["workspace_id"]
        source.reads.append(workspace_id)
        return {"snapshot_version": source.published[workspace_id]}

    async def provide(
        state: SnapshotState, *, runtime: Runtime[AgentContext]
    ) -> dict[str, object]:
        request = state["model_request"]
        snapshot = state["snapshot_version"]
        items = [
            item
            for item in request_items(request)
            if not (
                isinstance(item, dict)
                and item.get("role") == "developer"
                and str(item.get("content", "")).startswith(label + ":")
            )
        ]
        stamp = f"{label}:{snapshot}:items={len(items)}"
        return {
            "model_request": {
                **request,
                "instructions": f"{label}:static\n\n{stamp}",
                "input": cast(
                    ResponseInputParam,
                    [{"role": "developer", "content": stamp}, *items],
                ),
            },
            "snapshot_tool_context": stamp,
        }

    return AgentBundle(
        (
            AgentPlugin(
                label,
                tools=tools,
                required_services=(SNAPSHOT_SOURCE,),
                prompt_sections=(f"{label}:static",),
                state_schema=SnapshotChannels,
                on_turn_start=(PluginStep("pin_snapshot", pin_snapshot),),
                before_model_step=(PluginStep("provide", provide),),
                open_services=open_services,
            ),
        )
    )
