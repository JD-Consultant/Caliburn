"""用原生 PluginStep 組合正式來源函式；僅替代尚未接線的 Context 編排。"""

import asyncio
from collections.abc import Mapping
from typing import TypedDict, cast
from uuid import UUID

from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.interview.context import (
    insert_interview_context,
    load_interview_context,
    project_interview_context,
)
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items


class ContextChannels(TypedDict, total=False):
    test_context_prefix_size: int


class ContextState(AgentState, ContextChannels):
    pass


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    """已宣告的來源範圍與換窗政策由測試組裝固定，不從模型參數取得。"""
    selection = cast(tuple[UUID, ...] | None, config.get("selection"))
    window_selection = cast(tuple[UUID, ...] | None, config.get("window_selection"))
    mode = config.get("mode", "preload")

    async def probe() -> str:
        if config.get("fail_tool"):
            raise RuntimeError("synthetic context tool outage")
        return "合成工具結果"

    tool = StructuredTool.from_function(
        coroutine=probe, description="Context test probe."
    )

    async def preload(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        request = state["model_request"]
        selected = await asyncio.to_thread(
            load_interview_context,
            workspace_id=state["workspace_id"],
            turn_id=state["turn_id"],
            queries=runtime.context.services.require(INTERVIEW_QUERIES),
            message_ids=selection,
        )
        refs = await asyncio.to_thread(
            message_refs,
            workspace_id=state["workspace_id"],
            message_ids=tuple(source.message.message_id for source in selected),
            references=runtime.context.services.require(MODEL_REFERENCES),
        )
        material = project_interview_context(selected, refs=refs)
        return {
            "test_context_prefix_size": len(material),
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    insert_interview_context(
                        request_items(request), material, position=0
                    ),
                ),
            },
        }

    async def change_window(
        state: ContextState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        if state["model_step"] != 2 or mode not in ("compact", "window"):
            return {}
        request = state["model_request"]
        # 此編排只替換自己在輪首注入的 prefix；原生 input/output 全數沿用。
        retained = request_items(request)[state["test_context_prefix_size"] :]
        material: OpenAIItems
        if mode == "compact":
            material = [{"role": "user", "content": "合成壓縮摘要"}]
        else:
            selected = await asyncio.to_thread(
                load_interview_context,
                workspace_id=state["workspace_id"],
                turn_id=state["turn_id"],
                queries=runtime.context.services.require(INTERVIEW_QUERIES),
                message_ids=window_selection,
            )
            refs = await asyncio.to_thread(
                message_refs,
                workspace_id=state["workspace_id"],
                message_ids=tuple(source.message.message_id for source in selected),
                references=runtime.context.services.require(MODEL_REFERENCES),
            )
            material = project_interview_context(selected, refs=refs)
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    insert_interview_context(retained, material, position=0),
                ),
            }
        }

    return AgentBundle(
        (
            AgentPlugin(
                "synthetic_context",
                tools=(tool,),
                required_services=(INTERVIEW_QUERIES, MODEL_REFERENCES),
                state_schema=ContextChannels,
                on_turn_start=(PluginStep("preload", preload),)
                if config.get("preload", True)
                else (),
                before_model_step=(
                    PluginStep(
                        "change_window", change_window, input_schema=ContextState
                    ),
                ),
            ),
        )
    )
