"""B2 application wiring: adopted workflow, real staged-file tools, real SDK.

Every provider request is answered in process by httpx.MockTransport with a
body validated against the pinned OpenAI response schema, so the agent loop,
the tools, the SDK and the publication path are real and the network is not.
No provider access and no model-quality claim.

B1 runs first over this App's own source owner, because B2 may only take a
batch that B1 actually finished.
"""
import json
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from caliburn_memory import MemoryArtifacts, PublicationStore
from caliburn_memory.consolidation import INSTRUCTIONS
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from jd_relational.consolidation_app import (
    MAX_OUTPUT_TOKENS, build_consolidation_model, build_consolidation_workflow,
)
from jd_relational.extraction_app import build_extraction_model, build_extraction_workflow
from jd_relational.memory_sources import MemorySourceReader

from test_chat_history import native
from test_extraction_app import assistant_text, completed, response_body
from test_interview_window_source import interview, settled


def call(name, **arguments):
    return response_body([{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                           "name": name, "arguments": json.dumps(arguments, ensure_ascii=False),
                           "status": "completed"}])


def done(text="整併完成。"):
    return response_body([assistant_text(text)])


@pytest.fixture
def b2(interview, native):
    """One finished B1 batch, a real publication, and a live B2 over both."""
    graph, dataset, document, *_ = native
    windows, _, first_run, _ = interview
    third = settled(native, [AIMessage(id="b2a3", content="第三輪回覆")], text="第三輪原話")
    batch = windows.capture_window(document, first_run_id=first_run, last_run_id=third.record.run_id)
    sent, queue = [], []

    def respond(request):
        sent.append(json.loads(request.content))
        answer = queue.pop(0) if queue else completed()
        if callable(answer):
            answer = answer()
        # Provider item identities must differ across requests.
        answer = json.loads(json.dumps(answer))
        answer["id"] = f"resp_{len(sent)}"
        for index, item in enumerate(answer["output"]):
            item["id"] = f"item_{len(sent)}_{index}"
            if item.get("type") == "function_call":
                item["call_id"] = f"call_{len(sent)}_{index}"
        return httpx.Response(200, json=answer)

    store = InMemoryStore()
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False},
                              poolclass=StaticPool)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        reader = MemorySourceReader(windows, document, window_references=True, context_references=True)
        artifacts = MemoryArtifacts(store, document, source=reader)
        publication = PublicationStore(engine, artifacts)
        publication.setup()
        saver = InMemorySaver()
        b1 = build_extraction_workflow(service=windows, document_id=document, store=store,
            model=build_extraction_model(model="gpt-5.6-luna", api_key="offline",
                                         http_client=client).model_copy(update={"max_retries": 0}),
            checkpointer=saver)
        extracted = b1.start(batch)
        assert len(sent) == len(extracted["files"])
        sent.clear()
        model = build_consolidation_model(model="gpt-5.6-luna", api_key="offline",
                                          http_client=client).model_copy(update={"max_retries": 0})

        def build(**options):
            return build_consolidation_workflow(extraction=b1, publication=publication,
                model=model, checkpointer=InMemorySaver(), **options)

        try:
            yield build, artifacts, publication, batch, extracted, store, sent, queue
        finally:
            engine.dispose()


def wrote(path, text):
    return call("write_file", file_path=path, content=text)


def staged(summary_path, body="依客戶需求開發前端網站；案例計費及權限不同。"):
    """The edits a completed attempt makes: both staged files, then finish."""
    return [wrote("/memory/knowledge.md", f"{body}\n詳記：{summary_path}"),
            wrote("/memory/guide.md", "網站案例：見 /memory/knowledge.md"),
            done()]


def test_a_finished_b1_batch_becomes_published_understanding(b2):
    """The whole B2 path: staged edits, one version, one publication of it."""
    build, artifacts, publication, batch, extracted, _, sent, queue = b2
    summary_path = extracted["files"][0]["summary_path"]
    queue.extend(staged(summary_path))
    result = build().start()
    head = publication.current()
    assert result["result"]["revision"] == head.revision == 1
    assert head.processed_source == batch
    knowledge = artifacts.reader(head.memory).read("/memory/knowledge.md").file_data["content"]
    assert "依客戶需求開發前端網站" in knowledge and summary_path in knowledge
    assert len(sent) == 3, "two staged writes and the finishing reply"


def test_the_request_carries_this_batch_under_the_verified_profile(b2):
    """B2's own budgets and the adopted prompt reach the wire unchanged."""
    build, _, _, _, extracted, _, sent, queue = b2
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    build().start()
    request = sent[0]
    assert request["input"][0]["role"] == "system"
    assert request["input"][0]["content"] == INSTRUCTIONS
    assert request["max_output_tokens"] == MAX_OUTPUT_TOKENS == 8192
    assert request["reasoning"]["effort"] == "high"
    assert request["store"] is False and "truncation" not in request
    assert request["context_management"] == [{"type": "compaction", "compact_threshold": 12000}]
    payload = json.loads(request["input"][1]["content"])
    assert [item["summary_path"] for item in payload["NEW_CANDIDATES"]] == [
        file["summary_path"] for file in extracted["files"]]
    assert payload["MEMORY_FILES"] == {"knowledge": "/memory/knowledge.md", "guide": "/memory/guide.md"}
    assert payload["REEXTRACTION"] is None and payload["RECENT_REPAIRS"] == []


def test_details_are_dropped_from_the_payload_before_a_candidate_is_shortened(b2):
    """Over budget drops the inline copy; the summary_path route stays."""
    build, _, _, _, extracted, _, sent, queue = b2
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    build(max_candidate_chars=800).start()
    payload = json.loads(sent[0]["input"][1]["content"])
    assert payload["NEW_DETAILS"] == []
    assert payload["NEW_CANDIDATES"] and all(
        item["content"] for item in payload["NEW_CANDIDATES"])


def test_an_incomplete_or_refused_attempt_publishes_nothing(b2):
    """A response that never completed is not a consolidation."""
    build, _, publication, _, extracted, _, _, queue = b2
    queue.append(response_body([assistant_text("整併完成。")], status="incomplete",
                               incomplete={"reason": "max_output_tokens"}))
    with pytest.raises(ValueError, match="Consolidation response is not complete"):
        build().start()
    assert publication.current() is None


def test_a_staged_validation_error_is_corrected_inside_the_same_attempt(b2):
    """Runtime feedback returns to the model; it is never employee speech."""
    build, _, publication, _, extracted, _, sent, queue = b2
    summary_path = extracted["files"][0]["summary_path"]
    queue.extend([wrote("/memory/knowledge.md", f"有內容。\n詳記：{summary_path}"), done(),
                  *staged(summary_path)])
    build().start()
    assert publication.current().revision == 1
    feedback = [message for request in sent for message in request["input"]
                if "private B2" in json.dumps(message, ensure_ascii=False)]
    assert feedback, "the guide-missing error must come back as private runtime feedback"
    assert all(message["role"] != "assistant" for message in feedback)


def test_a_write_outside_the_two_staged_files_is_denied(b2):
    """Interview detail stays readable and unwritable."""
    build, _, publication, _, extracted, _, sent, queue = b2
    summary_path = extracted["files"][0]["summary_path"]
    queue.extend([wrote(summary_path, "改寫詳記"), *staged(summary_path)])
    build().start()
    denied = [request for request in sent if "Write denied" in json.dumps(request, ensure_ascii=False)]
    assert denied, "the denial must be visible to the model, not silently applied"
    assert publication.current().revision == 1


def test_a_later_repair_makes_b2_reread_its_source_instead_of_bumping_a_version(
        b2, interview, native, monkeypatch):
    """A stale base is re-loaded with the repair in hand, not re-published.

    The second attempt must see RECENT_REPAIRS and produce content from it.
    Publishing the first attempt's text under a new revision would silently
    undo the correction C just made.
    """
    build, artifacts, publication, batch, extracted, _, sent, queue = b2
    windows, document, first_run, _ = interview
    corrected_source = windows.capture_window(document, first_run_id=first_run, last_run_id=first_run)
    summary_path = extracted["files"][0]["summary_path"]
    original = PublicationStore.publish
    intervened = []

    def repair_first(self, request):
        """C publishes between B2 reading its base and B2 publishing."""
        if not intervened:
            intervened.append(True)
            version = artifacts.save_memory(knowledge="更正：權限分級由客戶自行設定。",
                                            guide="更正後導覽")
            intervened.append(original(self, self.prepare(version, expected_revision=0,
                kind="repair", repair_sources=(corrected_source,))))
        return original(self, request)

    monkeypatch.setattr(PublicationStore, "publish", repair_first)
    queue.extend([*staged(summary_path, body="第一次整併的說法。"),
                  *staged(summary_path, body="更正後：權限分級由客戶自行設定。")])
    result = build().start()

    assert intervened, "the repair must really have moved the head"
    payloads = [json.loads(request["input"][1]["content"]) for request in sent
                if request["input"][1]["role"] == "user"]
    assert payloads[0]["RECENT_REPAIRS"] == []
    later = next(p for p in payloads if p["RECENT_REPAIRS"])
    assert later["RECENT_REPAIRS"][0]["reference"] == corrected_source
    assert any("第一輪原話" in segment["text"]
               for segment in later["RECENT_REPAIRS"][0]["segments"])
    head = publication.current()
    assert head.revision == result["result"]["revision"] == 2
    assert head.processed_source == batch
    knowledge = artifacts.reader(head.memory).read("/memory/knowledge.md").file_data["content"]
    assert "更正後：權限分級由客戶自行設定。" in knowledge
    assert "第一次整併的說法。" not in knowledge


def test_a_lost_publish_reply_is_read_back_by_the_original_request(b2, monkeypatch):
    """The result exists; only the answer was lost. Never consolidate twice."""
    build, artifacts, publication, batch, extracted, _, sent, queue = b2
    queue.extend(staged(extracted["files"][0]["summary_path"]))
    original = PublicationStore.publish
    lost = []

    def commit_then_lose_the_reply(self, request):
        result = original(self, request)
        if not lost:
            lost.append(result)
            raise ConnectionError("synthetic reply loss after commit")
        return result

    monkeypatch.setattr(PublicationStore, "publish", commit_then_lose_the_reply)
    workflow = build()
    with pytest.raises(ConnectionError, match="synthetic reply loss"):
        workflow.start()
    calls = len(sent)
    assert publication.current().revision == 1
    monkeypatch.undo()
    resumed = workflow.resume()
    assert resumed["result"]["revision"] == 1
    assert len(sent) == calls, "the recorded publication must not be consolidated again"
    assert publication.current() == lost[0]
