"""正式 HTTP 唯讀組合不預載正文，仍可由導覽端點讀回原話。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
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


def test_read_only_without_preload_discovers_range_from_actual_model_request(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    factory = partial(SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine))
    for text in ("先前原話", "後續原話 message_77"):
        record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=uuid4(),
            text=text,
            uow_factory=factory,
        )
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        requests.append(body)
        if len(requests) == 1:
            navigation = next(
                value
                for item in body["input"]
                if isinstance(item.get("content"), str)
                and item["content"].startswith("{")
                and (value := json.loads(item["content"])).get("data_kind")
                == "interview_navigation"
            )
            assert "先前原話" not in json.dumps(body["input"], ensure_ascii=False)
            output = [
                call(
                    "read_interview",
                    "read-range",
                    json.dumps(
                        {
                            "query": {
                                "kind": "range",
                                "start_ref": navigation["first_ref"],
                                "end_ref": navigation["last_ref"],
                            }
                        }
                    ),
                )
            ]
        else:
            output = [message(text="已核對原話")]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=(
                        "interview_source_prompt",
                        "interview_read",
                        "interview_navigation",
                    ),
                ),
            ),
        ) as client:
            response = await client.post(
                f"/workspaces/{jd_workspace_id}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "查讀既有來源"},
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
    result = json.loads(
        next(
            item["output"]
            for item in requests[1]["input"]
            if item.get("type") == "function_call_output"
        )
    )
    assert [item["text"] for item in result["messages"]] == [
        "先前原話",
        "後續原話 message_77",
    ]
    assert all(item["ref"].startswith("message_") for item in result["messages"])
    schema = next(
        tool for tool in requests[0]["tools"] if tool["name"] == "read_interview"
    )
    assert set(schema["parameters"]["properties"]) == {"query"}
