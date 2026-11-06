"""B 角色可由明示的另一個 Bundle 提供 Prompt，沿同一原生 Agent 執行。"""

import asyncio
from collections.abc import Mapping
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.bundles.memory.coordinator import open_memory_role_agent
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.items import MemoryKind
from caliburn.modules.model_references import ModelReferences
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(
        (
            AgentPlugin(
                name="alternative_memory_prompt",
                prompt_sections=(f"替代角色 Prompt：{config['role']}。",),
            ),
        )
    )


@pytest.mark.parametrize("role", ["situation", "understanding"])
def test_role_factory_uses_selected_bundle_without_original_memory_plugins(
    role: MemoryKind,
) -> None:
    requests: list[dict[str, Any]] = []
    queries = Mock(spec=MemoryQueries)
    references = Mock(spec=ModelReferences)
    service = Mock(spec=MemoryService)

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses"
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_memory_role_agent(
                agent_id="memory-role-replacement",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                queries=queries,
                references=references,
                role=role,
                analysis_id=uuid4(),
                memory_service=service,
                bundles=(BundleConfig(__name__, {"role": role}),),
            ) as agent:
                await complete_turn(agent, workspace_id=uuid4(), input="合成角色輸入")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    (request,) = requests
    assert request["instructions"] == f"替代角色 Prompt：{role}。"
    assert request["tools"] == []
    assert request["input"] == [{"role": "user", "content": "合成角色輸入"}]
    assert not queries.mock_calls
    assert not references.mock_calls
    assert not service.mock_calls
