"""公開 Memory Bundle 的共同訪談 ref 與即時／固定來源範圍。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.interview.application.recording import (
    record_answers,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.memory.domain.errors import InvalidMemorySourceError
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.memory_reference_support import interview_ref
from tests.integration.agent.plan_plugin_support import tool_outputs
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
    tool,
)
from tests.unit.modules.agent.offline_openai import message


@pytest.mark.parametrize("context_window", [False, True])
def test_consultant_reads_question_and_answer_saved_after_memory_initialization(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    context_window: bool,
) -> None:
    turn_id = uuid4()
    employee_input = "我負責逐筆核對庫存。"
    question_text = "核對後如何處理？\n請說明交接對象。"
    answer_text = "先逐筆列出差異。\n再交給主管複核。"
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    refs: dict[str, str] = {}

    def save_then_read(_request: dict[str, Any]) -> list[dict[str, object]]:
        navigation = [
            json.loads(item["content"])
            for item in _request["input"]
            if item.get("role") == "user"
            and '"interview_navigation"' in item.get("content", "")
        ]
        assert len(navigation) == 1
        assert navigation[0]["first_ref"] == navigation[0]["last_ref"]
        assert navigation[0]["first_ref"].startswith("message_")
        (question,) = record_questions(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            questions=(Question(question=question_text),),
            uow_factory=factory,
        )
        (answer,) = record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=(
                AnswerInput(
                    question_message_id=question.message_id, custom=answer_text
                ),
            ),
            uow_factory=factory,
        )
        question_target = ReferenceTarget("message", question.message_id)
        answer_target = ReferenceTarget("message", answer.message_id)
        saved_refs = references.get_or_create_refs(
            jd_workspace_id, [question_target, answer_target]
        )
        refs["question"] = saved_refs[question_target]
        refs["answer"] = saved_refs[answer_target]
        return [
            tool(
                "read_interview",
                "new-question-answer",
                query={
                    "kind": "messages",
                    "refs": [refs["answer"], refs["question"], refs["answer"]],
                },
            )
        ]

    model = OfflineMemoryModel([save_then_read, [message(text="已核對本輪題答。")]])

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=context_window
        ) as (
            agent,
            _,
            memory,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input=employee_input,
                )
            )
            assert memory.get_current(workspace_id=jd_workspace_id).items == ()

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 2
    assert sum(t["name"] == "read_interview" for t in model.requests[0]["tools"]) == 1
    assert tool_outputs(model.requests[1])["new-question-answer"]["messages"] == [
        {
            "ref": refs["question"],
            "speaker": "consultant",
            "kind": "question",
            "text": question_text,
            "reply_to": None,
        },
        {
            "ref": refs["answer"],
            "speaker": "employee",
            "kind": "answer",
            "text": f"自填：{answer_text}",
            "reply_to": refs["question"],
        },
    ]


def test_analyst_rejects_valid_selection_after_another_frozen_source_is_withdrawn(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    old_turn, current_turn = uuid4(), uuid4()
    old_text = "先前已說明由我逐筆核對。"
    current_text = "本次補充差異交給主管。"
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))

    def withdraw_then_read(request: dict[str, Any]) -> list[dict[str, object]]:
        old_ref = interview_ref(request, old_text)
        current_ref = interview_ref(request, current_text)
        assert old_ref != current_ref
        withdraw_turn(
            workspace_id=jd_workspace_id,
            turn_id=old_turn,
            uow_factory=factory,
        )
        return [
            tool(
                "read_interview",
                "remaining-valid-source",
                query={"kind": "messages", "refs": [current_ref]},
            )
        ]

    model = OfflineMemoryModel(
        [
            [message(text="已收到先前做法。")],
            [tool("request_memory_consolidation", "consolidate")],
            [message(text="已收到本次補充。")],
            withdraw_then_read,
            complete(),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            for turn_id, text in ((old_turn, old_text), (current_turn, current_text)):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=turn_id, input=text
                    )
                )
            with pytest.raises(InvalidMemorySourceError):
                await coordinator.run(
                    workspace_id=jd_workspace_id, turn_id=current_turn
                )
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.analysis is None
            assert root.items == ()
            assert root.published_version is None
            assert root.failure is not None
            assert root.failure.reason == "invalid_source_window"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 5
    result = tool_outputs(model.requests[4])["remaining-valid-source"]
    assert result["status"] == "rejected"
    assert result["code"] == "scope_not_allowed"
    assert "messages" not in result
    assert old_text not in str(result)
    assert current_text not in str(result)


def test_analyst_rejects_wrong_kind_foreign_workspace_and_uuid_references(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    foreign_workspace = (
        WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, sessions))
        .create(interviewee_name="另一份合成訪談")
        .workspace_id
    )
    foreign_message = record_turn_input(
        workspace_id=foreign_workspace,
        turn_id=uuid4(),
        text="其他工作檔案的原話不得引用。",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    foreign_target = ReferenceTarget("message", foreign_message.message_id)
    foreign_ref = references.get_or_create_refs(foreign_workspace, [foreign_target])[
        foreign_target
    ]
    employee_input = "我核對庫存差異。"

    def rejected_creates(request: dict[str, Any]) -> list[dict[str, object]]:
        source_ref = interview_ref(request, employee_input)
        source = references.resolve_refs(jd_workspace_id, [source_ref])[source_ref]
        wrong_kind = ReferenceTarget("task", source.resource_id)
        wrong_kind_ref = references.get_or_create_refs(jd_workspace_id, [wrong_kind])[
            wrong_kind
        ]
        return [
            tool(
                "create_work_situation",
                call_id,
                title=call_id,
                description="不應保存",
                body="來源不合法的情境正文。",
                interview_references=[invalid_ref],
            )
            for call_id, invalid_ref in (
                ("wrong-kind", wrong_kind_ref),
                ("foreign-workspace", foreign_ref),
                ("uuid-shortcut", str(source.resource_id)),
            )
        ]

    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "consolidate")],
            [message(text="已收到庫存說明。")],
            rejected_creates,
            complete(),
            complete(),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            turn_id = uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input=employee_input,
                )
            )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=turn_id
            )
            assert published is not None
            assert published.items == ()
            assert memory.get_current(workspace_id=jd_workspace_id).items == ()

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    results = tool_outputs(model.requests[3])
    for call_id, code in (
        ("wrong-kind", "invalid_arguments"),
        ("foreign-workspace", "source_not_available"),
        ("uuid-shortcut", "invalid_arguments"),
    ):
        assert results[call_id]["status"] == "rejected"
        assert results[call_id]["code"] == code
