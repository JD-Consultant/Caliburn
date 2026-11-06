"""固定合成模型場景；所有業務效果仍由正式工具與資料庫產生。"""

import json
import logging
from typing import Any

import httpx2
from tests.integration.agent.jd_bundle_support import tool_outputs
from tests.integration.agent.memory_reference_support import interview_material
from tests.integration.agent.test_host_reconstruction_journey_support import (
    ANSWER,
    CHANGED_DESCRIPTION,
    CHANGED_PLAN,
    EMPLOYEE_INPUT,
    PLAN,
    QUESTION,
    SECOND_INPUT,
    SKIPPED_QUESTION,
    TASK_NAME,
    JourneyModel,
    tool,
)
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

OPTION = "逐筆核對庫存，交主管複核"
SECOND_OPTION = "由主管直接處理全部盤點"
CANCEL_QUESTION = "暫改的核准責任正確嗎？"
logger = logging.getLogger(__name__)


def current_turn(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """以正式輸入 ref 分界，排除 Context 保留的過去工具結果。"""
    text = ""
    found: tuple[str, int] | None = None
    for index, item in enumerate(body["input"]):
        content = item.get("content")
        if item.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            material = json.loads(content)
        except json.JSONDecodeError:
            text = content
            continue
        if isinstance(material, dict):
            if material.get("data_kind") == "employee_input_reference":
                found = (text, index)
            elif material.get("data_kind") == "employee_input":
                found = (material["text"], index)
    assert found is not None, "正式 Interview input reference 缺失"
    return found[0], {**body, "input": body["input"][found[1] + 1 :]}


def consultant(body: dict[str, Any]) -> list[dict[str, object]]:
    user_input, current = current_turn(body)
    results = tool_outputs(current)
    if user_input == SECOND_INPUT:
        if "read_current_jd" not in results:
            return [
                tool("read_jd", "read_current_jd", view="full"),
                tool("read_interview_plan", "read_current_plan"),
            ]
        if "change_task" in results:
            return [message(text="已收到確認。")]
        target = next(
            item
            for item in results["read_current_jd"]["tasks"]
            if item["name"] == TASK_NAME
        )
        changes: list[dict[str, object]] = [
            {
                "action": "set_field",
                "field": "description",
                "value": CHANGED_DESCRIPTION,
            }
        ]
        changes.extend(
            {"action": "remove_source", "citation_ref": source["citation_ref"]}
            for source in target["supporting_sources"]
        )
        return [
            tool(
                "revise_jd_item",
                "change_task",
                read_ref=target["read_ref"],
                changes=changes,
            ),
            tool(
                "edit_interview_plan",
                "change_plan",
                diff=f"@@\n-{PLAN}\n+{CHANGED_PLAN}",
            ),
            tool(
                "ask_user_question",
                "ask_cancelled",
                questions=[{"question": CANCEL_QUESTION}],
            ),
        ]
    assert user_input == EMPLOYEE_INPUT, (
        f"Unsupported synthetic scenario: {user_input!r}"
    )
    if "ask_work" not in results:
        return [
            tool(
                "ask_user_question",
                "ask_work",
                questions=[
                    {
                        "question": QUESTION,
                        "header": "盤點工作",
                        "options": [{"label": OPTION}, {"label": SECOND_OPTION}],
                        "multi_select": False,
                    },
                    {"question": SKIPPED_QUESTION, "header": "補充說明"},
                ],
            )
        ]
    answers = results["ask_work"]["answers"]
    assert answers[0]["selected"] == [OPTION], "請沿固定場景選取第一題第一選項"
    assert answers[0].get("custom") is None
    assert answers[1]["selected"] == [] and answers[1].get("custom") is None
    answer_ref = answers[0]["answer_ref"]
    if "read_answer" not in results:
        return [
            tool(
                "read_interview",
                "read_answer",
                query={"kind": "messages", "refs": [answer_ref]},
            ),
            tool("read_jd", "read_empty_jd", view="full"),
            tool("read_interview_plan", "read_empty_plan"),
        ]
    if "create_task" not in results:
        assert OPTION in results["read_answer"]["messages"][0]["text"]
        assert results["read_empty_jd"]["tasks"] == []
        assert results["read_empty_plan"]["plan"] is None
        return [
            tool(
                "create_jd_task",
                "create_task",
                name=TASK_NAME,
                description=ANSWER,
                outcomes=[{"text": "差異清單"}],
                supporting_sources=[{"kind": "interview", "message_ref": answer_ref}],
            ),
            tool(
                "edit_interview_plan",
                "write_plan",
                diff=f"@@\n+{PLAN}\n*** End of File",
            ),
            tool("request_memory_consolidation", "request_memory"),
        ]
    return JourneyModel().consultant(current, 4)


def situation(body: dict[str, Any]) -> list[dict[str, object]]:
    results = tool_outputs(body)
    if "create_situation" in results:
        assert results["create_situation"]["status"] == "created"
        return [message(text='{"status":"complete"}')]
    messages = interview_material(body)["messages"]
    answer = next(
        item for item in messages if item["kind"] == "answer" and OPTION in item["text"]
    )
    assert any(item["text"] == "略過" for item in messages)
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


def respond(request: httpx2.Request) -> httpx2.Response:
    """只替換 SDK HTTP；不攔截瀏覽器的任何 App API。"""
    if request.url.path.endswith("/input_tokens"):
        return JourneyModel().respond(request)
    body = request_body(request)
    names = {item["name"] for item in body["tools"]}
    role = (
        "situation"
        if "create_work_situation" in names
        else "understanding"
        if "create_work_understanding" in names
        else "consultant"
    )
    try:
        if role == "situation":
            output = situation(body)
        elif role == "understanding":
            results = tool_outputs(body)
            step = (
                3
                if "create_understanding" in results
                else 2
                if "read_situation" in results
                else 1
            )
            output = JourneyModel().understanding(body, step)
        else:
            output = consultant(body)
    except Exception:
        logger.exception(
            "Offline scenario rejected unexpected journey", extra={"role": role}
        )
        raise
    logger.info(
        "offline_response role=%s calls=%s",
        role,
        [item.get("name", "final") for item in output],
    )
    return sse_response(EventStream(response_events(response_payload(output))))
