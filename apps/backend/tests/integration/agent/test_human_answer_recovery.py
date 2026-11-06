"""故障後仍只接受原提問答案，不以舊 Checkpoint 提前回受理。"""

import asyncio
import json
from collections.abc import Collection
from uuid import UUID, uuid4

import httpx2
import pytest
from psycopg import AsyncConnection, sql
from psycopg.conninfo import make_conninfo
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.human_questions.questions import SavedQuestion
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_agent_http_admission import wait_for_database_lock
from tests.integration.agent.test_human_answers_http import (
    BUNDLES,
    QUESTIONS,
    assert_model_answers,
    read_answers,
    read_transcript,
    settled,
    start_question,
)
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("when", ["before", "after"])
def test_tool_failure_can_resume_without_replacing_a_saved_answer(
    pg_engine: Engine, checkpoint_conninfo: str, when: str
) -> None:
    """已消費答案沿原答案恢復；提問前失敗則重新確認等待後才接受答案。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        bundles = (
            *BUNDLES,
            BundleConfig(
                "tests.integration.agent.human_question_fixture", {"when": when}
            ),
        )
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "故障測試"})
            ).json()["workspace_id"]
            response = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "合成問題"},
            )
            assert response.status_code == 202
            location = response.headers["Location"]
            turn = await settled(client, location)
            if when == "after":
                assert turn["status"] == "waiting_for_input"
                answers = await read_answers(client, location)
                response = await client.post(location + "/answers", json=answers)
                assert response.status_code == 503, response.text
                assert (
                    await client.post(location + "/answers", json=answers)
                ).status_code == 409
            else:
                assert turn["status"] == "interrupted"
            assert (await client.post(location + "/resume")).status_code == 202
            turn = await settled(client, location)
            if when == "before":
                assert turn["status"] == "waiting_for_input"
                answers = await read_answers(client, location)
                assert (await client.post(location + "/resume")).status_code == 409
                response = await client.post(location + "/answers", json=answers)
                assert response.status_code == 202, response.text
                turn = await settled(client, location)
            assert turn["status"] == "completed"
            tool = (await client.get(location + "/steps")).json()[0]["tool_calls"][0]
            assert_model_answers(
                json.loads(tool["output"]),
                answers,
                await read_transcript(client, location),
                pg_engine,
                location,
            )
            assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("failed_kind", ["question", "answer"])
def test_reference_failure_recovers_saved_message_ids_after_reopening(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    failed_kind: str,
) -> None:
    """定位交易故障時，沿已保存 task 回傳恢復，題答都不產生新 UUID。"""
    original = SqlAlchemyModelReferences.get_or_create_refs
    failed = False
    committed_refs: dict[ReferenceTarget, str] = {}

    def fail_reference_transaction_once(
        references: SqlAlchemyModelReferences,
        workspace_id: UUID,
        targets: Collection[ReferenceTarget],
    ) -> dict[ReferenceTarget, str]:
        nonlocal failed
        messages = SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=workspace_id
        )
        target_ids = {target.resource_id for target in targets}
        if not failed and any(
            message.kind == failed_kind and message.message_id in target_ids
            for message in messages
        ):
            failed = True
            committed_refs.update(original(references, workspace_id, targets))
            raise RuntimeError("短碼已提交，合成故障阻止工具收到配置結果")
        return original(references, workspace_id, targets)

    monkeypatch.setattr(
        SqlAlchemyModelReferences,
        "get_or_create_refs",
        fail_reference_transaction_once,
    )

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "定位故障"})
            ).json()["workspace_id"]
            response = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "合成輸入"},
            )
            assert response.status_code == 202, response.text
            location = response.headers["Location"]
            turn = await settled(client, location)
            if failed_kind == "answer":
                assert turn["status"] == "waiting_for_input"
                answers = await read_answers(client, location)
                response = await client.post(location + "/answers", json=answers)
                assert response.status_code == 503, response.text
                turn = await settled(client, location)
                assert (
                    await client.post(location + "/answers", json=answers)
                ).status_code == 409
            assert failed
            assert turn["status"] == "interrupted"
            before = await read_transcript(client, location)
            original_questions = [m for m in before if m["kind"] == "question"]
            original_answers = [m for m in before if m["kind"] == "answer"]
            assert len(original_questions) == 2
            assert len(original_answers) == (2 if failed_kind == "answer" else 0)
            assert requests == 1

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            response = await client.post(location + "/resume")
            assert response.status_code == 202, response.text
            turn = await settled(client, location)
            if failed_kind == "question":
                assert turn["status"] == "waiting_for_input"
                assert await read_transcript(client, location) == before
                assert {
                    ReferenceTarget("message", UUID(question["message_id"])): question[
                        "question_ref"
                    ]
                    for question in turn["interrupts"][0]["value"]["questions"]
                } == committed_refs
                answers = await read_answers(client, location)
                response = await client.post(location + "/answers", json=answers)
                assert response.status_code == 202, response.text
                turn = await settled(client, location)
            assert turn["status"] == "completed"
            after = await read_transcript(client, location)
            assert [m for m in after if m["kind"] == "question"] == original_questions
            if failed_kind == "answer":
                assert [m for m in after if m["kind"] == "answer"] == original_answers
            tool = (await client.get(location + "/steps")).json()[0]["tool_calls"][0]
            assert_model_answers(
                json.loads(tool["output"]), answers, after, pg_engine, location
            )
            result_refs = {
                answer["question_ref" if failed_kind == "question" else "answer_ref"]
                for answer in json.loads(tool["output"])["answers"]
            }
            assert result_refs == set(committed_refs.values())
            assert (
                await client.post(location + "/answers", json=answers)
            ).status_code == 200
            assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_answer_waits_for_postgres_save_not_the_replayed_waiting_checkpoint(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """PG 寫入尚未成功時，舊待答快照不得使 answers 提前回 202。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        application_name = "human_answer_" + uuid4().hex
        conninfo = make_conninfo(checkpoint_conninfo, application_name=application_name)
        async with (
            api_client(
                pg_engine, conninfo, httpx2.MockTransport(respond), bundles=BUNDLES
            ) as client,
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as controller,
        ):
            location = await start_question(client)
            answers = await read_answers(client, location)
            lock_key = uuid4().int % (2**63)
            await controller.execute(
                "CREATE FUNCTION pause_answer_save() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "PERFORM pg_advisory_xact_lock(TG_ARGV[0]::bigint); "
                "RETURN NEW; END $$"
            )
            for table in ("checkpoints", "checkpoint_writes"):
                await controller.execute(
                    sql.SQL(
                        "CREATE TRIGGER pause_answer BEFORE INSERT ON {} FOR EACH ROW "
                        "EXECUTE FUNCTION pause_answer_save({})"
                    ).format(sql.Identifier(table), sql.Literal(str(lock_key)))
                )
            await controller.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
            answer = asyncio.create_task(
                client.post(location + "/answers", json=answers)
            )
            try:
                await wait_for_database_lock(checkpoint_conninfo, application_name)
                assert not answer.done()
                assert requests == 1
            finally:
                await controller.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            response = await asyncio.wait_for(answer, timeout=10)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_postgres_rejection_does_not_acknowledge_an_unsaved_answer(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """原生保存被 PG 拒絕，不得用舊問題快照回受理成功。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        async with (
            api_client(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(respond),
                bundles=BUNDLES,
            ) as client,
            await AsyncConnection.connect(
                checkpoint_conninfo, autocommit=True
            ) as controller,
        ):
            location = await start_question(client)
            answers = await read_answers(client, location)
            await controller.execute(
                "CREATE FUNCTION reject_answer_save() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'synthetic save failure'; END $$"
            )
            for table in ("checkpoints", "checkpoint_writes"):
                await controller.execute(
                    sql.SQL(
                        "CREATE TRIGGER reject_answer BEFORE INSERT ON {} "
                        "FOR EACH ROW EXECUTE FUNCTION reject_answer_save()"
                    ).format(sql.Identifier(table))
                )
            try:
                response = await client.post(location + "/answers", json=answers)
                assert response.status_code == 503, response.text
                tool = (await client.get(location + "/steps")).json()[0]["tool_calls"][
                    0
                ]
                assert tool["status"] == "not_recorded"
                assert requests == 1
            finally:
                for table in ("checkpoints", "checkpoint_writes"):
                    await controller.execute(
                        sql.SQL("DROP TRIGGER reject_answer ON {}").format(
                            sql.Identifier(table)
                        )
                    )
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("mode", ["rewrite", "reorder_answers"])
def test_answers_follow_displayed_questions_after_a_tool_wrapper_changes_arguments(
    pg_engine: Engine, checkpoint_conninfo: str, mode: str
) -> None:
    """驗證的是人實際看到的批次，不以模型原參數推定工具執行參數。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        bundles = (
            *BUNDLES,
            BundleConfig(
                "tests.integration.agent.human_question_fixture", {"when": mode}
            ),
        )
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            waiting = (await client.get(location)).json()
            displayed = waiting["interrupts"][0]["value"]["questions"]
            answer = (
                {
                    **answers,
                    "answers": [
                        {
                            "question_message_id": displayed[0]["message_id"],
                            "selected": ["實際選項"],
                        }
                    ],
                }
                if mode == "rewrite"
                else answers
            )
            response = await client.post(location + "/answers", json=answer)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            duplicate = await client.post(location + "/answers", json=answer)
            assert duplicate.status_code == 200, duplicate.text
            exchange = (await client.get(location + "/questions")).json()[0]
            assert [
                SavedQuestion.model_validate_json(json.dumps(item))
                for item in exchange["questions"]
            ] == [
                SavedQuestion.model_validate_json(json.dumps(item))
                for item in displayed
            ]
            assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_interview_commit_before_task_result_may_repeat_questions_on_recovery(
    pg_engine: Engine, checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """已提交但尚無 task 結果時可重建題目；新等待點只引用新 UUID。"""
    import importlib
    from collections.abc import Callable, Sequence
    from uuid import UUID

    from caliburn.modules.interview.application.persistence import InterviewUnitOfWork
    from caliburn.modules.interview.application.results import MessageView
    from caliburn.modules.interview.application.withdrawal import withdraw_turn
    from caliburn.modules.interview.domain.models.message_content import Question
    from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
        SqlAlchemyInterviewUnitOfWork,
    )
    from caliburn.shared.infrastructure.persistence.database import (
        create_session_factory,
    )
    from tests.integration.agent.test_human_answers_http import read_transcript

    question_tool = importlib.import_module(
        "caliburn.bundles.human_questions.ask_user_question"
    )
    record_questions = question_tool.record_questions
    fail_after_commit = True

    def commit_without_task_result(
        *,
        workspace_id: UUID,
        turn_id: UUID,
        questions: Sequence[Question],
        uow_factory: Callable[[], InterviewUnitOfWork],
    ) -> tuple[MessageView, ...]:
        nonlocal fail_after_commit
        result: tuple[MessageView, ...] = record_questions(
            workspace_id=workspace_id,
            turn_id=turn_id,
            questions=questions,
            uow_factory=uow_factory,
        )
        if fail_after_commit:
            fail_after_commit = False
            raise RuntimeError("訪談已提交，合成故障阻止 task 回傳")
        return result

    monkeypatch.setattr(question_tool, "record_questions", commit_without_task_result)

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            return sse_response(
                EventStream(
                    response_events(
                        response_payload(
                            [
                                call(
                                    "ask_user_question",
                                    "call_ask",
                                    json.dumps(QUESTIONS),
                                )
                            ]
                        )
                    )
                )
            )

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "提交空隙"})
            ).json()["workspace_id"]
            turn_id = uuid4()
            response = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(turn_id), "input": "合成輸入"},
            )
            location = response.headers["Location"]
            assert (await settled(client, location))["status"] == "interrupted"
            before = await read_transcript(client, location)
            original_ids = [m["message_id"] for m in before if m["kind"] == "question"]
            assert len(original_ids) == 2
            assert not [m for m in before if m["kind"] == "answer"]
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            assert (await client.post(location + "/resume")).status_code == 202
            waiting = await settled(client, location)
            assert waiting["status"] == "waiting_for_input"
            pending_ids = [
                q["message_id"] for q in waiting["interrupts"][0]["value"]["questions"]
            ]
            assert set(pending_ids).isdisjoint(original_ids)
            repeated = await read_transcript(client, location)
            assert [
                m["message_id"] for m in repeated if m["kind"] == "question"
            ] == original_ids + pending_ids
            assert not [m for m in repeated if m["kind"] == "answer"]
            assert requests == 1
            sessions = create_session_factory(pg_engine)
            withdraw_turn(
                workspace_id=UUID(workspace),
                turn_id=turn_id,
                uow_factory=lambda: SqlAlchemyInterviewUnitOfWork(sessions),
            )
            assert await read_transcript(client, location) == []
            for message_id in original_ids + pending_ids:
                assert (
                    await client.get(
                        f"/workspaces/{workspace}/interview/messages/{message_id}"
                    )
                ).status_code == 404

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
