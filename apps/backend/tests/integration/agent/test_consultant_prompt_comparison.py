"""沿正式 HTTP 與 SDK 入口驗證只替換顧問提示的對照。"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.bundles.consultant import OPENING_TEXT
from caliburn.bundles.consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.bundles.interview.source_prompt import INTERVIEW_SOURCE_PROMPT
from caliburn.bundles.plan.planning_instructions import INTERVIEW_PLAN_INSTRUCTIONS
from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_consultant_candidate_changes_only_its_instructions(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    employee = (
        "我是採購助理，最近處理一筆交貨延遲。我收到供應商改期通知後，"
        "核對訂單並把新的到貨日通知倉庫；要不要改採購單由主管決定。"
        "可以先看目前的訪談計畫，再接著問嗎？"
    )
    final = "目前沒有訪談計畫。除了追蹤交期，您平常還會定期處理哪些採購工作？"
    call_id = "call_read_plan"
    batches = (
        [
            message("commentary", "我先查閱訪談計畫。"),
            call("read_interview_plan", call_id, "{}"),
        ],
        [message(text=final)],
    )
    shared_bundles = (
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=("interview", "interview_source_prompt"),
        ),
        BundleConfig("caliburn.bundles.plan"),
    )

    async def run_arm(module: str) -> dict[str, Any]:
        requests: list[dict[str, Any]] = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            output = batches[len(requests)]
            requests.append(request_body(request))
            return sse_response(EventStream(response_events(response_payload(output))))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig(module, plugins=("consultant",)), *shared_bundles),
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "採購助理提示比較"}
            )
            assert created.status_code == 201, created.text
            workspace = created.json()["workspace_id"]
            prefix = f"/workspaces/{workspace}"
            transcript_path = f"{prefix}/interview/messages"
            plan_path = f"{prefix}/plan"
            initial_transcript = await client.get(transcript_path)
            assert initial_transcript.status_code == 200, initial_transcript.text
            (opening,) = initial_transcript.json()
            assert (opening["speaker"], opening["kind"], opening["text"]) == (
                "app",
                "text",
                OPENING_TEXT,
            )
            initial_plan = await client.get(plan_path)
            assert initial_plan.status_code == 200, initial_plan.text
            assert initial_plan.json() == {
                "workspace_id": workspace,
                "version": None,
                "body": None,
            }
            jd = await client.get(f"{prefix}/job-description")
            assert jd.status_code == 200, jd.text
            assert jd.json()["version"] == 1
            assert jd.json()["job_title"] is None
            assert jd.json()["purpose"] is None
            assert jd.json()["duties"] == []
            assert jd.json()["tasks"] == []
            assert not requests

            accepted = await client.post(
                f"{prefix}/agent/turns",
                json={"turn_id": str(uuid4()), "input": employee},
            )
            assert accepted.status_code == 202, accepted.text
            async with asyncio.timeout(10):
                while True:
                    turn = await client.get(accepted.headers["Location"])
                    assert turn.status_code == 200, turn.text
                    if turn.json()["status"] != "running":
                        break
                    await asyncio.sleep(0.01)
            assert turn.json()["status"] == "completed", turn.text

            plan = await client.get(plan_path)
            assert plan.status_code == 200, plan.text
            assert plan.json() == {
                "workspace_id": workspace,
                "version": 1,
                "body": None,
            }
            transcript = await client.get(transcript_path)
            assert transcript.status_code == 200, transcript.text
            saved = transcript.json()
            assert [
                (item["speaker"], item["kind"], item["text"]) for item in saved
            ] == [
                ("app", "text", OPENING_TEXT),
                ("employee", "text", employee),
                ("consultant", "text", final),
            ]
            assert saved[0]["message_id"] == opening["message_id"]

        first, resumed = requests
        assert sorted(tool["name"] for tool in first["tools"]) == [
            "edit_interview_plan",
            "read_interview_plan",
        ]
        (requested,) = [
            item for item in resumed["input"] if item.get("type") == "function_call"
        ]
        assert requested["name"] == "read_interview_plan"
        assert requested["arguments"] == "{}"
        assert requested["call_id"] == call_id
        (result,) = [
            item
            for item in resumed["input"]
            if item.get("type") == "function_call_output"
        ]
        assert result["call_id"] == requested["call_id"]
        assert json.loads(result["output"]) == {"plan": None}
        return first

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        baseline = await run_arm("caliburn.bundles.consultant")
        candidate = await run_arm("tests.integration.agent.consultant_prompt_candidate")
        return baseline, candidate

    baseline, candidate = asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    baseline_instructions = baseline.pop("instructions")
    candidate_instructions = candidate.pop("instructions")
    for request in (baseline, candidate):
        original, source = request["input"]
        assert original == {"role": "user", "content": employee}
        assert source["role"] == "user"
        material = json.loads(source["content"])
        assert material["data_kind"] == "employee_input_reference"
        reference = material["ref"]
        assert isinstance(reference, str) and reference.startswith("message_")
        # 兩個 Workspace 的持久短碼各自配置，只排除 ref 的值。
        material["ref"] = "<workspace reference>"
        source["content"] = material
    assert baseline == candidate

    shared_instructions = (
        f"\n\n{INTERVIEW_SOURCE_PROMPT}\n\n{INTERVIEW_PLAN_INSTRUCTIONS}"
    )
    assert baseline_instructions == CONSULTANT_INSTRUCTIONS + shared_instructions
    candidate_policy = candidate_instructions.removesuffix(shared_instructions)
    assert candidate_instructions == candidate_policy + shared_instructions
    assert candidate_policy.startswith(CONSULTANT_INSTRUCTIONS + "\n"), (
        "SDK candidate instructions must extend the complete consultant policy"
    )
    assert candidate_policy.removeprefix(CONSULTANT_INSTRUCTIONS + "\n") == (
        "訪談初期若已能辨認員工提到的案例屬於哪項工作及本人分工，"
        "且主要工作範圍仍不清楚，下一問先用一個中立問題了解其他平常或定期做的工作。"
    )
