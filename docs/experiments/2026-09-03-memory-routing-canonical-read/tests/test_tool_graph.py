from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import httpx
import openrouter
import pytest
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.store.memory import InMemoryStore

from memory_read_spike.canonical import (
    append_canonical_round,
    latest_canonical_messages,
)
from memory_read_spike.embeddings import DeterministicEmbeddingSpy
from memory_read_spike.fixtures import (
    load_canonical_rounds,
    semantic_memory_fixtures,
)
from memory_read_spike.graph import (
    MEMORY_READ_RECURSION_LIMIT,
    MemoryReadContext,
    MultipleToolCallsError,
    ToolBudgetExceededError,
    build_memory_read_graph,
    build_transient_input,
    rebuild_memory_guide,
)
from memory_read_spike.runtime import open_spike_runtime, seed_current_memories
from memory_read_spike.scope import TrustedReadScope, issue_message_ref
from memory_read_spike.settings import SpikeSettings
from memory_read_spike.tools import (
    MEMORY_READ_TOOLS,
    TemporaryMemoryReadError,
    bind_memory_read_tools,
)


def _settings() -> SpikeSettings:
    return SpikeSettings(
        database_url=os.environ["MEMORY_ROUTING_SPIKE_DATABASE_URL"],
        expected_database=os.environ["MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"],
        production_database_url=os.environ.get("DATABASE_URL"),
    )


def _scope() -> TrustedReadScope:
    return TrustedReadScope(
        run_id=uuid4(),
        document_id=uuid4(),
        thread_id=f"tool-graph-{uuid4()}",
    )


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


class OneToolThenFinalModel:
    def __init__(self, first: AIMessage) -> None:
        self.first = first
        self.calls = 0
        self.seen_messages: list[tuple[BaseMessage, ...]] = []

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.seen_messages.append(tuple(messages))
        self.calls += 1
        if self.calls == 1:
            return self.first
        return AIMessage(content="完成")


class SearchThenReadModel:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[tuple[BaseMessage, ...]] = []
        self.disclosed_ref: str | None = None

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.seen_messages.append(tuple(messages))
        self.calls += 1
        if self.calls == 1:
            return _tool_call(
                "search_semantic_memory",
                {"query": "餐飲預約網站三間分店過敏 Safari"},
                "call-search",
            )
        if self.calls == 2:
            search_result = next(
                message
                for message in reversed(messages)
                if isinstance(message, ToolMessage)
                and message.name == "search_semantic_memory"
            )
            self.disclosed_ref = json.loads(search_result.content)["memories"][0][
                "message_refs"
            ][1]
            return _tool_call(
                "read_conversation_context",
                {"message_ref": self.disclosed_ref},
                "call-read",
            )
        return AIMessage(content="已依工作記憶與員工原話完成核對。")


class AlwaysToolModel:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages: Sequence[BaseMessage]) -> AIMessage:
        self.calls += 1
        return _tool_call(
            "search_semantic_memory",
            {"query": ""},
            f"call-{self.calls}",
        )


def _last_tool_message(result: dict[str, Any]) -> ToolMessage:
    message = next(
        message
        for message in reversed(result["messages"])
        if isinstance(message, ToolMessage)
    )
    assert isinstance(message, ToolMessage)
    return message


def test_two_tools_have_frozen_descriptions_and_exact_one_field_schemas() -> None:
    assert [tool.name for tool in MEMORY_READ_TOOLS] == [
        "search_semantic_memory",
        "read_conversation_context",
    ]
    assert [tool.description for tool in MEMORY_READ_TOOLS] == [
        "搜尋目前文件中少量、相關且目前有效的完整工作記憶。當近期對話與主題導覽不足以回答、"
        "比較相似案例或核對久遠細節時使用。這不是列舉全部記憶或最終 JD 完整性檢查。"
        "只提供自然語言 query；不要提供文件、員工、scope、limit 或 filter。",
        "依 search_semantic_memory 實際回傳的 message_ref，讀取目前文件中最小且完整的員工原話"
        "與相鄰顧問問題。只有需要核對原句或短答脈絡時使用；不要自行猜測 message_ref。",
    ]

    expected_fields = ("query", "message_ref")
    for tool, expected_field in zip(MEMORY_READ_TOOLS, expected_fields, strict=True):
        # ``args_schema`` also contains LangGraph's injected ``ToolRuntime``.
        # ``tool_call_schema`` is the framework-owned schema actually exposed
        # to the model/provider after injected arguments are removed.
        schema = tool.tool_call_schema.model_json_schema()
        assert set(schema["properties"]) == {expected_field}
        assert schema["required"] == [expected_field]
        assert {
            "document_id",
            "thread_id",
            "run_id",
            "namespace",
            "limit",
            "filter",
            "runtime",
        }.isdisjoint(schema["properties"])

    # ``strict=True`` is applied while the provider request is built, so the
    # following HTTP-boundary test owns ``additionalProperties: false``.


@pytest.mark.asyncio
async def test_openrouter_actual_request_uses_strict_serial_tools() -> None:
    captured: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "gen-test",
                "object": "chat.completion",
                "created": 1,
                "model": "openai/test-model",
                "provider": "test-provider",
                "system_fingerprint": "fp-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "完成"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        sdk_client = openrouter.OpenRouter(
            api_key="test-only",
            server_url="https://openrouter.test/api/v1",
            async_client=async_client,
            retry_config=None,
        )
        model = ChatOpenRouter(
            client=sdk_client,
            model="openai/test-model",
            api_key="test-only",
            max_retries=0,
        )
        bound = bind_memory_read_tools(model)
        await bound.ainvoke("測試 strict tool request")

    payload = captured[-1]
    assert payload["parallel_tool_calls"] is False
    assert [tool["function"]["name"] for tool in payload["tools"]] == [
        "search_semantic_memory",
        "read_conversation_context",
    ]
    for tool, required in zip(payload["tools"], (["query"], ["message_ref"]), strict=True):
        function = tool["function"]
        assert function["strict"] is True
        assert function["parameters"]["required"] == required
        assert set(function["parameters"]["properties"]) == set(required)
        assert function["parameters"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_full_tool_graph_keeps_disclosure_transient_and_checkpoint_immutable() -> None:
    settings = _settings()
    scope = _scope()
    rounds = load_canonical_rounds()

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        for human, assistant in rounds:
            await append_canonical_round(runtime, scope, human, assistant)
        await seed_current_memories(runtime, scope, semantic_memory_fixtures(scope))
        canonical_before = await latest_canonical_messages(runtime, scope)
        guide = await rebuild_memory_guide(runtime.store, scope)
        model = SearchThenReadModel()
        graph = build_memory_read_graph(model, store=runtime.store)
        initial = build_transient_input(
            system_instructions="只根據可見內容與工具結果回答。",
            user_request="核對 A 案過敏欄位的員工精確原句。",
            canonical_messages=canonical_before,
            memory_guide=guide,
        )
        result = await graph.ainvoke(
            initial,
            context=MemoryReadContext(scope=scope, canonical_runtime=runtime),
        )
        canonical_after = await latest_canonical_messages(runtime, scope)

        assert model.calls == 3
        assert model.disclosed_ref is not None
        tool_messages = [
            message for message in result["messages"] if isinstance(message, ToolMessage)
        ]
        assert [(message.name, message.tool_call_id, message.status) for message in tool_messages] == [
            ("search_semantic_memory", "call-search", "success"),
            ("read_conversation_context", "call-read", "success"),
        ]
        assert model.disclosed_ref in result["disclosed_message_refs"]
        assert json.loads(tool_messages[-1].content)["context"][-1]["text"] == (
            rounds[2][0].content
        )

        first_call_text = "\n".join(
            str(message.content) for message in model.seen_messages[0]
        )
        assert len(
            [
                message
                for message in model.seen_messages[0]
                if message.id in {item.id for item in canonical_before}
            ]
        ) == 6
        assert rounds[2][0].content not in first_call_text
        assert "A 案：餐飲預約網站" in first_call_text
        assert "三間分店" not in guide
        assert "mref_v1_" not in guide

        assert [type(message) for message in canonical_after] == [
            type(message) for message in canonical_before
        ]
        assert [message.id for message in canonical_after] == [
            message.id for message in canonical_before
        ]
        assert [message.content for message in canonical_after] == [
            message.content for message in canonical_before
        ]

        independent_model = OneToolThenFinalModel(
            _tool_call(
                "read_conversation_context",
                {"message_ref": model.disclosed_ref},
                "call-undisclosed",
            )
        )
        independent_graph = build_memory_read_graph(
            independent_model,
            store=runtime.store,
        )
        independent = await independent_graph.ainvoke(
            build_transient_input(
                system_instructions="測試",
                user_request="直接讀取",
                canonical_messages=canonical_after,
                memory_guide=guide,
            ),
            context=MemoryReadContext(scope=scope, canonical_runtime=runtime),
        )

    undisclosed = _last_tool_message(independent)
    assert undisclosed.status == "error"
    assert undisclosed.tool_call_id == "call-undisclosed"
    assert json.loads(undisclosed.content) == {
        "error": {"code": "reference_unavailable"}
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "args", "expected_status", "expected_payload"),
    [
        (
            "search_semantic_memory",
            {"query": ""},
            "error",
            {"error": {"code": "invalid_input"}},
        ),
        (
            "read_conversation_context",
            {"message_ref": "not-issued-by-search"},
            "error",
            {"error": {"code": "reference_unavailable"}},
        ),
        (
            "search_semantic_memory",
            {"query": "此 scope 沒有資料"},
            "success",
            {"memories": []},
        ),
    ],
)
async def test_tool_node_normalizes_validation_reference_and_empty_success(
    tool_name: str,
    args: dict[str, Any],
    expected_status: str,
    expected_payload: dict[str, Any],
) -> None:
    settings = _settings()
    scope = _scope()
    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        model = OneToolThenFinalModel(_tool_call(tool_name, args, "call-one"))
        graph = build_memory_read_graph(model, store=runtime.store)
        result = await graph.ainvoke(
            build_transient_input(
                system_instructions="測試",
                user_request="執行一次工具",
                canonical_messages=(),
                memory_guide="目前文件可搜尋的工作記憶主題：\n- （無）",
            ),
            context=MemoryReadContext(scope=scope, canonical_runtime=runtime),
        )

    message = _last_tool_message(result)
    assert message.status == expected_status
    assert message.tool_call_id == "call-one"
    assert json.loads(message.content) == expected_payload
    assert "Traceback" not in message.content


@pytest.mark.asyncio
async def test_expected_temporary_failure_is_generic_but_unexpected_error_escapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.tools as tools_module

    settings = _settings()
    scope = _scope()

    async def temporary(*_args, **_kwargs):
        raise TemporaryMemoryReadError("backend socket contains sensitive detail")

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        monkeypatch.setattr(tools_module, "search_current_memories", temporary)
        temporary_model = OneToolThenFinalModel(
            _tool_call(
                "search_semantic_memory",
                {"query": "A 案"},
                "call-temporary",
            )
        )
        graph = build_memory_read_graph(temporary_model, store=runtime.store)
        result = await graph.ainvoke(
            build_transient_input(
                system_instructions="測試",
                user_request="搜尋",
                canonical_messages=(),
                memory_guide="目前文件可搜尋的工作記憶主題：\n- A",
            ),
            context=MemoryReadContext(scope=scope, canonical_runtime=runtime),
        )
        message = _last_tool_message(result)
        assert json.loads(message.content) == {
            "error": {"code": "temporary_failure"}
        }
        assert "sensitive" not in message.content

        async def unexpected(*_args, **_kwargs):
            raise RuntimeError("unexpected programming defect")

        monkeypatch.setattr(tools_module, "search_current_memories", unexpected)
        unexpected_model = OneToolThenFinalModel(
            _tool_call(
                "search_semantic_memory",
                {"query": "A 案"},
                "call-unexpected",
            )
        )
        failing_graph = build_memory_read_graph(unexpected_model, store=runtime.store)
        with pytest.raises(RuntimeError, match="unexpected programming defect"):
            await failing_graph.ainvoke(
                build_transient_input(
                    system_instructions="測試",
                    user_request="搜尋",
                    canonical_messages=(),
                    memory_guide="目前文件可搜尋的工作記憶主題：\n- A",
                ),
                context=MemoryReadContext(scope=scope, canonical_runtime=runtime),
            )


def test_graph_budget_is_frozen_and_topology_has_no_summary_or_writer_node() -> None:
    graph = build_memory_read_graph(
        OneToolThenFinalModel(AIMessage(content="完成")),
        store=InMemoryStore(),
    )

    assert MEMORY_READ_RECURSION_LIMIT == 6
    assert graph.config["recursion_limit"] == 6
    assert set(graph.get_graph().nodes) == {"__start__", "model", "tools", "__end__"}
    assert graph.checkpointer is None


@pytest.mark.asyncio
async def test_graph_rejects_parallel_calls_and_a_third_tool_request() -> None:
    parallel_model = OneToolThenFinalModel(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_semantic_memory",
                    "args": {"query": "A"},
                    "id": "parallel-a",
                    "type": "tool_call",
                },
                {
                    "name": "search_semantic_memory",
                    "args": {"query": "B"},
                    "id": "parallel-b",
                    "type": "tool_call",
                },
            ],
        )
    )
    parallel_graph = build_memory_read_graph(parallel_model, store=InMemoryStore())
    initial = build_transient_input(
        system_instructions="測試",
        user_request="搜尋",
        canonical_messages=(),
        memory_guide="目前文件可搜尋的工作記憶主題：\n- （無）",
    )
    with pytest.raises(MultipleToolCallsError, match="parallel tool calls"):
        await parallel_graph.ainvoke(initial)

    repeated_model = AlwaysToolModel()
    repeated_graph = build_memory_read_graph(repeated_model, store=InMemoryStore())
    with pytest.raises(ToolBudgetExceededError, match="third tool call"):
        await repeated_graph.ainvoke(initial)
    assert repeated_model.calls == 3
