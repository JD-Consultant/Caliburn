"""關閉重開 Agent 後，Plan task 結果、輪前基準及查詢故障的恢復界線。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from psycopg import errors as pg_errors
from sqlalchemy import Engine
from sqlalchemy.pool import PoolProxiedConnection

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.plan.application.errors import (
    PlanPersistenceError,
    PlanQueryError,
)
from caliburn.modules.plan.application.plans import patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.plan_plugin_fixture import UnavailablePlanQueries
from tests.integration.agent.plan_plugin_support import (
    ScriptedPlanModel,
    edit_call,
    open_plan_agent,
    read_call,
    tool_outputs,
)
from tests.integration.agent.stream_support import consume


def test_saved_edit_task_survives_reopen_without_reapplying_or_rebasing(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    turn_id = uuid4()
    queries = SqlAlchemyPlanQueries(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, create_session_factory(pg_engine))
    model = ScriptedPlanModel(
        [
            [
                read_call("before"),
                edit_call("edit", "@@\n+原輪安排\n*** End of File"),
                read_call("after"),
            ],
            None,
        ]
    )

    async def run() -> None:
        for fail in (True, False):
            async with open_plan_agent(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(model),
                initialize=fail,
                extra_bundles=(
                    BundleConfig(
                        "tests.integration.agent.plan_plugin_fixture", {"fail": fail}
                    ),
                ),
            ) as agent:
                if fail:
                    with pytest.raises(
                        RuntimeError, match="synthetic post-edit outage"
                    ):
                        await consume(
                            agent.astream(
                                workspace_id=jd_workspace_id,
                                turn_id=turn_id,
                                input="原輪輸入",
                            )
                        )
                    assert queries.get_current(
                        workspace_id=jd_workspace_id
                    ) == PlanView(jd_workspace_id, 2, "原輪安排")
                    saved = await agent.aget_state(workspace_id=jd_workspace_id)
                    assert saved.next
                    assert saved.values["plan_turn_start_version"] == 1
                    assert saved.values["plan_version"] == 1
                    assert len(model.requests) == 1
                else:
                    await consume(
                        agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id)
                    )
                    saved = await agent.aget_state(workspace_id=jd_workspace_id)
                    assert not saved.next
                    assert saved.values["turn_id"] == turn_id
                    assert saved.values["plan_turn_start_version"] == 1
                    assert saved.values["plan_version"] == 3
            if fail:
                patch_plan(
                    workspace_id=jd_workspace_id,
                    expected_version=2,
                    diff="@@\n-原輪安排\n+故障期間的外部安排",
                    uow_factory=factory,
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    outputs = tool_outputs(model.requests[1])
    assert outputs["before"] == {"plan": None}
    assert outputs["edit"]["status"] == "updated"
    assert "+原輪安排" in outputs["edit"]["diff"]
    assert outputs["after"] == {"plan": "故障期間的外部安排"}
    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 3, "故障期間的外部安排"
    )


def test_query_failure_stops_tools_then_reopen_resumes_the_original_turn(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    turn_id = uuid4()
    queries = SqlAlchemyPlanQueries(pg_engine)
    model = ScriptedPlanModel(
        [
            [read_call("read"), edit_call("edit", "@@\n+恢復後安排\n*** End of File")],
            None,
        ]
    )

    async def run() -> None:
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            queries=UnavailablePlanQueries(),
        ) as agent:
            with pytest.raises(PlanQueryError, match="synthetic Plan query outage"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=turn_id, input="讀取安排"
                    )
                )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.next
            assert saved.values["plan_turn_start_version"] == 1
            assert saved.values["plan_version"] is None
            assert not any(
                isinstance(item, dict) and item.get("type") == "function_call_output"
                for item in saved.values["model_request"]["input"]
            )
            assert len(model.requests) == 1
            assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
                jd_workspace_id, 1, None
            )
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=False,
        ) as agent:
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert not saved.next
            assert saved.values["plan_turn_start_version"] == 1
            assert saved.values["plan_version"] == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[1])["read"] == {"plan": None}
    assert tool_outputs(model.requests[1])["edit"]["status"] == "updated"
    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 2, "恢復後安排"
    )


def test_unconfirmed_edit_commit_resumes_with_stale_rejection_without_reapplying(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turn_id = uuid4()
    queries = SqlAlchemyPlanQueries(pg_engine)
    native_commit = pg_engine.dialect.do_commit
    model = ScriptedPlanModel(
        [
            [read_call("before")],
            [edit_call("edit", "@@\n+僅修改一次\n*** End of File"), read_call("after")],
            None,
        ]
    )

    def lose_commit_reply(connection: PoolProxiedConnection) -> None:
        native_commit(connection)
        raise pg_errors.TransactionResolutionUnknown("synthetic lost commit reply")

    async def run() -> None:
        with monkeypatch.context() as injection:

            def respond(request: httpx2.Request) -> httpx2.Response:
                # 初始化與 read 已完成；只切斷實際 edit 提交的回覆。
                if len(model.requests) == 1:
                    injection.setattr(pg_engine.dialect, "do_commit", lose_commit_reply)
                return model(request)

            async with open_plan_agent(
                pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
            ) as agent:
                with pytest.raises(PlanPersistenceError) as failure:
                    await consume(
                        agent.astream(
                            workspace_id=jd_workspace_id,
                            turn_id=turn_id,
                            input="保存安排",
                        )
                    )
                assert failure.value.commit_status == "unknown"
                saved = await agent.aget_state(workspace_id=jd_workspace_id)
                assert saved.next
                assert saved.values["plan_version"] == 1
                assert saved.values["plan_turn_start_version"] == 1
                assert len(model.requests) == 2
        assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
            jd_workspace_id, 2, "僅修改一次"
        )
        async with open_plan_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=False,
        ) as agent:
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert not saved.next
            assert saved.values["plan_turn_start_version"] == 1
            assert saved.values["plan_version"] == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    outputs = tool_outputs(model.requests[2])
    assert outputs["edit"]["status"] == "rejected"
    assert outputs["edit"]["code"] == "target_stale"
    assert outputs["after"] == {"plan": "僅修改一次"}
    assert queries.get_current(workspace_id=jd_workspace_id) == PlanView(
        jd_workspace_id, 2, "僅修改一次"
    )
