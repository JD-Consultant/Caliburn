"""Memory 角色走真 PostgreSQL 與原生保存，模型只走離線 transport。"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.context.history import previous_completed_window
from caliburn.bundles.context.services import (
    COMPACTION_CLIENT,
    COMPLETED_TURNS,
    PREVIOUS_WINDOW,
)
from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.bundles.job_description.services import JD_UOW_FACTORY
from caliburn.bundles.memory import coordinator as coordination
from caliburn.bundles.memory import writes
from caliburn.bundles.memory.completion import InvalidMemoryCompletion
from caliburn.bundles.memory.coordinator import (
    MemoryAnalysisCoordinator,
    completed_consultant_turns,
    open_memory_role_agent,
)
from caliburn.bundles.memory.services import (
    MEMORY_COMPLETED_TURNS,
    MEMORY_QUERIES,
)
from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.host.consultant import compose_consultant_bundles
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.openai.call_model import ModelResponseError
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.state import AgentLimitError
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.memory.application.errors import MemoryPersistenceError
from caliburn.modules.memory.application.results import MemoryUpdateResult
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.errors import InvalidMemorySourceError
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.domain.text_editing.body_edits import EditLimits
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.memory_reference_support import (
    interview_material,
    interview_ref,
)
from tests.integration.agent.plan_plugin_support import tool_outputs
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    message,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def tool(name: str, call_id: str, **arguments: object) -> dict[str, object]:
    return call(name=name, call_id=call_id, arguments=json.dumps(arguments))


def complete(text: str = '{"status":"complete"}') -> list[dict[str, object]]:
    return [message(text=text)]


@dataclass
class OfflineMemoryModel:
    replies: list[
        list[dict[str, object]]
        | Callable[[dict[str, Any]], list[dict[str, object]]]
        | None
    ]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request_body(request))
        output = self.replies[len(self.requests) - 1]
        if callable(output):
            output = output(self.requests[-1])
        payload = response_payload(
            output, status="failed" if output is None else "completed"
        )
        return sse_response(EventStream(response_events(payload)))


@asynccontextmanager
async def open_memory_flow(
    engine: Engine,
    checkpoint_conninfo: str,
    model: OfflineMemoryModel,
    *,
    initialize: bool = True,
    max_tool_result_characters: int = 1_000_000,
    context_window: bool = False,
    native_compaction: bool = False,
) -> AsyncIterator[tuple[Agent, MemoryAnalysisCoordinator, SqlAlchemyMemoryQueries]]:
    sessions = create_session_factory(engine)
    interview = SqlAlchemyInterviewQueries(engine)
    memory = SqlAlchemyMemoryQueries(engine)
    references = SqlAlchemyModelReferences(sessions)

    async def completed(workspace_id: UUID) -> frozenset[UUID]:
        return await completed_consultant_turns(consultant, workspace_id=workspace_id)

    async def previous(workspace_id: UUID, turn_id: UUID) -> Any:
        return await previous_completed_window(
            consultant, workspace_id=workspace_id, turn_id=turn_id
        )

    async with (
        open_postgres_checkpointer(checkpoint_conninfo, initialize=initialize) as saver,
        offline_client(httpx2.MockTransport(model)) as client,
        open_agent(
            agent_id="memory-integration",
            resume_version="memory-v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=compose_consultant_bundles(
                (
                    BundleConfig(
                        "caliburn.bundles.interview",
                        plugins=(
                            "interview",
                            *(("interview_context",) if not context_window else ()),
                            "interview_source_prompt",
                        ),
                    ),
                    BundleConfig(
                        "caliburn.bundles.memory",
                        plugins=(
                            "memory_context",
                            "memory_prompt",
                            "memory_read",
                            "memory_consolidation",
                            *(("memory_window",) if context_window else ()),
                        ),
                    ),
                    *(
                        (
                            BundleConfig("caliburn.bundles.plan"),
                            BundleConfig(
                                "caliburn.bundles.context",
                                plugins=(
                                    "window",
                                    *(
                                        ("native_compaction",)
                                        if native_compaction
                                        else ()
                                    ),
                                ),
                            ),
                        )
                        if context_window
                        else ()
                    ),
                )
            ),
            checkpointer=saver,
            external_services=(
                MODEL_REFERENCES.bind(references),
                JD_UOW_FACTORY.bind(
                    partial(SqlAlchemyJobDescriptionUnitOfWork, sessions)
                ),
                COMPACTION_CLIENT.bind(client),
                PREVIOUS_WINDOW.bind(previous),
                COMPLETED_TURNS.bind(completed),
                PLAN_QUERIES.bind(SqlAlchemyPlanQueries(engine)),
                PLAN_UOW_FACTORY.bind(partial(SqlAlchemyPlanUnitOfWork, sessions)),
                INTERVIEW_UOW_FACTORY.bind(
                    partial(SqlAlchemyInterviewUnitOfWork, sessions)
                ),
                INTERVIEW_QUERIES.bind(interview),
                MEMORY_QUERIES.bind(memory),
                MEMORY_COMPLETED_TURNS.bind(completed),
            ),
        ) as consultant,
    ):
        coordinator = MemoryAnalysisCoordinator(
            consultant=consultant,
            interview_queries=interview,
            queries=memory,
            uow_factory=partial(SqlAlchemyMemoryUnitOfWork, sessions),
            open_role_agent=partial(
                open_memory_role_agent,
                agent_id="memory-integration",
                resume_version="memory-v1",
                client=client,
                model_settings=MODEL_REQUEST,
                checkpointer=saver,
                queries=memory,
                references=references,
                max_tool_result_characters=max_tool_result_characters,
            ),
        )
        yield consultant, coordinator, memory


def test_completed_consultant_admits_b1_and_reopen_resumes_b2_only(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    employee_input = " 我逐筆核對庫存差異，再交由主管複核。\n"
    model = OfflineMemoryModel(
        [
            [
                tool("read_work_situation_map", "initial-map"),
                tool("request_memory_consolidation", "request"),
            ],
            [message(text="已了解。")],
            lambda request: [
                tool(
                    "read_interview",
                    "b1-source",
                    query={
                        "kind": "range",
                        "start_ref": interview_ref(request, employee_input),
                        "end_ref": interview_ref(request, employee_input),
                    },
                ),
                tool(
                    "create_work_situation",
                    "s",
                    title="盤點",
                    description="日常工作",
                    body="我逐筆核對庫存差異，再交由主管複核。",
                    interview_references=[interview_ref(request, employee_input)],
                ),
            ],
            complete(),
            None,
            lambda request: [
                tool(
                    "read_interview",
                    "b2-source",
                    query={
                        "kind": "messages",
                        "refs": [interview_ref(model.requests[2], employee_input)],
                    },
                ),
                tool(
                    "create_work_understanding",
                    "u",
                    title="盤點責任",
                    description="本人範圍",
                    body="負責逐筆核對差異，主管複核。",
                    work_situation_references=["盤點"],
                ),
            ],
            complete(),
            [tool("read_work_understanding", "published", target_title="盤點責任")],
            [message(text="可查閱盤點責任。")],
        ]
    )
    turn_id = uuid4()

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
                is None
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=turn_id, input=employee_input
                )
            )
            with pytest.raises(ModelResponseError):
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.analysis and root.analysis.phase == "understanding"
            assert root.published_version is None
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, initialize=False
        ) as (agent, coordinator, memory):
            first, duplicate = await asyncio.gather(
                coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id),
                coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id),
            )
            assert first is not None and duplicate is None
            assert (
                memory.get_current(workspace_id=jd_workspace_id).published_version
                == first.version
            )
            assert {item.content.title for item in first.items} == {"盤點", "盤點責任"}
            next_turn = uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=next_turn, input="繼續"
                )
            )
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=next_turn)
                is None
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[1])["initial-map"] == {"items": []}
    b1, b2 = (
        json.loads(model.requests[index]["input"][0]["content"]) for index in (2, 4)
    )
    assert b1["work_situation_map"] == {"items": []}
    ref = interview_ref(model.requests[2], employee_input)
    assert interview_material(model.requests[2])["messages"] == [
        {
            "ref": ref,
            "speaker": "employee",
            "kind": "text",
            "text": employee_input,
            "reply_to": None,
            "supporting_question": False,
        },
        {
            "ref": interview_ref(model.requests[2], "已了解。"),
            "speaker": "consultant",
            "kind": "text",
            "text": "已了解。",
            "reply_to": None,
            "supporting_question": False,
        },
    ]
    assert "work_understanding_map" not in b1
    assert {item["name"] for item in model.requests[2]["tools"]}.isdisjoint(
        {"read_work_understanding", "create_work_understanding"}
    )
    assert b2["work_understanding_map"] == {"items": []}
    assert b2["work_situation_changes"][0]["target_title"] == "盤點"
    assert "逐筆核對庫存差異" in b2["work_situation_changes"][0]["diff"]
    assert "create_work_situation" not in {
        item["name"] for item in model.requests[4]["tools"]
    }
    assert (
        tool_outputs(model.requests[3])["b1-source"]["messages"][0]["text"]
        == employee_input
    )
    assert (
        tool_outputs(model.requests[6])["b2-source"]["messages"][0]["text"]
        == employee_input
    )
    assert tool_outputs(model.requests[3])["b1-source"]["messages"][0]["ref"] == ref
    assert tool_outputs(model.requests[6])["b2-source"]["messages"][0]["ref"] == ref
    assert tool_outputs(model.requests[8])["published"][
        "work_situation_references"
    ] == [{"target_title": "盤點", "description": "日常工作"}]


def test_consultant_pinned_empty_remains_empty_during_publication(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "request")],
            [message(text="收到。")],
            None,
            lambda request: [
                tool(
                    "create_work_situation",
                    "s",
                    title="盤點",
                    description="庫存",
                    body="核對。",
                    interview_references=[interview_ref(request, "我核對庫存。")],
                )
            ],
            complete(),
            complete(),
            [tool("read_work_situation_map", "empty-after-publish")],
            [message(text="本輪的原始資料。")],
            [tool("read_work_situation_map", "new-pin")],
            [message(text="新輪資料。")],
        ]
    )

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            first, pinned, new = uuid4(), uuid4(), uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=first, input="我核對庫存。"
                )
            )
            with pytest.raises(ModelResponseError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=pinned, input="尚未完成。"
                    )
                )
            assert (await agent.aget_state(workspace_id=jd_workspace_id)).values[
                "memory_published_version"
            ] is None
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=first
            )
            assert published is not None
            assert (
                memory.get_current(workspace_id=jd_workspace_id).published_version
                == published.version
            )
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=pinned))
            assert (await agent.aget_state(workspace_id=jd_workspace_id)).values[
                "memory_published_version"
            ] is None
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=new, input="新的顧問輪。"
                )
            )
            assert (await agent.aget_state(workspace_id=jd_workspace_id)).values[
                "memory_published_version"
            ] == published.version

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert tool_outputs(model.requests[7])["empty-after-publish"] == {"items": []}
    assert tool_outputs(model.requests[9])["new-pin"] == {
        "items": [{"target_title": "盤點", "description": "庫存"}]
    }


def test_capacity_rejects_before_writing_and_invalid_b2_cannot_publish(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(writes, "_LIMITS", EditLimits(1000, 64_000, 128, 20_000_000))
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "request")],
            [message(text="收到。")],
            lambda request: [
                tool(
                    "create_work_situation",
                    "too-large-create",
                    title="超量正文",
                    description="不該保存",
                    body="文" * 1001,
                    interview_references=[],
                ),
                tool(
                    "create_work_situation",
                    "create",
                    title="原標題",
                    description="原導覽",
                    body="原本完整正文",
                    interview_references=[interview_ref(request, "原本完整正文")],
                ),
                tool(
                    "update_work_situation",
                    "too-large",
                    target_title="原標題",
                    changes=[
                        {"field": "title", "value": "不能先改標題"},
                        {
                            "field": "body",
                            "diff": "@@\n-原本完整正文\n+" + "新正文" * 200,
                        },
                    ],
                ),
                tool("read_work_situation", "still-original", target_title="原標題"),
            ],
            complete(),
            complete('{"status":"complete","status":"complete"}'),
            [message(text="補充一。")],
            [message(text="補充二。")],
            [message(text="補充三。")],
            complete(),
            complete(),
        ]
    )

    async def run() -> None:
        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, max_tool_result_characters=128
        ) as (agent, coordinator, memory):
            turn_id = uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=turn_id, input="原本完整正文"
                )
            )
            intent_messages = SqlAlchemyInterviewQueries(pg_engine).list_messages(
                workspace_id=jd_workspace_id, turn_id=turn_id
            )
            assert intent_messages[-1].text == "收到。"
            intent_through = intent_messages[-1].message_id
            with pytest.raises(InvalidMemoryCompletion):
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.published_version is None
            assert root.analysis is None and not root.items
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=turn_id)
                is None
            )
            assert len(model.requests) == 5
            for index in range(3):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input=f"新資料 {index}",
                    )
                )
                result = await coordinator.run(
                    workspace_id=jd_workspace_id, turn_id=turn_id
                )
                if index < 2:
                    assert result is None
                    assert len(model.requests) == 6 + index
                else:
                    assert result is not None
                    assert len(model.requests) == 10
                    assert result.covered_through_message_id == intent_through

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    outputs = tool_outputs(model.requests[3])
    assert outputs["too-large-create"]["code"] == "patch_limit_exceeded"
    assert outputs["too-large"]["code"] == "write_result_limit_exceeded"
    assert outputs["still-original"]["body"] == "原本完整正文"


def test_exact_and_fuzzy_edits_preserve_text_and_update_sources(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    before = "每日檢查庫存差異後交由主管複核。"
    after = "每日核對庫存差異後交由主管複核。"
    model = OfflineMemoryModel(
        [
            [message(text="了解原本分工。")],
            [tool("request_memory_consolidation", "request")],
            [message(text="收到更正。")],
            lambda request: [
                tool(
                    "create_work_situation",
                    "create",
                    title="原標題",
                    description="盤點實況",
                    body=before,
                    interview_references=[
                        interview_ref(request, "我每日檢查庫存差異。")
                    ],
                ),
                tool(
                    "update_work_situation",
                    "exact",
                    target_title="原標題",
                    changes=[
                        {
                            "field": "body",
                            "diff": "@@\n-" + before + "\n+" + before + "\n+保留這行",
                        },
                    ],
                ),
            ],
            lambda request: [
                tool(
                    "update_work_situation",
                    "fuzzy",
                    target_title="原標題",
                    changes=[
                        {"field": "title", "value": "盤點"},
                        {
                            "field": "body",
                            "diff": "@@\n-每日檢查庫存差異後交由主管覆核。\n+" + after,
                        },
                        {
                            "field": "interview_references",
                            "add": [
                                interview_ref(
                                    request, "更正說法：我核對差異，再交給主管。"
                                )
                            ],
                            "remove": [interview_ref(request, "我每日檢查庫存差異。")],
                        },
                    ],
                ),
                tool("read_work_situation_map", "renamed"),
            ],
            complete(),
            complete(),
        ]
    )

    async def run() -> None:
        turn_id = uuid4()
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            _,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=uuid4(),
                    input="我每日檢查庫存差異。",
                )
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input="更正說法：我核對差異，再交給主管。",
                )
            )
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=turn_id
            )
            assert published is not None
            assert published.items[0].content.body == after + "\n保留這行"
            assert published.items[0].content.title == "盤點"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert (
        "+保留這行"
        in tool_outputs(model.requests[4])["exact"]["applied_changes"][0]["diff"]
    )
    outputs = tool_outputs(model.requests[5])
    assert outputs["fuzzy"]["status"] == "updated"
    assert outputs["fuzzy"]["title"] == "盤點"
    changes = outputs["fuzzy"]["applied_changes"]
    assert f"-{before}" in changes[1]["diff"] and f"+{after}" in changes[1]["diff"]
    assert changes[2] == {
        "field": "interview_references",
        "added": [
            interview_ref(model.requests[3], "更正說法：我核對差異，再交給主管。")
        ],
        "removed": [interview_ref(model.requests[3], "我每日檢查庫存差異。")],
    }
    assert outputs["renamed"]["items"][0]["target_title"] == "盤點"


def test_b1_can_remove_withdrawn_reference_and_b2_still_receives_diff(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
) -> None:
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "old-request")],
            [message(text="收到原話。")],
            lambda request: [
                tool(
                    "create_work_situation",
                    "create",
                    title="盤點",
                    description="庫存",
                    body="逐筆核對。",
                    interview_references=[interview_ref(request, "我逐筆核對庫存。")],
                )
            ],
            complete(),
            complete(),
            [tool("request_memory_consolidation", "new-request")],
            [message(text="收到新原話。")],
            lambda request: [
                tool("read_work_situation", "before", target_title="盤點"),
                tool(
                    "read_interview",
                    "withdrawn",
                    query={
                        "kind": "messages",
                        "refs": [interview_ref(model.requests[2], "我逐筆核對庫存。")],
                    },
                ),
                tool(
                    "update_work_situation",
                    "replace-ref",
                    target_title="盤點",
                    changes=[
                        {
                            "field": "interview_references",
                            "remove": [
                                interview_ref(model.requests[2], "我逐筆核對庫存。")
                            ],
                            "add": [interview_ref(request, "確認目前逐筆核對。")],
                        },
                    ],
                ),
                tool(
                    "update_work_situation",
                    "readd-withdrawn",
                    target_title="盤點",
                    changes=[
                        {
                            "field": "interview_references",
                            "add": [
                                interview_ref(model.requests[2], "我逐筆核對庫存。")
                            ],
                        }
                    ],
                ),
            ],
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
            first, second = uuid4(), uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=first,
                    input="我逐筆核對庫存。",
                )
            )
            old = await coordinator.run(workspace_id=jd_workspace_id, turn_id=first)
            assert old is not None
            await asyncio.to_thread(
                withdraw_turn,
                workspace_id=jd_workspace_id,
                turn_id=first,
                uow_factory=partial(
                    SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
                ),
            )
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=second,
                    input="確認目前逐筆核對。",
                )
            )
            new = await coordinator.run(workspace_id=jd_workspace_id, turn_id=second)
            assert new is not None
            assert new.items[0].id == old.items[0].id
            assert new.covered_through_message_id != old.covered_through_message_id

            assert (
                memory.get_published(
                    workspace_id=jd_workspace_id, published_version=old.version
                )
                == old
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    b1 = json.loads(model.requests[7]["input"][0]["content"])
    old_ref = interview_ref(model.requests[2], "我逐筆核對庫存。")
    new_ref = interview_ref(model.requests[7], "確認目前逐筆核對。")
    assert b1["unavailable_interview_refs"] == [old_ref]
    outputs = tool_outputs(model.requests[8])
    assert outputs["before"]["interview_references"] == [old_ref]
    assert outputs["withdrawn"]["code"] == "scope_not_allowed"
    assert outputs["replace-ref"]["status"] == "updated"
    assert outputs["readd-withdrawn"]["code"] == "source_not_available"
    b2 = json.loads(model.requests[9]["input"][0]["content"])
    assert f"-訪談引用：{old_ref}" in b2["work_situation_changes"][0]["diff"]
    assert f"+訪談引用：{new_ref}" in b2["work_situation_changes"][0]["diff"]


@pytest.mark.parametrize("retry_old_request", [True, False])
def test_withdrawn_frozen_window_settles_and_later_intent_can_publish(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
    retry_old_request: bool,
) -> None:
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "old")],
            [message(text="先前的原話。")],
            lambda request: [
                tool(
                    "create_work_situation",
                    "old-s",
                    title="先前情境",
                    description="失效的整理",
                    body="舊來源",
                    interview_references=[interview_ref(request, "先前員工原話。")],
                ),
            ],
            complete(),
            complete(),
            [tool("request_memory_consolidation", "new")],
            [message(text="新的原話。")],
            *(
                [message(text="後續完成的正式訪談。")]
                for _ in range(2 if retry_old_request else 3)
            ),
            complete(),
            complete(),
        ]
    )

    def fail_before_commit(
        service: MemoryService, *args: object, **kwargs: object
    ) -> MemoryUpdateResult:
        raise MemoryPersistenceError(commit_status="not_committed")

    async def run() -> None:
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            old, new = uuid4(), uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=old, input="先前員工原話。"
                )
            )
            with monkeypatch.context() as fault:
                fault.setattr(MemoryService, "publish", fail_before_commit)
                with pytest.raises(MemoryPersistenceError):
                    await coordinator.run(workspace_id=jd_workspace_id, turn_id=old)
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.analysis is not None and root.analysis.phase == "understanding"
            assert root.published_version is None and root.situations

            await asyncio.to_thread(
                withdraw_turn,
                workspace_id=jd_workspace_id,
                turn_id=old,
                uow_factory=partial(
                    SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
                ),
            )
            if retry_old_request:
                with pytest.raises(InvalidMemorySourceError):
                    await coordinator.run(workspace_id=jd_workspace_id, turn_id=old)
                assert memory.get_current(workspace_id=jd_workspace_id).analysis is None

            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=new, input="新一輪員工原話。"
                )
            )
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=new) is None
            )
            assert len(model.requests) == 7
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.published_version is None
            assert root.analysis is None and not root.items
            assert root.failure is not None
            assert root.failure.reason == "invalid_source_window"
            count = 2 if retry_old_request else 3
            for i in range(count):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input=f"後續原話 {i}",
                    )
                )
                result = await coordinator.run(
                    workspace_id=jd_workspace_id, turn_id=new
                )
                if i < count - 1:
                    assert result is None
                else:
                    assert result is not None and not result.items
            assert len(model.requests) == 7 + count + 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_exhausted_analysis_releases_the_workspace_after_six_formal_messages(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = OfflineMemoryModel(
        [
            [tool("request_memory_consolidation", "initial")],
            [message(text="收到原先分工。")],
            complete(),
            complete(),
            [tool("request_memory_consolidation", "limited")],
            [message(text="收到整理要求。")],
            [
                tool(
                    "create_work_situation",
                    "candidate",
                    title="只在失敗稿",
                    description="分工",
                    body="第一次分析尚未完成。",
                    interview_references=[],
                )
            ],
            [tool("request_memory_consolidation", "next")],
            [message(text="收到新一輪原話。")],
            [message(text="補充一。")],
            [message(text="補充二。")],
            complete(),
            complete(),
        ]
    )

    async def run() -> None:
        old, limited, new = uuid4(), uuid4(), uuid4()
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            memory,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=old, input="我負責庫存盤點。"
                )
            )
            old_publication = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=old
            )
            assert old_publication is not None
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=limited,
                    input="盤點時也會核對入庫單。",
                )
            )
            with monkeypatch.context() as limit:
                limit.setattr(
                    coordination, "open_agent", partial(open_agent, max_model_steps=1)
                )
                with pytest.raises(AgentLimitError, match="Model step limit reached"):
                    await coordinator.run(workspace_id=jd_workspace_id, turn_id=limited)
            root = memory.get_current(workspace_id=jd_workspace_id)
            assert root.analysis is None and not root.items
            assert root.published_version == old_publication.version
            assert root.failure is not None and root.failure.reason == "analysis_limit"
            assert len(model.requests) == 7

        async with open_memory_flow(
            pg_engine, checkpoint_conninfo, model, initialize=False
        ) as (agent, coordinator, memory):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=new,
                    input="確認這是每週工作。",
                )
            )
            assert (
                await coordinator.run(workspace_id=jd_workspace_id, turn_id=new) is None
            )
            for i in range(2):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=uuid4(),
                        input=f"後續原話 {i}",
                    )
                )
                publication = await coordinator.run(
                    workspace_id=jd_workspace_id, turn_id=new
                )
                if i == 0:
                    assert publication is None
                else:
                    assert publication is not None
                    assert publication.version > old_publication.version
            assert len(model.requests) == 13
            assert memory.get_current(workspace_id=jd_workspace_id).failure is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
