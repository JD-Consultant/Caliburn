"""訪談 Context 已存進 PG Checkpoint 後，冷恢復沿已保存請求。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine, create_engine, text

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.interview.application.errors import InterviewQueryError
from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
)
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.interview_context_support import (
    ScriptedInterviewModel,
    context_messages,
    open_interview_agent,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import call, reasoning


class UnavailableInterviewQueries:
    """恢復時外部查詢不可用；仍應能沿已保存材料繼續。"""

    def list_messages(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID | None = None,
        after_message_id: UUID | None = None,
    ) -> tuple[TranscriptMessage, ...]:
        raise RuntimeError("Interview query unavailable after checkpoint")

    def get_message(self, *, workspace_id: UUID, message_id: UUID) -> MessageView:
        raise RuntimeError("Interview query unavailable after checkpoint")


def test_cold_resume_keeps_saved_context_when_new_sources_arrive_and_query_is_down(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="故障前已選原文",
        uow_factory=factory,
    )
    first = ScriptedInterviewModel([[reasoning(), call("probe", "probe", "{}")]])
    resumed = ScriptedInterviewModel([None])
    turn_id = uuid4()
    fixture = "tests.integration.agent.interview_context_fixture"

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(first),
            extra_bundles=(
                BundleConfig(fixture, {"preload": False, "fail_tool": True}),
            ),
        ) as agent:
            with pytest.raises(RuntimeError, match="synthetic context tool outage"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="故障中的本輪輸入",
                    )
                )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert (
                saved.values["model_request"]["input"][0]
                == first.requests[0]["input"][0]
            )
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            text="故障後新到原文",
            uow_factory=factory,
        )
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(resumed),
            initialize=False,
            queries=UnavailableInterviewQueries(),
            extra_bundles=(BundleConfig(fixture, {"preload": False}),),
        ) as agent:
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))
            state = await agent.aget_state(workspace_id=jd_workspace_id)
            assert state.values["model_response"].output_text == "Synthetic reply"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert context_messages(resumed.requests[0]) == context_messages(first.requests[0])
    items = resumed.requests[0]["input"]
    assert "故障後新到原文" not in str(items)
    assert str(items).count("故障中的本輪輸入") == 1
    assert next(
        item for item in items if item.get("type") == "function_call_output"
    ) == {"type": "function_call_output", "call_id": "probe", "output": "合成工具結果"}
    assert (
        next(item for item in items if item.get("type") == "reasoning")[
            "encrypted_content"
        ]
        == "synthetic-opaque-content"
    )


def test_query_failure_stops_before_model_without_pretending_history_is_empty(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    model = ScriptedInterviewModel([None])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            queries=UnavailableInterviewQueries(),
        ) as agent:
            with pytest.raises(RuntimeError, match="Interview query unavailable"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input="查詢失敗本輪",
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert model.requests == []


@pytest.mark.parametrize("database_failure", [False, True])
def test_context_query_releases_its_only_connection_after_success_or_database_error(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    database_failure: bool,
) -> None:
    query_url = pg_engine.url
    if database_failure:
        # 獨立讀取連線使用不存在的 schema，造成真 PG 查詢失敗；不修改任何表。
        query_url = query_url.update_query_dict(
            {"options": f"-csearch_path=context_missing_{uuid4().hex}"}
        )
    query_engine = create_engine(
        query_url, pool_size=1, max_overflow=0, pool_timeout=0.25, hide_parameters=True
    )
    model = ScriptedInterviewModel([None])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            recording=False,
            queries=SqlAlchemyInterviewQueries(query_engine),
        ) as agent:
            invocation = agent.astream(
                workspace_id=jd_workspace_id, turn_id=uuid4(), input="短查詢生命週期"
            )
            if database_failure:
                with pytest.raises(InterviewQueryError):
                    await consume(invocation)
            else:
                await consume(invocation)
            # Runtime 仍存活時即可重用唯一連線，排除把 Session 留在插件或 State。
            with query_engine.connect() as connection:
                assert connection.scalar(text("SELECT 1")) == 1

    try:
        asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    finally:
        query_engine.dispose()
    assert len(model.requests) == (0 if database_failure else 1)
