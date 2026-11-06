"""訪談取消沿可信 Workspace／Turn 撤回原話與問答，可無 State 重試。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.interview.application.errors import InterviewMessageNotFoundError
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.interview_context_support import (
    ScriptedInterviewModel,
    context_messages,
    open_interview_agent,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import call


def test_cancel_withdraws_target_dialogue_and_answers_using_trusted_identity(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    other_workspace = WorkspaceService(
        partial(SqlAlchemyWorkspaceUnitOfWork, sessions)
    ).create(interviewee_name="其他合成訪談")
    turn_id, other_turn_id = uuid4(), uuid4()
    employee = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="本輪原話",
        uow_factory=factory,
    )
    (question,) = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="本輪問題"),),
        uow_factory=factory,
    )
    record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=(AnswerInput(question_message_id=question.message_id, custom="原話"),),
        uow_factory=factory,
    )
    following = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=other_turn_id,
        text="保留另一輪",
        uow_factory=factory,
    )
    other = record_turn_input(
        workspace_id=other_workspace.workspace_id,
        turn_id=turn_id,
        text="保留另一份 Workspace",
        uow_factory=factory,
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    context = AgentContext(PluginServices({INTERVIEW_UOW_FACTORY: factory}))
    (plugin,) = load_plugins(
        (BundleConfig("caliburn.bundles.interview", plugins=("interview",)),)
    )
    callback = plugin.on_turn_cancel
    assert callback is not None

    async def run() -> None:
        for state in (
            {"workspace_id": other_workspace.workspace_id, "turn_id": other_turn_id},
            None,
        ):
            await callback(
                state,
                workspace_id=jd_workspace_id,
                turn_id=turn_id,
                context=context,
            )
            assert [
                item.message_id
                for item in queries.list_messages(workspace_id=jd_workspace_id)
            ] == [following.message_id]
            assert [
                item.message_id
                for item in queries.list_messages(
                    workspace_id=other_workspace.workspace_id
                )
            ] == [other.message_id]
            with pytest.raises(InterviewMessageNotFoundError):
                queries.get_message(
                    workspace_id=jd_workspace_id, message_id=employee.message_id
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_agent_cancel_withdraws_recorded_input_before_next_turn_reloads_context(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="保留的既有原話",
        uow_factory=factory,
    )
    model = ScriptedInterviewModel([[call("probe", "old_tool", "{}")], None])
    turn_id, next_turn_id = uuid4(), uuid4()
    fixture = "tests.integration.agent.interview_context_fixture"
    queries = SqlAlchemyInterviewQueries(pg_engine)

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            extra_bundles=(
                BundleConfig(fixture, {"preload": False, "fail_tool": True}),
            ),
        ) as agent:
            with pytest.raises(RuntimeError, match="synthetic context tool outage"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="將取消的本輪原話",
                    )
                )
            assert [
                item.text
                for item in queries.list_messages(
                    workspace_id=jd_workspace_id, turn_id=turn_id
                )
            ] == ["將取消的本輪原話"]
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=turn_id)
            assert (
                queries.list_messages(workspace_id=jd_workspace_id, turn_id=turn_id)
                == ()
            )
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=False,
            extra_bundles=(BundleConfig(fixture, {"preload": False}),),
        ) as agent:
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=turn_id)
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=next_turn_id,
                    input="下一輪新輸入",
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [item["text"] for item in context_messages(model.requests[1])] == [
        "保留的既有原話"
    ]
    assert (
        sum(
            item == {"role": "user", "content": "下一輪新輸入"}
            for item in model.requests[1]["input"]
        )
        == 1
    )
    assert "將取消的本輪原話" not in str(model.requests[1]["input"])
    assert "old_tool" not in str(model.requests[1]["input"])
    assert [
        item.text
        for item in queries.list_messages(
            workspace_id=jd_workspace_id, turn_id=next_turn_id
        )
    ] == ["下一輪新輸入", "Synthetic reply"]
