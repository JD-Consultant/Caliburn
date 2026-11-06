"""由正式組裝入口確認顧問提示是否送入 Responses 請求。"""

import asyncio

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

CONSULTANT = "caliburn.bundles.consultant"


@pytest.mark.parametrize("enabled", [True, False])
def test_consultant_role_is_sent_only_when_configured(enabled: bool) -> None:
    sent = []
    input_text = "我是客服專員，主要處理退貨申請。"

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(CONSULTANT)] if enabled else [],
                agent_id="test-consultant",
                resume_version="v1",
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:
                result = await complete_turn(
                    agent, workspace_id=TEST_WORKSPACE_ID, input=input_text
                )
        assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)

    (body,) = sent
    assert body["input"] == [{"role": "user", "content": input_text}]
    assert body["tools"] == []
    if enabled:
        instructions = body["instructions"]
        assert "你是 Caliburn 的職務顧問。" in instructions
        assert "先建立工作廣度" in instructions
        assert "JD 各部分怎麼寫" in instructions
        assert "未入稿" in instructions
        assert "自然答覆" in instructions
        assert "本輪可執行的下一步" in instructions
        assert "有已讀且仍有效的已發布正文時" in instructions
        assert "本輪可查讀 Memory 時" in instructions
        assert "有訪談查讀工具才補讀" in instructions
        assert "本輪提供計畫寫入工具時" in instructions
        assert "本輪有公版搜尋工具時" in instructions
    else:
        assert "instructions" not in body


def test_opening_invites_employee_to_describe_role_and_major_work() -> None:
    from caliburn.bundles.consultant import OPENING_TEXT

    assert "職務說明書" in OPENING_TEXT
    assert "不必一次說完" in OPENING_TEXT
    assert "目前擔任什麼職位，主要負責哪些工作" in OPENING_TEXT
    assert "用自己的說法" in OPENING_TEXT
