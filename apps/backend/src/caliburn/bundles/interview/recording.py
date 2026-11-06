"""正常輪次首尾保存原話；中途輸出仍屬 Agent 執行紀錄。"""

import asyncio
from typing import cast

from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.interview.context import project_employee_input_reference
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY, MODEL_REFERENCES
from caliburn.modules.agent.application.turn_history import message_text
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState, request_items
from caliburn.modules.interview.application.recording import (
    record_consultant_message,
    record_turn_input,
)


async def record_input(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> dict[str, object]:
    """保存後配置 ref；映射失敗重入時，原用例依輪次回同一筆輸入 UUID。"""
    text = state["turn_input"]
    if not isinstance(text, str):
        raise TypeError("訪談輸入必須是員工原文，不接受模型訊息陣列")
    saved = await asyncio.to_thread(
        record_turn_input,
        workspace_id=state["workspace_id"],
        turn_id=state["turn_id"],
        text=text,
        uow_factory=runtime.context.services.require(INTERVIEW_UOW_FACTORY),
    )
    refs = await asyncio.to_thread(
        message_refs,
        workspace_id=state["workspace_id"],
        message_ids=(saved.message_id,),
        references=runtime.context.services.require(MODEL_REFERENCES),
    )
    request = state["model_request"]
    return {
        "model_request": {
            **request,
            "input": cast(
                ResponseInputParam,
                [
                    *request_items(request),
                    *project_employee_input_reference(refs[saved.message_id]),
                ],
            ),
        }
    }


async def record_final_message(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> dict[str, object]:
    response = state["model_response"]
    assert response is not None
    (text,) = message_text(response, final_only=True)
    await asyncio.to_thread(
        record_consultant_message,
        workspace_id=state["workspace_id"],
        turn_id=state["turn_id"],
        text=text,
        uow_factory=runtime.context.services.require(INTERVIEW_UOW_FACTORY),
    )
    return {}
