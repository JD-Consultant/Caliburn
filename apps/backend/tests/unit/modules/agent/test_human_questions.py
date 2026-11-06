"""人工提問契約、正式保存、原生等待及回答隔離。"""

import asyncio
import json
import re
from threading import Event
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import httpx2
import pytest
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from caliburn.bundles.human_questions import create_bundle
from caliburn.bundles.human_questions.ask_user_question import create_question_tool
from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY, MODEL_REFERENCES
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.human_questions.api import AnswerTurnRequest
from caliburn.modules.human_questions.questions import (
    AnswerBatch,
    InvalidAnswers,
    PendingQuestions,
)
from caliburn.modules.interview.application.recording import record_turn_input
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

BUNDLE_MODULE = "caliburn.bundles.human_questions"
FIRST_ID, SECOND_ID = str(UUID(int=100)), str(UUID(int=101))


def answer_batch(value: object) -> AnswerBatch:
    return AnswerBatch.model_validate_json(json.dumps(value))


def pending_from_json(value: object) -> PendingQuestions:
    return PendingQuestions.model_validate_json(json.dumps(value))


def pending_questions(*, multi_select: bool = False) -> PendingQuestions:
    return pending_from_json(
        {
            "model_step": 1,
            "call_id": "call_questions",
            "questions": [
                {
                    "message_id": FIRST_ID,
                    "question_ref": "message_101",
                    "question": "先做哪件事？",
                    "options": [{"label": "A"}, {"label": "B"}],
                    "multi_select": multi_select,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "identifier",
    [
        "00112233-4455-6677-8899-aabbccddeeff",
        "00112233-4455-6677-8899-AABBCCDDEEFF",
    ],
)
def test_http_answer_uses_canonical_uuid_and_converts_json_selections(
    identifier: str,
) -> None:
    request = AnswerTurnRequest.model_validate(
        {
            "model_step": 1,
            "call_id": "call_questions",
            "answers": [
                {
                    "question_message_id": identifier,
                    "selected": ["A"],
                    "custom": " 原文 ",
                }
            ],
        }
    )
    assert request.answers[0].question_message_id == UUID(
        "00112233-4455-6677-8899-aabbccddeeff"
    )
    assert request.answers[0].selected == ("A",)
    assert request.answers[0].custom == " 原文 "


@pytest.mark.parametrize(
    "answer",
    [
        {"question_message_id": UUID(FIRST_ID).hex, "selected": []},
        {"question_message_id": "urn:uuid:" + FIRST_ID, "selected": []},
        {"question_message_id": FIRST_ID},
        {"id": FIRST_ID, "selected": []},
    ],
)
def test_http_answer_rejects_legacy_ids_and_missing_explicit_selection(
    answer: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        AnswerTurnRequest.model_validate(
            {"model_step": 1, "call_id": "call_questions", "answers": [answer]}
        )


def test_bundle_exposes_questions_without_execution_parameters() -> None:
    tools = [tool for plugin in create_bundle({}).plugins for tool in plugin.tools]
    assert [tool.name for tool in tools] == ["ask_user_question"]
    declaration = convert_to_openai_function(tools[0], strict=True)
    properties = declaration["parameters"]["properties"]
    assert set(properties) == {"questions"}
    assert set(properties["questions"]["items"]["properties"]) == {
        "question",
        "header",
        "options",
        "multi_select",
    }


def test_tool_schema_explains_each_question_and_option_field() -> None:
    tool = create_bundle({}).plugins[0].tools[0]
    properties = convert_to_openai_function(tool, strict=True)["parameters"][
        "properties"
    ]
    question = properties["questions"]["items"]["properties"]
    option = question["options"]["items"]["properties"]
    assert properties["questions"].get("description")
    assert all(field.get("description") for field in question.values())
    assert all(field.get("description") for field in option.values())


@pytest.mark.parametrize(
    ("questions", "location", "repair"),
    [
        (
            [{"id": "old-model-id", "question": "Ready?"}],
            "questions[0].<extra>",
            "移除",
        ),
        (
            [{"question": "Choose?", "options": [{"label": "A"}, {"label": "A"}]}],
            "questions[0].options[1].label",
            "不可重複",
        ),
        (
            [{"question": "Choose?", "multi_select": "sensitive-invalid-value"}],
            "questions[0].multi_select",
            "布林",
        ),
        (
            [{"question": "Choose?", "options": [{"label": ""}]}],
            "questions[0].options[0].label",
            "不可為空",
        ),
        ([{"question": ""}], "questions[0].question", "不可為空"),
        ([{"question": "Choose?", "options": {}}], "questions[0].options", "陣列"),
        ([], "questions", "至少一題"),
    ],
)
def test_invalid_tool_questions_locate_the_field_to_repair(
    questions: list[dict[str, object]],
    location: str,
    repair: str,
) -> None:
    tool = create_bundle({}).plugins[0].tools[0]

    async def run() -> None:
        result = await tool.ainvoke({"questions": questions})
        assert isinstance(result, str)
        assert location in result
        assert repair in result
        assert "sensitive-invalid-value" not in result
        assert "old-model-id" not in result

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_pending_questions_accept_saved_message_ids_and_answer_in_question_order() -> (
    None
):
    pending = pending_from_json(
        {
            "model_step": 1,
            "call_id": "call_questions",
            "questions": [
                {
                    "message_id": FIRST_ID,
                    "question_ref": "message_101",
                    "question": "先做哪件事？",
                    "options": [{"label": "A"}, {"label": "B"}],
                    "multi_select": True,
                },
                {
                    "message_id": SECOND_ID,
                    "question_ref": "message_102",
                    "question": "還有補充嗎？",
                },
            ],
        }
    )
    result = pending.validate_answers(
        answer_batch(
            {
                "answers": [
                    {"question_message_id": SECOND_ID, "selected": []},
                    {
                        "question_message_id": FIRST_ID,
                        "selected": ["B", "A"],
                        "custom": " 原文 ",
                    },
                ]
            }
        )
    )
    assert result.model_dump(mode="json", exclude_none=True) == {
        "answers": [
            {
                "question_message_id": FIRST_ID,
                "selected": ["A", "B"],
                "custom": " 原文 ",
            },
            {"question_message_id": SECOND_ID, "selected": []},
        ]
    }


@pytest.mark.parametrize(
    "answers",
    [
        [],
        [{"question_message_id": SECOND_ID, "selected": []}],
        [{"question_message_id": FIRST_ID, "selected": []}] * 2,
        [{"question_message_id": FIRST_ID, "selected": ["unknown"]}],
        [{"question_message_id": FIRST_ID, "selected": ["A", "A"]}],
        [{"question_message_id": FIRST_ID, "selected": ["A", "B"]}],
    ],
)
def test_answer_batch_rejects_missing_duplicate_unknown_and_invalid_choices(
    answers: list[dict[str, object]],
) -> None:
    with pytest.raises(InvalidAnswers):
        pending_questions().validate_answers(answer_batch({"answers": answers}))


@pytest.mark.parametrize(
    "answer",
    [
        {"question_message_id": FIRST_ID, "selected": []},
        {"question_message_id": FIRST_ID, "selected": [], "custom": " Exact text. "},
        {"question_message_id": FIRST_ID, "selected": ["A"]},
        {"question_message_id": FIRST_ID, "selected": ["A"], "custom": " Also this. "},
    ],
)
def test_skip_text_choice_and_choice_with_text_preserve_human_answer(
    answer: dict[str, object],
) -> None:
    result = pending_questions().validate_answers(answer_batch({"answers": [answer]}))
    assert result.model_dump(mode="json", exclude_none=True) == {"answers": [answer]}


@pytest.mark.parametrize("field", ["selected", "custom"])
@pytest.mark.parametrize("invalid", ["\ud800", "\udfff", "\u0000"])
def test_answer_contract_rejects_unstorable_text(field: str, invalid: str) -> None:
    answer: dict[str, object] = {
        "question_message_id": FIRST_ID,
        "selected": [],
        "custom": "Exact text",
    }
    answer[field] = [invalid] if field == "selected" else invalid
    with pytest.raises(ValidationError):
        answer_batch(json.loads(json.dumps({"answers": [answer]})))


def test_answer_contract_preserves_unicode_and_exports_the_same_text_policy() -> None:
    answer = {
        "question_message_id": FIRST_ID,
        "selected": ["選項📝"],
        "custom": " 原文\n🙂 ",
    }
    batch = answer_batch(json.loads(json.dumps({"answers": [answer]})))
    assert batch.model_dump(mode="json") == {"answers": [answer]}
    properties = AnswerBatch.model_json_schema()["$defs"]["AnswerInput"]["properties"]
    for pattern in [
        properties["selected"]["items"]["pattern"],
        properties["custom"]["anyOf"][0]["pattern"],
    ]:
        assert re.fullmatch(pattern, "繁體中文🙂\n")
        assert not re.fullmatch(pattern, "\ud800")
        assert not re.fullmatch(pattern, "\u0000")


def test_saved_answers_match_despite_question_and_selection_order() -> None:
    saved = answer_batch(
        {
            "answers": [
                {
                    "question_message_id": FIRST_ID,
                    "selected": ["B", "A"],
                    "custom": " Exact text ",
                },
                {"question_message_id": SECOND_ID, "selected": []},
            ]
        }
    )
    replayed = answer_batch(
        {
            "answers": [
                {"question_message_id": SECOND_ID, "selected": []},
                {
                    "question_message_id": FIRST_ID,
                    "selected": ["A", "B"],
                    "custom": " Exact text ",
                },
            ]
        }
    )
    assert saved.matches(replayed)
    assert replayed.matches(saved)


@pytest.mark.parametrize(
    "changed",
    [
        [],
        [
            {
                "question_message_id": SECOND_ID,
                "selected": ["A", "B"],
                "custom": " Exact text ",
            }
        ],
        [
            {
                "question_message_id": FIRST_ID,
                "selected": ["A"],
                "custom": " Exact text ",
            }
        ],
        [
            {
                "question_message_id": FIRST_ID,
                "selected": ["A", "B"],
                "custom": "Exact text",
            }
        ],
        [{"question_message_id": FIRST_ID, "selected": ["A", "B"]}],
        [
            {
                "question_message_id": FIRST_ID,
                "selected": ["A", "A", "B"],
                "custom": " Exact text ",
            }
        ],
        [
            {
                "question_message_id": FIRST_ID,
                "selected": ["A", "B"],
                "custom": " Exact text ",
            }
        ]
        * 2,
    ],
)
def test_saved_answers_do_not_match_changed_or_duplicate_answers(
    changed: list[dict[str, object]],
) -> None:
    saved = answer_batch(
        {
            "answers": [
                {
                    "question_message_id": FIRST_ID,
                    "selected": ["A", "B"],
                    "custom": " Exact text ",
                }
            ]
        }
    )
    replayed = answer_batch({"answers": changed})
    assert not saved.matches(replayed)
    assert not replayed.matches(saved)


@pytest.mark.parametrize(
    "answers",
    [
        [{"question_message_id": FIRST_ID, "selected": ["A", "A"]}],
        [{"question_message_id": FIRST_ID, "selected": []}] * 2,
    ],
)
def test_duplicate_answers_never_match_even_themselves(
    answers: list[dict[str, object]],
) -> None:
    batch = answer_batch({"answers": answers})
    assert not batch.matches(batch)


def test_multiple_questions_are_saved_once_and_resumed_as_one_tool_result() -> None:
    questions = [
        {
            "question": "Which modes?",
            "header": "Modes",
            "options": [{"label": "A"}, {"label": "B", "description": "Second"}],
            "multi_select": True,
        },
        {"question": "Anything else?"},
    ]
    sent: list[dict[str, Any]] = []
    question_ids: list[str] = []
    store = MemoryInterviewStore()
    references = Mock(spec=ModelReferences)
    question_refs: dict[ReferenceTarget, str] = {}

    def project_refs(
        workspace_id: UUID, targets: list[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        assert workspace_id == UUID(int=1)
        if not question_refs:
            question_refs.update(
                zip(targets, ("message_101", "message_102"), strict=True)
            )
        if set(targets) == question_refs.keys():
            return question_refs
        return dict(zip(targets, ("message_201", "message_202"), strict=True))

    references.get_or_create_refs.side_effect = project_refs
    record_turn_input(
        workspace_id=UUID(int=1),
        turn_id=UUID(int=2),
        text="Original input",
        uow_factory=store.uow_factory,
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [
                call(
                    "ask_user_question",
                    "call_questions",
                    json.dumps({"questions": questions}),
                )
            ]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="questions",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[
                    AgentBundle(
                        plugins=(
                            AgentPlugin(
                                "question_task", tools=(create_question_tool(),)
                            ),
                        )
                    )
                ],
                external_services=[
                    INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                    MODEL_REFERENCES.bind(references),
                ],
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=1),
                    turn_id=UUID(int=2),
                    input="Original input",
                ):
                    pass
                waiting = await agent.aget_state(workspace_id=UUID(int=1))
                assert len(waiting.interrupts) == 1
                pending = waiting.interrupts[0].value
                question_ids.extend(
                    question["message_id"] for question in pending["questions"]
                )
                assert len(set(question_ids)) == 2
                assert all(UUID(value) for value in question_ids)
                assert [question["question"] for question in pending["questions"]] == [
                    "Which modes?",
                    "Anything else?",
                ]
                assert len(sent) == 1
                reply = {
                    "answers": [
                        {"question_message_id": question_ids[1], "selected": []},
                        {
                            "question_message_id": question_ids[0],
                            "selected": ["B", "A"],
                            "custom": " Keep this. ",
                        },
                    ]
                }
                async for _ in agent.aresume(
                    workspace_id=UUID(int=1),
                    turn_id=UUID(int=2),
                    resume_command=Command(resume={waiting.interrupts[0].id: reply}),
                ):
                    pass
                completed = await agent.aget_state(workspace_id=UUID(int=1))
                assert not completed.interrupts and not completed.next
                assert completed.values["turn_input"] == "Original input"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 2
    assert "question_ref" in json.loads(sent[1]["input"][-1]["output"])["answers"][0]
    assert json.loads(sent[1]["input"][-1]["output"]) == {
        "answers": [
            {
                "question_ref": "message_101",
                "answer_ref": "message_201",
                "question": "Which modes?",
                "selected": ["A", "B"],
                "custom": " Keep this. ",
            },
            {
                "question_ref": "message_102",
                "answer_ref": "message_202",
                "question": "Anything else?",
                "selected": [],
            },
        ]
    }
    assert [item for item in sent[1]["input"] if item.get("role") == "user"] == [
        {"role": "user", "content": "Original input"}
    ]
    transcript = store.list_messages(workspace_id=UUID(int=1), turn_id=UUID(int=2))
    assert [
        str(message.message_id) for message in transcript if message.kind == "question"
    ] == question_ids
    assert [
        str(message.reply_to_message_id)
        for message in transcript
        if message.kind == "answer"
    ] == question_ids


def test_reference_transaction_wait_allows_unrelated_agent_reads() -> None:
    """同步定位 I/O 等待時，另一個查讀仍能完成並解除等待。"""
    started, release = Event(), Event()
    store = MemoryInterviewStore()
    record_turn_input(
        workspace_id=UUID(int=1),
        turn_id=UUID(int=2),
        text="Original input",
        uow_factory=store.uow_factory,
    )
    references = Mock(spec=ModelReferences)

    def blocked_refs(
        workspace_id: UUID, targets: tuple[ReferenceTarget, ...]
    ) -> dict[ReferenceTarget, str]:
        started.set()
        if not release.wait(5):
            raise TimeoutError("定位 I/O 等待阻塞了其他查讀")
        return {targets[0]: "message_101"}

    references.get_or_create_refs.side_effect = blocked_refs

    def respond(request: httpx2.Request) -> httpx2.Response:
        return sse_response(
            EventStream(
                response_events(
                    response_payload(
                        [
                            call(
                                "ask_user_question",
                                "call_questions",
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
                bundles=[
                    AgentBundle(
                        plugins=(
                            AgentPlugin(
                                "question_task", tools=(create_question_tool(),)
                            ),
                        )
                    )
                ],
                external_services=[
                    INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                    MODEL_REFERENCES.bind(references),
                ],
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:

                async def read_while_waiting() -> None:
                    try:
                        assert await asyncio.to_thread(started.wait, 5)
                        await agent.aget_state(workspace_id=UUID(int=1))
                    finally:
                        release.set()

                async with asyncio.TaskGroup() as group:
                    group.create_task(read_while_waiting())
                    async for _ in agent.astream(
                        workspace_id=UUID(int=1),
                        turn_id=UUID(int=2),
                        input="Original input",
                    ):
                        pass
                assert (await agent.aget_state(workspace_id=UUID(int=1))).interrupts

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("enabled", [True, False])
def test_bundle_is_available_only_when_explicitly_loaded(enabled: bool) -> None:
    sent = []
    store = MemoryInterviewStore()
    references = Mock(spec=ModelReferences)
    references.get_or_create_refs.side_effect = lambda workspace_id, targets: {
        target: "message_1" for target in targets
    }
    bundles = [BundleConfig("caliburn.bundles.interview", plugins=("interview",))]
    if enabled:
        bundles.append(BundleConfig(BUNDLE_MODULE))

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="questions",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                external_services=[
                    INTERVIEW_UOW_FACTORY.bind(store.uow_factory),
                    MODEL_REFERENCES.bind(references),
                ],
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=1), turn_id=UUID(int=2), input="Hello"
                ):
                    pass
                state = await agent.aget_state(workspace_id=UUID(int=1))
                assert set(state.values) == {
                    "workspace_id",
                    "turn_id",
                    "turn_input",
                    "model_step",
                    "model_request",
                    "model_response",
                    "compaction_response",
                    "cancel_status",
                    "turn_completed",
                }
                assert state.values["compaction_response"] is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [tool["name"] for tool in sent[0]["tools"]] == (
        ["ask_user_question"] if enabled else []
    )
