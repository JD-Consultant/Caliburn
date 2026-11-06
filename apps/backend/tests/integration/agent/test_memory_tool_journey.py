"""經實際 OpenAI adapter 驗證兩個分析層的公開編修旅程。"""

import asyncio
from functools import partial
from uuid import UUID, uuid4

from sqlalchemy import Engine

from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.memory.domain.items import WorkSituation, WorkUnderstanding
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.memory_reference_support import interview_ref
from tests.integration.agent.plan_plugin_support import tool_outputs
from tests.integration.agent.stream_support import consume
from tests.integration.agent.test_memory_flow import (
    OfflineMemoryModel,
    complete,
    open_memory_flow,
    tool,
)
from tests.unit.modules.agent.offline_openai import message


def test_public_memory_tools_revise_and_delete_each_own_layer(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    original = "開頭\n逐筆核對\n逐筆核對\n結尾"
    outside_ref = ""
    model = OfflineMemoryModel(
        [
            [message(text="了解先前做法。")],
            [tool("request_memory_consolidation", "request")],
            [message(text="收到補充。")],
            lambda request: [
                tool(
                    "read_interview",
                    "selection",
                    query={
                        "kind": "messages",
                        "refs": [
                            interview_ref(request, "核對後由主管複核。"),
                            interview_ref(request, "我逐筆核對差異。"),
                            interview_ref(request, "核對後由主管複核。"),
                        ],
                    },
                ),
                tool(
                    "read_interview",
                    "out-of-scope",
                    query={
                        "kind": "messages",
                        "refs": [
                            interview_ref(request, "我逐筆核對差異。"),
                            outside_ref,
                        ],
                    },
                ),
                tool(
                    "create_work_situation",
                    "sa",
                    title="盤點 A",
                    description="初始導覽",
                    body=original,
                    interview_references=[interview_ref(request, "我逐筆核對差異。")],
                ),
                tool(
                    "create_work_situation",
                    "sb",
                    title="盤點 B",
                    description="補充導覽",
                    body="核對後交接主管。",
                    interview_references=[interview_ref(request, "核對後由主管複核。")],
                ),
                tool(
                    "create_work_situation",
                    "temp-s",
                    title="待刪情境",
                    description="暫存",
                    body="暫存正文",
                    interview_references=[],
                ),
                tool("delete_work_situation", "delete-s", target_title="待刪情境"),
            ],
            [
                tool("read_work_situation", "short-title", target_title="盤點"),
                tool(
                    "update_work_situation",
                    "ambiguous",
                    target_title="盤點 A",
                    changes=[
                        {"field": "title", "value": "不應出現"},
                        {"field": "description", "value": "不應採用"},
                        {"field": "body", "diff": "@@\n-逐筆核對\n+逐筆分類"},
                    ],
                ),
                tool("read_work_situation", "unchanged", target_title="盤點 A"),
                tool(
                    "update_work_situation",
                    "describe",
                    target_title="盤點 A",
                    changes=[
                        {"field": "description", "value": "差異比對"},
                    ],
                ),
            ],
            complete(),
            [
                tool(
                    "create_work_understanding",
                    "create-u",
                    title="原理解",
                    description="工作概述",
                    body="核對數量。",
                    work_situation_references=["盤點 A"],
                ),
                tool(
                    "create_work_understanding",
                    "temp-u",
                    title="待刪理解",
                    description="暫存",
                    body="暫存正文",
                    work_situation_references=[],
                ),
                tool(
                    "update_work_understanding",
                    "edit-u",
                    target_title="原理解",
                    changes=[
                        {"field": "title", "value": "核對後交接"},
                        {"field": "description", "value": "本人負責範圍"},
                        {
                            "field": "body",
                            "diff": "@@\n-核對數量。\n+核對差異後交由主管。",
                        },
                        {
                            "field": "work_situation_references",
                            "add": ["盤點 B"],
                            "remove": ["盤點 A"],
                        },
                    ],
                ),
                tool("delete_work_understanding", "delete-u", target_title="待刪理解"),
                tool("read_work_understanding", "updated-u", target_title="核對後交接"),
            ],
            complete(),
        ]
    )

    async def run() -> None:
        nonlocal outside_ref
        async with open_memory_flow(pg_engine, checkpoint_conninfo, model) as (
            agent,
            coordinator,
            _,
        ):
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=uuid4(),
                    input="我逐筆核對差異。",
                )
            )
            turn_id = uuid4()
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id,
                    turn_id=turn_id,
                    input="核對後由主管複核。",
                )
            )
            sessions = create_session_factory(pg_engine)
            later_message = record_turn_input(
                workspace_id=jd_workspace_id,
                turn_id=uuid4(),
                text="較晚尚未完成的訪談不得進入固定範圍。",
                uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
            )
            target = ReferenceTarget("message", later_message.message_id)
            references = SqlAlchemyModelReferences(sessions)
            outside_ref = references.get_or_create_refs(jd_workspace_id, [target])[
                target
            ]
            assert references.resolve_refs(jd_workspace_id, [outside_ref]) == {
                outside_ref: target
            }
            published = await coordinator.run(
                workspace_id=jd_workspace_id, turn_id=turn_id
            )
            assert published is not None
            assert {item.content.title for item in published.items} == {
                "盤點 A",
                "盤點 B",
                "核對後交接",
            }
            updated = next(
                item for item in published.items if isinstance(item, WorkUnderstanding)
            )
            source = next(
                item for item in published.items if item.content.title == "盤點 B"
            )
            assert isinstance(source, WorkSituation)
            assert updated.situation_ids == (source.id,)
            assert updated.content.description == "本人負責範圍"
            assert updated.content.body == "核對差異後交由主管。"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    first_ref = interview_ref(model.requests[3], "我逐筆核對差異。")
    second_ref = interview_ref(model.requests[3], "核對後由主管複核。")
    b1_first = tool_outputs(model.requests[4])
    assert b1_first["selection"]["messages"] == [
        {
            "ref": first_ref,
            "speaker": "employee",
            "kind": "text",
            "text": "我逐筆核對差異。",
            "reply_to": None,
        },
        {
            "ref": second_ref,
            "speaker": "employee",
            "kind": "text",
            "text": "核對後由主管複核。",
            "reply_to": None,
        },
    ]
    assert b1_first["out-of-scope"]["status"] == "rejected"
    assert b1_first["out-of-scope"]["code"] == "scope_not_allowed"
    assert "messages" not in b1_first["out-of-scope"]
    assert b1_first["delete-s"] == {"status": "deleted"}
    b1_last = tool_outputs(model.requests[5])
    assert b1_last["short-title"]["code"] == "target_not_found"
    assert b1_last["ambiguous"]["code"] == "ambiguous_patch_context"
    assert b1_last["unchanged"] == {
        "title": "盤點 A",
        "description": "初始導覽",
        "body": original,
        "interview_references": [first_ref],
    }
    assert b1_last["describe"] == {
        "status": "updated",
        "title": "盤點 A",
        "description": "差異比對",
        "applied_changes": [{"field": "description"}],
    }
    b2_last = tool_outputs(model.requests[7])
    assert b2_last["edit-u"] == {
        "status": "updated",
        "title": "核對後交接",
        "description": "本人負責範圍",
        "applied_changes": [
            {"field": "title"},
            {"field": "description"},
            {
                "field": "body",
                "diff": (
                    "--- body_before\n+++ body_after\n@@ -1 +1 @@\n"
                    "-核對數量。\n\\ No newline at end of file\n"
                    "+核對差異後交由主管。\n\\ No newline at end of file\n"
                ),
            },
            {
                "field": "work_situation_references",
                "added": ["盤點 B"],
                "removed": ["盤點 A"],
            },
        ],
    }
    assert b2_last["delete-u"] == {"status": "deleted"}
    assert b2_last["updated-u"]["work_situation_references"] == [
        {"target_title": "盤點 B", "description": "補充導覽"},
    ]
