"""窗口生命週期與靜態擴充接點；不知道任何業務模組或來源格式。"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, TypedDict, cast

from langgraph.func import task
from langgraph.runtime import Runtime
from openai.types.responses import CompactedResponse

from caliburn.bundles.context.request_compaction import compaction_input
from caliburn.bundles.context.services import (
    HISTORY_COMPACTION,
    PREVIOUS_WINDOW,
    WINDOW_CONTRIBUTIONS,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items


class _PreparedWindow(TypedDict):
    updates: dict[str, Any]
    input: OpenAIItems
    continues: bool


def create_window_plugin() -> AgentPlugin:
    @asynccontextmanager
    async def open_services(
        services: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        contributions = services.require(WINDOW_CONTRIBUTIONS)
        if sum(item.prepare_input is not None for item in contributions) > 1:
            raise ValueError("Window requires at most one input projection provider")
        if len(services.require(HISTORY_COMPACTION)) > 1:
            raise ValueError("Window requires at most one history compaction provider")
        yield ()

    async def initialize(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        contributions = runtime.context.services.require(WINDOW_CONTRIBUTIONS)
        compactors = runtime.context.services.require(HISTORY_COMPACTION)

        @task
        async def capture() -> _PreparedWindow:
            saved = await runtime.context.services.require(PREVIOUS_WINDOW)(
                state["workspace_id"], state["turn_id"]
            )
            previous = saved.values if saved else None
            rebuilding = previous is None or any(
                contribution.should_renew is not None
                and contribution.should_renew(state, previous)
                for contribution in contributions
            )
            history: OpenAIItems = []
            if not rebuilding:
                assert previous is not None
                history = request_items(previous["model_request"])
            working: dict[str, Any] = dict(state)
            working["model_request"] = {**state["model_request"], "input": history}
            updates: dict[str, Any] = {}
            for contribution in contributions:
                update = await contribution.prepare(
                    cast(AgentState, working),
                    previous=previous,
                    rebuilding=rebuilding,
                    runtime=runtime,
                )
                working.update(update)
                updates.update(update)
            request = working["model_request"]
            updates["model_request"] = request

            original = state["turn_input"]
            input_items: OpenAIItems = (
                [{"role": "user", "content": original}]
                if isinstance(original, str)
                else list(original)
            )
            working["model_request"] = {**request, "input": input_items}
            for contribution in contributions:
                if contribution.prepare_input is not None:
                    update = await contribution.prepare_input(
                        cast(AgentState, working),
                        previous=previous,
                        rebuilding=rebuilding,
                        runtime=runtime,
                    )
                    working.update(update)
                    updates.update(
                        {
                            key: value
                            for key, value in update.items()
                            if key != "model_request"
                        }
                    )
            return {
                "updates": updates,
                "input": request_items(working["model_request"]),
                "continues": not rebuilding,
            }

        captured = await capture()
        updates = captured["updates"]
        request = updates["model_request"]
        history = request_items(request)
        if captured["continues"] and compactors:

            @task
            async def compact_history() -> CompactedResponse | None:
                return await compactors[0](request)

            response = await compact_history()
            if response is not None:
                history = cast(OpenAIItems, compaction_input(response))
                updates = {**updates, "compaction_response": response}
        return {
            **updates,
            "model_request": {**request, "input": [*history, *captured["input"]]},
        }

    required = (
        PREVIOUS_WINDOW,
        WINDOW_CONTRIBUTIONS,
        HISTORY_COMPACTION,
    )
    return AgentPlugin(
        name="window",
        required_services=required,
        open_services=open_services,
        on_turn_start=(PluginStep("prepare_window", initialize, run_last=True),),
    )
