"""Real Deep Agents tools and LangGraph injection, without a model/provider."""
import asyncio
import re

import pytest
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore

from caliburn_memory.memory import MemoryArtifacts
from caliburn_memory.read_tools import readonly_file_tools


def _graph(tools):
    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


def _input(name, arguments):
    return {"messages": [HumanMessage("合成訪談原話\r\n  請保留", id="human-original"),
        AIMessage("", id="tool-request", tool_calls=[{
            "name": name, "args": arguments, "id": "call-original", "type": "tool_call"}])]}


def _invoke(graph, name, arguments, document="document-a"):
    return graph.invoke(_input(name, arguments), {"configurable": {"thread_id": document}})


def _memory(knowledge="第一行\n第二行\n第三行"):
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    version = artifacts.save_memory(knowledge=knowledge, guide="工作理解 → /memory/knowledge.md")
    return artifacts, version


def test_factory_preserves_native_tool_call_schemas_and_only_three_read_tools():
    artifacts, version = _memory()
    backend = artifacts.reader(version)
    tools = readonly_file_tools(backend)
    native = FilesystemMiddleware(backend=backend, tools=["ls", "read_file", "grep"]).tools
    assert [tool.name for tool in tools] == ["ls", "read_file", "grep"]
    for actual, expected in zip(tools, native, strict=True):
        assert actual.args_schema is expected.args_schema
        assert actual.tool_call_schema.model_json_schema()["properties"] == expected.tool_call_schema.model_json_schema()["properties"]
        assert actual.func.__module__ == "deepagents.middleware.filesystem"
        assert actual.coroutine is not None


def test_native_0713_requires_a_backend_instance_not_the_removed_factory_api():
    with pytest.raises(TypeError, match="Backend factories were removed in deepagents 0.7"):
        readonly_file_tools(lambda _runtime: None)


@pytest.mark.parametrize("name,arguments", [
    ("ls", {"path": ["PRIVATE_INPUT_MARKER"]}),
    ("grep", {"pattern": {"private": "PRIVATE_INPUT_MARKER"}, "path": "/memory/"}),
    ("read_file", {"file_path": "/memory/knowledge.md", "offset": "PRIVATE_INPUT_MARKER"}),
])
def test_invalid_arguments_use_safe_native_validation_feedback_without_echoing_input(name, arguments):
    artifacts, version = _memory()
    message = _invoke(_graph(readonly_file_tools(artifacts.reader(version))), name, arguments)["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.status == "error"
    assert message.name == name and message.tool_call_id == "call-original"
    assert "PRIVATE_INPUT_MARKER" not in message.content
    assert "invalid_input" in message.content


@pytest.mark.parametrize("name,arguments,expected", [
    ("read_file", {"file_path": "/memory/knowledge.md"}, "第一行"),
    ("ls", {"path": "/memory/"}, "/memory/knowledge.md"),
    ("grep", {"pattern": "第二行", "path": "/memory/", "output_mode": "content"}, "第二行"),
])
def test_native_tool_override_uses_fixed_backend_and_keeps_runtime_state_store(name, arguments, expected):
    artifacts, version = _memory()
    # Base BackendProtocol cannot execute. The App replaces only the backend-
    # bound native tool using the public ToolCallRequest.override seam.
    advertised = readonly_file_tools(BackendProtocol())
    replacements = {tool.name: tool for tool in readonly_file_tools(artifacts.reader(version))}
    intercepted = []

    def wrap(request, handler):
        assert request.runtime.store is artifacts.store
        assert request.runtime.config["configurable"]["thread_id"] == "document-a"
        assert request.state["messages"][0].content == "合成訪談原話\r\n  請保留"
        original = request.tool
        updated = request.override(tool=replacements[request.tool_call["name"]])
        assert request.tool is original and updated.tool is not original
        assert updated.tool_call == request.tool_call
        assert updated.runtime is request.runtime
        intercepted.append(request.tool_call["id"])
        return handler(updated)

    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode(advertised, wrap_tool_call=wrap))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    result = _invoke(graph.compile(store=artifacts.store), name, arguments)
    assert intercepted == ["call-original"]
    assert result["messages"][-1].status == "success"
    assert expected in result["messages"][-1].content


def test_native_read_formats_offsets_and_preserves_original_messages():
    artifacts, version = _memory()
    result = _invoke(_graph(readonly_file_tools(artifacts.reader(version))), "read_file",
        {"file_path": "/memory/knowledge.md", "offset": 1, "limit": 1})
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.status == "success"
    assert message.name == "read_file" and message.tool_call_id == "call-original"
    assert re.search(r"^\s*2  第二行$", message.content, re.MULTILINE)
    assert "第一行" not in message.content and "第三行" not in message.content
    assert result["messages"][:2] == _input("read_file",
        {"file_path": "/memory/knowledge.md", "offset": 1, "limit": 1})["messages"]
    assert set(result) == {"messages"}


@pytest.mark.parametrize("path", ["/memory/missing.md", "/../../outside.txt"])
def test_native_read_errors_keep_tool_identity_and_error_status(path):
    artifacts, version = _memory()
    message = _invoke(_graph(readonly_file_tools(artifacts.reader(version))), "read_file",
        {"file_path": path})["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.name == "read_file" and message.tool_call_id == "call-original"
    assert message.status == "error"
    assert message.content.startswith("Error:")


def test_write_tool_is_not_dispatchable_and_cannot_mutate_saved_memory():
    artifacts, version = _memory()
    message = _invoke(_graph(readonly_file_tools(artifacts.reader(version))), "write_file",
        {"file_path": "/memory/knowledge.md", "content": "不准覆蓋"})["messages"][-1]
    assert message.status == "error"
    assert "write_file" in message.content
    assert artifacts.read_text("/memory/knowledge.md", version) == "第一行\n第二行\n第三行"


def test_fixed_reader_does_not_follow_later_memory_versions():
    artifacts, first = _memory("原版工作理解")
    original = _graph(readonly_file_tools(artifacts.reader(first)))
    second = artifacts.save_memory(knowledge="更正版工作理解", guide="更正導覽")
    current = _graph(readonly_file_tools(artifacts.reader(second)))
    arguments = {"file_path": "/memory/knowledge.md"}
    old_text = _invoke(original, "read_file", arguments)["messages"][-1].content
    new_text = _invoke(current, "read_file", arguments)["messages"][-1].content
    assert "原版工作理解" in old_text and "更正版" not in old_text
    assert "更正版工作理解" in new_text and "原版" not in new_text


def test_grep_is_literal_and_ls_only_lists_the_supplied_memory_backend():
    artifacts, version = _memory("only foo\nonly bar\nliteral foo|bar")
    graph = _graph(readonly_file_tools(artifacts.reader(version)))
    message = _invoke(graph, "grep", {"pattern": "foo|bar", "path": "/memory/",
        "output_mode": "content"})["messages"][-1]
    assert message.status == "success"
    assert "literal foo|bar" in message.content
    assert "only foo" not in message.content and "only bar" not in message.content
    listing = _invoke(graph, "ls", {"path": "/memory/"})["messages"][-1]
    assert listing.status == "success"
    assert "/memory/knowledge.md" in listing.content and "/memory/guide.md" in listing.content


def test_tool_runtime_enforces_the_actual_graph_document_scope():
    artifacts, version = _memory()
    with pytest.raises(ValueError, match="document"):
        _invoke(_graph(readonly_file_tools(artifacts.reader(version))), "read_file",
            {"file_path": "/memory/knowledge.md"}, document="document-b")


def test_long_chinese_native_pages_are_complete_without_offload_or_store_writes():
    expected = [f"案例{i}：" + "條件與例外" * 160 for i in range(41)]
    artifacts, version = _memory("\n".join(expected))
    graph = _graph(readonly_file_tools(artifacts.reader(version)))
    before = artifacts.store.search(("q019-memory", "document-a"), limit=100)
    offset, collected, page_count = 0, [], 0
    for _ in range(10):
        result = _invoke(graph, "read_file", {
            "file_path": "/memory/knowledge.md", "offset": offset, "limit": 2000})
        message = result["messages"][-1]
        assert message.status == "success"
        assert len(message.content) <= 16000
        assert result["messages"][0] == _input("read_file", {})["messages"][0]
        collected.extend(re.findall(r"^\s*\d+  (案例[^\n]+)$", message.content, re.MULTILINE))
        page_count += 1
        next_offset = re.search(r"remaining from offset (\d+)", message.content)
        if next_offset is None:
            break
        assert int(next_offset[1]) > offset
        offset = int(next_offset[1])
    assert page_count > 1
    assert collected == expected
    assert artifacts.store.search(("q019-memory", "document-a"), limit=100) == before


def test_native_async_read_uses_the_same_fixed_backend():
    artifacts, version = _memory()
    graph = _graph(readonly_file_tools(artifacts.reader(version)))
    result = asyncio.run(graph.ainvoke(_input("read_file", {"file_path": "/memory/knowledge.md"}),
        {"configurable": {"thread_id": "document-a"}}))
    assert result["messages"][-1].status == "success"
    assert "第一行" in result["messages"][-1].content
