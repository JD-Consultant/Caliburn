"""公開工具把可修正 patch 錯誤轉成提示，保存故障仍向外傳遞。"""

import asyncio
import json
from uuid import UUID

import pytest
from langgraph.func import entrypoint
from langgraph.prebuilt import ToolRuntime

from caliburn.bundles.plan import create_bundle
from caliburn.bundles.plan.services import PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.plan.application.errors import PlanPersistenceError
from caliburn.modules.plan.application.persistence import PlanUnitOfWork
from caliburn.modules.plan.domain.errors import BodyEditError, BodyMatch


def invoke_rejected_write(error: Exception) -> object:
    def failing_uow() -> PlanUnitOfWork:
        raise error

    runtime = ToolRuntime[AgentContext, PlanToolState](
        state={"workspace_id": UUID(int=23), "plan_version": 7},
        context=AgentContext(PluginServices({PLAN_UOW_FACTORY: failing_uow})),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="edit-1",
        store=None,
    )
    edit = create_bundle({}).plugins[0].tools[1]

    @entrypoint()
    async def execute(input: bool) -> object:
        return await edit.ainvoke({"diff": "@@\n-a\n+b", "runtime": runtime})

    return asyncio.run(execute.ainvoke(True))


def test_patch_error_preserves_safe_hunk_and_candidate_locations() -> None:
    result = invoke_rejected_write(
        BodyEditError(
            "ambiguous_patch_context",
            "INTERNAL_EXCEPTION_DETAIL",
            hunk_number=3,
            candidates=(BodyMatch(2, 4), BodyMatch(7, 9)),
        )
    )

    assert isinstance(result, str)
    rejection = json.loads(result)
    assert rejection["code"] == "ambiguous_patch_context"
    assert "第 3 段" in rejection["message"]
    assert "2–4" in rejection["message"]
    assert "7–9" in rejection["message"]
    assert "INTERNAL_EXCEPTION_DETAIL" not in result
    assert str(UUID(int=23)) not in result


def test_unknown_commit_is_not_converted_to_a_retriable_tool_rejection() -> None:
    error = PlanPersistenceError(commit_status="unknown")

    with pytest.raises(PlanPersistenceError) as caught:
        invoke_rejected_write(error)

    assert caught.value.commit_status == "unknown"
