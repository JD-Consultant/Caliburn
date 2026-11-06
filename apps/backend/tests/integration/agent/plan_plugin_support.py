"""Plan 公開 Agent 測試的真資料庫接線與離線模型材料。"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import httpx2
from sqlalchemy import Engine

from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle
from caliburn.modules.plan.application.queries import PlanQueries
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def read_call(call_id: str) -> dict[str, object]:
    return call("read_interview_plan", call_id=call_id, arguments="{}")


def edit_call(call_id: str, diff: str) -> dict[str, object]:
    return call(
        "edit_interview_plan", call_id=call_id, arguments=json.dumps({"diff": diff})
    )


@dataclass
class ScriptedPlanModel:
    batches: list[list[dict[str, object]] | None]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request_body(request))
        output = self.batches[len(self.requests) - 1]
        return sse_response(EventStream(response_events(response_payload(output))))


def tool_outputs(request: dict[str, Any]) -> dict[str, Any]:
    """只在實際模型 HTTP 邊界解析工具 JSON。"""
    return {
        item["call_id"]: json.loads(item["output"])
        for item in request["input"]
        if item.get("type") == "function_call_output"
    }


@asynccontextmanager
async def open_plan_agent(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    initialize: bool = True,
    queries: PlanQueries | None = None,
    plan_plugins: tuple[str, ...] | None = None,
    extra_bundles: tuple[BundleConfig | AgentBundle, ...] = (),
) -> AsyncIterator[Agent]:
    sessions = create_session_factory(pg_engine)
    async with (
        open_postgres_checkpointer(checkpoint_conninfo, initialize=initialize) as saver,
        offline_client(transport) as client,
        open_agent(
            agent_id="plan-integration",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig("caliburn.bundles.plan", plugins=plan_plugins),
                *extra_bundles,
            ),
            checkpointer=saver,
            external_services=(
                PLAN_QUERIES.bind(queries or SqlAlchemyPlanQueries(pg_engine)),
                PLAN_UOW_FACTORY.bind(partial(SqlAlchemyPlanUnitOfWork, sessions)),
            ),
        ) as agent,
    ):
        yield agent
