"""Plan 工具觀察版本與輪前版本在競爭、跨輪及跨 Workspace 的界線。"""

import asyncio
import json
from functools import partial
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.plan_plugin_support import (
    ScriptedPlanModel,
    edit_call,
    open_plan_agent,
    read_call,
    tool_outputs,
)
from tests.integration.agent.stream_support import consume


def test_stale_edit_preserves_external_changes_until_model_reads_again(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    queries = SqlAlchemyPlanQueries(pg_engine)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+共同範圍\n+原安排\n*** End of File",
        uow_factory=factory,
    )
    model = ScriptedPlanModel(
        [
            [read_call("original")],
            [edit_call("stale", "@@\n-共同範圍\n+模型範圍")],
            [read_call("latest"), edit_call("fresh", "@@\n-共同範圍\n+模型範圍")],
            None,
        ]
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        if len(model.requests) == 1:
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=2,
                diff="@@\n-原安排\n+外部安排",
                uow_factory=factory,
            )
        if len(model.requests) == 2:
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 3, "共同範圍\n外部安排"
            )
        return model(request)

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="調整安排"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["plan_turn_start_version"] == 2
            assert saved.values["plan_version"] == 4

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    rejection = tool_outputs(model.requests[2])["stale"]
    assert rejection["status"] == "rejected"
    assert rejection["code"] == "target_stale"
    assert rejection["next_action"]
    outputs = tool_outputs(model.requests[3])
    assert outputs["latest"] == {"plan": "共同範圍\n外部安排"}
    assert outputs["fresh"]["status"] == "updated"
    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 4, "模型範圍\n外部安排"
    )


def test_new_turn_uses_latest_baseline_but_requires_a_new_read(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    model = ScriptedPlanModel(
        [
            [
                read_call("first"),
                edit_call("create", "@@\n+第一輪安排\n*** End of File"),
            ],
            None,
            [edit_call("unread", "@@\n-輪間最新安排\n+不應寫入"), read_call("latest")],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第一輪"
                )
            )
            first = await agent.aget_state(workspace_id=jd_workspace_id)
            assert first.values["plan_turn_start_version"] == 1
            assert first.values["plan_version"] == 2
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=2,
                diff="@@\n-第一輪安排\n+輪間最新安排",
                uow_factory=factory,
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第二輪"
                )
            )
            second = await agent.aget_state(workspace_id=jd_workspace_id)
            assert second.values["plan_turn_start_version"] == 3
            assert second.values["plan_version"] == 3

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    second_request = model.requests[2]
    assert second_request["input"] == [{"role": "user", "content": "第二輪"}]
    assert "輪間最新安排" not in json.dumps(second_request, ensure_ascii=False)
    outputs = tool_outputs(model.requests[3])
    assert outputs["unread"]["status"] == "rejected"
    assert outputs["unread"]["code"] == "source_not_available"
    assert outputs["latest"] == {"plan": "輪間最新安排"}
    assert SqlAlchemyPlanQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    ) == PlanView(jd_workspace_id, 3, "輪間最新安排")


def test_one_agent_keeps_plan_contents_and_versions_separate_by_workspace(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    other = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="另一份 Plan")
        .workspace_id
    )
    model = ScriptedPlanModel(
        [
            [read_call("first"), edit_call("create", "@@\n+甲的安排\n*** End of File")],
            None,
            [
                read_call("second"),
                edit_call("create", "@@\n+乙的安排\n*** End of File"),
            ],
            None,
            [read_call("first_again")],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            for workspace in (jd_workspace_id, other, jd_workspace_id):
                await consume(
                    agent.astream(
                        workspace_id=workspace, turn_id=uuid4(), input="讀取這份安排"
                    )
                )
            first = await agent.aget_state(workspace_id=jd_workspace_id)
            second = await agent.aget_state(workspace_id=other)
            assert first.values["plan_turn_start_version"] == 2
            assert second.values["plan_turn_start_version"] == 1
            assert first.values["workspace_id"] == jd_workspace_id
            assert second.values["workspace_id"] == other

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[3])["second"] == {"plan": None}
    assert tool_outputs(model.requests[5])["first_again"] == {"plan": "甲的安排"}
    queries = SqlAlchemyPlanQueries(pg_engine)
    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 2, "甲的安排"
    )
    assert queries.get_current(workspace_id=other) == PlanView(other, 2, "乙的安排")
