"""Plan 正文及模型已見版本必須來自同一筆查詢投影。"""

import asyncio
import json
from copy import deepcopy
from threading import current_thread, main_thread
from uuid import UUID

import pytest
from langgraph.runtime import Runtime

from caliburn.bundles.plan.context import prepare_plan_window, project_plan_context
from caliburn.bundles.plan.services import PLAN_QUERIES
from caliburn.bundles.plan.state import PlanState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.agent.state import AgentState
from caliburn.modules.plan.application.errors import PlanNotInitializedError
from caliburn.modules.plan.application.results import PlanView


@pytest.mark.parametrize(
    ("body", "version"),
    [
        ("## 目前焦點\n釐清本人分工與交接。", 7),
        (None, 1),
        ("", 9),
    ],
    ids=["body", "null", "empty"],
)
def test_projection_keeps_body_and_version_from_the_same_plan(
    body: str | None, version: int
) -> None:
    plan = PlanView(workspace_id=UUID(int=20), version=version, body=body)

    projected = project_plan_context(plan)

    assert projected["plan_version"] == version
    (item,) = projected["items"]
    assert isinstance(item, dict)
    assert set(item) == {"role", "content"}
    assert item.get("role") == "user"
    content = item.get("content")
    assert isinstance(content, str)
    assert json.loads(content) == {
        "data_kind": "consultant_interview_plan",
        "plan": body,
    }
    assert json.loads(json.dumps(projected)) == projected


def test_projection_rejects_an_uninitialized_plan() -> None:
    plan = PlanView(workspace_id=UUID(int=20), version=None, body=None)

    with pytest.raises(PlanNotInitializedError):
        project_plan_context(plan)


class PlanWindowState(AgentState, PlanState):
    pass


class CapturedQueries:
    def __init__(self, body: str | None) -> None:
        self.body = body
        self.workspace_ids: list[UUID] = []

    def get_current(self, *, workspace_id: UUID) -> PlanView:
        assert current_thread() is not main_thread()
        self.workspace_ids.append(workspace_id)
        return PlanView(workspace_id, 8, self.body)


def window_state() -> PlanWindowState:
    return {
        "workspace_id": UUID(int=20),
        "plan_turn_id": UUID(int=30),
        "plan_turn_start_version": 7,
        "plan_version": None,
        "model_request": {
            "model": "offline-test",
            "instructions": "保留原指令",
            "input": [
                {
                    "type": "compaction",
                    "id": "compact-1",
                    "encrypted_content": "opaque-content",
                },
                {"role": "user", "content": "既有資料"},
            ],
        },
    }


@pytest.mark.parametrize(
    "body", ["下一步：釐清交接", None, ""], ids=["body", "null", "empty"]
)
def test_rebuilding_appends_one_captured_plan_and_preserves_other_state(
    body: str | None,
) -> None:
    state = window_state()
    original = deepcopy(state)
    queries = CapturedQueries(body)
    runtime = Runtime(context=AgentContext(PluginServices({PLAN_QUERIES: queries})))

    update = asyncio.run(
        prepare_plan_window(
            state,
            previous={"plan_version": 3},
            rebuilding=True,
            runtime=runtime,
        )
    )

    assert set(update) == {"model_request", "plan_version"}
    assert update["plan_version"] == 8
    request = update["model_request"]
    assert isinstance(request, dict)
    assert request["model"] == "offline-test"
    assert request["instructions"] == "保留原指令"
    items = request["input"]
    assert isinstance(items, list)
    assert items[:-1] == original["model_request"]["input"]
    assert items[-1]["role"] == "user"
    assert json.loads(items[-1]["content"]) == {
        "data_kind": "consultant_interview_plan",
        "plan": body,
    }
    assert queries.workspace_ids == [UUID(int=20)]
    assert state == original


@pytest.mark.parametrize(
    ("previous", "expected_version"),
    [
        ({"plan_version": 3}, 3),
        ({"plan_version": None}, None),
        ({}, None),
        (None, None),
    ],
)
def test_continuing_preserves_the_seen_version_without_querying_current_plan(
    previous: dict[str, int | None] | None, expected_version: int | None
) -> None:
    state = window_state()
    original = deepcopy(state)
    runtime = Runtime(context=AgentContext(PluginServices({})))

    update = asyncio.run(
        prepare_plan_window(state, previous=previous, rebuilding=False, runtime=runtime)
    )

    assert update == {"plan_version": expected_version}
    assert state == original
