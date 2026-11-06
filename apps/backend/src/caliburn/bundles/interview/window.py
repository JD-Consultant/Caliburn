"""換窗時提供合法既有原話；是否換窗由 Context 編排決定。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, cast

from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam
from pydantic import BaseModel, ConfigDict

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.services import COMPLETED_TURNS, WINDOW_CONTRIBUTIONS
from caliburn.bundles.interview.context import (
    load_interview_context,
    project_employee_input_reference,
    project_interview_context,
)
from caliburn.bundles.interview.discovery import discover_interview_sources
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
)
from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceKey,
)
from caliburn.modules.agent.state import AgentState, request_items


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    preload: bool = True
    include_input_reference: bool = True
    include_navigation: bool = True


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    """明示選用窗口投影；獨立保存、工具與 Prompt 仍由原 Bundle 提供。"""
    settings = _Settings.model_validate(config)
    contribution = WindowContribution(
        prepare=partial(prepare_interview_window, preload=settings.preload),
        prepare_input=(
            partial(
                prepare_interview_input,
                include_input_reference=settings.include_input_reference,
                include_navigation=settings.include_navigation,
            )
            if settings.include_input_reference or settings.include_navigation
            else None
        ),
    )
    required_services: tuple[ServiceKey[Any], ...] = ()
    if (
        settings.preload
        or settings.include_input_reference
        or settings.include_navigation
    ):
        required_services = (INTERVIEW_QUERIES, MODEL_REFERENCES)
    if settings.preload:
        required_services += (COMPLETED_TURNS,)

    @asynccontextmanager
    async def open_services(
        services: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        yield (WINDOW_CONTRIBUTIONS.bind((contribution,)),)

    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="interview_window",
                required_plugins=("interview",)
                if settings.include_input_reference
                else (),
                required_services=required_services,
                provided_services=(WINDOW_CONTRIBUTIONS,),
                open_services=open_services,
            ),
        )
    )


async def prepare_interview_window(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
    preload: bool = True,
) -> Mapping[str, object]:
    """重建才預載已完成輪次與 App 原話，不含本輪，也不補寫新輸入。"""
    if not rebuilding or not preload:
        return {}
    services = runtime.context.services
    completed = await services.require(COMPLETED_TURNS)(state["workspace_id"])
    sources = await asyncio.to_thread(
        load_interview_context,
        workspace_id=state["workspace_id"],
        turn_id=state["turn_id"],
        queries=services.require(INTERVIEW_QUERIES),
    )
    selected = tuple(
        source
        for source in sources
        if source.message.speaker == "app" or source.message.turn_id in completed
    )
    refs = await asyncio.to_thread(
        message_refs,
        workspace_id=state["workspace_id"],
        message_ids=tuple(source.message.message_id for source in selected),
        references=services.require(MODEL_REFERENCES),
    )
    material = project_interview_context(selected, refs=refs)
    request = state["model_request"]
    return {
        "model_request": {
            **request,
            "input": cast(ResponseInputParam, [*request_items(request), *material]),
        }
    }


async def prepare_interview_input(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
    include_input_reference: bool = True,
    include_navigation: bool = True,
) -> Mapping[str, object]:
    """補本輪定位且保留原生 items；啟用 input ref 前須已保存有效員工輸入。"""
    request = state["model_request"]
    items = request_items(request)
    if include_input_reference:
        services = runtime.context.services
        messages = await asyncio.to_thread(
            services.require(INTERVIEW_QUERIES).list_messages,
            workspace_id=state["workspace_id"],
            turn_id=state["turn_id"],
        )
        original = next(
            (
                message
                for message in messages
                if message.speaker == "employee" and message.kind == "text"
            ),
            None,
        )
        if original is None:
            raise ValueError("本輪已保存的員工輸入不可用，不能提供來源定位")
        refs = await asyncio.to_thread(
            message_refs,
            workspace_id=state["workspace_id"],
            message_ids=(original.message_id,),
            references=services.require(MODEL_REFERENCES),
        )
        items = [
            *items,
            *project_employee_input_reference(refs[original.message_id]),
        ]
    prepared: AgentState = {
        **state,
        "model_request": {**request, "input": cast(ResponseInputParam, items)},
    }
    if include_navigation:
        return await discover_interview_sources(prepared, runtime=runtime)
    return {"model_request": prepared["model_request"]}
