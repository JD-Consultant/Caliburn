"""B1 application wiring: adopted workflow, this App's source owner, real SDK.

Every provider request is answered in-process by httpx.MockTransport with a
body validated against the pinned OpenAI response schema, so the adapter, the
SDK and the structured-output binding are real and the network is not. No
provider access, no model-quality claim, no publication and no JD tool.

The conversation consultant keeps its Anthropic runtime; only B1 is bound to
OpenAI here.
"""
import json

import httpx
import pytest
from caliburn_memory import MemoryArtifacts
from caliburn_memory.extraction import ExtractionOutput
from caliburn_memory.sources import InvalidSourceReference
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from openai.types.responses import Response

from jd_relational.extraction_app import (
    ExtractionSourceAdapter, accepted, build_extraction_model, build_extraction_workflow,
)
from jd_relational.memory_sources import MemorySourceReader

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
    return response_body([assistant_text(fields(**kwargs))])


def refused() -> dict:
    return response_body([{"type": "message", "id": "msg_refusal", "role": "assistant",
                           "status": "completed", "phase": "final_answer",
                           "content": [{"type": "refusal", "refusal": "無法協助。"}]}])


def truncated() -> dict:
    return response_body([assistant_text('{"rollout_summary": "甲案：單次付')], status="incomplete",
                         incomplete={"reason": "max_output_tokens"})


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
        item = queue.pop(0) if queue else completed()
        if isinstance(item, int):
            return httpx.Response(item, json={"error": {"message": "synthetic", "type": "server_error"}})
        return httpx.Response(200, json=item)

    store = FlakyStore()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_extraction_model(model="gpt-5.6-luna", api_key="offline",
                                       http_client=client).model_copy(update={"max_retries": 0})

        def build(*, retries=0, **options):
            return build_extraction_workflow(service=windows, document_id=document, store=store,
                model=model.model_copy(update={"max_retries": retries}),
                checkpointer=InMemorySaver(), **options)

        yield build, windows, document, whole, store, sent, queue


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
    assert request["store"] is False and request["truncation"] == "disabled"
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    assert sorted(request["text"]["format"]["schema"]["properties"]) == sorted(ExtractionOutput.model_fields)
    assert request["max_output_tokens"] == 8192 and request["reasoning"]["effort"] == "high"


def test_a_refusal_is_never_saved_as_an_empty_success(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(refused())
    with pytest.raises(ValueError, match="^Extraction refused, incomplete or invalid"):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_truncated_response_is_never_saved_as_an_empty_success(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(truncated())
    with pytest.raises(ValueError):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_a_structurally_invalid_response_is_never_saved(b1):
    build, _, document, whole, store, _, queue = b1
    queue.append(response_body([assistant_text(json.dumps({"rollout_summary": "只有一欄"}))]))
    with pytest.raises(ValueError):
        build().start(whole)
    assert not list(store.search(("q019-memory", document, "interviews")))


def test_an_unreadable_artifact_format_is_corrected_before_it_is_persisted(b1):
    build, _, _, whole, _, sent, queue = b1
    queue.extend([completed(summary="甲" * 2100), completed()])
    result = build().start(whole)
    assert len(sent) >= 2 and result["files"]
    assert "Runtime validation feedback (not employee speech)" in json.dumps(sent[1], ensure_ascii=False)


def test_a_transport_retry_is_one_model_step_not_a_second_saved_window(b1):
    build, _, _, whole, _, sent, queue = b1
    queue.extend([500, completed()])
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
    # A context range is readable for disambiguation, but never admissible as a
    # completed window, and it reports no settled turns of its own.
    context = next(pair["context_reference"] for pair in planned if pair["context_reference"])
    assert adapter.read(context)["turns"] == []
    with pytest.raises(InvalidSourceReference):
        adapter.validate_reference(context)
    # A current-turn source is neither.
    turn_source = windows.capture(document, windows.safe_turns(document)[-1]["input_id"]).source_ref
    with pytest.raises(InvalidSourceReference):
        adapter.read(turn_source)
    with pytest.raises(InvalidSourceReference):
        adapter.validate_reference(turn_source)


def test_a_saved_pair_is_revalidated_at_its_own_position(b1):
    build, windows, document, whole, _, _, _ = b1
    adapter = ExtractionSourceAdapter(windows, document)
    planned = adapter.extraction_windows(whole, max_chars=20, context_chars=10)
    assert len(planned) > 1
    for pair in planned:
        adapter.validate_saved_window(pair["source_reference"], pair["context_reference"],
                                      max_chars=20, context_chars=10)


def test_the_terminal_evidence_port_reads_only_public_provider_fields():
    assert accepted(AIMessage("好", response_metadata={"status": "completed"}))
    assert not accepted(AIMessage("好", response_metadata={"status": "incomplete"}))
    assert not accepted(AIMessage("好", response_metadata={"status": "completed"},
                                  additional_kwargs={"refusal": "無法協助。"}))
