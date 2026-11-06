"""Plan 已見內容與版本沿原生保存、恢復及完整壓縮窗口接續。"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.runtime import Runtime
from sqlalchemy import Engine

from caliburn.bundles import context as context_bundle
from caliburn.bundles.context import create_bundle as create_context_bundle
from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    PluginHook,
)
from caliburn.modules.agent.state import AgentState
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.plan_context_support import assert_turn_input
from tests.integration.agent.plan_plugin_support import edit_call, tool_outputs
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
    tool,
)
from tests.integration.agent.test_plan_context import plan_materials
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import request_body


@dataclass
class CompactingPlanModel(OfflineMemoryModel):
    compact_after_requests: int = 1
    threshold_reported: bool = False
    compactions: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("input_tokens"):
            input_tokens = 1
            if (
                len(self.requests) == self.compact_after_requests
                and not self.threshold_reported
            ):
                input_tokens = 160000
                self.threshold_reported = True
            return httpx2.Response(
                200,
                json={"object": "response.input_tokens", "input_tokens": input_tokens},
            )
        if request.url.path.endswith("compact"):
            self.compactions.append(request_body(request))
            return httpx2.Response(200, json=compacted_payload())
        return super().__call__(request)


def test_reopen_resumes_fixed_plan_input_and_observed_version_after_external_edit(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+故障前已見安排：message_101／task_102\n*** End of File",
        uow_factory=factory,
    )
    model = OfflineMemoryModel([None, complete("沿原安排完成")])
    turn_id = uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, _, _):
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="保存本輪安排",
                    )
                )
            failed = await agent.aget_state(workspace_id=jd_workspace_id)
            assert failed.values["plan_version"] == 2
            assert failed.values["plan_turn_start_version"] == 2
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=2,
                diff="@@\n-故障前已見安排：message_101／task_102\n+故障後外部安排：task_999",
                uow_factory=factory,
            )
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))
            resumed = await agent.aget_state(workspace_id=jd_workspace_id)
            assert resumed.values["plan_version"] == 2
            assert resumed.values["plan_turn_start_version"] == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 2
    assert model.requests[1]["input"] == model.requests[0]["input"]
    assert plan_materials(model.requests[0]) == [
        {
            "data_kind": "consultant_interview_plan",
            "plan": "故障前已見安排：message_101／task_102",
        }
    ]
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id).body
        == "故障後外部安排：task_999"
    )


def test_reopen_reuses_captured_plan_before_parent_window_update(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+已捕捉的輪前安排：`message_101`／[工作](task_102)\n*** End of File",
        uow_factory=factory,
    )
    model = OfflineMemoryModel([complete("使用保存的安排完成")])
    turn_id = uuid4()
    fail_window = True

    def fail_after(inner: PluginHook[AgentState]) -> PluginHook[AgentState]:
        async def invoke(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            nonlocal fail_window
            result = await inner(state, runtime=runtime)
            if fail_window:
                assert result["plan_version"] == 2
                fail_window = False
                raise RuntimeError("synthetic outage after captured window")
            return result

        return invoke

    def bundle_with_failure(config: Mapping[str, object]) -> AgentBundle:
        bundle = create_context_bundle(config)
        plugins = []
        for plugin in bundle.plugins:
            if plugin.name == "window":
                plugin = replace(
                    plugin,
                    on_turn_start=tuple(
                        replace(step, wrappers=(*step.wrappers, fail_after))
                        if step.name == "prepare_window"
                        else step
                        for step in plugin.on_turn_start
                    ),
                )
            plugins.append(plugin)
        return replace(bundle, plugins=tuple(plugins))

    def reject_current_plan(
        self: SqlAlchemyPlanQueries, *, workspace_id: UUID
    ) -> PlanView:
        raise AssertionError("resuming a captured window must not query current Plan")

    async def run(injection: pytest.MonkeyPatch) -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, _, _):
            with pytest.raises(
                RuntimeError, match="synthetic outage after captured window"
            ):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="取回已保存的安排",
                    )
                )
            failed = await agent.aget_state(workspace_id=jd_workspace_id)
            assert_turn_input(
                failed.values["model_request"]["input"],
                engine=pg_engine,
                workspace_id=jd_workspace_id,
                turn_id=turn_id,
                text="取回已保存的安排",
                memory_projected=False,
            )
            assert failed.values["plan_version"] is None
            assert failed.values["plan_turn_start_version"] == 2
            assert model.requests == []
        patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=2,
            diff=(
                "@@\n-已捕捉的輪前安排：`message_101`／[工作](task_102)"
                "\n+父節點故障後外部安排：task_999"
            ),
            uow_factory=factory,
        )
        injection.setattr(SqlAlchemyPlanQueries, "get_current", reject_current_plan)
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))
            resumed = await agent.aget_state(workspace_id=jd_workspace_id)
            assert resumed.values["plan_version"] == 2
            assert resumed.values["plan_turn_start_version"] == 2

    with monkeypatch.context() as injection:
        injection.setattr(context_bundle, "create_bundle", bundle_with_failure)
        asyncio.run(run(injection), loop_factory=asyncio.SelectorEventLoop)

    assert len(model.requests) == 1
    assert plan_materials(model.requests[0]) == [
        {
            "data_kind": "consultant_interview_plan",
            "plan": "已捕捉的輪前安排：`message_101`／[工作](task_102)",
        }
    ]
    assert_turn_input(
        model.requests[0]["input"][-2:],
        engine=pg_engine,
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="取回已保存的安排",
    )
    current = SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
    assert current.version == 3
    assert current.body == "父節點故障後外部安排：task_999"


def test_native_compaction_keeps_full_window_and_plan_version_for_direct_edits(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+壓縮前安排\n*** End of File",
        uow_factory=factory,
    )
    model = CompactingPlanModel(
        [
            [tool("read_work_situation_map", "map")],
            [edit_call("after-compact", "@@\n-壓縮前安排\n+壓縮後安排")],
            complete("本輪完成"),
            [edit_call("next-turn", "@@\n-壓縮後安排\n+下一輪安排")],
            complete("接續完成"),
        ]
    )
    next_turn = uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine,
            checkpoint_conninfo,
            model,
            context_window=True,
            native_compaction=True,
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="整理安排"
                )
            )
            first = await agent.aget_state(workspace_id=jd_workspace_id)
            assert first.values["plan_turn_start_version"] == 2
            assert first.values["plan_version"] == 3
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=next_turn,
                    input="繼續修改安排",
                )
            )
            second = await agent.aget_state(workspace_id=jd_workspace_id)
            assert second.values["plan_turn_start_version"] == 3
            assert second.values["plan_version"] == 4

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.compactions) == 1
    assert plan_materials(model.requests[0]) == [
        {"data_kind": "consultant_interview_plan", "plan": "壓縮前安排"}
    ]
    assert model.requests[1]["input"] == compacted_payload()["output"]
    prefix = [
        *model.requests[2]["input"],
        *complete("本輪完成"),
    ]
    assert model.requests[3]["input"][: len(prefix)] == prefix
    assert_turn_input(
        model.requests[3]["input"][len(prefix) :],
        engine=pg_engine,
        workspace_id=jd_workspace_id,
        turn_id=next_turn,
        text="繼續修改安排",
    )
    assert model.requests[3]["input"][:2] == compacted_payload()["output"]
    assert plan_materials(model.requests[3]) == []
    assert tool_outputs(model.requests[2])["after-compact"]["status"] == "updated"
    assert tool_outputs(model.requests[4])["next-turn"]["status"] == "updated"
    current = SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
    assert current.version == 4
    assert current.body == "下一輪安排"
