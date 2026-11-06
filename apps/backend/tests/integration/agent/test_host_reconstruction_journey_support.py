"""Host 總旅程的離線模型；定位只取自實際模型請求。"""

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2

from tests.integration.agent.jd_bundle_support import tool_outputs
from tests.integration.agent.memory_reference_support import interview_material
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

EMPLOYEE_INPUT = "我負責庫存盤點。"
QUESTION = "盤點時您實際做哪些事？"
SKIPPED_QUESTION = "異常判斷還有補充嗎？"
ANSWER = "我逐筆核對庫存，把差異交主管複核。"
ANSWER_TEXT = "自填：" + ANSWER
FINAL = "已整理盤點工作；略過的異常判斷仍待釐清。"
PLAN = "盤點流程已整理；異常判斷待釐清。"
CHANGED_PLAN = "暫改計畫，等待員工確認。"
TASK_NAME = "核對庫存差異"
CHANGED_DESCRIPTION = "暫改為員工自行核准差異。"
FRESH_INPUT = "取消後開始新的工作。"
SECOND_INPUT = "暫改核准責任，待我確認。"


class PausedSituationStream(EventStream):
    def __init__(
        self,
        events: list[dict[str, object]],
        started: asyncio.Event,
        release: asyncio.Event,
    ) -> None:
        super().__init__(events)
        self._started = started
        self._release = release

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self._started.set()
        async with asyncio.timeout(30):
            await self._release.wait()
        async for part in super().__aiter__():
            yield part


def tool(tool_name: str, call_id: str, **arguments: object) -> dict[str, object]:
    return call(tool_name, call_id, json.dumps(arguments, ensure_ascii=False))


def material(request: dict[str, Any], data_kind: str) -> dict[str, Any]:
    for item in request["input"]:
        content = item.get("content")
        if item.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("data_kind") == data_kind:
            return value
    raise AssertionError(f"Model request lacks {data_kind}")


class JourneyModel:
    def __init__(self) -> None:
        self.requests: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.errors: list[Exception] = []
        self.answer_ref = ""
        self.task_ref = ""
        self.b1_messages: list[dict[str, Any]] = []
        self.situation_started = asyncio.Event()
        self.release_situation = asyncio.Event()

    @asynccontextmanager
    async def release_on_exit(self) -> AsyncIterator[None]:
        """即使 HTTP 斷言失敗，也先放行自有模型串流，再退出 Host。"""
        try:
            yield
        finally:
            self.release_situation.set()

    def check(self) -> None:
        if self.errors:
            raise AssertionError(
                "Offline model observed an invalid journey boundary"
            ) from (self.errors[0])

    def respond(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        body = request_body(request)
        names = {item["name"] for item in body["tools"]}
        role = (
            "situation"
            if "create_work_situation" in names
            else "understanding"
            if "create_work_understanding" in names
            else "consultant"
            if names
            else "disabled"
        )
        self.requests[role].append(body)
        try:
            output = self.reply(role, body, len(self.requests[role]))
        except Exception as error:
            self.errors.append(error)
            raise
        events = response_events(response_payload(output))
        if role == "situation" and len(self.requests[role]) == 1:
            return sse_response(
                PausedSituationStream(
                    events, self.situation_started, self.release_situation
                )
            )
        return sse_response(EventStream(events))

    def reply(
        self, role: str, body: dict[str, Any], step: int
    ) -> list[dict[str, object]]:
        if role == "disabled":
            assert body["tools"] == []
            assert body["input"] == [{"role": "user", "content": FRESH_INPUT}]
            return [message(text="新的工作已完成。")]
        if role == "situation":
            return self.situation(body, step)
        if role == "understanding":
            return self.understanding(body, step)
        return self.consultant(body, step)

    def consultant(self, body: dict[str, Any], step: int) -> list[dict[str, object]]:
        results = tool_outputs(body)
        if step == 1:
            names = {item["name"] for item in body["tools"]}
            assert {
                "ask_user_question",
                "create_jd_task",
                "edit_interview_plan",
                "request_memory_consolidation",
            } <= names
            return [
                tool(
                    "ask_user_question",
                    "ask_work",
                    questions=[{"question": QUESTION}, {"question": SKIPPED_QUESTION}],
                )
            ]
        if step == 2:
            answers = results["ask_work"]["answers"]
            assert answers[0]["custom"] == ANSWER
            assert answers[1]["selected"] == []
            assert answers[1].get("custom") is None
            self.answer_ref = answers[0]["answer_ref"]
            assert self.answer_ref.startswith("message_")
            return [
                tool(
                    "read_interview",
                    "read_answer",
                    query={"kind": "messages", "refs": [self.answer_ref]},
                ),
                tool("read_jd", "read_empty_jd", view="full"),
                tool("read_interview_plan", "read_empty_plan"),
            ]
        if step == 3:
            assert results["read_answer"]["messages"][0]["text"] == ANSWER_TEXT
            assert results["read_empty_jd"]["tasks"] == []
            assert results["read_empty_plan"]["plan"] is None
            return [
                tool(
                    "create_jd_task",
                    "create_task",
                    name=TASK_NAME,
                    description=ANSWER,
                    outcomes=[{"text": "差異清單"}],
                    supporting_sources=[
                        {"kind": "interview", "message_ref": self.answer_ref}
                    ],
                ),
                tool(
                    "edit_interview_plan",
                    "write_plan",
                    diff=f"@@\n+{PLAN}\n*** End of File",
                ),
                tool("request_memory_consolidation", "request_memory"),
            ]
        if step == 4:
            assert results["create_task"]["status"] == "created", results["create_task"]
            self.task_ref = results["create_task"]["read_ref"]
            assert results["write_plan"]["status"] == "updated"
            assert "message" in results["request_memory"]
            return [message(text=FINAL)]
        if step == 5:
            # B1 尚在處理原批次，晚來新輪仍沿正式工具查讀現況。
            return [
                tool("read_jd", "read_current_jd", view="full"),
                tool("read_interview_plan", "read_current_plan"),
            ]
        assert step == 6, f"Unexpected consultant step {step}"
        target = next(
            item
            for item in results["read_current_jd"]["tasks"]
            if item["name"] == TASK_NAME
        )
        assert target["read_ref"] == self.task_ref
        citation_ref = target["supporting_sources"][0]["citation_ref"]
        assert results["read_current_plan"]["plan"] == PLAN
        return [
            tool(
                "revise_jd_item",
                "change_task",
                read_ref=target["read_ref"],
                changes=[
                    {
                        "action": "set_field",
                        "field": "description",
                        "value": CHANGED_DESCRIPTION,
                    },
                    {"action": "remove_source", "citation_ref": citation_ref},
                ],
            ),
            tool(
                "edit_interview_plan",
                "change_plan",
                diff=f"@@\n-{PLAN}\n+{CHANGED_PLAN}",
            ),
            tool(
                "ask_user_question",
                "ask_cancelled",
                questions=[{"question": "暫改的核准責任正確嗎？"}],
            ),
        ]

    def situation(self, body: dict[str, Any], step: int) -> list[dict[str, object]]:
        if step == 1:
            self.b1_messages = interview_material(body)["messages"]
            assert [item["text"] for item in self.b1_messages] == [
                EMPLOYEE_INPUT,
                QUESTION,
                SKIPPED_QUESTION,
                ANSWER_TEXT,
                "略過",
                FINAL,
            ]
            answer = next(
                item for item in self.b1_messages if item["text"] == ANSWER_TEXT
            )
            assert answer["ref"] == self.answer_ref
            assert answer["reply_to"] == self.b1_messages[1]["ref"]
            assert self.b1_messages[4]["reply_to"] == self.b1_messages[2]["ref"]
            return [
                tool(
                    "create_work_situation",
                    "create_situation",
                    title="庫存盤點",
                    description="逐筆核對並交主管複核",
                    body=ANSWER,
                    interview_references=[answer["ref"]],
                )
            ]
        assert step == 2
        assert interview_material(body)["messages"] == self.b1_messages
        assert SECOND_INPUT not in json.dumps(body, ensure_ascii=False)
        assert tool_outputs(body)["create_situation"]["status"] == "created"
        return [message(text='{"status":"complete"}')]

    def understanding(self, body: dict[str, Any], step: int) -> list[dict[str, object]]:
        assert SECOND_INPUT not in json.dumps(body, ensure_ascii=False)
        if step == 1:
            navigation = material(body, "memory_analysis_input")["work_situation_map"]
            title = navigation["items"][0]["target_title"]
            return [tool("read_work_situation", "read_situation", target_title=title)]
        if step == 2:
            situation = tool_outputs(body)["read_situation"]
            assert situation["body"] == ANSWER
            return [
                tool(
                    "create_work_understanding",
                    "create_understanding",
                    title="盤點複核分工",
                    description="本人核對，主管複核",
                    body="員工逐筆核對，主管負責複核差異。",
                    work_situation_references=[situation["title"]],
                )
            ]
        assert step == 3
        assert tool_outputs(body)["create_understanding"]["status"] == "created"
        return [message(text='{"status":"complete"}')]


async def get_json(client: httpx2.AsyncClient, path: str) -> Any:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def wait_turn(
    client: httpx2.AsyncClient, path: str, model: JourneyModel
) -> dict[str, Any]:
    async with asyncio.timeout(15):
        while True:
            model.check()
            turn: dict[str, Any] = await get_json(client, path)
            if turn["status"] != "running":
                model.check()
                return turn
            await asyncio.sleep(0.01)


async def wait_memory(
    client: httpx2.AsyncClient, path: str, model: JourneyModel
) -> dict[str, Any]:
    async with asyncio.timeout(15):
        while True:
            model.check()
            published: dict[str, Any] = await get_json(client, path)
            if published["published_version"] is not None:
                return published
            await asyncio.sleep(0.01)
