from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base.embed import ensure_embeddings
from pydantic import ValidationError

from memory_read_spike.contracts import (
    ConversationItem,
    MemoryHit,
    ReadConversationContextInput,
    ReadConversationContextResult,
    SearchSemanticMemoryInput,
    SearchSemanticMemoryResult,
)


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (SearchSemanticMemoryInput, "query"),
        (ReadConversationContextInput, "message_ref"),
    ],
)
def test_tool_input_schema_exposes_one_required_string_and_rejects_extras(
    model: type[SearchSemanticMemoryInput] | type[ReadConversationContextInput],
    field_name: str,
) -> None:
    """Catches accidental model-visible scope, limits, filters, or optional fields."""
    schema = model.model_json_schema()

    assert schema["type"] == "object"
    assert set(schema["properties"]) == {field_name}
    assert schema["properties"][field_name]["type"] == "string"
    assert schema["properties"][field_name]["minLength"] == 1
    assert schema["required"] == [field_name]
    assert schema["additionalProperties"] is False

    with pytest.raises(ValidationError):
        model.model_validate({field_name: ""})
    with pytest.raises(ValidationError):
        model.model_validate({field_name: "valid", "document_id": "model-controlled"})


def test_success_payloads_reject_unknown_fields_and_allow_empty_search() -> None:
    """Catches leakage of Store metadata or invented result fields."""
    empty = SearchSemanticMemoryResult(memories=())
    assert empty.model_dump(mode="json") == {"memories": []}

    hit = MemoryHit(title="A 案", content="三間分店。", message_refs=("h-002",))
    assert SearchSemanticMemoryResult(memories=(hit,)).model_dump(mode="json") == {
        "memories": [
            {"title": "A 案", "content": "三間分店。", "message_refs": ["h-002"]}
        ]
    }
    context = ReadConversationContextResult(
        context=(ConversationItem(speaker="employee", text="原句"),)
    )
    assert context.model_dump(mode="json") == {
        "context": [{"speaker": "employee", "text": "原句"}]
    }

    with pytest.raises(ValidationError):
        MemoryHit.model_validate(
            {
                "title": "A 案",
                "content": "內容",
                "message_refs": [],
                "namespace": ["secret"],
            }
        )


@pytest.mark.asyncio
async def test_pinned_tool_node_serializes_dict_result_with_call_linkage() -> None:
    """Catches a boundary that drops the call ID or emits non-JSON tool content."""

    async def search(query: str) -> dict[str, object]:
        return SearchSemanticMemoryResult(
            memories=(
                MemoryHit(title="A 案", content=query, message_refs=("h-002",)),
            )
        ).model_dump(mode="json")

    tool = StructuredTool.from_function(
        coroutine=search,
        name="search_semantic_memory",
        description="Search current semantic memory.",
        args_schema=SearchSemanticMemoryInput,
    )
    builder = StateGraph(MessagesState)
    builder.add_node("tools", ToolNode([tool]))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    graph = builder.compile()
    output = await graph.ainvoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_semantic_memory",
                            "args": {"query": "三間分店"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }
    )

    message = output["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "call-1"
    assert message.status == "success"
    assert json.loads(message.content) == {
        "memories": [
            {"title": "A 案", "content": "三間分店", "message_refs": ["h-002"]}
        ]
    }
    assert not hasattr(message, "code")


@pytest.mark.asyncio
async def test_framework_async_embedding_wrapper_preserves_order_and_dimensions() -> None:
    """Catches reordering or shape loss at the framework embedding boundary."""
    seen: list[list[str]] = []

    async def embed(texts: list[str]) -> list[list[float]]:
        seen.append(list(texts))
        return [[float(index), float(len(text))] for index, text in enumerate(texts)]

    wrapped = ensure_embeddings(embed)
    vectors = await wrapped.aembed_documents(["second", "first"])

    assert seen == [["second", "first"]]
    assert vectors == [[0.0, 6.0], [1.0, 5.0]]
    assert {len(vector) for vector in vectors} == {2}
