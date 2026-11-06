"""正式 Host 的建立、問答、編修、Memory 發布及停用後取消總旅程。"""

import asyncio
import json
from uuid import uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.bundles.consultant import OPENING_TEXT
from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_host_reconstruction_journey_support import (
    ANSWER,
    ANSWER_TEXT,
    CHANGED_DESCRIPTION,
    CHANGED_PLAN,
    EMPLOYEE_INPUT,
    FINAL,
    FRESH_INPUT,
    PLAN,
    QUESTION,
    SECOND_INPUT,
    SKIPPED_QUESTION,
    TASK_NAME,
    JourneyModel,
    get_json,
    wait_memory,
    wait_turn,
)

BUNDLES = (
    BundleConfig("caliburn.bundles.consultant"),
    BundleConfig(
        "caliburn.bundles.interview",
        plugins=("interview", "interview_source_prompt"),
    ),
    BundleConfig("caliburn.bundles.human_questions"),
    BundleConfig("caliburn.bundles.plan"),
    BundleConfig("caliburn.bundles.job_description"),
    BundleConfig("caliburn.bundles.memory"),
    BundleConfig("caliburn.bundles.context", plugins=("window",)),
)


def test_host_journey_preserves_completed_work_when_disabled_turn_is_cancelled(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    model = JourneyModel()
    transport = httpx2.MockTransport(model.respond)

    async def run() -> None:
        async with (
            api_client(
                pg_engine, checkpoint_conninfo, transport, bundles=BUNDLES
            ) as client,
            model.release_on_exit(),
        ):
            created = await client.post(
                "/workspaces", json={"interviewee_name": "Synthetic full journey"}
            )
            assert created.status_code == 201, created.text
            workspace = created.json()["workspace_id"]
            prefix = f"/workspaces/{workspace}"
            jd_path = prefix + "/job-description"
            interview_path = prefix + "/interview/messages"
            memory_path = prefix + "/memory"
            turns = prefix + "/agent/turns"

            empty_jd = await get_json(client, jd_path)
            assert empty_jd["job_title"] is empty_jd["purpose"] is None
            for field in (
                "duties",
                "tasks",
                "knowledge",
                "skills",
                "collaborations",
                "conditions",
                "citations",
            ):
                assert empty_jd[field] == []
            opening = await get_json(client, interview_path)
            assert len(opening) == 1
            assert opening[0]["text"] == OPENING_TEXT
            assert opening[0]["speaker"] == "app"
            assert model.requests == {}

            first_id = str(uuid4())
            accepted = await client.post(
                turns, json={"turn_id": first_id, "input": EMPLOYEE_INPUT}
            )
            assert accepted.status_code == 202, accepted.text
            first = accepted.headers["Location"]
            assert (await wait_turn(client, first, model))[
                "status"
            ] == "waiting_for_input"
            exchange = (await get_json(client, first + "/questions"))[0]
            assert [item["question"] for item in exchange["questions"]] == [
                QUESTION,
                SKIPPED_QUESTION,
            ]
            answered = await client.post(
                first + "/answers",
                json={
                    "model_step": exchange["model_step"],
                    "call_id": exchange["call_id"],
                    "answers": [
                        {
                            "question_message_id": exchange["questions"][0][
                                "message_id"
                            ],
                            "selected": [],
                            "custom": ANSWER,
                        },
                        {
                            "question_message_id": exchange["questions"][1][
                                "message_id"
                            ],
                            "selected": [],
                        },
                    ],
                },
            )
            assert answered.status_code == 202, answered.text
            completed = await wait_turn(client, first, model)
            assert completed["status"] == "completed"
            assert completed["output"] == FINAL
            first_request_count = len(model.requests["consultant"])
            assert first_request_count == 4
            baseline_interview = await get_json(client, interview_path)
            first_messages = [
                item for item in baseline_interview if item["turn_id"] == first_id
            ]
            assert [item["text"] for item in first_messages] == [
                EMPLOYEE_INPUT,
                QUESTION,
                SKIPPED_QUESTION,
                ANSWER_TEXT,
                "略過",
                FINAL,
            ]
            answer_id = next(
                item["message_id"]
                for item in first_messages
                if item["text"] == ANSWER_TEXT
            )
            baseline_jd = await get_json(client, jd_path)
            assert baseline_jd["job_description_id"] == empty_jd["job_description_id"]
            assert len(baseline_jd["tasks"]) == 1
            assert baseline_jd["tasks"][0]["name"] == TASK_NAME
            assert baseline_jd["tasks"][0]["description"] == ANSWER
            assert len(baseline_jd["citations"]) == 1
            citation = baseline_jd["citations"][0]
            assert citation["source"]["message_id"] == answer_id
            citation_path = (
                prefix
                + f"/job-descriptions/{baseline_jd['job_description_id']}"
                + f"/citations/{citation['id']}"
            )
            source = (await get_json(client, citation_path))["source"]
            assert source["availability"] == "available"
            assert source["text"] == ANSWER_TEXT
            baseline_plan = await get_json(client, prefix + "/plan")
            assert baseline_plan["body"] == PLAN

            await asyncio.wait_for(model.situation_started.wait(), timeout=15)
            model.check()
            assert not model.release_situation.is_set()
            second_id = str(uuid4())
            pending = await client.post(
                turns, json={"turn_id": second_id, "input": SECOND_INPUT}
            )
            assert pending.status_code == 202, pending.text
            second = pending.headers["Location"]
            assert (await wait_turn(client, second, model))[
                "status"
            ] == "waiting_for_input"
            changed_jd = await get_json(client, jd_path)
            assert changed_jd["tasks"][0]["description"] == CHANGED_DESCRIPTION
            assert changed_jd["citations"] == []
            assert (await client.get(citation_path)).status_code == 404
            assert (await get_json(client, prefix + "/plan"))["body"] == CHANGED_PLAN
            second_messages = await get_json(
                client, interview_path + f"?turn_id={second_id}"
            )
            assert [item["kind"] for item in second_messages] == ["text", "question"]
            assert (await get_json(client, memory_path))["published_version"] is None

            model.release_situation.set()
            published = await wait_memory(client, memory_path, model)
            assert (
                published["covered_through_message_id"]
                == first_messages[-1]["message_id"]
            )
            assert {item["kind"] for item in published["items"]} == {
                "situation",
                "understanding",
            }
            version = published["published_version"]
            details = {
                item["kind"]: await get_json(
                    client, f"{memory_path}/versions/{version}/items/{item['item_id']}"
                )
                for item in published["items"]
            }
            assert details["situation"]["source_ids"] == [answer_id]
            assert details["understanding"]["source_ids"] == [
                details["situation"]["item_id"]
            ]
            assert len(model.b1_messages) == len(first_messages)
            assert (await get_json(client, second))["status"] == "waiting_for_input"
            assert await get_json(client, memory_path) == published

        counts_before = {
            role: len(requests) for role, requests in model.requests.items()
        }
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, resume_version="disabled-v2"
        ) as client:
            assert (await client.post(second + "/resume")).status_code == 409
            cancelled = await client.post(second + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            assert (await client.post(second + "/cancel")).status_code == 204
            assert (await client.get(second)).status_code == 404
            restored_jd = await get_json(client, jd_path)
            assert restored_jd["version"] > baseline_jd["version"]
            assert {
                key: value for key, value in restored_jd.items() if key != "version"
            } == {key: value for key, value in baseline_jd.items() if key != "version"}
            assert (await get_json(client, citation_path))["source"] == source
            restored_plan = await get_json(client, prefix + "/plan")
            assert restored_plan["body"] == baseline_plan["body"]
            assert restored_plan["version"] > baseline_plan["version"]
            assert await get_json(client, interview_path) == baseline_interview
            assert (
                await get_json(client, interview_path + f"?turn_id={second_id}") == []
            )
            assert await get_json(client, memory_path) == published
            assert (
                await get_json(client, f"{memory_path}/versions/{version}") == published
            )
            assert {
                role: len(requests) for role, requests in model.requests.items()
            } == counts_before

            steps = await get_json(client, first + "/steps")
            assert [step["model_step"] for step in steps] == [1, 2, 3, 4]
            assert len(steps) == first_request_count
            assert [
                [item["call_id"] for item in step["tool_calls"]] for step in steps
            ] == [
                ["ask_work"],
                ["read_answer", "read_empty_jd", "read_empty_plan"],
                ["create_task", "write_plan", "request_memory"],
                [],
            ]
            for step in steps:
                assert step["usage"] == {
                    "input_tokens": 13,
                    "output_tokens": 8,
                    "total_tokens": 21,
                }
            calls = {
                item["call_id"]: item for step in steps for item in step["tool_calls"]
            }
            assert calls["ask_work"]["status"] == "recorded"
            assert (
                json.loads(calls["ask_work"]["output"])["answers"][0]["answer_ref"]
                == model.answer_ref
            )
            assert calls["create_task"]["status"] == "recorded"
            assert calls["request_memory"]["status"] == "recorded"
            old = await get_json(client, first)
            assert old["status"] == "completed"
            assert old["usage"] == {
                "input_tokens": 52,
                "output_tokens": 32,
                "total_tokens": 84,
            }
            assert [turn["turn_id"] for turn in await get_json(client, turns)] == [
                first_id
            ]

            fresh = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": FRESH_INPUT}
            )
            assert fresh.status_code == 202, fresh.text
            assert (await wait_turn(client, fresh.headers["Location"], model))[
                "status"
            ] == "completed"
            assert await get_json(client, jd_path) == restored_jd
            assert await get_json(client, prefix + "/plan") == restored_plan
            assert await get_json(client, interview_path) == baseline_interview
            assert await get_json(client, memory_path) == published

        model.check()
        assert {role: len(requests) for role, requests in model.requests.items()} == {
            "consultant": 6,
            "situation": 2,
            "understanding": 3,
            "disabled": 1,
        }

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
