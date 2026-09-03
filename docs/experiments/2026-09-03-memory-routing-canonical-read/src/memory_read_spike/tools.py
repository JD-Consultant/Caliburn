"""The two framework-executed, model-visible Memory read tools."""

import json
from types import SimpleNamespace
from typing import Annotated, Any

import psycopg
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt.tool_node import ToolInvocationError
from langgraph.types import Command
from pydantic import Field

from memory_read_spike.canonical import (
    ReferenceUnavailableError,
    read_canonical_context,
)
from memory_read_spike.runtime import (
    SemanticIndexUnavailableError,
    search_current_memories,
)
from memory_read_spike.state import MemoryReadContext, MemoryReadState


SEARCH_SEMANTIC_MEMORY_DESCRIPTION = (
    "搜尋目前文件中少量、相關且目前有效的完整工作記憶。當近期對話與主題導覽不足以回答、"
    "比較相似案例或核對久遠細節時使用。這不是列舉全部記憶或最終 JD 完整性檢查。"
    "只提供自然語言 query；不要提供文件、員工、scope、limit 或 filter。"
)

READ_CONVERSATION_CONTEXT_DESCRIPTION = (
    "依 search_semantic_memory 實際回傳的 message_ref，讀取目前文件中最小且完整的員工原話"
    "與相鄰顧問問題。只有需要核對原句或短答脈絡時使用；不要自行猜測 message_ref。"
)


class TemporaryMemoryReadError(RuntimeError):
    pass


def _tool_call_id(runtime: ToolRuntime) -> str:
    if runtime.tool_call_id is None:
        raise RuntimeError("ToolNode did not inject a tool call ID")
    return runtime.tool_call_id


async def search_semantic_memory(
    query: Annotated[str, Field(min_length=1)],
    runtime: ToolRuntime[MemoryReadContext, MemoryReadState],
) -> Command:
    """Search bounded current Semantic Memory through trusted runtime scope."""
    context = runtime.context
    if context is None or runtime.store is None:
        raise RuntimeError("Memory read runtime was not injected")
    try:
        result = await search_current_memories(
            SimpleNamespace(store=runtime.store),
            context.scope,
            query,
        )
    except psycopg.OperationalError as exc:
        raise TemporaryMemoryReadError("semantic Memory backend unavailable") from exc

    returned_refs = {
        message_ref
        for memory in result.memories
        for message_ref in memory.message_refs
    }
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="search_semantic_memory",
                    tool_call_id=_tool_call_id(runtime),
                    status="success",
                    content=result.model_dump_json(),
                )
            ],
            "disclosed_message_refs": returned_refs,
        }
    )


async def read_conversation_context(
    message_ref: Annotated[str, Field(min_length=1)],
    runtime: ToolRuntime[MemoryReadContext, MemoryReadState],
) -> dict[str, object]:
    """Read a disclosed canonical message reference in the trusted current scope."""
    context = runtime.context
    if context is None:
        raise RuntimeError("Memory read context was not injected")
    disclosed = runtime.state.get("disclosed_message_refs", set())
    if message_ref not in disclosed:
        raise ReferenceUnavailableError("undisclosed")
    try:
        result = await read_canonical_context(
            context.canonical_runtime,
            context.scope,
            message_ref,
        )
    except psycopg.OperationalError as exc:
        raise TemporaryMemoryReadError("canonical conversation unavailable") from exc
    return result.model_dump(mode="json")


def handle_memory_read_error(
    error: ToolInvocationError
    | ReferenceUnavailableError
    | TemporaryMemoryReadError
    | SemanticIndexUnavailableError,
) -> str:
    if isinstance(error, ToolInvocationError):
        code = "invalid_input"
    elif isinstance(error, ReferenceUnavailableError):
        code = "reference_unavailable"
    else:
        code = "temporary_failure"
    return json.dumps(
        {"error": {"code": code}},
        ensure_ascii=False,
        separators=(",", ":"),
    )


SEARCH_SEMANTIC_MEMORY_TOOL = StructuredTool.from_function(
    coroutine=search_semantic_memory,
    name="search_semantic_memory",
    description=SEARCH_SEMANTIC_MEMORY_DESCRIPTION,
)
READ_CONVERSATION_CONTEXT_TOOL = StructuredTool.from_function(
    coroutine=read_conversation_context,
    name="read_conversation_context",
    description=READ_CONVERSATION_CONTEXT_DESCRIPTION,
)
MEMORY_READ_TOOLS = (
    SEARCH_SEMANTIC_MEMORY_TOOL,
    READ_CONVERSATION_CONTEXT_TOOL,
)


def bind_memory_read_tools(model: Any):
    return model.bind_tools(
        MEMORY_READ_TOOLS,
        strict=True,
        parallel_tool_calls=False,
    )
