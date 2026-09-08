"""Q019 boundary tests: actual frameworks, only paid provider I/O is synthetic."""

import importlib.util
import json
import base64
import re

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from test_native_continuity import assistant_text, response_body


def modules():
    # A missing feature is an explicit assertion in the first red run.
    assert importlib.util.find_spec("analysis_agent.sources"), "Missing source-reference reader"
    from analysis_agent.sources import ConversationReader
    from analysis_agent.memory import MemoryArtifacts
    from analysis_agent.memory_tools import memory_access
    return ConversationReader, MemoryArtifacts, memory_access


def setup_source(saver=None, document="document-a", answer="不是，例外由主管核准。"):
    Reader, _, _ = modules()
    saver = saver or InMemorySaver()
    # update_state is the public deterministic fixture insertion seam; no model.
    model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected model call"))))
    graph = build_agent(model=model, checkpointer=saver, instructions="test")
    config = {"configurable": {"thread_id": document}}
    graph.update_state(config, {"messages": [
        AIMessage(content=[{"type": "reasoning", "encrypted_content": "opaque-secret", "summary": []}, {"type": "text", "text": "例外也是你核准嗎？"}], id="question-a"),
        HumanMessage(answer, id="answer-a"),
    ]}, as_node="model")
    reader = Reader(graph, document)
    reference = reader.capture("question-a", "answer-a")
    return graph, reader, reference, config


def test_references_reopen_exact_question_answer_and_never_latest_or_reasoning():
    Reader, _, _ = modules()
    graph, reader, ref, config = setup_source()
    graph.update_state(config, {"messages": [HumanMessage("另一個案例是每月結算。", id="answer-b")]}, as_node="model")
    page = Reader(graph, "document-a").read(ref)
    assert [(s["role"], s["text"]) for s in page["segments"]] == [
        ("assistant", "例外也是你核准嗎？"), ("user", "不是，例外由主管核准。")]
    assert page["next_offset"] is None
    assert "opaque-secret" not in json.dumps(page)
    assert "每月結算" not in json.dumps(page, ensure_ascii=False)
    with pytest.raises(ValueError, match="document"):
        Reader(graph, "document-b").read(ref)
    with pytest.raises(ValueError):
        reader.read("invented-reference")
    with pytest.raises(ValueError):
        reader.read(ref, offset=-1)


def test_long_chinese_answer_is_read_completely_without_skips():
    _, reader, ref, _ = setup_source(answer="長案例：" + "甲乙丙丁🛠" * 2500 + "特殊尾端")
    pages, offset = [], 0
    while True:
        page = reader.read(ref, offset=offset)
        assert sum(len(s["text"]) for s in page["segments"]) <= 3000
        pages.extend(page["segments"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    answer = "".join(s["text"] for s in pages if s["role"] == "user")
    assert answer == "長案例：" + "甲乙丙丁🛠" * 2500 + "特殊尾端"


def test_unknown_checkpoint_and_missing_messages_do_not_return_latest():
    _, reader, ref, _ = setup_source()
    data = json.loads(base64.urlsafe_b64decode(ref[13:]))
    for field, bad_value in [("checkpoint", "00000000-0000-0000-0000-000000000000"), ("first", "missing-message")]:
        altered = dict(data, **{field: bad_value})
        bad_ref = "conversation:" + base64.urlsafe_b64encode(json.dumps(altered).encode()).decode()
        with pytest.raises(ValueError, match="unavailable"):
            reader.read(bad_ref)


def test_incomplete_source_window_is_not_sealed_for_extraction():
    from langgraph.graph import StateGraph, START, END
    Reader, _, _ = modules()
    graph = StateGraph(dict).add_node("unfinished", lambda s: s).add_edge(START, "unfinished").add_edge("unfinished", END).compile(checkpointer=InMemorySaver())
    graph.update_state({"configurable": {"thread_id": "document-a"}}, {"messages": [HumanMessage("尚未答完", id="first")]}, as_node=START)
    with pytest.raises(ValueError, match="completed"):
        Reader(graph, "document-a").capture("first", "first")


def test_all_knowledge_lines_can_be_enumerated_without_top_k():
    _, Artifacts, _ = modules()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    knowledge = "\n".join(f"工作細節{i}：條件與例外" for i in range(137))
    reader = artifacts.reader(artifacts.save_memory(knowledge=knowledge, guide="導覽"))
    lines, offset = [], 0
    while True:
        result = reader.read("/memory/knowledge.md", offset=offset, limit=50)
        assert not result.error
        lines.extend(result.file_data["content"].splitlines())
        assert result.end_line - result.start_line + 1 <= 50
        if result.next_offset is None:
            break
        assert result.next_offset > offset
        offset = result.next_offset
    assert "\n".join(lines) == knowledge


@pytest.mark.parametrize("separator", ["\n", "\r\n", "\u2028", "\x85"])
def test_official_model_visible_pagination_preserves_every_long_line(separator):
    from langgraph.graph import MessagesState, StateGraph, START, END
    from langgraph.prebuilt import ToolNode
    _, Artifacts, make_access = modules()
    _, source, _, _ = setup_source()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    expected = [f"案例{i}：" + "中文細節" * 240 for i in range(41)]
    version = artifacts.save_memory(knowledge=separator.join(expected), guide="導覽")
    _, tools = make_access(artifacts, version, source)
    graph = StateGraph(MessagesState).add_node("tools", ToolNode(tools)).add_edge(START, "tools").add_edge("tools", END).compile()
    actual, offset, pages = [], 0, 0
    while True:
        result = graph.invoke({"messages": [AIMessage("", tool_calls=[{"name": "read_file", "args": {"file_path": "/memory/knowledge.md", "offset": offset, "limit": 2000}, "id": "read"}])]}, {"configurable": {"thread_id": "document-a"}})
        output = result["messages"][-1]
        assert output.status == "success"
        assert len(output.content) <= 16000
        actual.extend(re.findall(r"^\s*\d+  (案例[^\n]+)$", output.content, re.MULTILINE))
        more = re.search(r"remaining from offset (\d+)", output.content)
        pages += 1
        if not more:
            break
        new_offset = int(more.group(1))
        assert new_offset > offset
        offset = new_offset
    assert pages > 1
    assert actual == expected


@pytest.mark.parametrize("content", [
    "參閱 /interviews/missing/summary.md",
    "參阅 [案例][case]\n\n[case]: /interviews/missing/summary.md",
    "參阅 `/interviews/missing/summary.md`",
])
def test_unavailable_literal_addresses_are_rejected_in_all_reference_styles(content):
    _, Artifacts, _ = modules()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    with pytest.raises(ValueError, match="reference"):
        artifacts.save_memory(knowledge=content, guide="導覽")


@pytest.mark.parametrize("suffix", [".", "...", "。"])
def test_existing_bare_reference_accepts_sentence_punctuation(suffix):
    _, Artifacts, _ = modules()
    _, _, ref, _ = setup_source()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    record = artifacts.save_extraction(summary="案例", candidates="線索", slug="案例", source_reference=ref)
    knowledge = f"See {record.summary_path}{suffix}"
    version = artifacts.save_memory(knowledge=knowledge, guide="導覽")
    assert artifacts.reader(version).read("/memory/knowledge.md").file_data["content"] == knowledge


def test_read_only_backend_rejects_cross_document_tool_execution():
    from langgraph.graph import StateGraph, START, END
    _, Artifacts, _ = modules()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    version = artifacts.save_memory(knowledge="A sensitive content", guide="A guide")
    reader = artifacts.reader(version)

    def read_node(state: dict):
        return {"result": reader.read("/memory/knowledge.md")}

    workflow = StateGraph(dict).add_node("read", read_node).add_edge(START, "read").add_edge("read", END).compile()
    with pytest.raises(ValueError, match="document"):
        workflow.invoke({}, {"configurable": {"thread_id": "document-b"}})


def test_large_directory_returns_explicit_error_instead_of_unbounded_listing():
    from deepagents.backends.protocol import LsResult
    from analysis_agent.memory import ReadOnlyFiles

    class LargeDirectory:
        def ls(self, path):
            return LsResult(entries=[{"path": f"/{i}.md", "is_dir": False} for i in range(101)])

    result = ReadOnlyFiles(LargeDirectory(), "document-a").ls("/")
    assert result.error and not result.entries


def test_artifacts_have_real_addresses_and_fixed_isolated_read_versions():
    _, Artifacts, _ = modules()
    _, _, ref, _ = setup_source()
    store = InMemoryStore()
    artifacts = Artifacts(store, "document-a")
    extraction = artifacts.save_extraction(summary="案例 A 是單次付款，例外由主管核准。", candidates="網站交付與例外核准的責任不同。", slug="網站 A / 付款", source_reference=ref)
    version = artifacts.save_memory(knowledge=f"# 前端開發\n依客戶需求開發網站。\n[案例 A]({extraction.summary_path})", guide="網站案例 A → /memory/knowledge.md")
    access = artifacts.reader(version)
    assert extraction.summary_path in access.read("/memory/knowledge.md").file_data["content"]
    summary = access.read(extraction.summary_path, limit=4)
    # Backend pages honestly advertise the source header and remaining lines.
    assert ref in summary.file_data["content"]
    assert summary.next_offset is not None
    assert access.read(extraction.summary_path, offset=summary.next_offset).file_data["content"]
    new_version = artifacts.save_memory(knowledge="# 前端開發\n新規則：專案經理核准。", guide="新版網站導覽")
    assert "專案經理" not in access.read("/memory/knowledge.md").file_data["content"]
    assert "專案經理" in artifacts.reader(new_version).read("/memory/knowledge.md").file_data["content"]
    with pytest.raises(ValueError, match="document"):
        Artifacts(store, "document-b").reader(version)
    empty_b = Artifacts(store, "document-b").save_memory(knowledge="B only", guide="B guide")
    assert Artifacts(store, "document-b").reader(empty_b).read(extraction.summary_path).error
    with pytest.raises((PermissionError, NotImplementedError)):
        access.write("/memory/knowledge.md", "corrupt")
    with pytest.raises(ValueError, match="line"):
        artifacts.save_memory(knowledge="太" * 2001, guide="guide")
    with pytest.raises(ValueError, match="reference"):
        artifacts.save_memory(knowledge="[不存在](/interviews/missing/summary.md)", guide="guide")


def test_official_tools_follow_guide_memory_summary_source_in_compiled_agent():
    _, Artifacts, make_access = modules()
    graph, source, ref, config = setup_source()
    artifacts = Artifacts(InMemoryStore(), "document-a")
    record = artifacts.save_extraction(summary="案例 A 由主管核准例外。", candidates="例外核准不是員工責任。", slug="案例A", source_reference=ref)
    version = artifacts.save_memory(knowledge=f"# 網站\n案例 A\n[詳記]({record.summary_path})", guide="網站案例請搜尋 /memory/knowledge.md")
    middleware, tools = make_access(artifacts, version, source)
    requests = []
    calls = [("grep", {"pattern": "案例 A", "path": "/memory/knowledge.md"}),
             ("read_file", {"file_path": "/memory/knowledge.md"}),
             ("read_file", {"file_path": record.summary_path}),
             ("read_conversation", {"reference": record.summary_path})]

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        i = len(requests) - 1
        assert "網站案例請搜尋" in json.dumps(payload["input"], ensure_ascii=False)
        # CT43 checks what the real SDK sends, not natural model obedience.
        system_text = json.dumps([item for item in payload['input'] if item.get('role') in {'system', 'developer'}], ensure_ascii=False)
        assert "call read_conversation(reference=<known summary path>)" in system_text
        assert "not a reconstructed encoded locator" in system_text
        tool_names = {t["name"] for t in payload["tools"]}
        assert tool_names == {"ls", "grep", "read_file", "read_conversation"}
        if i < len(calls):
            name, args = calls[i]
            body = response_body([
                {"type": "reasoning", "id": f"rs_{i}", "summary": [], "encrypted_content": "opaque-step"},
                {"type": "function_call", "id": f"fc_{i}", "call_id": f"call_{i}", "name": name, "arguments": json.dumps(args), "status": "completed"},
            ], f"resp_{i}")
        else:
            if i == len(calls):
                assert "不是，例外由主管核准。" in json.dumps(payload, ensure_ascii=False)
                body = response_body([
                    {"type": "compaction", "id": "cmp_memory", "encrypted_content": "opaque-compaction"},
                    {"type": "reasoning", "id": "rs_after", "encrypted_content": "opaque-after", "summary": []},
                    assistant_text("原話確認例外由主管核准。", "msg_done")])
            else:
                body = response_body([assistant_text("下一個案例呢？", "msg_next")])
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        agent = build_agent(model=build_model(model="gpt-5.6-luna", api_key="offline", http_client=client), checkpointer=graph.checkpointer, instructions="固定訪談規則", tools=tools, middleware=middleware)
        result = agent.invoke({"messages": [HumanMessage("請核實案例A。", id="new-question")]}, config, durability="sync")
        agent.invoke({"messages": [HumanMessage("繼續下一題", id="next-question")]}, config, durability="sync")
    assert len(requests) == 6
    assert result["messages"][-1].text == "原話確認例外由主管核准。"
    assert any(x.get("encrypted_content") == "opaque-step" for x in requests[-2]["input"])
    assert any(x.get("encrypted_content") == "opaque-compaction" for x in requests[-1]["input"])
    assert any(x.get("encrypted_content") == "opaque-after" for x in requests[-1]["input"])
    assert not any(x.get("type") == "function_call_output" for x in requests[-1]["input"])
    assert source.read(ref)["segments"][1]["text"] == "不是，例外由主管核准。"
    # No additional archive/offload state written by filesystem middleware.
    assert "files" not in agent.get_state(config).values
