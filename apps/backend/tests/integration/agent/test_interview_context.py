"""正式訪談 Bundle 經真 PostgreSQL 後送給離線 SDK 的 Context。"""

import asyncio
import json
from functools import partial
from uuid import UUID, uuid4

import httpx2
from langgraph.types import Command
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.human_questions.questions import PendingQuestions
from caliburn.modules.interview.application.recording import (
    record_opening,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
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
from tests.integration.agent.http_support import api_client
from tests.integration.agent.interview_context_support import (
    ScriptedInterviewModel,
    context_messages,
    open_interview_agent,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import call, message, reasoning


def test_each_new_turn_preloads_ordered_history_without_repeating_current_input(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    record_opening(workspace_id=jd_workspace_id, text="正式開場", uow_factory=factory)
    model = ScriptedInterviewModel([[message(text="第一輪收尾")], None])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            for text in (" 第一輪員工原文\n", "第二輪目前輸入"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=uuid4(), input=text
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [item["text"] for item in context_messages(model.requests[0])] == [
        "正式開場"
    ]
    assert [item["text"] for item in context_messages(model.requests[1])] == [
        "正式開場",
        " 第一輪員工原文\n",
        "第一輪收尾",
    ]
    assert [item["speaker"] for item in context_messages(model.requests[1])] == [
        "app",
        "employee",
        "consultant",
    ]
    assert {"role": "user", "content": "第二輪目前輸入"} in model.requests[1]["input"]
    assert str(model.requests[1]["input"]).count("第二輪目前輸入") == 1
    assert [
        item.text
        for item in SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
    ] == [
        "正式開場",
        " 第一輪員工原文\n",
        "第一輪收尾",
        "第二輪目前輸入",
        "Synthetic reply",
    ]


def test_host_supplies_interview_query_dependency_for_new_turn_context(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    model = ScriptedInterviewModel([[message(text="Host 第一輪收尾")], None])

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            bundles=(BundleConfig("caliburn.bundles.interview"),),
        ) as client:
            for text in ("Host 第一輪原文", "Host 第二輪輸入"):
                response = await client.post(
                    f"/workspaces/{jd_workspace_id}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": text},
                )
                assert response.status_code == 202, response.text
                async with asyncio.timeout(10):
                    while True:
                        turn = (await client.get(response.headers["Location"])).json()
                        if turn["status"] != "running":
                            break
                        await asyncio.sleep(0.01)
                assert turn["status"] == "completed", turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [item["text"] for item in context_messages(model.requests[1])] == [
        "Host 第一輪原文",
        "Host 第一輪收尾",
    ]


def test_multiple_question_steps_keep_native_exchanges_without_reloading_transcript(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    record_opening(
        workspace_id=jd_workspace_id, text="問題前的開場", uow_factory=factory
    )
    model = ScriptedInterviewModel(
        [
            [
                reasoning(),
                call(
                    "ask_user_question",
                    "first",
                    json.dumps({"questions": [{"question": "第一題？"}]}),
                ),
            ],
            [
                call(
                    "ask_user_question",
                    "second",
                    json.dumps({"questions": [{"question": "第二題？"}]}),
                )
            ],
            None,
        ]
    )
    turn_id = uuid4()

    async def run() -> None:
        async with open_interview_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            extra_bundles=(BundleConfig("caliburn.bundles.human_questions"),),
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=turn_id, input="本輪唯一原文"
                )
            )
            for custom in (" 自填答案原文\n", None):
                state = await agent.aget_state(workspace_id=jd_workspace_id)
                assert len(state.interrupts) == 1
                pending = PendingQuestions.model_validate_json(
                    json.dumps(state.interrupts[0].value)
                )
                reply: dict[str, object] = {
                    "answers": [
                        {
                            "question_message_id": str(pending.questions[0].message_id),
                            "selected": [],
                            "custom": custom,
                        }
                    ]
                }
                await consume(
                    agent.aresume(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        resume_command=Command(resume={state.interrupts[0].id: reply}),
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 3
    for request in model.requests:
        assert [item["text"] for item in context_messages(request)] == ["問題前的開場"]
        assert str(request["input"]).count("本輪唯一原文") == 1
    final_items = model.requests[-1]["input"]
    assert [
        item["call_id"] for item in final_items if item.get("type") == "function_call"
    ] == ["first", "second"]
    outputs = [
        json.loads(item["output"])
        for item in final_items
        if item.get("type") == "function_call_output"
    ]
    assert outputs[0]["answers"][0]["custom"] == " 自填答案原文\n"
    assert outputs[1]["answers"][0]["selected"] == []
    assert (
        next(item for item in final_items if item.get("type") == "reasoning")[
            "encrypted_content"
        ]
        == "synthetic-opaque-content"
    )
    transcript = SqlAlchemyInterviewQueries(pg_engine).list_messages(
        workspace_id=jd_workspace_id
    )
    assert [item.text for item in transcript] == [
        "問題前的開場",
        "本輪唯一原文",
        "第一題？",
        "自填： 自填答案原文\n",
        "第二題？",
        "略過",
        "Synthetic reply",
    ]


def test_new_turn_excludes_withdrawn_sources_and_other_workspace_history(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    other_id = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="其他訪談")
        .workspace_id
    )
    withdrawn_turn = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=withdrawn_turn,
        text="稍後撤回的原文",
        uow_factory=factory,
    )
    record_turn_input(
        workspace_id=other_id,
        turn_id=uuid4(),
        text="其他 Workspace 原文",
        uow_factory=factory,
    )
    model = ScriptedInterviewModel([None, None, None])

    async def run() -> None:
        async with open_interview_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(model)
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="撤回前新輪"
                )
            )
            withdraw_turn(
                workspace_id=jd_workspace_id,
                turn_id=withdrawn_turn,
                uow_factory=factory,
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="撤回後新輪"
                )
            )
            await consume(
                agent.astream(
                    workspace_id=other_id, turn_id=uuid4(), input="其他 Workspace 本輪"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [item["text"] for item in context_messages(model.requests[0])] == [
        "稍後撤回的原文"
    ]
    assert [item["text"] for item in context_messages(model.requests[1])] == [
        "撤回前新輪",
        "Synthetic reply",
    ]
    assert [item["text"] for item in context_messages(model.requests[2])] == [
        "其他 Workspace 原文"
    ]
