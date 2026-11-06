"""換窗與同版原生延續沿真訪談、Memory 與 PostgreSQL checkpoint。"""

import asyncio
import json
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from openai.types.responses.compacted_response import CompactedResponse
from sqlalchemy import Engine

from caliburn.modules.agent.application.turn_history import compaction_views
from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_opening,
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
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
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
from tests.integration.agent.plan_plugin_support import tool_outputs
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
    tool,
)
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import request_body


@dataclass
class WindowModel(OfflineMemoryModel):
    counts: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("input_tokens"):
            self.counts.append(request_body(request))
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        return super().__call__(request)


@pytest.mark.parametrize("completion_shape", COMPLETION_SHAPES)
def test_cold_renewal_keeps_uncovered_completed_dialogue(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    completion_shape: CompletionShape,
) -> None:
    first_turn, recent_turn = uuid4(), uuid4()
    interview = partial(
        SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
    )

    def finish_recent(_: dict[str, Any]) -> list[dict[str, object]]:
        questions = record_questions(
            workspace_id=jd_workspace_id,
            turn_id=recent_turn,
            questions=(
                Question(question="如何複核？"),
                Question(question="其他補充？"),
            ),
            uow_factory=interview,
        )
        record_answers(
            workspace_id=jd_workspace_id,
            turn_id=recent_turn,
            answers=(
                AnswerInput(
                    question_message_id=questions[0].message_id, custom="主管複核"
                ),
                AnswerInput(question_message_id=questions[1].message_id),
            ),
            uow_factory=interview,
        )
        return completion_messages(completion_shape, "已保存本輪完整問答。")

    model = WindowModel(
        [
            [tool("request_memory_consolidation", "first-request")],
            complete("舊輪已完成。"),
            finish_recent,
            complete(),
            complete(),
            complete("換窗後完成。"),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, coordinator, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=first_turn, input="舊輪原話"
                )
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=recent_turn,
                    input="本輪新增盤點責任。",
                )
            )
            recent_messages = SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id, turn_id=recent_turn
            )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=first_turn
            )
            assert published is not None
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="換窗後新輸入"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["memory_published_version"] == published.version
            assert {message.message_id for message in recent_messages} <= set(
                saved.values["memory_interview_ids"]
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [
        (item["kind"], item["text"])
        for item in interview_material(model.requests[5])["messages"]
    ] == [
        ("text", "本輪新增盤點責任。"),
        ("question", "如何複核？"),
        ("question", "其他補充？"),
        ("answer", "自填：主管複核"),
        ("answer", "略過"),
        ("text", "已保存本輪完整問答。"),
    ]


def test_same_version_continues_and_publication_replaces_only_next_turn(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    sessions = create_session_factory(pg_engine)
    record_opening(
        workspace_id=jd_workspace_id,
        text="開場原文",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    create_job_description(
        workspace_id=jd_workspace_id,
        uow_factory=partial(SqlAlchemyJobDescriptionUnitOfWork, sessions),
    )
    plan_factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=plan_factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+確認盤點分工\n*** End of File",
        uow_factory=plan_factory,
    )
    model = WindowModel(
        [
            complete("第一輪回覆"),
            [tool("request_memory_consolidation", "request")],
            complete("第二輪回覆"),
            lambda request: [
                tool(
                    "create_work_situation",
                    "s",
                    title="盤點",
                    description="核對庫存",
                    body="逐筆核對。",
                    interview_references=[interview_ref(request, " 第一次原文\n")],
                )
            ],
            complete(),
            [
                tool(
                    "create_work_understanding",
                    "u",
                    title="盤點責任",
                    description="本人核對",
                    body="本人核對差異。",
                    work_situation_references=["盤點"],
                )
            ],
            complete(),
            complete("換窗後回覆"),
            lambda request: [
                tool(
                    "read_interview",
                    "before-window",
                    query={
                        "kind": "messages",
                        "refs": [interview_ref(model.requests[0], " 第一次原文\n")],
                    },
                )
            ],
            complete("同版後續回覆"),
        ]
    )
    first, second = uuid4(), uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, coordinator, memory):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=first, input=" 第一次原文\n"
                )
            )
            first_saved = await agent.aget_state(workspace_id=jd_workspace_id)
            first_ref = interview_ref(model.requests[0], " 第一次原文\n")
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=2,
                diff=f"@@\n 確認盤點分工\n+原話定位：{first_ref}",
                uow_factory=plan_factory,
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=second, input="第二次原文"
                )
            )
            second_saved = await agent.aget_state(workspace_id=jd_workspace_id)
            first_items = first_saved.values["model_request"]["input"]
            assert (
                second_saved.values["model_request"]["input"][: len(first_items)]
                == first_items
            )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=second
            )
            assert published is not None
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第三次原文"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["memory_published_version"] == published.version
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第四次原文"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    initial = [json.loads(item["content"]) for item in model.requests[0]["input"]]
    assert initial[0]["data_kind"] == "memory_navigation"
    assert [item.get("data_kind", item.get("source")) for item in initial] == [
        "memory_navigation",
        "interview",
        "consultant_interview_plan",
        "employee_input",
        "interview_navigation",
    ]
    assert initial[-3]["plan"] == "確認盤點分工"
    assert [entry["text"] for entry in initial[1]["messages"]] == ["開場原文"]
    assert initial[-2] == {
        "data_kind": "employee_input",
        "ref": interview_ref(model.requests[0], " 第一次原文\n"),
        "text": " 第一次原文\n",
    }
    first_ref = initial[-2]["ref"]
    assert initial[-1]["first_ref"] == interview_ref(model.requests[0], "開場原文")
    assert initial[-1]["last_ref"] == first_ref
    assert first_ref.startswith("message_")
    assert interview_ref(model.requests[3], " 第一次原文\n") == first_ref
    renewed = [json.loads(item["content"]) for item in model.requests[7]["input"]]
    assert renewed[0]["work_situation_map"]["items"][0]["target_title"] == "盤點"
    assert [item.get("data_kind", item.get("source")) for item in renewed] == [
        "memory_navigation",
        "consultant_interview_plan",
        "employee_input",
        "interview_navigation",
    ]
    assert renewed[-2]["text"] == "第三次原文"
    assert renewed[-3]["plan"] == f"確認盤點分工\n原話定位：{first_ref}"
    assert renewed[-1]["last_ref"] == renewed[-2]["ref"]
    assert not model.counts  # 關閉原生壓縮時，換窗不呼叫計數／壓縮 API。
    assert json.loads(model.requests[8]["input"][-2]["content"])["text"] == "第四次原文"
    assert tool_outputs(model.requests[9])["before-window"]["messages"] == [
        {
            "ref": first_ref,
            "speaker": "employee",
            "kind": "text",
            "text": " 第一次原文\n",
            "reply_to": None,
        }
    ]


def test_history_compacts_before_new_input_and_cold_resume_keeps_adopted_window(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    payload = compacted_payload()
    compacts: list[dict[str, Any]] = []

    class CompactModel(WindowModel):
        def __call__(self, request: httpx2.Request) -> httpx2.Response:
            body = request_body(request)
            if request.url.path.endswith("input_tokens"):
                self.counts.append(body)
                old_history = body["input"][-1].get("role") == "assistant"
                return httpx2.Response(
                    200,
                    json={
                        "object": "response.input_tokens",
                        "input_tokens": 96000 if old_history else 1,
                    },
                )
            if request.url.path.endswith("compact"):
                compacts.append(body)
                return httpx2.Response(200, json=payload)
            return OfflineMemoryModel.__call__(self, request)

    model = CompactModel([complete("歷史回覆"), None, complete("恢復完成")])
    pending = uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine,
            checkpoint_conninfo,
            model,
            context_window=True,
            native_compaction=True,
        ) as (agent, _, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="舊原文"
                )
            )
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=pending,
                        input="新輸入不可先送compact",
                    )
                )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            compacted = saved.values["compaction_response"]
            assert isinstance(compacted, CompactedResponse)
            assert (
                compacted.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )
        async with open_memory_flow(
            pg_engine,
            checkpoint_conninfo,
            model,
            context_window=True,
            native_compaction=True,
            initialize=False,
        ) as (agent, _, _):
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            compacted = saved.values["compaction_response"]
            assert isinstance(compacted, CompactedResponse)
            assert (
                compacted.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=pending))
            resumed = await agent.aget_state(workspace_id=jd_workspace_id)
            compacted = resumed.values["compaction_response"]
            assert isinstance(compacted, CompactedResponse)
            assert (
                compacted.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )
            history = [
                snapshot
                async for snapshot in agent.aget_state_history(
                    workspace_id=jd_workspace_id
                )
            ]
            (observed,) = compaction_views(history, pending)
            assert observed.response_id == compacted.id
            assert observed.model_step == 0
            assert observed.usage is not None
            assert observed.usage.total_tokens == compacted.usage.total_tokens

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(compacts) == 1 and len(model.counts) == 3
    assert compacts[0]["input"] == model.counts[1]["input"]
    assert compacts[0]["input"][-1]["role"] == "assistant"
    for request_field in ("model", "instructions", "tools"):
        assert model.counts[1][request_field] == model.requests[1][request_field]
    assert compacts[0]["instructions"] == model.requests[1]["instructions"]
    assert "新輸入不可先送compact" not in json.dumps(
        compacts[0]["input"], ensure_ascii=False
    )
    assert model.requests[1]["input"][:-2] == payload["output"]
    assert (
        json.loads(model.requests[1]["input"][-2]["content"])["text"]
        == "新輸入不可先送compact"
    )
    assert model.requests[1]["input"] == model.requests[2]["input"]
    pending_ref = interview_ref(model.requests[1], "新輸入不可先送compact")
    assert pending_ref.startswith("message_")
    assert interview_ref(model.requests[2], "新輸入不可先送compact") == pending_ref
    assert interview_ref(model.requests[0], "舊原文") != pending_ref


def test_publication_during_pending_turn_keeps_capture_and_cancelled_renewal_rebuilds(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    model = WindowModel(
        [
            [tool("request_memory_consolidation", "request")],
            complete("已完成舊輪"),
            None,
            lambda request: [
                tool(
                    "create_work_situation",
                    "s",
                    title="盤點",
                    description="庫存",
                    body="逐筆核對",
                    interview_references=[interview_ref(request, "第一輪原話")],
                )
            ],
            complete(),
            [
                tool(
                    "create_work_understanding",
                    "u",
                    title="責任",
                    description="本人範圍",
                    body="本人核對",
                    work_situation_references=["盤點"],
                )
            ],
            complete(),
            complete("恢復原輪"),
            None,
            complete("取消後重建"),
        ]
    )
    first, pending, cancelled = uuid4(), uuid4(), uuid4()

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True
        ) as (agent, coordinator, _):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=first, input="第一輪原話"
                )
            )
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=pending,
                        input="待恢復原話",
                    )
                )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=first
            )
            assert published is not None
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, context_window=True, initialize=False
        ) as (agent, _, _):
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=pending))
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["memory_published_version"] is None
            assert model.requests[2]["input"] == model.requests[7]["input"]
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=cancelled,
                        input="取消的原話",
                    )
                )
            await agent.acancel_turn(workspace_id=jd_workspace_id, turn_id=cancelled)
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="重新開始原話"
                )
            )
            saved = await agent.aget_state(workspace_id=jd_workspace_id)
            assert saved.values["memory_published_version"] == published.version
            assert model.requests[8]["input"][:-2] == model.requests[9]["input"][:-2]
            before, after = (
                json.loads(model.requests[index]["input"][-2]["content"])
                for index in (8, 9)
            )
            assert before["ref"] != after["ref"]
            assert before["ref"].startswith("message_")
            assert after["ref"].startswith("message_")
            assert "取消的原話" not in json.dumps(
                model.requests[9]["input"], ensure_ascii=False
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
