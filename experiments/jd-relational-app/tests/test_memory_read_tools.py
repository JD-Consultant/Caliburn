"""Source paging and native ToolRuntime handoff: in-memory only, zero provider."""
import json
from types import SimpleNamespace
from uuid import uuid4

from caliburn_memory.memory import MemoryArtifacts
from langchain_core.messages import AIMessage
from langchain_core.tools import ToolException
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore
import pytest

from jd_relational.conversation_sources import ConversationSourceError, SourceExcerpt, SourceMessage
from jd_relational.memory_context import MemoryReadError, MemoryReadSession
from jd_relational.memory_read_tools import build_conversation_read_tool, source_page
from jd_relational.memory_sources import MemorySourceReader
from test_chat_history import native
from test_conversation_sources import seed, service


def test_page_preserves_exact_unicode_and_original_message_positions():
    first = "問句\r\n" + "界" * 2992 + "😀\u0301"
    second = "  員工原話\r\n" + "答" * 4000
    excerpt = SourceExcerpt("conversation:original", (
        SourceMessage("question", "assistant", first), SourceMessage("human", "user", second)))
    recovered = {"question": "", "human": ""}
    offset = 0
    pages = []
    while True:
        page = source_page(excerpt, offset)
        pages.append(page)
        assert page["reference"] == excerpt.source_ref
        assert sum(len(s["text"]) for s in page["segments"]) <= 3000
        for segment in page["segments"]:
            assert segment["text_offset"] == len(recovered[segment["message_id"]])
            recovered[segment["message_id"]] += segment["text"]
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert recovered == {"question": first, "human": second}
    assert len(pages[0]["segments"]) == 2
    assert source_page(excerpt, len(first) + len(second))["segments"] == []


@pytest.mark.parametrize("offset", [-1, True, 1.5, "0", 2**63, 4])
def test_bad_offset_is_a_repairable_tool_error(offset):
    with pytest.raises(ToolException, match="^invalid_input"):
        source_page(SourceExcerpt("original", (SourceMessage("m", "user", "字"),)), offset)


class ReadState(MessagesState):
    jd_memory_view: dict


@pytest.fixture
def bound(native):
    observed, _ = seed(native)
    _, dataset, document, *_ = native
    owner = service(native)
    source = MemorySourceReader(owner, document)
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, document, source=source)
    session = MemoryReadSession(dataset, document, observed.record.run_id, artifacts, source,
                                None, "", artifacts.reader(None))
    context = SimpleNamespace(dataset_id=dataset, document_id=document, run_id=session.run_id,
                              memory_session=session, stop_event=None)
    graph = StateGraph(ReadState)
    graph.add_node("tools", ToolNode([build_conversation_read_tool()]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile(store=store)
    ref = owner.capture(document, session.run_id).source_ref
    def invoke(arguments, *, thread=document, view=None):
        result = compiled.invoke({"jd_memory_view": session.view if view is None else view,
            "messages": [AIMessage(content="", tool_calls=[{"id": "original-call",
                "name": "read_conversation", "args": arguments}])]},
            {"configurable": {"thread_id": thread}}, context=context)
        message = result["messages"][-1]
        return message, json.loads(message.content) if message.status == "success" else message.content
    return session, owner, ref, invoke, context


def test_native_tool_runtime_keeps_scope_hidden_and_original_public_messages(bound):
    session, owner, ref, invoke, _ = bound
    schema = build_conversation_read_tool().tool_call_schema
    schema = schema if isinstance(schema, dict) else schema.model_json_schema()
    assert set(schema["properties"]) == {"reference", "offset", "part"}
    message, page = invoke({"reference": ref})
    assert message.tool_call_id == "original-call" and message.status == "success"
    assert page["reference"] == ref
    assert [(s["message_id"], s["role"], s["text"]) for s in page["segments"]] == [
        (m.message_id, m.role, m.text) for m in owner.read(ref, session.document_id).messages]
    assert "PRIVATE" not in json.dumps(page)


def test_summary_header_routes_source_and_context_through_the_same_owner(bound):
    session, owner, ref, invoke, _ = bound
    bare = ref.removeprefix("conversation:")
    files = session.artifacts.save_extraction(summary="這是詳記，不是原話", candidates="候選",
        slug="合成", source_reference=ref, context_reference=bare)
    _, page = invoke({"reference": files.summary_path})
    assert page["reference"] == ref and page["summary_path"] == files.summary_path
    assert page["part"] == "source" and page["context_available"] is True
    _, context = invoke({"reference": files.summary_path, "part": "context"})
    assert context["reference"] == bare and context["part"] == "context"
    assert context["segments"] == page["segments"]
    assert "這是詳記" not in json.dumps(context)


def test_no_separate_context_is_explicit_without_fake_source_read(bound, monkeypatch):
    session, owner, ref, invoke, _ = bound
    files = session.artifacts.save_extraction(summary="詳記", candidates="候選", slug="合成",
                                             source_reference=ref)
    monkeypatch.setattr(owner, "read", lambda *args: pytest.fail("No context is not a source read"))
    _, page = invoke({"reference": files.summary_path, "part": "context"})
    assert page["context_available"] is False and page["reference"] is None
    assert page["segments"] == [] and page["next_offset"] is None and page["notice"]
    message, error = invoke({"reference": files.summary_path, "part": "context", "offset": 1})
    assert message.status == "error" and "invalid_input" in error


@pytest.mark.parametrize("change", ["negative", "bool", "extra", "direct-context", "wrong-ref", "missing-summary", "malformed-summary-id"])
def test_model_input_errors_are_fixed_native_tool_errors(bound, change):
    _, _, ref, invoke, _ = bound
    args = {"reference": ref}
    if change == "negative": args["offset"] = -1
    elif change == "bool": args["offset"] = True
    elif change == "extra": args["document_id"] = str(uuid4())
    elif change == "direct-context": args["part"] = "context"
    elif change == "wrong-ref": args["reference"] = "conversation:RAW_SECRET-invalid"
    elif change == "malformed-summary-id": args["reference"] = "/interviews/bad/summary.md"
    else: args["reference"] = f"/interviews/{uuid4()}/summary.md"
    message, error = invoke(args)
    assert message.status == "error"
    assert any(code in error for code in ("invalid_input", "invalid_ref", "summary_missing"))
    assert "RAW_SECRET" not in error


@pytest.mark.parametrize("change", ["thread", "context", "view", "stop"])
def test_online_scope_is_checked_before_source_or_store(bound, monkeypatch, change):
    session, owner, ref, invoke, context = bound
    monkeypatch.setattr(owner, "read", lambda *args: pytest.fail("Wrong session must not read"))
    kwargs = {}
    if change == "thread": kwargs["thread"] = str(uuid4())
    elif change == "context": context.document_id = str(uuid4())
    elif change == "view": kwargs["view"] = session.view | {"revision": 4}
    else:
        from threading import Event
        context.stop_event = Event()
        context.stop_event.set()
    with pytest.raises(MemoryReadError) as raised:
        invoke({"reference": ref}, **kwargs)
    assert raised.value.code == "invalid_memory_session"


def test_source_unavailable_aborts_instead_of_becoming_a_model_retry(bound, monkeypatch):
    _, owner, ref, invoke, _ = bound
    def failed(*args): raise ConversationSourceError("source_not_available")
    monkeypatch.setattr(owner, "read", failed)
    with pytest.raises(ConversationSourceError) as raised:
        invoke({"reference": ref})
    assert raised.value.code == "source_not_available"


def test_store_io_aborts_instead_of_claiming_summary_missing(bound, monkeypatch):
    session, _, ref, invoke, _ = bound
    files = session.artifacts.save_extraction(summary="詳記", candidates="候選", slug="合成",
                                             source_reference=ref)
    def failed(*args, **kwargs): raise RuntimeError("RAW_STORAGE_SECRET")
    monkeypatch.setattr(type(session.artifacts.store), "get", failed)
    with pytest.raises(MemoryReadError) as raised:
        invoke({"reference": files.summary_path})
    assert raised.value.code == "memory_not_available"
    assert str(raised.value) == "memory_not_available" and raised.value.__suppress_context__


def test_unknown_value_error_is_not_downgraded_to_repairable_input(bound, monkeypatch):
    session, _, ref, invoke, _ = bound
    def failed(*args): raise ValueError("RAW_STORAGE_SECRET")
    monkeypatch.setattr(session.artifacts, "source_window", failed)
    with pytest.raises(MemoryReadError) as raised:
        invoke({"reference": f"/interviews/{uuid4()}/summary.md"})
    assert raised.value.code == "memory_not_available"


def test_summary_without_runtime_header_never_guesses_locator(bound):
    session, _, ref, invoke, _ = bound
    summary_path = f"/interviews/{uuid4()}/summary.md"
    session.artifacts._save(session.artifacts.interview_backend(),
        summary_path.removeprefix("/interviews"), f"Model prose\nSource: {ref}\n")
    message, error = invoke({"reference": summary_path})
    assert message.status == "error" and error.startswith("invalid_ref:")


def test_direct_previously_saved_bare_reference_is_not_reissued(bound):
    _, _, ref, invoke, _ = bound
    bare = ref.removeprefix("conversation:")
    message, page = invoke({"reference": bare})
    assert message.status == "success" and page["reference"] == bare
