"""Memory 完成邊界包含當輪完整正式問答，並固定分析的來源窗口。"""

import asyncio
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.bundles.memory.completion import InvalidMemoryCompletion
from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_questions,
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
from caliburn.modules.memory.domain.items import WorkSituation, WorkUnderstanding
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.memory_completion_support import (
    COMPLETION_SHAPES,
    CompletionShape,
    completion_messages,
)
from tests.integration.agent.memory_reference_support import (
    interview_material,
    interview_ref,
)
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
    tool,
)


@pytest.mark.parametrize("completion_shape", COMPLETION_SHAPES)
def test_completed_request_includes_later_questions_answers_skips_and_final(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    completion_shape: CompletionShape,
) -> None:
    sessions = create_session_factory(pg_engine)
    interview = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    turn_id = uuid4()
    answer_ids: list[UUID] = []

    def finish_dialogue(_: dict[str, Any]) -> list[dict[str, object]]:
        questions = record_questions(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            questions=(
                Question(question="差異如何複核？"),
                Question(question="還有其他補充嗎？"),
            ),
            uow_factory=interview,
        )
        answers = record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=(
                AnswerInput(
                    question_message_id=questions[0].message_id,
                    custom="逐筆核對後交由主管複核。",
                ),
                AnswerInput(question_message_id=questions[1].message_id),
            ),
            uow_factory=interview,
        )
        answer_ids.extend(answer.message_id for answer in answers)
        return completion_messages(completion_shape, "已確認盤點及主管複核的分工。")

    def create_situation(request: dict[str, Any]) -> list[dict[str, object]]:
        material = interview_material(request)
        assert [(item["kind"], item["text"]) for item in material["messages"]] == [
            ("text", "我負責庫存盤點。"),
            ("question", "差異如何複核？"),
            ("question", "還有其他補充嗎？"),
            ("answer", "自填：逐筆核對後交由主管複核。"),
            ("answer", "略過"),
            ("text", "已確認盤點及主管複核的分工。"),
        ]
        return [
            tool(
                "create_work_situation",
                "situation",
                title="盤點複核",
                description="本人核對、主管複核",
                body="逐筆核對後交由主管複核；其他補充明確略過。",
                interview_references=[
                    interview_ref(request, "自填：逐筆核對後交由主管複核。"),
                    interview_ref(request, "略過"),
                ],
            )
        ]

    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "request")],
            finish_dialogue,
            None,
            complete("後輪採購作業已完成。"),
            create_situation,
            complete(),
            [
                tool(
                    "create_work_understanding",
                    "understanding",
                    title="盤點分工",
                    description="複核責任分離",
                    body="本人逐筆核對，主管負責複核。",
                    work_situation_references=["盤點複核"],
                )
            ],
            complete(),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input="我負責庫存盤點。",
                )
            )
            transcript = SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id
            )
            with pytest.raises(ModelResponseError):
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
            analysis = memory.get_current(workspace_id=jd_workspace_id).analysis
            assert analysis is not None
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=uuid4(),
                    input="後輪新增採購作業。",
                )
            )
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, initialize=False
        ) as (_, coordinator, memory):
            assert memory.get_current(workspace_id=jd_workspace_id).analysis == analysis
            fixed_sources = memory.list_analysis_sources(
                workspace_id=jd_workspace_id, analysis_id=analysis.analysis_id
            )
            assert [(source.message_id, source.text) for source in fixed_sources] == [
                (message.message_id, message.text) for message in transcript
            ]
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=turn_id
            )
            assert published is not None
            assert published.covered_through_message_id == transcript[-1].message_id
            situation = next(
                item for item in published.items if isinstance(item, WorkSituation)
            )
            understanding = next(
                item for item in published.items if isinstance(item, WorkUnderstanding)
            )
            assert set(situation.interview_message_ids) == set(answer_ids)
            assert understanding.situation_ids == (situation.id,)
            references = SqlAlchemyModelReferences(sessions)
            answer_ref = interview_ref(
                model.requests[4], "自填：逐筆核對後交由主管複核。"
            )
            skipped_ref = interview_ref(model.requests[4], "略過")
            assert references.resolve_refs(
                jd_workspace_id, [answer_ref, skipped_ref]
            ) == {
                answer_ref: ReferenceTarget("message", answer_ids[0]),
                skipped_ref: ReferenceTarget("message", answer_ids[1]),
            }
            assert (
                memory.get_published(
                    workspace_id=jd_workspace_id, published_version=published.version
                )
                == published
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("role", ["situation", "understanding"])
@pytest.mark.parametrize("completion_shape", ["refusal", "multiple_finals"])
def test_analyst_nontext_or_multiple_final_cannot_publish(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    role: str,
    completion_shape: CompletionShape,
) -> None:
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "request")],
            complete("顧問已完成。"),
            *([complete()] if role == "understanding" else []),
            completion_messages(completion_shape, '{"status":"complete"}'),
        ]
    )
    turn_id = uuid4()

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input="每日核對庫存。",
                )
            )
            with pytest.raises(InvalidMemoryCompletion):
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
            current = memory.get_current(workspace_id=jd_workspace_id)
            assert current.analysis is None
            assert current.published_version is None
            assert current.failure is not None
            assert current.failure.reason == "invalid_completion"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("cancelled", [False, True], ids=["pending", "cancelled"])
def test_uncompleted_request_does_not_start_memory_analysis(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    cancelled: bool,
) -> None:
    model = OfflineMemoryModel(
        [[tool("request_memory_consolidation", "request")], None]
    )
    turn_id = uuid4()

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=turn_id,
                        input="這輪尚未成功完成。",
                    )
                )
            if cancelled:
                await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=turn_id)
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
                is None
            )
            current = memory.get_current(workspace_id=jd_workspace_id)
            assert current.analysis is None
            assert current.published_version is None
            assert len(model.requests) == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_started_analysis_retains_window_after_later_turn_completes(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    first_turn, later_turn = uuid4(), uuid4()

    def continue_situation(request: dict[str, Any]) -> list[dict[str, object]]:
        material = interview_material(request)
        assert material == interview_material(model.requests[2])
        assert [item["text"] for item in material["messages"]] == [
            "每日核對庫存。",
            "已了解每日盤點。",
        ]
        return [
            tool(
                "create_work_situation",
                "situation",
                title="固定的盤點情境",
                description="首輪已完成訪談",
                body="每日核對庫存。",
                interview_references=[interview_ref(request, "每日核對庫存。")],
            )
        ]

    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "first-request")],
            complete("已了解每日盤點。"),
            None,
            [tool("request_memory_consolidation", "later-request")],
            complete("後一輪的採購作業已完成。"),
            continue_situation,
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
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=first_turn,
                    input="每日核對庫存。",
                )
            )
            original_messages = SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id
            )
            with pytest.raises(ModelResponseError):
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=first_turn)
            analysis = memory.get_current(workspace_id=jd_workspace_id).analysis
            assert analysis is not None and analysis.phase == "situation"
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=later_turn,
                    input="後一輪才新增採購作業。",
                )
            )
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, initialize=False
        ) as (_, coordinator, memory):
            assert memory.get_current(workspace_id=jd_workspace_id).analysis == analysis
            assert {
                message.message_id
                for message in memory.list_analysis_sources(
                    workspace_id=jd_workspace_id, analysis_id=analysis.analysis_id
                )
            } == {message.message_id for message in original_messages}
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=first_turn
            )
            assert published is not None
            assert (
                published.covered_through_message_id == original_messages[-1].message_id
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
