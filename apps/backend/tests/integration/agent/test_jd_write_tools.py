"""六寫工具接正式 PG UoW／短碼；離線調用，不宣稱真模型品質。"""

import asyncio
from collections.abc import Collection
from functools import partial
from uuid import UUID, uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint
from langgraph.prebuilt import ToolRuntime
from sqlalchemy import Engine

from caliburn.bundles.job_description.services import (
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.bundles.job_description.write_tools import create_write_tools
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.model_references.contracts import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_support import factory, read_current
from tests.unit.bundles.job_description.test_write_tools import payload


def invoke(
    engine: Engine,
    state: JobDescriptionToolState,
    name: str,
    arguments: dict[str, object],
) -> object:
    tool = next(tool for tool in create_write_tools() if tool.name == name)
    runtime = ToolRuntime[AgentContext, JobDescriptionToolState](
        state=state,
        context=AgentContext(
            PluginServices(
                {
                    JD_QUERIES: SqlAlchemyJobDescriptionQueries(engine),
                    JD_REFERENCES: SqlAlchemyModelReferences(
                        create_session_factory(engine)
                    ),
                    JD_UOW_FACTORY: factory(engine),
                }
            )
        ),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="write",
        store=None,
    )

    @entrypoint()
    async def execute(value: bool) -> object:
        return await tool.ainvoke({**arguments, "runtime": runtime})

    return asyncio.run(execute.ainvoke(True))


def prepare(engine: Engine, workspace_id: UUID) -> JobDescriptionToolState:
    root = create_job_description(
        workspace_id=workspace_id, uow_factory=factory(engine)
    )
    return {
        "workspace_id": workspace_id,
        "turn_id": uuid4(),
        "jd_id": root.job_description_id,
        "jd_version": root.version,
    }


def test_full_task_and_sources_create_one_history_version(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    state = prepare(pg_engine, jd_workspace_id)
    assert state["jd_id"] is not None
    message = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=state["turn_id"],
        text="每天維修設備",
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    refs = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    source_target = ReferenceTarget("message", message.message_id)
    source_ref = refs.get_or_create_refs(jd_workspace_id, [source_target])[
        source_target
    ]
    result = invoke(
        pg_engine,
        state,
        "create_jd_task",
        {
            "name": "維修設備",
            "outcomes": [{"text": "運作設備"}],
            "requirements": [{"text": "安全完成"}],
            "required_knowledge": [{"kind": "new", "name": "機械原理"}],
            "required_skills": [{"kind": "new", "name": "異常診斷"}],
            "supporting_sources": [{"kind": "interview", "message_ref": source_ref}],
        },
    )
    output = payload(result)
    assert output["status"] == "created"
    saved = read_current(
        pg_engine, workspace_id=jd_workspace_id, job_description_id=state["jd_id"]
    )
    assert saved.version == 2
    assert (
        len(saved.tasks)
        == len(saved.knowledge)
        == len(saved.skills)
        == len(saved.citations)
        == 1
    )
    assert saved.citations[0].target_id == saved.tasks[0].id
    assert saved.tasks[0].knowledge_ids == (saved.knowledge[0].id,)
    assert saved.tasks[0].skill_ids == (saved.skills[0].id,)
    history = SqlAlchemyJobDescriptionQueries(pg_engine).list_history(
        workspace_id=jd_workspace_id,
        job_description_id=state["jd_id"],
        correlation_id=str(state["turn_id"]),
    )
    assert [entry.version for entry in history.items] == [2]
    assert refs.resolve_refs(jd_workspace_id, [output["read_ref"]])[
        output["read_ref"]
    ] == ReferenceTarget("task", saved.tasks[0].id)


def test_withdrawn_source_rolls_back_task_details_new_definitions_and_history(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    state = prepare(pg_engine, jd_workspace_id)
    assert state["jd_id"] is not None
    message = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="已撤回資料",
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    refs = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    target = ReferenceTarget("message", message.message_id)
    source_ref = refs.get_or_create_refs(jd_workspace_id, [target])[target]
    withdraw_turn(
        workspace_id=jd_workspace_id,
        turn_id=message.turn_id,
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    result = invoke(
        pg_engine,
        state,
        "create_jd_task",
        {
            "name": "不應保存",
            "outcomes": [{"text": "成果"}],
            "required_skills": [{"kind": "new", "name": "技能"}],
            "supporting_sources": [{"kind": "interview", "message_ref": source_ref}],
        },
    )
    assert payload(result)["code"] == "source_not_available"
    saved = read_current(
        pg_engine, workspace_id=jd_workspace_id, job_description_id=state["jd_id"]
    )
    assert (saved.version, saved.tasks, saved.skills, saved.citations) == (
        1,
        (),
        (),
        (),
    )


def test_stale_model_cannot_overwrite_first_successful_tool(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    state = prepare(pg_engine, jd_workspace_id)
    first = invoke(
        pg_engine, state, "create_jd_item", {"item": {"kind": "duty", "name": "原職責"}}
    )
    second = invoke(
        pg_engine,
        state,
        "create_jd_item",
        {"item": {"kind": "duty", "name": "衝突職責"}},
    )
    assert payload(first)["status"] == "created"
    assert payload(second)["code"] == "target_stale"
    assert state["jd_id"] is not None
    saved = read_current(
        pg_engine, workspace_id=jd_workspace_id, job_description_id=state["jd_id"]
    )
    assert [item.name for item in saved.duties] == ["原職責"]
    assert saved.version == 2


def test_committed_write_recovers_after_mapping_failure_with_reopened_pg_saver(
    pg_engine: Engine, jd_workspace_id: UUID, checkpoint_conninfo: str
) -> None:
    state = prepare(pg_engine, jd_workspace_id)
    assert state["jd_id"] is not None
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))

    class UnavailableMapping:
        def get_or_create_refs(
            self, workspace_id: UUID, targets: Collection[ReferenceTarget]
        ) -> dict[ReferenceTarget, str]:
            raise RuntimeError("mapping unavailable after commit")

        def resolve_refs(
            self, workspace_id: UUID, refs: Collection[str]
        ) -> dict[str, ReferenceTarget]:
            return references.resolve_refs(workspace_id, refs)

    async def run(*, first: bool) -> object:
        runtime = ToolRuntime[AgentContext, JobDescriptionToolState](
            state=state,
            context=AgentContext(
                PluginServices(
                    {
                        JD_QUERIES: SqlAlchemyJobDescriptionQueries(pg_engine),
                        JD_REFERENCES: UnavailableMapping() if first else references,
                        JD_UOW_FACTORY: factory(pg_engine),
                    }
                )
            ),
            config={},
            stream_writer=lambda value: None,
            tool_call_id="write",
            store=None,
        )
        tool = next(
            tool for tool in create_write_tools() if tool.name == "create_jd_item"
        )
        async with open_postgres_checkpointer(
            checkpoint_conninfo, initialize=first
        ) as saver:

            @entrypoint(checkpointer=saver)
            async def execute(value: bool) -> object:
                return await tool.ainvoke(
                    {"item": {"kind": "duty", "name": "唯一職責"}, "runtime": runtime}
                )

            config: RunnableConfig = {
                "configurable": {"thread_id": "jd-write-recovery"}
            }
            return await execute.ainvoke(
                True if first else None, config=config, durability="sync"
            )

    with pytest.raises(RuntimeError, match="mapping unavailable"):
        asyncio.run(run(first=True), loop_factory=asyncio.SelectorEventLoop)
    before = read_current(
        pg_engine, workspace_id=jd_workspace_id, job_description_id=state["jd_id"]
    )
    assert before.version == 2
    output = payload(
        asyncio.run(run(first=False), loop_factory=asyncio.SelectorEventLoop)
    )
    after = read_current(
        pg_engine, workspace_id=jd_workspace_id, job_description_id=state["jd_id"]
    )
    assert output["status"] == "created"
    assert after == before
    assert len(after.duties) == 1
