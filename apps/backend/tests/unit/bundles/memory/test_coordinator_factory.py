"""背景工廠沿真 Coordinator／Core 執行角色；只替換外部持久 port。"""

import asyncio
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypedDict
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from caliburn.bundles.memory.projections import ToolRejection
from caliburn.bundles.memory.situation_instructions import SITUATION_INSTRUCTIONS
from caliburn.bundles.memory.understanding_instructions import (
    UNDERSTANDING_INSTRUCTIONS,
)
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.memory.application.persistence import (
    MemoryQueries,
    MemoryUnitOfWork,
)
from caliburn.modules.memory.application.results import MemoryInterviewMessage
from caliburn.modules.memory.domain.analysis import MemorySourceWindow
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.modules.model_references import ModelReferences, ReferenceTarget
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.execution import complete_turn
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

if TYPE_CHECKING:
    from caliburn.bundles.memory.services import MemoryCoordinatorFactory


@pytest.fixture(autouse=True)
def isolate_external_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


class IntentState(TypedDict):
    memory_consolidation_requested: bool


async def saved_intent(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> IntentState:
    return {"memory_consolidation_requested": True}


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(
        (AgentPlugin("alternative_prompt", prompt_sections=(str(config["prompt"]),)),)
    )


def run_analysis(
    factory: MemoryCoordinatorFactory,
    *,
    read_map: bool = False,
    input_tokens: int = 159999,
) -> tuple[MemorySnapshot | None, list[dict[str, Any]], list[str]]:
    workspace_id, turn_id, analysis_id, message_id = (uuid4() for _ in range(4))
    window = MemorySourceWindow(
        workspace_id=workspace_id,
        through_message_id=message_id,
        message_ids=(message_id,),
        required_message_ids=(message_id,),
    )
    root = WorkMemory.create(workspace_id=workspace_id)
    root.begin_analysis(analysis_id=analysis_id, source_window=window, baseline=None)
    queries = Mock(spec=MemoryQueries)
    queries.get_current.return_value = root
    queries.get_published.return_value = None
    queries.list_analysis_sources.return_value = (
        MemoryInterviewMessage(
            message_id, turn_id, "employee", "text", "每日核對庫存。", None
        ),
    )
    interview = Mock(spec=InterviewQueries)
    interview.list_messages.return_value = ()
    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.return_value = {
        ReferenceTarget("message", message_id): "message_1"
    }
    uow = MagicMock(spec=MemoryUnitOfWork)
    uow.__enter__.return_value = uow
    uow.memories.get_for_update.return_value = root
    requests: list[dict[str, Any]] = []
    paths: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/responses/input_tokens":
            compacted = any(
                item.get("type") == "compaction"
                for item in request_body(request)["input"]
            )
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 1 if compacted else input_tokens,
                },
            )
        if request.url.path == "/v1/responses/compact":
            return httpx2.Response(200, json=compacted_payload())
        assert request.url.path == "/v1/responses"
        requests.append(request_body(request))
        output = (
            [call("read_work_situation_map", arguments="{}")]
            if read_map and len(requests) == 2
            else [message(text='{"status":"complete"}')]
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> MemorySnapshot | None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            saver = InMemorySaver(serde=openai_checkpoint_serializer())
            async with open_agent(
                agent_id="factory-consultant",
                resume_version="factory-v1",
                client=client,
                model_settings=MODEL_REQUEST,
                checkpointer=saver,
                bundles=(
                    AgentBundle(
                        (
                            AgentPlugin(
                                "synthetic_saved_intent",
                                state_schema=IntentState,
                                on_turn_start=(PluginStep("request", saved_intent),),
                            ),
                        )
                    ),
                ),
            ) as consultant:
                await complete_turn(
                    consultant,
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    input="合成已完成整理要求",
                )
                coordinator = factory(
                    consultant=consultant,
                    client=client,
                    model_settings=MODEL_REQUEST,
                    checkpointer=saver,
                    agent_id="factory-memory",
                    resume_version="factory-v1",
                    queries=queries,
                    interview_queries=interview,
                    uow_factory=lambda: uow,
                    references=references,
                )
                return await coordinator.run(workspace_id=workspace_id, turn_id=turn_id)

    result = asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert result is not None and result.version == 3
    assert result.covered_through_message_id == message_id
    assert root.analysis is None
    return result, requests, paths


@pytest.mark.parametrize("input_tokens", [159999, 160000])
def test_default_factory_completes_builtin_roles_with_native_compaction(
    input_tokens: int,
) -> None:
    from caliburn.bundles.memory.factory import create_coordinator_factory

    _, requests, paths = run_analysis(
        create_coordinator_factory(), input_tokens=input_tokens
    )

    assert len(requests) == 3
    assert requests[1]["instructions"] == SITUATION_INSTRUCTIONS
    assert requests[2]["instructions"] == UNDERSTANDING_INSTRUCTIONS
    if input_tokens < 160000:
        assert "每日核對庫存。" in json.dumps(requests[1]["input"], ensure_ascii=False)
        assert paths == [
            "/v1/responses",
            "/v1/responses/input_tokens",
            "/v1/responses",
            "/v1/responses/input_tokens",
            "/v1/responses",
        ]
    else:
        assert paths == [
            "/v1/responses",
            *[
                "/v1/responses/input_tokens",
                "/v1/responses/compact",
                "/v1/responses/input_tokens",
                "/v1/responses",
            ]
            * 2,
        ]
        assert any(item.get("type") == "compaction" for item in requests[1]["input"])
        assert any(item.get("type") == "compaction" for item in requests[2]["input"])


def test_factory_uses_each_explicit_role_composition() -> None:
    from caliburn.bundles.memory.factory import create_coordinator_factory

    factory = create_coordinator_factory(
        situation_bundles=(
            AgentBundle((AgentPlugin("alternative_b1", prompt_sections=("替代B1",)),)),
        ),
        understanding_bundles=(BundleConfig(__name__, {"prompt": "替代B2"}),),
    )

    _, requests, paths = run_analysis(factory)

    assert len(requests) == 3
    assert requests[1]["instructions"] == "替代B1"
    assert requests[2]["instructions"] == "替代B2"
    assert requests[1]["tools"] == requests[2]["tools"] == []
    assert paths == ["/v1/responses"] * 3


def test_factory_snapshots_nested_bundle_configuration() -> None:
    from caliburn.bundles.memory.factory import create_coordinator_factory

    prompt = ["固定B1"]
    bundle = BundleConfig(__name__, {"prompt": prompt}, plugins=("alternative_prompt",))
    factory = create_coordinator_factory(
        situation_bundles=(bundle,), understanding_bundles=()
    )
    prompt[0] = "建廠後改動B1"

    _, requests, paths = run_analysis(factory)

    assert requests[1]["instructions"] == "['固定B1']"
    assert paths == ["/v1/responses"] * 3


def test_factory_applies_the_builtin_role_context_limit() -> None:
    from caliburn.bundles.memory.factory import create_coordinator_factory

    with pytest.raises(ToolRejection) as rejected:
        run_analysis(create_coordinator_factory(max_context_characters=1))

    assert rejected.value.code == "read_limit_exceeded"


def test_factory_applies_the_builtin_role_tool_result_limit() -> None:
    from caliburn.bundles.memory.factory import create_coordinator_factory

    _, requests, _ = run_analysis(
        create_coordinator_factory(max_tool_result_characters=1), read_map=True
    )

    assert len(requests) == 4
    result = next(
        item
        for item in requests[2]["input"]
        if item.get("type") == "function_call_output"
    )
    assert json.loads(result["output"])["code"] == "read_limit_exceeded"
