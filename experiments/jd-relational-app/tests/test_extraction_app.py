"""B1 application wiring: adopted workflow, this App's source owner, real SDK.

Every B1 provider request is answered in-process by httpx.MockTransport using
the real OpenRouter SDK and strict structured-output binding. The network is
not used. No provider access, model-quality claim, publication or JD tool.
"""
import asyncio
import json

import httpx
import pytest
from caliburn_memory import MemoryArtifacts
from caliburn_memory.extraction import ExtractionOutput
from caliburn_memory.sources import (
    EvidenceExchangePage, EvidenceTextPage, InvalidSourceReference,
)
from openrouter.errors import BadRequestResponseError
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from openai.types.responses import Response

from jd_relational.ai_history import MAX_PARENT_LOOKUPS
from jd_relational.conversation_sources import ConversationSourceError, WindowBudgetExceeded
from jd_relational.extraction_app import (
    ExtractionSourceAdapter, accepted, build_extraction_model, build_extraction_workflow,
)
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.openrouter_model import OPENROUTER_HEADERS
from support.openrouter_replies import (
    refused as openrouter_refused, reply as openrouter_reply,
    truncated as openrouter_truncated,
)

from test_chat_history import native
from test_interview_window_source import interview, settled


def response_body(output: list[dict], *, status: str = "completed", incomplete: dict | None = None) -> dict:
    """Validate synthetic items with the installed official SDK response schema."""
    return Response.model_validate({
        "id": "resp_test", "object": "response", "created_at": 1788624000,
        "model": "gpt-5.6-luna", "status": status, "output": output,
        "incomplete_details": incomplete, "parallel_tool_calls": False,
        "tool_choice": "auto", "tools": [], "store": False,
        "reasoning": {"effort": "high", "context": "all_turns"},
        "usage": {"input_tokens": 100,
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens": 20, "output_tokens_details": {"reasoning_tokens": 10},
                  "total_tokens": 120},
    }).model_dump(mode="json", exclude_none=True)


def assistant_text(text: str) -> dict:
    return {"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
            "phase": "final_answer", "content": [{"type": "output_text", "text": text, "annotations": []}]}


def fields(summary="甲案：單次付款、無障礙。\n乙案：月租、權限分級。", candidates="兩案計費與權限條件不同。",
           slug="網站案例"):
    return json.dumps({"rollout_summary": summary, "raw_memory": candidates,
                       "rollout_slug": slug}, ensure_ascii=False)


def completed(**kwargs) -> dict:
    """Legacy Responses fixture retained only while B2 remains on that seam."""
    return response_body([assistant_text(fields(**kwargs))])


def refused() -> dict:
    return response_body([{"type": "message", "id": "msg_refusal", "role": "assistant",
                           "status": "completed", "phase": "final_answer",
                           "content": [{"type": "refusal", "refusal": "無法協助。"}]}])


def truncated() -> dict:
    return response_body([assistant_text('{"rollout_summary": "甲案：單次付')], status="incomplete",
                         incomplete={"reason": "max_output_tokens"})


def router_completed(**kwargs) -> dict:
    return openrouter_reply("b1", text=fields(**kwargs))


def router_refused() -> dict:
    return openrouter_refused("b1")


def router_truncated() -> dict:
    value = openrouter_truncated("b1")
    value["choices"][0]["message"]["content"] = '{"rollout_summary":"甲案：單次付'
    return value


def router_invalid() -> dict:
    return openrouter_reply("b1", text=json.dumps({"rollout_summary": "只有一欄"},
                                                    ensure_ascii=False))


class FlakyStore(InMemoryStore):
    """Real Store with an armable write fault; nothing else is simulated."""

    def __init__(self):
        super().__init__()
        self.faults = 0

    def batch(self, operations):
        if self.faults and any(type(operation).__name__ == "PutOp" for operation in operations):
            self.faults -= 1
            raise RuntimeError("synthetic store fault")
        return super().batch(operations)


@pytest.fixture
def b1(interview, native):
    """One three-turn interview, its completed-window reference and a live B1."""
    graph, dataset, document, *_ = native
    windows, _, first_run, _ = interview
    third = settled(native, [AIMessage(id="b1a3", content="第三輪回覆")], text="第三輪原話")
    whole = windows.capture_window(document, first_run_id=first_run, last_run_id=third.record.run_id)
    sent, queue = [], []

    def respond(request):
        sent.append(json.loads(request.content))
        item = queue.pop(0) if queue else router_completed()
        if isinstance(item, int):
            return httpx.Response(item, json={"error": {"code": item, "message": "synthetic"}})
        item = json.loads(json.dumps(item))
        item["id"] = f"chat_{len(sent)}"
        return httpx.Response(200, json=item)

    store = FlakyStore()
    transport = httpx.MockTransport(respond)
    with httpx.Client(transport=transport, headers=OPENROUTER_HEADERS) as client:
        async_client = httpx.AsyncClient(transport=transport, headers=OPENROUTER_HEADERS)
        def build(*, retries=0, **options):
            model = build_extraction_model(api_key="offline", http_client=client,
                async_http_client=async_client, max_retries=retries)
            return build_extraction_workflow(service=windows, document_id=document, store=store,
                model=model, checkpointer=InMemorySaver(), **options)

        try:
            yield build, windows, document, whole, store, sent, queue
        finally:
            asyncio.run(async_client.aclose())


def test_a_completed_interview_becomes_memory_artifacts_over_the_real_source(b1):
    build, windows, document, whole, store, sent, _ = b1
    workflow = build()
    result = workflow.start(whole)
    assert len(result["files"]) >= 1 and len(sent) == len(result["files"])
    artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(
        windows, document, window_references=True, context_references=True))
    summary_path = result["files"][0]["summary_path"]
    assert artifacts.read_text(summary_path).endswith("甲案：單次付款、無障礙。\n乙案：月租、權限分級。")
    saved = artifacts.source_window(summary_path)
    assert saved == {"source_reference": result["files"][0]["source_reference"],
                     "context_reference": result["files"][0]["context_reference"]}


def test_the_request_carries_employee_speech_under_a_strict_schema_without_storage(b1):
    build, _, _, whole, _, sent, _ = b1
    build().start(whole)
    request = sent[0]
    payload = json.dumps(request, ensure_ascii=False)
    assert "第一輪原話" in payload and "NEW_SOURCE" in payload
    assert "store" not in request and "plugins" not in request
    assert request["response_format"]["type"] == "json_schema"
    schema = request["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert sorted(schema["schema"]["properties"]) == sorted(ExtractionOutput.model_fields)
    assert request["max_tokens"] == 8192 and request["reasoning"] == {"effort": "high"}
    assert request["provider"] == {"only": ["openai"], "order": ["openai"],
        "allow_fallbacks": False, "require_parameters": False}
    assert request["parallel_tool_calls"] is False
    assert request["model"] == "openai/gpt-5.6-luna"


def test_a_refusal_is_never_saved_as_an_empty_success(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(router_refused())
    with pytest.raises(ValueError, match="^Extraction refused, incomplete or invalid"):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_truncated_response_is_never_saved_as_an_empty_success(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(router_truncated())
    with pytest.raises(ValueError):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_structurally_invalid_response_is_never_saved(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(router_invalid())
    with pytest.raises(ValueError):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_an_unreadable_artifact_format_is_corrected_before_it_is_persisted(b1):
    build, _, _, whole, _, sent, queue = b1
    queue.extend([router_completed(summary="甲" * 2100), router_completed()])
    result = build().start(whole)
    assert len(sent) >= 2 and result["files"]
    assert "Runtime validation feedback (not employee speech)" in json.dumps(sent[1], ensure_ascii=False)


def test_a_transport_retry_is_one_model_step_not_a_second_saved_window(b1):
    build, _, _, whole, _, sent, queue = b1
    queue.extend([500, router_completed()])
    result = build(retries=1).start(whole)
    # Two HTTP attempts, one accepted model step, one artifact pair for it.
    assert len(sent) == 2 and len(result["files"]) == 1


def test_a_store_failure_resumes_the_saved_model_result_without_calling_the_model_again(b1):
    build, _, _, whole, store, sent, _ = b1
    workflow = build()
    store.faults = 1
    with pytest.raises(RuntimeError, match="synthetic store fault"):
        workflow.start(whole)
    before = len(sent)
    resumed = workflow.resume()
    assert resumed["files"] and len(sent) == before


def test_paging_assembles_a_window_longer_than_one_page(interview, native):
    """A window past the 3000-character page limit reaches B1 whole."""
    windows, document, first_run, _ = interview
    head, tail = "長訪談開頭。", "長訪談結尾。"
    long_turn = settled(native, [AIMessage(id="b1long", content="收到。")],
                        text=head + "詳" * 3200 + tail)
    whole = windows.capture_window(document, first_run_id=first_run,
                                   last_run_id=long_turn.record.run_id)
    adapter = ExtractionSourceAdapter(windows, document)
    pages, offset = [], 0
    while True:
        page = adapter.read(whole, offset)
        pages.append(page)
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert len(pages) > 1
    text = "".join(segment["text"] for page in pages for segment in page["segments"])
    # The window spans every settled turn, so the long turn arrives whole:
    # both ends of it survive, with its own reply after it.
    assert text.startswith("第一輪原話") and head in text and tail in text
    assert text.index(head) < text.index(tail) and text.endswith("收到。")
    assert all(page["turns"] for page in pages)


def test_reextraction_reads_the_original_pair_and_leaves_the_normal_position(b1):
    build, _, _, whole, _, sent, _ = b1
    workflow = build()
    first = workflow.start(whole)
    saved = first["files"][0]["summary_path"]
    position = workflow.graph.get_state(workflow.config).values["source_reference"]
    again = workflow.reextract(saved)
    assert again["replaces_summary"] == saved
    assert again["files"][0]["source_reference"] == first["files"][0]["source_reference"]
    assert again["files"][0]["context_reference"] == first["files"][0]["context_reference"]
    assert workflow.graph.get_state(workflow.config).values["source_reference"] == position


def test_the_adapter_reads_windows_and_context_but_refuses_a_turn_source(b1):
    build, windows, document, whole, _, _, _ = b1
    adapter = ExtractionSourceAdapter(windows, document)
    planned = adapter.extraction_windows(whole, max_chars=20, context_chars=10)
    assert planned and set(planned[0]) == {"source_reference", "context_reference"}
    page = adapter.read(planned[0]["source_reference"])
    assert page["turns"] and page["next_offset"] is None
    # A context range is readable for disambiguation and never admissible as a
    # completed window, but the owner's turn terminals reach B1 unchanged.
    context = next(pair["context_reference"] for pair in planned if pair["context_reference"])
    page = adapter.read(context)
    assert page["turns"] == windows.read_context(context, document)["turns"]
    assert page["next_offset"] is None
    with pytest.raises(InvalidSourceReference):
        adapter.validate_reference(context)
    # A current-turn source is neither.
    turn_source = windows.capture(document, windows.safe_turns(document)[-1]["input_id"]).source_ref
    with pytest.raises(InvalidSourceReference):
        adapter.read(turn_source)
    with pytest.raises(InvalidSourceReference):
        adapter.validate_reference(turn_source)


def test_the_adapter_exposes_typed_ordered_evidence_without_reordering(interview):
    windows, document, first_run, second_run = interview
    whole = windows.capture_window(
        document, first_run_id=first_run, last_run_id=second_run)
    adapter = ExtractionSourceAdapter(windows, document)

    fixed = adapter.window_exchanges(whole)
    history = adapter.history_exchanges(whole, limit=1)
    exact = adapter.read_source_page(fixed.exchanges[-1].source_reference)

    assert isinstance(fixed, EvidenceExchangePage)
    assert fixed.order == history.order == "oldest_to_newest"
    assert [row.messages[-1].message_id for row in fixed.exchanges] == [
        first_run, second_run]
    assert all(not hasattr(message, "text") for row in fixed.exchanges
               for message in row.messages)
    assert [row.messages[-1].message_id for row in history.exchanges] == [first_run]
    assert history.next_offset == 1
    assert isinstance(exact, EvidenceTextPage)
    assert exact.reference == fixed.exchanges[-1].source_reference
    assert [(row.role, row.text) for row in exact.segments][-1] == (
        "user", "第二輪原話😀")


def test_a_saved_pair_is_revalidated_at_its_own_position(b1):
    build, windows, document, whole, _, _, _ = b1
    adapter = ExtractionSourceAdapter(windows, document)
    planned = adapter.extraction_windows(whole, max_chars=20, context_chars=10)
    assert len(planned) > 1
    for pair in planned:
        adapter.validate_saved_window(pair["source_reference"], pair["context_reference"],
                                      max_chars=20, context_chars=10)


def test_an_oversize_turn_fails_before_the_model_instead_of_being_shortened(b1):
    """The source budget, not a provider truncation flag, bounds the input."""
    build, _, _, whole, _, sent, _ = b1
    with pytest.raises(WindowBudgetExceeded):
        build(max_chars=8, context_chars=4).start(whole)
    assert sent == []


def test_a_provider_input_overflow_surfaces_instead_of_a_shortened_source(b1):
    """With truncation at its default, an oversize request is a 400, not a cut."""
    build, _, document, whole, store, sent, queue = b1
    queue.append(400)
    with pytest.raises(BadRequestResponseError):
        build().start(whole)
    assert len(sent) == 1
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_context_range_carries_its_turn_terminals_into_the_payload(b1):
    """B1 must be able to tell a cancelled context turn from a successful one."""
    build, windows, document, whole, _, sent, _ = b1
    build(max_chars=24, context_chars=12).start(whole)
    contexts = [json.loads(request["messages"][-1]["content"])["CONTEXT_ONLY"]
                for request in sent]
    carried = [turn for context in contexts if context for turn in context["turns"]]
    assert carried and any(turn["answer_succeeded"] is False for turn in carried)


def test_a_sibling_branch_window_is_refused_before_the_first_model_call(b1, native):
    """A token pinned to an abandoned branch must never reach the model.

    Both siblings hold the same turns, so accepting it would hand B1 whichever
    branch happens to be current as if it were the saved window.
    """
    build, windows, document, _, store, sent, _ = b1
    graph, *_ = native
    turns = windows.safe_turns(document)
    last = turns[-1]["input_id"]
    parent = windows._codec._resolve_window(windows.capture_window(
        document, first_run_id=last, last_run_id=last), document).root_config()
    graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    abandoned = windows.capture_window(document, first_run_id=turns[0]["input_id"], last_run_id=last)
    graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    with pytest.raises(InvalidSourceReference):
        build().start(abandoned)
    assert sent == []
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_later_turns_never_change_what_a_saved_window_extracts(b1, native):
    """Planning reads the reference's own root, so new speech stays out of it."""
    build, _, _, whole, _, sent, _ = b1
    settled(native, [AIMessage(id="b1a4", content="第四輪回覆")], text="第四輪原話")
    build().start(whole)
    payload = json.dumps(sent, ensure_ascii=False)
    assert "第三輪原話" in payload and "第四輪原話" not in payload


def test_a_reached_lookup_bound_is_reported_as_unavailable_not_an_internal_error(b1, native):
    """Beyond the bound nothing is proven, so the port reports its own failure.

    The owner raises a checkpoint error there, which is the right signal for it
    but is not part of this port's contract. Every I/O method has to translate
    it, and none of them may call the model, write an artifact or guess.
    """
    build, windows, document, whole, store, sent, _ = b1
    graph, *_ = native
    adapter = ExtractionSourceAdapter(windows, document)
    for _ in range(MAX_PARENT_LOOKUPS + 4):
        graph.update_state({"configurable": {"thread_id": document}},
                           {"jd_manual_pending": None}, as_node="consultant")
    for call in (lambda: adapter.extraction_windows(whole, max_chars=24, context_chars=12),
                 lambda: adapter.read(whole),
                 lambda: adapter.validate_saved_window(whole, None, max_chars=24, context_chars=12),
                 lambda: adapter.require_new_source_after(whole, whole)):
        with pytest.raises(ConversationSourceError, match="^source_not_available$"):
            call()
    with pytest.raises(ConversationSourceError, match="^source_not_available$"):
        build().start(whole)
    assert sent == []
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_crossed_pair_is_refused_at_save_and_at_re_extraction(b1):
    """Artifacts may only ever record the pair that was planned together."""
    build, windows, document, whole, store, _, _ = b1
    adapter = ExtractionSourceAdapter(windows, document)
    planned = adapter.extraction_windows(whole, max_chars=24, context_chars=12)
    assert len(planned) > 1 and planned[-1]["context_reference"]
    artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(
        windows, document, window_references=True, context_references=True))
    with pytest.raises(InvalidSourceReference):
        artifacts.save_extraction(summary="詳記。", candidates="候選。", slug="交叉",
                                  source_reference=planned[0]["source_reference"],
                                  context_reference=planned[-1]["context_reference"])
    with pytest.raises(InvalidSourceReference):
        adapter.validate_saved_window(planned[0]["source_reference"],
                                      planned[-1]["context_reference"],
                                      max_chars=24, context_chars=12)


def test_a_saved_pair_reads_back_and_re_extracts_as_the_pair_it_was_planned_as(b1):
    """The whole round trip keeps one pair: save, read back, re-extract."""
    build, windows, document, whole, store, sent, _ = b1
    workflow = build(max_chars=24, context_chars=12)
    result = workflow.start(whole)
    artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(
        windows, document, window_references=True, context_references=True))
    for saved in result["files"]:
        assert artifacts.source_window(saved["summary_path"]) == {
            "source_reference": saved["source_reference"],
            "context_reference": saved["context_reference"]}
    again = workflow.reextract(result["files"][-1]["summary_path"])
    assert again["files"][0]["source_reference"] == result["files"][-1]["source_reference"]
    assert again["files"][0]["context_reference"] == result["files"][-1]["context_reference"]


def test_a_mismatched_pair_already_on_disk_is_refused_when_read_back(b1):
    """Saving refuses a crossed pair, and reading one back refuses it too.

    An artifact that already holds a neighbouring window's prefix — however it
    got there — must not become a re-extraction input. This exercises the
    read-back check on its own rather than trusting the save-time one.
    """
    build, windows, document, whole, store, _, _ = b1
    adapter = ExtractionSourceAdapter(windows, document)
    planned = adapter.extraction_windows(whole, max_chars=20, context_chars=10)
    paired = [pair for pair in planned if pair["context_reference"]]
    assert len(paired) > 1
    artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(
        windows, document, window_references=True, context_references=True))
    files = artifacts.save_extraction(summary="詳記。", candidates="候選。", slug="原對", **paired[0])
    assert artifacts.source_window(files.summary_path) == paired[0]
    crossed = artifacts.read_text(files.summary_path).replace(
        paired[0]["context_reference"], paired[1]["context_reference"])
    assert not artifacts.interview_backend().write(
        files.summary_path.removeprefix("/interviews"), crossed).error
    with pytest.raises(InvalidSourceReference):
        artifacts.source_window(files.summary_path)


def test_the_terminal_evidence_port_reads_only_public_provider_fields():
    assert accepted(AIMessage("好", response_metadata={"status": "completed"}))
    assert not accepted(AIMessage("好", response_metadata={"status": "incomplete"}))
    assert not accepted(AIMessage("好", response_metadata={"status": "completed"},
                                  additional_kwargs={"refusal": "無法協助。"}))
