"""JD 旅程的公開組裝與合成材料；不替代 Host 接線或業務保存。"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from functools import partial
from typing import Any
from uuid import UUID

import httpx2
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command, StateSnapshot
from sqlalchemy import Engine

from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_HISTORY_QUERIES,
    JD_MEMORY_QUERIES,
    JD_PREVIOUS_COMPLETED,
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.job_description.application.duties import add_duty
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    NewDefinitionInput,
)
from caliburn.modules.job_description.application.tasks.lifecycle import add_task
from caliburn.modules.job_description.infrastructure.persistence import citation_sources
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, call, offline_client


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    """在公開工具 wrapper 注入提交後故障，不替代 JD 工具。"""

    async def lose_tool_result(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[str]]],
    ) -> ToolMessage | Command[str]:
        result = await execute(request)
        if request.tool_call["name"] == config.get("fail_after"):
            raise RuntimeError("synthetic JD post-commit result failure")
        return result

    return AgentBundle(
        (AgentPlugin("jd-journey-outage", wrap_tool_call=(lose_tool_result,)),)
    )


def prepare_jd(
    engine: Engine,
    workspace_id: UUID,
    *,
    initialized: JobDescriptionResult | None = None,
) -> JobDescriptionResult:
    """只用公開 JD 用例準備含 O/P、K/S 的輪前正式內容。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(engine)
    )
    current = (
        initialized
        if initialized is not None
        else create_job_description(workspace_id=workspace_id, uow_factory=factory)
    )
    current = add_duty(
        workspace_id=workspace_id,
        job_description_id=current.job_description_id,
        expected_version=current.version,
        name="交付",
        scope="交付範圍保持原文 task_999",
        uow_factory=factory,
    )
    current = add_task(
        workspace_id=workspace_id,
        input=AddTaskInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name="核對成果",
            description="核對交付內容與來源",
            duty_id=current.duties[0].id,
            outcomes=("交付核對清單", "異常紀錄"),
            requirements=("逐項確認",),
            knowledge=(NewDefinitionInput(name="交付規格", description="完整規格"),),
            skills=(NewDefinitionInput(name="異常判讀", description="完整判讀方法"),),
        ),
        uow_factory=factory,
    )
    return add_task(
        workspace_id=workspace_id,
        input=AddTaskInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name="待分類任務",
        ),
        uow_factory=factory,
    )


def read_call(
    call_id: str, view: str, read_ref: str | None = None
) -> dict[str, object]:
    arguments = {"view": view, **({"read_ref": read_ref} if read_ref else {})}
    return call("read_jd", call_id, json.dumps(arguments))


def tool_outputs(request: Mapping[str, Any]) -> dict[str, Any]:
    """在實際 OpenAI HTTP request 取得模型已收到的工具結果。"""
    return {
        item["call_id"]: json.loads(item["output"])
        for item in request["input"]
        if item.get("type") == "function_call_output"
    }


async def wait_for_idle(client: httpx2.AsyncClient, location: str) -> dict[str, Any]:
    async with asyncio.timeout(10):
        while True:
            response = await client.get(location)
            assert response.status_code == 200, response.text
            turn: dict[str, Any] = response.json()
            if turn["status"] != "running":
                return turn
            await asyncio.sleep(0.01)


@asynccontextmanager
async def open_jd_agent(
    engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    initialize: bool = True,
) -> AsyncIterator[Agent]:
    """明示 public open_agent 依賴；此入口不宣稱已驗 Host 的 JD 注入。"""
    sessions = create_session_factory(engine)
    queries = SqlAlchemyJobDescriptionQueries(engine)
    active_agent: Agent | None = None

    async def previous_completed(
        workspace_id: UUID, turn_id: UUID
    ) -> StateSnapshot | None:
        assert active_agent is not None
        return await active_agent.aget_previous_completed_turn(
            workspace_id=workspace_id, before_turn_id=turn_id
        )

    async with (
        open_postgres_checkpointer(checkpoint_conninfo, initialize=initialize) as saver,
        offline_client(transport) as client,
        open_agent(
            agent_id="jd-journey",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
            checkpointer=saver,
            external_services=(
                JD_QUERIES.bind(queries),
                JD_CITATION_SOURCES.bind(
                    citation_sources.SqlAlchemyCitationSourceQueries(engine)
                ),
                JD_HISTORY_QUERIES.bind(queries),
                JD_MEMORY_QUERIES.bind(SqlAlchemyMemoryQueries(engine)),
                JD_PREVIOUS_COMPLETED.bind(previous_completed),
                JD_UOW_FACTORY.bind(
                    partial(SqlAlchemyJobDescriptionUnitOfWork, sessions)
                ),
                JD_REFERENCES.bind(SqlAlchemyModelReferences(sessions)),
            ),
        ) as agent,
    ):
        active_agent = agent
        yield agent
