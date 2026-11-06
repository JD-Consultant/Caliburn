"""Interview 換窗貢獻只提供合法原話，不控制 Context 換窗或續接。"""

import asyncio
import json
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from langgraph.runtime import Runtime

from caliburn.bundles.context.services import COMPLETED_TURNS
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.bundles.interview.window import (
    prepare_interview_input,
    prepare_interview_window,
)
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.agent.state import AgentState, request_items
from caliburn.modules.interview.application.recording import (
    record_consultant_message,
    record_opening,
    record_turn_input,
)
from caliburn.modules.interview.application.results import MessageView
from caliburn.modules.model_references import ModelReferences, ReferenceTarget
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST
from tests.unit.modules.interview.memory_store import MemoryInterviewStore


def test_rebuild_projects_only_completed_dialogue_and_app_originals() -> None:
    workspace, completed, unfinished, current = (uuid4() for _ in range(4))
    store = MemoryInterviewStore()
    opening = record_opening(
        workspace_id=workspace, text="開場原文", uow_factory=store.uow_factory
    )
    completed_messages: list[MessageView] = []
    for turn_id, text in (
        (completed, "  合法員工原文\n "),
        (unfinished, "未完成原文"),
        (current, "本輪原文"),
    ):
        employee = record_turn_input(
            workspace_id=workspace,
            turn_id=turn_id,
            text=text,
            uow_factory=store.uow_factory,
        )
        consultant = record_consultant_message(
            workspace_id=workspace,
            turn_id=turn_id,
            text="回覆",
            uow_factory=store.uow_factory,
        )
        if turn_id == completed:
            completed_messages.extend((employee, consultant))

    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.return_value = {
        ReferenceTarget("message", opening.message_id): "message_41",
        ReferenceTarget("message", completed_messages[0].message_id): "message_2",
        ReferenceTarget("message", completed_messages[1].message_id): "message_90",
    }

    async def completed_turns(workspace_id: UUID) -> frozenset[UUID]:
        assert workspace_id == workspace
        return frozenset({completed})

    state: AgentState = {
        "workspace_id": workspace,
        "turn_id": current,
        "turn_input": "本輪原文",
        "model_request": {**MODEL_REQUEST, "input": []},
    }
    runtime = Runtime(
        context=AgentContext(
            PluginServices(
                {
                    INTERVIEW_QUERIES: store,
                    COMPLETED_TURNS: completed_turns,
                    MODEL_REFERENCES: references,
                }
            )
        )
    )

    async def run() -> None:
        update = await prepare_interview_window(
            state, previous=None, rebuilding=True, runtime=runtime
        )
        assert set(update) == {"model_request"}
        request = update["model_request"]
        assert isinstance(request, dict)
        (projected,) = request["input"]
        data = json.loads(projected["content"])
        assert [(item["speaker"], item["text"]) for item in data["messages"]] == [
            ("app", "開場原文"),
            ("employee", "  合法員工原文\n "),
            ("consultant", "回覆"),
        ]
        assert [item["ref"] for item in data["messages"]] == [
            "message_41",
            "message_2",
            "message_90",
        ]
        assert all("position" not in item for item in data["messages"])

    asyncio.run(run())
    assert request_items(state["model_request"]) == []
    assert state["turn_input"] == "本輪原文"


@pytest.mark.parametrize(
    ("rebuilding", "preload"), [(False, True), (True, False), (False, False)]
)
def test_disabled_or_continuing_window_does_not_query_or_reinsert_history(
    rebuilding: bool, preload: bool
) -> None:
    runtime = Runtime(context=AgentContext(PluginServices({})))
    state: AgentState = {}
    assert (
        asyncio.run(
            prepare_interview_window(
                state,
                previous={},
                rebuilding=rebuilding,
                runtime=runtime,
                preload=preload,
            )
        )
        == {}
    )


@pytest.mark.parametrize("rebuilding", [False, True])
@pytest.mark.parametrize("include_input_reference", [False, True])
@pytest.mark.parametrize("include_navigation", [False, True])
def test_input_callback_preserves_native_input_and_projects_only_enabled_metadata(
    rebuilding: bool, include_input_reference: bool, include_navigation: bool
) -> None:
    workspace, current = uuid4(), uuid4()
    store = MemoryInterviewStore()
    opening = record_opening(
        workspace_id=workspace, text="開場原文", uow_factory=store.uow_factory
    )
    original = "  本輪原文 message_777\n "
    saved = record_turn_input(
        workspace_id=workspace,
        turn_id=current,
        text=original,
        uow_factory=store.uow_factory,
    )
    before = store.list_messages(workspace_id=workspace)
    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.return_value = {
        ReferenceTarget("message", opening.message_id): "message_41",
        ReferenceTarget("message", saved.message_id): "message_2",
    }
    runtime = Runtime(
        context=AgentContext(
            PluginServices({INTERVIEW_QUERIES: store, MODEL_REFERENCES: references})
        )
    )
    state: AgentState = {
        "workspace_id": workspace,
        "turn_id": current,
        "turn_input": original,
        "model_request": {
            **MODEL_REQUEST,
            "input": [{"role": "user", "content": original}],
        },
    }
    update = asyncio.run(
        prepare_interview_input(
            state,
            previous={} if not rebuilding else None,
            rebuilding=rebuilding,
            runtime=runtime,
            include_input_reference=include_input_reference,
            include_navigation=include_navigation,
        )
    )
    request = update["model_request"]
    assert isinstance(request, dict)
    assert request["input"][0] == {"role": "user", "content": original}
    projected = [json.loads(item["content"]) for item in request["input"][1:]]
    expected = []
    if include_input_reference:
        expected.append({"data_kind": "employee_input_reference", "ref": "message_2"})
    if include_navigation:
        expected.append(
            {
                "data_kind": "interview_navigation",
                "first_ref": "message_41",
                "last_ref": "message_2",
                "scope": "目前有效訪談，含本輪已保存原話；空集合兩端為 null。",
            }
        )
    assert projected == expected
    assert request_items(state["model_request"]) == [
        {"role": "user", "content": original}
    ]
    assert store.list_messages(workspace_id=workspace) == before


def test_enabled_input_reference_rejects_missing_saved_input() -> None:
    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.return_value = {}
    runtime = Runtime(
        context=AgentContext(
            PluginServices(
                {
                    INTERVIEW_QUERIES: MemoryInterviewStore(),
                    MODEL_REFERENCES: references,
                }
            )
        )
    )
    state: AgentState = {
        "workspace_id": uuid4(),
        "turn_id": uuid4(),
        "turn_input": "尚未正式保存的原文",
        "model_request": {
            **MODEL_REQUEST,
            "input": [{"role": "user", "content": "尚未正式保存的原文"}],
        },
    }
    with pytest.raises(ValueError, match="本輪已保存的員工輸入不可用"):
        asyncio.run(
            prepare_interview_input(
                state, previous=None, rebuilding=True, runtime=runtime
            )
        )
