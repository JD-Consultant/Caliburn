"""唯一公開工具選取與錯誤契約；持久映射另由真 PG 旅程驗證。"""

import asyncio
import json
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.prebuilt import ToolRuntime
from pydantic import ValidationError

from caliburn.bundles.interview import create_bundle
from caliburn.bundles.interview.read_tool import (
    InterviewReadScopeError,
    create_read_interview_tool,
)
from caliburn.bundles.interview.services import MODEL_REFERENCES
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.interview.application.results import TranscriptMessage
from caliburn.modules.model_references import ModelReferences, ReferenceTarget

WORKSPACE = UUID(int=10)
QUESTION = UUID(int=11)
ANSWER = UUID(int=12)
LAST = UUID(int=13)
REFS = {QUESTION: "message_90", ANSWER: "message_4", LAST: "message_7"}
SOURCES = (
    TranscriptMessage(QUESTION, UUID(int=20), "consultant", "question", "多久？", None),
    TranscriptMessage(
        ANSWER, UUID(int=20), "employee", "answer", "自填：每週", QUESTION
    ),
    TranscriptMessage(LAST, UUID(int=21), "employee", "text", "原文 message_4\n", None),
)


async def invoke(
    query: dict[str, object],
    *,
    sources: tuple[TranscriptMessage, ...] = SOURCES,
    error: Exception | None = None,
    limit: int = 24000,
) -> dict[str, Any]:
    # 靜態 I/O 回應只隔離 mapping 邊界；不實作另一套配號或解析規則。
    references = Mock(spec=ModelReferences)
    references.resolve_refs.return_value = {
        ref: ReferenceTarget("message", message_id) for message_id, ref in REFS.items()
    }
    references.get_or_create_refs.return_value = {
        ReferenceTarget("message", message_id): ref for message_id, ref in REFS.items()
    }
    runtime = ToolRuntime(
        state={"workspace_id": WORKSPACE},
        context=AgentContext(PluginServices({MODEL_REFERENCES: references})),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="read",
        store=None,
    )

    async def reader(
        runtime: ToolRuntime[AgentContext, Any],
    ) -> tuple[TranscriptMessage, ...]:
        if error is not None:
            raise error
        return sources

    tool = create_read_interview_tool(reader=reader, max_output_characters=limit)
    output = await tool.ainvoke({"query": query, "runtime": runtime})
    assert isinstance(output, str)
    decoded = json.loads(output)
    assert isinstance(decoded, dict)
    return decoded


def test_messages_are_deduplicated_and_sorted_by_owner_order() -> None:
    result = asyncio.run(
        invoke({"kind": "messages", "refs": ["message_4", "message_90", "message_4"]})
    )
    assert result == {
        "data_kind": "interview",
        "messages": [
            {
                "ref": "message_90",
                "speaker": "consultant",
                "kind": "question",
                "text": "多久？",
                "reply_to": None,
            },
            {
                "ref": "message_4",
                "speaker": "employee",
                "kind": "answer",
                "text": "自填：每週",
                "reply_to": "message_90",
            },
        ],
    }


def test_range_uses_formal_order_and_keeps_text_unchanged() -> None:
    result = asyncio.run(
        invoke({"kind": "range", "start_ref": "message_90", "end_ref": "message_7"})
    )
    assert [message["ref"] for message in result["messages"]] == [
        "message_90",
        "message_4",
        "message_7",
    ]
    assert result["messages"][-1]["text"] == "原文 message_4\n"


def test_selected_answer_does_not_add_question_body() -> None:
    result = asyncio.run(invoke({"kind": "messages", "refs": ["message_4"]}))
    assert len(result["messages"]) == 1
    assert result["messages"][0]["reply_to"] == "message_90"


@pytest.mark.parametrize(
    ("query", "field"),
    [
        (
            {"kind": "range", "start_ref": "message_7", "end_ref": "message_90"},
            "query.start_ref",
        ),
        ({"kind": "messages", "refs": []}, "query.refs"),
        ({"kind": "messages", "refs": [str(QUESTION)]}, "query.refs[0]"),
        ({"kind": "messages", "refs": ["task_1"]}, "query.refs[0]"),
        ({"kind": "messages", "refs": ["message_01"]}, "query.refs[0]"),
        ({"kind": "range", "start_ref": "message_7"}, "query.end_ref"),
        (
            {"kind": "range", "start_ref": "task_7", "end_ref": "message_90"},
            "query.start_ref",
        ),
    ],
)
def test_invalid_selection_has_field_and_action(
    query: dict[str, object], field: str
) -> None:
    result = asyncio.run(invoke(query))
    assert result["status"] == "rejected"
    assert result["code"] == "invalid_arguments"
    assert field in result["message"]
    assert result["next_action"]


def test_fixed_scope_failure_is_not_reduced_to_surviving_selection() -> None:
    result = asyncio.run(
        invoke(
            {"kind": "messages", "refs": ["message_90"]},
            error=InterviewReadScopeError("private"),
        )
    )
    assert result["code"] == "scope_not_allowed"
    assert "private" not in json.dumps(result)


def test_query_failure_is_not_disguised_as_empty_or_rejected() -> None:
    with pytest.raises(ConnectionError):
        asyncio.run(
            invoke(
                {"kind": "messages", "refs": ["message_90"]},
                error=ConnectionError("offline"),
            )
        )


@pytest.mark.parametrize(
    "query",
    [
        {"kind": "range", "start_ref": "message_90", "end_ref": "message_7"},
        {"kind": "messages", "refs": ["message_7", "message_90"]},
    ],
)
def test_limit_repair_can_read_exact_original_selection(
    query: dict[str, object],
) -> None:
    pending = [query]
    read_refs: list[str] = []
    splits = 0
    while pending:
        result = asyncio.run(invoke(pending.pop(0), limit=210))
        if result.get("code") == "read_limit_exceeded":
            splits += 1
            suggestions = json.loads(result["next_action"].split("：", 1)[1])
            pending.extend(item["query"] for item in suggestions)
        else:
            read_refs.extend(message["ref"] for message in result["messages"])
    assert splits > 0
    assert read_refs == (
        ["message_90", "message_4", "message_7"]
        if query["kind"] == "range"
        else ["message_90", "message_7"]
    )


def test_single_message_over_limit_needs_application_action() -> None:
    result = asyncio.run(invoke({"kind": "messages", "refs": ["message_90"]}, limit=1))
    assert result["code"] == "read_limit_exceeded"
    assert "應用" in result["next_action"]
    assert "不要重試" in result["next_action"]
    assert "messages" not in result


def test_bundle_can_provide_read_tool_without_recording_or_preload() -> None:
    plugins = load_plugins(
        [
            BundleConfig(
                "caliburn.bundles.interview",
                plugins=("interview_read", "interview_navigation"),
            )
        ]
    )
    assert [tool.name for plugin in plugins for tool in plugin.tools] == [
        "read_interview"
    ]
    assert MODEL_REFERENCES in plugins[0].required_services
    assert any(plugin.on_turn_start for plugin in plugins)


@pytest.mark.parametrize("name", ["recording", "context", "source_prompt", "read"])
def test_plugin_selection_cannot_be_overridden_by_a_second_setting(name: str) -> None:
    with pytest.raises(ValidationError):
        create_bundle({name: False})


def test_read_tool_can_be_selected_without_standalone_navigation() -> None:
    plugins = load_plugins(
        [BundleConfig("caliburn.bundles.interview", plugins=("interview_read",))]
    )
    assert [tool.name for plugin in plugins for tool in plugin.tools] == [
        "read_interview"
    ]
    assert not any(plugin.on_turn_start for plugin in plugins)


def test_navigation_can_be_selected_without_tool_or_preload() -> None:
    (plugin,) = load_plugins(
        [BundleConfig("caliburn.bundles.interview", plugins=("interview_navigation",))]
    )
    assert not plugin.tools
    assert [step.name for step in plugin.on_turn_start] == ["discover_sources"]


def test_model_schema_uses_supported_union_without_dangling_discriminator() -> None:
    declaration = convert_to_openai_function(create_read_interview_tool(), strict=True)
    query = declaration["parameters"]["properties"]["query"]
    assert "anyOf" in query
    encoded = json.dumps(declaration)
    assert '"discriminator"' not in encoded
    assert '"oneOf"' not in encoded
    assert "#/$defs/" not in encoded
