"""人工回答沿正式 HTTP、離線模型與真 PG 接回原輪。"""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.human_questions.questions import AnswerBatch, SavedQuestion
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    response_events,
    response_payload,
    sse_response,
)

QUESTIONS = {
    "questions": [
        {
            "question": "主要優先事項？",
            "options": [{"label": "交期"}, {"label": "品質"}],
        },
        {"question": "還有補充嗎？"},
    ]
}
BUNDLES = (
    BundleConfig("caliburn.bundles.interview"),
    BundleConfig("caliburn.bundles.human_questions"),
)


async def read_answers(client: httpx2.AsyncClient, location: str) -> dict[str, Any]:
    pending = (await client.get(location)).json()["interrupts"][0]["value"]
    return {
        "model_step": pending["model_step"],
        "call_id": pending["call_id"],
        "answers": [
            {
                "question_message_id": question["message_id"],
                "selected": ["交期"] if index == 0 else [],
            }
            for index, question in enumerate(pending["questions"])
        ],
    }


def assert_model_answers(
    output: dict[str, Any],
    answers: dict[str, Any],
    transcript: list[dict[str, Any]],
    pg_engine: Engine,
    location: str,
) -> None:
    """從公開訊息與持久定位解析核對模型看到的每個短碼。"""
    assert set(output) == {"answers"}
    assert len(output["answers"]) == len(answers["answers"])
    workspace_id = UUID(location.split("/workspaces/")[1].split("/")[0])
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    expected_questions = {
        message["message_id"]: message
        for message in transcript
        if message["kind"] == "question"
    }
    expected_answers = {
        message["reply_to_message_id"]: message
        for message in transcript
        if message["kind"] == "answer"
    }
    for model_answer, submitted in zip(
        output["answers"], answers["answers"], strict=True
    ):
        question_id = submitted["question_message_id"]
        expected_answer = expected_answers[question_id]
        question_ref = model_answer["question_ref"]
        answer_ref = model_answer["answer_ref"]
        assert question_ref.startswith("message_")
        assert answer_ref.startswith("message_")
        resolved = references.resolve_refs(workspace_id, [question_ref, answer_ref])
        assert resolved == {
            question_ref: ReferenceTarget("message", UUID(question_id)),
            answer_ref: ReferenceTarget("message", UUID(expected_answer["message_id"])),
        }
        assert model_answer == {
            "question_ref": question_ref,
            "answer_ref": answer_ref,
            "question": expected_questions[question_id]["text"],
            **{
                key: value
                for key, value in submitted.items()
                if key != "question_message_id"
            },
        }


async def read_transcript(
    client: httpx2.AsyncClient, location: str
) -> list[dict[str, Any]]:
    workspace_path, turn_id = location.split("/agent/turns/")
    response = await client.get(
        workspace_path + "/interview/messages", params={"turn_id": turn_id}
    )
    assert response.status_code == 200, response.text
    transcript: list[dict[str, Any]] = response.json()
    return transcript


async def settled(client: httpx2.AsyncClient, location: str) -> dict[str, Any]:
    async with asyncio.timeout(10):
        while True:
            response = await client.get(location)
            assert response.status_code == 200, response.text
            turn: dict[str, Any] = response.json()
            if turn["status"] != "running":
                return turn
            await asyncio.sleep(0.01)


async def start_question(client: httpx2.AsyncClient) -> str:
    workspace = (
        await client.post("/workspaces", json={"interviewee_name": "人工問答測試"})
    ).json()["workspace_id"]
    response = await client.post(
        f"/workspaces/{workspace}/agent/turns",
        json={"turn_id": str(uuid4()), "input": "請協助整理工作內容"},
    )
    assert response.status_code == 202, response.text
    location = response.headers["Location"]
    turn = await settled(client, location)
    assert turn["status"] == "waiting_for_input"
    pending = turn["interrupts"][0]["value"]
    assert pending["type"] == "user_questions"
    assert pending["model_step"] == 1
    assert pending["call_id"] == "call_ask"
    return location


def test_answers_resume_original_turn_and_are_readable_after_reopening(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """人可選擇與略過；答案作為原工具結果保存，重送不再呼叫模型。"""

    async def run() -> None:
        requests: list[dict[str, Any]] = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            requests.append(json.loads(request.content))
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if len(requests) == 1
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            first_id, second_id = [
                answer["question_message_id"] for answer in answers["answers"]
            ]
            question_response = await client.get(location + "/questions")
            assert question_response.status_code == 200, question_response.text
            batches = question_response.json()
            assert len(batches) == 1
            assert batches[0]["model_step"] == 1
            assert batches[0]["call_id"] == "call_ask"
            assert batches[0]["status"] == "waiting"
            assert batches[0]["answers"] is None
            assert [q["message_id"] for q in batches[0]["questions"]] == [
                first_id,
                second_id,
            ]
            assert UUID(first_id) != UUID(second_id)
            assert all(
                question["question_ref"].startswith("message_")
                for question in batches[0]["questions"]
            )
            transcript = await read_transcript(client, location)
            assert [message["kind"] for message in transcript] == [
                "text",
                "question",
                "question",
            ]
            assert [message["message_id"] for message in transcript[1:]] == [
                first_id,
                second_id,
            ]
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 202, response.text
            turn = await settled(client, location)
            assert turn["status"] == "completed"
            assert turn["input"] == "請協助整理工作內容"
            steps = (await client.get(location + "/steps")).json()
            assert [step["model_step"] for step in steps] == [1, 2]
            tool = steps[0]["tool_calls"][0]
            assert tool["status"] == "recorded"
            assert "questions" not in tool
            assert [
                SavedQuestion.model_validate_json(json.dumps(item))
                for item in steps[0]["interrupts"][0]["value"]["questions"]
            ] == [
                SavedQuestion.model_validate_json(json.dumps(question))
                for question in batches[0]["questions"]
            ]
            transcript = await read_transcript(client, location)
            assert_model_answers(
                json.loads(tool["output"]), answers, transcript, pg_engine, location
            )
            assert requests[1]["input"][-1]["type"] == "function_call_output"
            assert requests[1]["input"][-1]["call_id"] == "call_ask"
            user_contents = [
                item["content"]
                for item in requests[1]["input"]
                if item.get("role") == "user"
            ]
            assert user_contents.count("請協助整理工作內容") == 1
            source_materials = [
                json.loads(content)
                for content in user_contents
                if content != "請協助整理工作內容"
            ]
            metadata = [
                material
                for material in source_materials
                if material.get("data_kind")
                in {"employee_input_reference", "interview_navigation"}
            ]
            assert {item["data_kind"] for item in metadata} == {
                "employee_input_reference",
                "interview_navigation",
            }
            input_reference = next(
                item
                for item in metadata
                if item["data_kind"] == "employee_input_reference"
            )
            navigation = next(
                item for item in metadata if item["data_kind"] == "interview_navigation"
            )
            assert input_reference["ref"].startswith("message_")
            assert navigation["last_ref"] == input_reference["ref"]
            workspace_path = location.split("/agent/turns/")[0]
            all_messages = (
                await client.get(workspace_path + "/interview/messages")
            ).json()
            resolved = SqlAlchemyModelReferences(
                create_session_factory(pg_engine)
            ).resolve_refs(
                UUID(workspace_path.rsplit("/", 1)[1]),
                [navigation["first_ref"], input_reference["ref"]],
            )
            assert resolved == {
                navigation["first_ref"]: ReferenceTarget(
                    "message", UUID(all_messages[0]["message_id"])
                ),
                input_reference["ref"]: ReferenceTarget(
                    "message", UUID(transcript[0]["message_id"])
                ),
            }
            transcript = await read_transcript(client, location)
            assert [
                message["message_id"]
                for message in transcript
                if message["kind"] == "question"
            ] == [first_id, second_id]
            saved_answers = [
                message for message in transcript if message["kind"] == "answer"
            ]
            assert [
                (message["reply_to_message_id"], message["text"])
                for message in saved_answers
            ] == [(first_id, "選擇：交期"), (second_id, "略過")]
            assert len({message["message_id"] for message in transcript}) == len(
                transcript
            )

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            batches = (await client.get(location + "/questions")).json()
            assert batches[0]["status"] == "answered"
            assert AnswerBatch.model_validate_json(
                json.dumps({"answers": batches[0]["answers"]})
            ) == AnswerBatch.model_validate_json(
                json.dumps({"answers": answers["answers"]})
            )
            duplicate = await client.post(location + "/answers", json=answers)
            assert duplicate.status_code == 200, duplicate.text
            assert duplicate.json()["status"] == "completed"
            different = {
                **answers,
                "answers": [
                    {"question_message_id": first_id, "selected": ["品質"]},
                    {"question_message_id": second_id, "selected": []},
                ],
            }
            assert (
                await client.post(location + "/answers", json=different)
            ).status_code == 409
            assert len(requests) == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_model_reads_saved_question_and_answer_refs_in_the_same_turn(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """HTTP 回答後，模型只沿實際工具結果的短碼讀回本輪題答原文。"""

    async def run() -> None:
        requests: list[dict[str, Any]] = []
        question_result: dict[str, Any] = {}
        read_result: dict[str, Any] = {}

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal question_result, read_result
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) == 1:
                output = [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
            elif len(requests) == 2:
                result = next(
                    item
                    for item in body["input"]
                    if item.get("type") == "function_call_output"
                    and item["call_id"] == "call_ask"
                )
                question_result = json.loads(result["output"])
                refs = [
                    answer[field]
                    for answer in question_result["answers"]
                    for field in ("question_ref", "answer_ref")
                ]
                output = [
                    call(
                        "read_interview",
                        "call_read_answers",
                        json.dumps({"query": {"kind": "messages", "refs": refs}}),
                    )
                ]
            else:
                result = next(
                    item
                    for item in body["input"]
                    if item.get("type") == "function_call_output"
                    and item["call_id"] == "call_read_answers"
                )
                read_result = json.loads(result["output"])
                output = None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=BUNDLES,
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            answers["answers"][0]["custom"] = " 保留 message_9999 原文\n第二行 "
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert len(requests) == 3
            assert_model_answers(
                question_result,
                answers,
                await read_transcript(client, location),
                pg_engine,
                location,
            )
            first, skipped = question_result["answers"]
            assert read_result == {
                "data_kind": "interview",
                "messages": [
                    {
                        "ref": first["question_ref"],
                        "speaker": "consultant",
                        "kind": "question",
                        "text": "主要優先事項？",
                        "reply_to": None,
                    },
                    {
                        "ref": skipped["question_ref"],
                        "speaker": "consultant",
                        "kind": "question",
                        "text": "還有補充嗎？",
                        "reply_to": None,
                    },
                    {
                        "ref": first["answer_ref"],
                        "speaker": "employee",
                        "kind": "answer",
                        "text": "選擇：交期\n自填： 保留 message_9999 原文\n第二行 ",
                        "reply_to": first["question_ref"],
                    },
                    {
                        "ref": skipped["answer_ref"],
                        "speaker": "employee",
                        "kind": "answer",
                        "text": "略過",
                        "reply_to": skipped["question_ref"],
                    },
                ],
            }

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_invalid_answers_and_foreign_scope_leave_question_waiting(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """輸入錯誤不能變成略過，另一 Workspace 也不能回答這一輪。"""

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

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=BUNDLES,
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            first_id, second_id = [
                answer["question_message_id"] for answer in answers["answers"]
            ]
            before = (await client.get(location)).json()
            expected_locations = [
                ["body", "answers"],
                ["body", "answers", 0, "selected"],
                ["body", "answers"],
                ["body", "answers", 0, "selected"],
                ["body", "answers", 1, "custom"],
            ]
            for index, invalid_answers in enumerate(
                (
                    [{"question_message_id": first_id, "selected": []}],
                    [
                        {"question_message_id": first_id, "selected": ["未知"]},
                        {"question_message_id": second_id, "selected": []},
                    ],
                    [
                        {"question_message_id": first_id, "selected": []},
                        {"question_message_id": first_id, "selected": []},
                    ],
                    [
                        {"question_message_id": first_id, "selected": ["交期", "品質"]},
                        {"question_message_id": second_id, "selected": []},
                    ],
                    [
                        {"question_message_id": first_id, "selected": []},
                        {
                            "question_message_id": second_id,
                            "selected": [],
                            "custom": "\ud800",
                        },
                    ],
                )
            ):
                response = await client.post(
                    location + "/answers",
                    content=json.dumps({**answers, "answers": invalid_answers}),
                    headers={"Content-Type": "application/json"},
                )
                assert response.status_code == 422, response.text
                assert (
                    response.json()["detail"]["errors"][0]["loc"]
                    == (expected_locations[index])
                )
                assert "未知" not in response.text
            for changes in ({"model_step": 2}, {"call_id": "another_call"}):
                response = await client.post(
                    location + "/answers", json={**answers, **changes}
                )
                assert response.status_code == 409, response.text
            other = (
                await client.post("/workspaces", json={"interviewee_name": "另一份"})
            ).json()["workspace_id"]
            foreign = f"/workspaces/{other}/agent/turns/{before['turn_id']}/answers"
            assert (await client.post(foreign, json=answers)).status_code == 404
            assert (await client.post(location + "/resume")).status_code == 409
            assert (
                await client.post(
                    location.rsplit("/", 1)[0],
                    json={"turn_id": str(uuid4()), "input": "跳過原問題"},
                )
            ).status_code == 409
            assert (await client.get(location)).json() == before
            assert requests == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_reused_call_id_in_next_step_does_not_receive_old_answers(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """同名 call_id 在後續 Step 仍是另一批問題；並行重送只恢復一次。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            output = (
                [call("ask_user_question", "call_ask", json.dumps(QUESTIONS))]
                if requests <= 2
                else None
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=BUNDLES,
        ) as client:
            location = await start_question(client)
            answers = await read_answers(client, location)
            first_id, second_id = [
                answer["question_message_id"] for answer in answers["answers"]
            ]
            responses = await asyncio.gather(
                *[client.post(location + "/answers", json=answers) for _ in range(3)]
            )
            assert sorted(r.status_code for r in responses) == [200, 200, 202]
            waiting = await settled(client, location)
            assert waiting["status"] == "waiting_for_input"
            assert waiting["interrupts"][0]["value"]["model_step"] == 2
            duplicate = await client.post(location + "/answers", json=answers)
            assert duplicate.status_code == 200
            assert (await client.get(location)).json() == waiting
            assert requests == 2
            second_answers = await read_answers(client, location)
            assert second_answers["answers"][0]["question_message_id"] != first_id
            stale = await client.post(
                location + "/answers", json={**answers, "model_step": 2}
            )
            assert stale.status_code == 422
            response = await client.post(location + "/answers", json=second_answers)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            steps = (await client.get(location + "/steps")).json()
            assert [s["tool_calls"][0]["status"] for s in steps[:2]] == [
                "recorded",
                "recorded",
            ]
            assert requests == 3

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_cold_waiting_turn_accepts_answers_and_model_failure_resumes_without_reasking(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    """問答與模型分開保存：後續模型故障不撤銷已答內容。"""

    async def run() -> None:
        requests = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            if requests == 2:
                raise httpx2.ConnectError("離線模型故障")
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
            location = await start_question(client)
            answers = await read_answers(client, location)
            first_id, second_id = [
                answer["question_message_id"] for answer in answers["answers"]
            ]
            waiting = (await client.get(location)).json()["interrupts"]
            before = await read_transcript(client, location)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            assert (await client.get(location)).json()["interrupts"] == waiting
            assert await read_transcript(client, location) == before
            assert requests == 1
            response = await client.post(location + "/answers", json=answers)
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "interrupted"
            after = await read_transcript(client, location)
            assert [m["message_id"] for m in after if m["kind"] == "question"] == [
                first_id,
                second_id,
            ]
            assert [
                (m["reply_to_message_id"], m["text"])
                for m in after
                if m["kind"] == "answer"
            ] == [(first_id, "選擇：交期"), (second_id, "略過")]
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
        ) as client:
            duplicate = await client.post(location + "/answers", json=answers)
            assert duplicate.status_code == 200, duplicate.text
            assert requests == 2
            response = await client.post(location + "/resume")
            assert response.status_code == 202, response.text
            assert (await settled(client, location))["status"] == "completed"
            assert requests == 3
            tool = (await client.get(location + "/steps")).json()[0]["tool_calls"][0]
            assert_model_answers(
                json.loads(tool["output"]),
                answers,
                await read_transcript(client, location),
                pg_engine,
                location,
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
