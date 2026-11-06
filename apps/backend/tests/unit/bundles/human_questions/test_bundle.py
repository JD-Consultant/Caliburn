"""提問配置明確驗證，並以選中的訪談保存能力維持正式問答。"""

import asyncio
import sys
from types import ModuleType
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from caliburn.bundles.human_questions import create_bundle
from caliburn.bundles.interview import create_bundle as create_interview_bundle
from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY, MODEL_REFERENCES
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.model_references import ModelReferences, ReferenceTarget
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)
from tests.unit.modules.interview.memory_store import MemoryInterviewStore


@pytest.mark.parametrize("config", [{"enabled": False}, {"unknown": True}])
def test_unknown_settings_are_rejected_before_exposing_the_tool(
    config: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as rejected:
        create_bundle(config)
    assert rejected.value.errors(include_input=False)[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    "interview_configured", [False, True], ids=["absent", "unselected"]
)
def test_questions_require_selected_interview_recording_before_startup(
    interview_configured: bool,
) -> None:
    store = MemoryInterviewStore()
    bundles = [BundleConfig("caliburn.bundles.human_questions")]
    if interview_configured:
        bundles.append(BundleConfig("caliburn.bundles.interview", plugins=()))

    def respond(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("Invalid composition must fail before model I/O")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(ValueError, match="human_questions.*interview"):
                async with open_agent(
                    agent_id="questions",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=bundles,
                    external_services=(
                        INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                        MODEL_REFERENCES.bind(Mock(spec=ModelReferences)),
                    ),
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("recording_first", [False, True])
def test_alternative_bundle_can_supply_selected_recording_for_questions(
    monkeypatch: pytest.MonkeyPatch, recording_first: bool
) -> None:
    alternate = ModuleType("alternate_interview_bundle")
    monkeypatch.setattr(
        alternate, "create_bundle", create_interview_bundle, raising=False
    )
    monkeypatch.setitem(sys.modules, alternate.__name__, alternate)
    recording = BundleConfig(alternate.__name__, plugins=("interview",))
    questions = BundleConfig("caliburn.bundles.human_questions")
    bundles = (recording, questions) if recording_first else (questions, recording)
    store = MemoryInterviewStore()
    references = Mock(spec=ModelReferences)
    synthetic_refs = iter(("message_1", "message_2"))
    sent: list[dict[str, Any]] = []

    def project_refs(
        workspace_id: UUID, targets: tuple[ReferenceTarget, ...]
    ) -> dict[ReferenceTarget, str]:
        return {target: next(synthetic_refs) for target in targets}

    references.get_or_create_refs.side_effect = project_refs

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(
                    response_payload(
                        [
                            call(
                                "ask_user_question",
                                "question",
                                '{"questions":[{"question":"Ready?"}]}',
                            )
                        ]
                    )
                )
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="questions",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                external_services=(
                    INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                    MODEL_REFERENCES.bind(references),
                ),
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=1), turn_id=UUID(int=2), input="Hello"
                ):
                    pass
                state = await agent.aget_state(workspace_id=UUID(int=1))
                assert len(state.interrupts) == 1
                pending = state.interrupts[0].value["questions"][0]
                transcript = store.list_messages(workspace_id=UUID(int=1))
                assert [(message.speaker, message.text) for message in transcript] == [
                    ("employee", "Hello"),
                    ("consultant", "Ready?"),
                ]
                assert pending["message_id"] == str(transcript[1].message_id)
                assert pending["question_ref"] == "message_2"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 1
    assert [tool["name"] for tool in sent[0]["tools"]] == ["ask_user_question"]
