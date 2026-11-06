"""Memory 選擇接入換窗的投影；未啟用換窗時不呼叫。"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any, cast

from langgraph.runtime import Runtime

from caliburn.bundles.interview.discovery import discover_interview_sources
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.bundles.memory.projections import historical_interview, map_items
from caliburn.bundles.memory.services import MEMORY_QUERIES
from caliburn.bundles.memory.state import ConsultantState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items


def memory_published_changed(state: AgentState, previous: Mapping[str, Any]) -> bool:
    return cast(ConsultantState, state)["memory_published_version"] != previous.get(
        "memory_published_version"
    )


async def prepare_memory_window(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
) -> Mapping[str, object]:
    scope = cast(ConsultantState, state)
    ids = scope["memory_interview_ids"]
    if not rebuilding:
        return {}
    services = runtime.context.services
    snapshot = await asyncio.to_thread(
        services.require(MEMORY_QUERIES).get_published,
        workspace_id=state["workspace_id"],
        published_version=scope["memory_published_version"],
    )
    items = snapshot.items if snapshot else ()
    transcript = await asyncio.to_thread(
        services.require(INTERVIEW_QUERIES).list_messages,
        workspace_id=state["workspace_id"],
        after_message_id=snapshot.covered_through_message_id if snapshot else None,
    )
    selected = tuple(
        message.message_id
        for message in transcript
        if message.turn_id != state["turn_id"] and message.message_id in ids
    )
    navigation = {
        "data_kind": "memory_navigation",
        "published_version": scope["memory_published_version"],
        "work_situation_map": map_items(items, "situation"),
        "work_understanding_map": map_items(items, "understanding"),
    }
    material: OpenAIItems = [
        {
            "role": "user",
            "content": json.dumps(navigation, ensure_ascii=False),
        }
    ]
    if selected:
        refs = await asyncio.to_thread(
            message_refs,
            workspace_id=state["workspace_id"],
            message_ids=tuple(message.message_id for message in transcript),
            references=services.require(MODEL_REFERENCES),
        )
        material.extend(historical_interview(selected, messages=transcript, refs=refs))
    return {
        "model_request": {
            **state["model_request"],
            "input": [
                *request_items(state["model_request"]),
                *material,
            ],
        },
    }


async def prepare_memory_input(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
) -> Mapping[str, object]:
    messages = await asyncio.to_thread(
        runtime.context.services.require(INTERVIEW_QUERIES).list_messages,
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
        return await discover_interview_sources(state, runtime=runtime)
    refs = await asyncio.to_thread(
        message_refs,
        workspace_id=state["workspace_id"],
        message_ids=(original.message_id,),
        references=runtime.context.services.require(MODEL_REFERENCES),
    )
    prepared = {
        **state,
        "model_request": {
            **state["model_request"],
            "input": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "data_kind": "employee_input",
                            "ref": refs[original.message_id],
                            "text": original.text,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        },
    }
    return await discover_interview_sources(cast(AgentState, prepared), runtime=runtime)
