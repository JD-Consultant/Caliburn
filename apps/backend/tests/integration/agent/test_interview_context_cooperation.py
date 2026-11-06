"""Memory 範圍及壓縮／換窗替身只沿公開來源函式和原生 PluginStep 合作。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.interview.context import InterviewContextSelectionError
from caliburn.modules.agent.bootstrap import BundleConfig
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
from tests.unit.modules.agent.offline_openai import call, message, reasoning

FIXTURE = "tests.integration.agent.interview_context_fixture"


def test_memory_roles_select_their_own_scope_and_answer_adds_only_its_question(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="未指定的原話",
        uow_factory=factory,
    )
    question, unanswered = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(
            Question(question="答案所需原題？"),
            Question(question="未答而未選的問題？"),
        ),
        uow_factory=factory,
    )
    (answer,) = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=(
            AnswerInput(question_message_id=question.message_id, custom="指定答案"),
        ),
        uow_factory=factory,
    )
    queries = SqlAlchemyInterviewQueries(pg_engine)
    before = queries.list_messages(workspace_id=jd_workspace_id)
    model = ScriptedInterviewModel([None, None, None])

    async def run() -> None:
        for role, selection in (
            ("B1", (answer.message_id,)),
            ("B2", ()),
            ("other-analysis", (unanswered.message_id,)),
        ):
            async with open_interview_agent(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(model),
                agent_id=role,
                context=False,
                recording=False,
                extra_bundles=(BundleConfig(FIXTURE, {"selection": selection}),),
            ) as agent:
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input=f"{role}本輪",
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    first = context_messages(model.requests[0])
    assert [item["text"] for item in first] == ["答案所需原題？", "自填：指定答案"]
    assert [item["supporting_question"] for item in first] == [True, False]
    assert first[1]["reply_to"] == first[0]["ref"]
    assert context_messages(model.requests[1]) == []
    assert [item["text"] for item in context_messages(model.requests[2])] == [
        "未答而未選的問題？"
    ]
    assert queries.list_messages(workspace_id=jd_workspace_id) == before
    assert all(
        str(jd_workspace_id) not in str(request["input"]) for request in model.requests
    )


@pytest.mark.parametrize("mode", ["compact", "window"])
def test_context_replacement_preserves_native_turn_and_does_not_resurrect_old_history(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID, mode: str
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    old = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="被替換的舊原話",
        uow_factory=factory,
    )
    new = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=uuid4(),
        text="換窗指定的原話",
        uow_factory=factory,
    )
    model = ScriptedInterviewModel(
        [
            [reasoning(), call("probe", "probe", "{}")],
            [message("commentary", "仍在同輪繼續")],
            None,
        ]
    )

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            context=False,
            extra_bundles=(
                BundleConfig(
                    FIXTURE,
                    {
                        "mode": mode,
                        "selection": (old.message_id,),
                        "window_selection": (new.message_id,),
                    },
                ),
            ),
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="本輪保留原文"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [item["text"] for item in context_messages(model.requests[0])] == [
        "被替換的舊原話"
    ]
    for request in model.requests[1:]:
        items = request["input"]
        assert "被替換的舊原話" not in str(items)
        assert str(items).count("本輪保留原文") == 1
        assert [
            item["call_id"] for item in items if item.get("type") == "function_call"
        ] == ["probe"]
        assert [
            item["call_id"]
            for item in items
            if item.get("type") == "function_call_output"
        ] == ["probe"]
        assert (
            next(item for item in items if item.get("type") == "reasoning")[
                "encrypted_content"
            ]
            == "synthetic-opaque-content"
        )
        if mode == "compact":
            assert context_messages(request) == []
            assert items[0] == {"role": "user", "content": "合成壓縮摘要"}
        else:
            assert [item["text"] for item in context_messages(request)] == [
                "換窗指定的原話"
            ]


@pytest.mark.parametrize("kind", ["input", "question", "answer"])
def test_window_rejects_current_turn_input_question_or_answer(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID, kind: str
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    turn_id = uuid4()
    current = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        text="本輪原話",
        uow_factory=factory,
    )
    (question,) = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="本輪問題？"),),
        uow_factory=factory,
    )
    (answer,) = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=(
            AnswerInput(question_message_id=question.message_id, custom="本輪答案"),
        ),
        uow_factory=factory,
    )
    selected = {"input": current, "question": question, "answer": answer}[kind]
    model = ScriptedInterviewModel([[call("probe", "probe", "{}")]])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            context=False,
            extra_bundles=(
                BundleConfig(
                    FIXTURE,
                    {
                        "mode": "window",
                        "selection": (),
                        "window_selection": (selected.message_id,),
                    },
                ),
            ),
        ) as agent:
            with pytest.raises(InterviewContextSelectionError) as caught:
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=turn_id, input="本輪原話"
                    )
                )
            assert caught.value.reason == "current_turn"
            assert caught.value.message_id == selected.message_id

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 1


def test_explicit_selection_cannot_read_a_message_from_another_workspace(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    other = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="來源界線")
        .workspace_id
    )
    source = record_turn_input(
        workspace_id=other,
        turn_id=uuid4(),
        text="不可跨範圍讀取",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    model = ScriptedInterviewModel([None])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            context=False,
            extra_bundles=(BundleConfig(FIXTURE, {"selection": (source.message_id,)}),),
        ) as agent:
            with pytest.raises(InterviewContextSelectionError) as caught:
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input="只讀本 Workspace",
                    )
                )
            assert caught.value.reason == "unavailable"
            assert caught.value.message_id == source.message_id

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert model.requests == []
