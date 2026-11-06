"""正式 Bundle 組裝與 SDK 出站契約；記憶體 I/O 不代替 PG 驗收。"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any, cast
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.interview.context import (
    load_interview_context,
    project_interview_context,
)
from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.interview.application.queries import list_messages
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_opening,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.model_references import ModelReferences, ReferenceTarget
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
from tests.unit.modules.interview.memory_store import MemoryInterviewStore

WORKSPACE_ID = UUID(int=20)


def run_interview_turn(
    store: MemoryInterviewStore,
    *,
    plugins: tuple[str, ...],
    input: str | ResponseInputParam = "本輪原文",
    refs: Mapping[UUID, str] | None = None,
) -> list[dict[str, Any]]:
    sent = []
    turn_id = uuid4()
    known_refs = dict(refs or {})
    if "interview" in plugins and isinstance(input, str):
        saved = record_turn_input(
            workspace_id=WORKSPACE_ID,
            turn_id=turn_id,
            text=input,
            uow_factory=store.uow_factory,
        )
        known_refs[saved.message_id] = "message_900"
    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.return_value = {
        ReferenceTarget("message", message_id): ref
        for message_id, ref in known_refs.items()
    }

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="interview-context",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig("caliburn.bundles.interview", plugins=plugins)],
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                external_services=(
                    INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                    INTERVIEW_QUERIES.bind(store),
                    MODEL_REFERENCES.bind(references),
                ),
            ) as agent:
                await complete_turn(
                    agent, workspace_id=WORKSPACE_ID, turn_id=turn_id, input=input
                )

    asyncio.run(run())
    return sent


def test_saved_current_input_exposes_its_reference_without_repeating_the_text() -> None:
    store = MemoryInterviewStore()
    (request,) = run_interview_turn(
        store,
        plugins=("interview",),
        input=" 本輪原文 message_777\n ",
    )

    references = [
        json.loads(item["content"])
        for item in request["input"]
        if item.get("role") == "user"
        and item.get("content", "").startswith('{"data_kind":')
    ]
    assert len(references) == 1
    assert references[0]["data_kind"] == "employee_input_reference"
    assert references[0] == {
        "data_kind": "employee_input_reference",
        "ref": "message_900",
    }
    assert str(request["input"]).count("本輪原文 message_777") == 1


def test_prior_transcript_precedes_current_input_without_repeating_current_turn() -> (
    None
):
    store = MemoryInterviewStore()
    prior_turn = uuid4()
    opening = record_opening(
        workspace_id=WORKSPACE_ID, text="原開場", uow_factory=store.uow_factory
    )
    prior_input = record_turn_input(
        workspace_id=WORKSPACE_ID,
        turn_id=prior_turn,
        text=" 員工原話\n第二行 ",
        uow_factory=store.uow_factory,
    )
    final = record_consultant_message(
        workspace_id=WORKSPACE_ID,
        turn_id=prior_turn,
        text="前輪顧問回覆",
        uow_factory=store.uow_factory,
    )

    (request,) = run_interview_turn(
        store,
        plugins=("interview", "interview_context"),
        refs={
            opening.message_id: "message_500",
            prior_input.message_id: "message_13",
            final.message_id: "message_200",
        },
    )

    assert len(request["input"]) == 3
    assert request["input"][1] == {"role": "user", "content": "本輪原文"}
    source = request["input"][0]
    assert source["role"] == "user"
    material = json.loads(source["content"])
    assert material["source"] == "interview"
    assert [item["ref"] for item in material["messages"]] == [
        "message_500",
        "message_13",
        "message_200",
    ]
    assert all("position" not in item for item in material["messages"])
    assert [(item["speaker"], item["text"]) for item in material["messages"]] == [
        ("app", "原開場"),
        ("employee", " 員工原話\n第二行 "),
        ("consultant", "前輪顧問回覆"),
    ]


@pytest.mark.parametrize("recording", [True, False])
@pytest.mark.parametrize("context", [True, False])
@pytest.mark.parametrize("source_prompt", [True, False])
def test_recording_context_and_source_prompt_can_be_enabled_independently(
    recording: bool, context: bool, source_prompt: bool
) -> None:
    store = MemoryInterviewStore()
    opening = record_opening(
        workspace_id=WORKSPACE_ID, text="既有開場", uow_factory=store.uow_factory
    )

    (request,) = run_interview_turn(
        store,
        plugins=tuple(
            name
            for name, enabled in (
                ("interview", recording),
                ("interview_context", context),
                ("interview_source_prompt", source_prompt),
            )
            if enabled
        ),
        refs={opening.message_id: "message_50"},
    )

    assert len(request["input"]) == 1 + int(context) + int(recording)
    assert bool(request.get("instructions")) is source_prompt
    assert [
        message.text
        for message in list_messages(workspace_id=WORKSPACE_ID, queries=store)
    ] == (["既有開場", "本輪原文", "Synthetic reply"] if recording else ["既有開場"])


def test_selected_question_does_not_imply_its_omitted_answer_is_missing() -> None:
    store = MemoryInterviewStore()
    prior_turn = uuid4()
    record_turn_input(
        workspace_id=WORKSPACE_ID,
        turn_id=prior_turn,
        text="開始訪談",
        uow_factory=store.uow_factory,
    )
    (question,) = record_questions(
        workspace_id=WORKSPACE_ID,
        turn_id=prior_turn,
        questions=(Question(question="已回答的題目？"),),
        uow_factory=store.uow_factory,
    )
    record_answers(
        workspace_id=WORKSPACE_ID,
        turn_id=prior_turn,
        answers=(AnswerInput(question_message_id=question.message_id, custom="已答"),),
        uow_factory=store.uow_factory,
    )
    selected = load_interview_context(
        workspace_id=WORKSPACE_ID,
        turn_id=uuid4(),
        queries=store,
        message_ids=(question.message_id,),
    )

    (request,) = run_interview_turn(
        store,
        plugins=("interview_source_prompt",),
        input=cast(
            ResponseInputParam,
            project_interview_context(
                selected, refs={question.message_id: "message_5"}
            ),
        ),
    )

    (source,) = request["input"]
    material = json.loads(source["content"])
    assert [(item["kind"], item["text"]) for item in material["messages"]] == [
        ("question", "已回答的題目？")
    ]
    assert "未選入答案不代表該題尚未回答，不得推定未答" in request["instructions"]
    assert "尚無 answer 的題目仍是未答" not in request["instructions"]
