"""即使不預載正文，也讓模型取得有效訪談集合的可讀端點。"""

import asyncio
import json
from typing import cast

from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState, request_items


async def discover_interview_sources(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> dict[str, object]:
    services = runtime.context.services
    messages = await asyncio.to_thread(
        services.require(INTERVIEW_QUERIES).list_messages,
        workspace_id=state["workspace_id"],
    )
    endpoints = (messages[0].message_id, messages[-1].message_id) if messages else ()
    refs = await asyncio.to_thread(
        message_refs,
        workspace_id=state["workspace_id"],
        message_ids=endpoints,
        references=services.require(MODEL_REFERENCES),
    )
    material = {
        "data_kind": "interview_navigation",
        "first_ref": refs[endpoints[0]] if endpoints else None,
        "last_ref": refs[endpoints[-1]] if endpoints else None,
        "scope": "目前有效訪談，含本輪已保存原話；空集合兩端為 null。",
    }
    request = state["model_request"]
    return {
        "model_request": {
            **request,
            "input": cast(
                ResponseInputParam,
                [
                    *request_items(request),
                    {
                        "role": "user",
                        "content": json.dumps(material, ensure_ascii=False),
                    },
                ],
            ),
        }
    }
