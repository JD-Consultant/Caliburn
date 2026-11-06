"""Plan 取消接點只恢復目標輪基準，重試不重複增加內容版本。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from psycopg import errors as pg_errors
from sqlalchemy import Engine
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.bundles.plan import create_bundle
from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.plan.application.errors import PlanPersistenceError
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
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


def test_cancel_restores_baseline_from_latest_commit_and_retry_preserves_version(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    queries = SqlAlchemyPlanQueries(pg_engine)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+輪前安排\n*** End of File",
        uow_factory=factory,
    )
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=2,
        diff="@@\n-輪前安排\n+本輪第一次修改",
        uow_factory=factory,
    )
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=3,
        diff="@@\n-本輪第一次修改\n+已提交但尚未保存工具結果",
        uow_factory=factory,
    )
    turn_id = uuid4()
    context = AgentContext(
        PluginServices({PLAN_QUERIES: queries, PLAN_UOW_FACTORY: factory})
    )
    callback = next(
        plugin
        for plugin in create_bundle({}).plugins
        if plugin.name == "plan_lifecycle"
    ).on_turn_cancel
    assert callback is not None

    async def run() -> None:
        for _ in range(2):
            await callback(
                {
                    "plan_turn_id": turn_id,
                    "plan_turn_start_version": 2,
                    "plan_version": 3,
                },
                workspace_id=jd_workspace_id,
                turn_id=turn_id,
                context=context,
            )
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 5, "輪前安排"
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_agent_cancel_restores_committed_edit_then_new_turn_reinitializes_plan(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    queries = SqlAlchemyPlanQueries(pg_engine)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+輪前安排\n*** End of File",
        uow_factory=factory,
    )
    turn_id, next_turn_id = uuid4(), uuid4()
    fixture = "tests.integration.agent.plan_plugin_fixture"
    model = ScriptedPlanModel(
        [
            [
                read_call("before"),
                edit_call("committed", "@@\n-輪前安排\n+取消輪修改"),
                edit_call("must_not_run", "@@\n-輪前安排\n+取消輪未執行工具"),
            ],
            [
                edit_call("new_unread", "@@\n-輪前安排\n+不得沿用前輪已讀版本"),
                read_call("new_read"),
            ],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            extra_bundles=(BundleConfig(fixture, {"fail": True}),),
        ) as agent:
            with pytest.raises(RuntimeError, match="synthetic post-edit outage"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="取消輪輸入",
                    )
                )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["plan_turn_id"] == turn_id
            assert saved.values["plan_turn_start_version"] == 2
            assert saved.values["plan_version"] == 2
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 3, "取消輪修改"
            )
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=turn_id)
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=turn_id)
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 4, "輪前安排"
            )
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=False,
            extra_bundles=(BundleConfig(fixture, {"fail": False}),),
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=next_turn_id,
                    input="全新輪輸入",
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["plan_turn_id"] == next_turn_id
            assert saved.values["plan_turn_start_version"] == 4
            assert saved.values["plan_version"] == 4
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 4, "輪前安排"
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert model.requests[1]["input"] == [{"role": "user", "content": "全新輪輸入"}]
    outputs = tool_outputs(model.requests[2])
    assert outputs["new_unread"]["code"] == "source_not_available"
    assert outputs["new_read"] == {"plan": "輪前安排"}
    assert set(outputs) == {"new_unread", "new_read"}


@pytest.mark.parametrize("baseline", ["no_values", "not_initialized", "previous_turn"])
def test_cancel_without_target_turn_baseline_preserves_current_plan(
    pg_engine: Engine, jd_workspace_id: UUID, baseline: str
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    queries = SqlAlchemyPlanQueries(pg_engine)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+已完成前輪安排\n*** End of File",
        uow_factory=factory,
    )
    state: dict[str, object] | None = {
        "plan_turn_id": uuid4(),
        "plan_turn_start_version": 1,
        "plan_version": 2,
    }
    if baseline == "no_values":
        state = None
    elif baseline == "not_initialized":
        state = {}
    context = AgentContext(
        PluginServices({PLAN_QUERIES: queries, PLAN_UOW_FACTORY: factory})
    )
    callback = next(
        plugin
        for plugin in create_bundle({}).plugins
        if plugin.name == "plan_lifecycle"
    ).on_turn_cancel
    assert callback is not None

    asyncio.run(
        callback(
            state,
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            context=context,
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )

    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 2, "已完成前輪安排"
    )


def test_cancel_retry_confirms_restore_after_losing_commit_reply(
    pg_engine: Engine, jd_workspace_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    queries = SqlAlchemyPlanQueries(pg_engine)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+取消本輪修改\n*** End of File",
        uow_factory=factory,
    )
    turn_id = uuid4()
    state = {
        "plan_turn_id": turn_id,
        "plan_turn_start_version": 1,
        "plan_version": 2,
    }
    context = AgentContext(
        PluginServices({PLAN_QUERIES: queries, PLAN_UOW_FACTORY: factory})
    )
    callback = next(
        plugin
        for plugin in create_bundle({}).plugins
        if plugin.name == "plan_lifecycle"
    ).on_turn_cancel
    assert callback is not None
    native_commit = pg_engine.dialect.do_commit

    def lose_commit_reply(connection: PoolProxiedConnection) -> None:
        native_commit(connection)
        raise pg_errors.TransactionResolutionUnknown("synthetic lost commit reply")

    async def run() -> None:
        with monkeypatch.context() as injection:
            injection.setattr(pg_engine.dialect, "do_commit", lose_commit_reply)
            with pytest.raises(PlanPersistenceError) as failure:
                await callback(
                    state,
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    context=context,
                )
            assert failure.value.commit_status == "unknown"
        assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
            jd_workspace_id, 3, None
        )
        await callback(
            state,
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            context=context,
        )
        assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
            jd_workspace_id, 3, None
        )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
