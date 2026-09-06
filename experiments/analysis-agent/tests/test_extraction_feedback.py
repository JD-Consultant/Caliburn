"""B1 application feedback: real SDK/graph/checkpoints, offline HTTP only."""

from contextlib import contextmanager
import json

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START
from langgraph.store.memory import InMemoryStore
from openai import InternalServerError

from analysis_agent.extraction import ExtractionOutput, ExtractionWorkflow
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from test_extraction import body, source
from test_native_continuity import assistant_text, response_body


def candidate(**changes):
    fields = {"rollout_summary": "甲" * 2100, "raw_memory": "候選", "rollout_slug": "案例"}
    fields.update(changes)
    return response_body([
        {"type": "reasoning", "id": "rs_b1", "encrypted_content": "B1-OPAQUE", "summary": []},
        assistant_text(json.dumps(fields, ensure_ascii=False), item_id="msg_candidate"),
    ])


@contextmanager
def offline(replies, **options):
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        reply = replies.pop(0)
        if callable(reply):
            reply = reply()
        if isinstance(reply, httpx.Response):
            # Exercise an exhausted SDK transport failure, not its HTTP retry.
            reply.headers["x-should-retry"] = "false"
        return reply if isinstance(reply, httpx.Response) else httpx.Response(200, json=reply)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
        saver, store = InMemorySaver(), InMemoryStore()
        reader, ref = source(model, saver, turns=options.pop("turns", None))
        artifacts = MemoryArtifacts(store, reader.document_id)
        workflow = ExtractionWorkflow(reader, artifacts, model, saver, **options)
        yield workflow, ref, sent, store, model, saver


def test_invalid_candidate_checkpointed_then_precise_private_native_correction():
    bad = candidate()
    with offline([bad, body()], max_output_tokens=321) as (b1, ref, sent, store, _, _):
        original_source = b1.reader.read(ref)
        result = b1.start(ref)
        assert len(sent) == 2 and len(result["files"]) == 1
        # The correction extends the exact original input and native AI items.
        assert sent[1]["input"][:2] == sent[0]["input"]
        assert sent[1]["input"][2] == bad["output"][0]
        native_candidate = sent[1]["input"][3]
        assert native_candidate["role"] == "assistant" and native_candidate["phase"] == "final_answer"
        assert native_candidate["content"][0]["text"] == bad["output"][1]["content"][0]["text"]
        feedback = sent[1]["input"][-1]
        assert feedback["role"] in {"system", "developer"}
        assert "Runtime validation feedback" in feedback["content"]
        assert "rollout_summary" in feedback["content"] and "2000" in feedback["content"]
        assert "without removing detail" in feedback["content"]
        assert len(feedback["content"]) < 700
        assert "甲" not in feedback["content"] and "input_value" not in feedback["content"]
        for request in sent:
            assert request["max_output_tokens"] == 321 and request["store"] is False
            assert request["text"]["format"]["strict"] is True and not request.get("tools")
            # The public adapter moves the schema title into the format name.
            schema = ExtractionOutput.model_json_schema()
            assert request["text"]["format"]["name"] == schema.pop("title")
            assert request["text"]["format"]["schema"] == schema
        history = list(b1.graph.get_state_history(b1.config))
        reserved = next(s for s in history if s.next == ("correct",))
        assert reserved.values["corrections_used"] == 1
        assert reserved.values["candidate"]["rollout_summary"] == "甲" * 2100
        assert reserved.values["raw_response"].content
        assert "2000" in reserved.values["validation_error"]
        assert reserved.values["extracted"] is None and reserved.values["files"] == []
        assert b1.reader.read(ref) == original_source
        saved = json.dumps([s.value for s in store.search(("q019-memory", b1.reader.document_id))], ensure_ascii=False)
        assert "Runtime validation feedback" not in saved and "甲" * 2100 not in saved
        assert store.search(("q019-memory", b1.reader.document_id, "versions")) == []


@pytest.mark.parametrize("field,value,reason", [
    ("raw_memory", "乙" * 2100, "2000"),
    ("rollout_summary", " \n\t", "empty"),
], ids=["candidate-line", "empty-summary"])
def test_feedback_identifies_other_application_failures(field, value, reason):
    fields = {"rollout_summary": "有效詳記", field: value}
    with offline([candidate(**fields), body()]) as (b1, ref, sent, *_):
        assert b1.start(ref)["files"]
        feedback = sent[1]["input"][-1]["content"]
        assert field in feedback and reason in feedback


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_exhaustion_reopen_never_replenishes_or_publishes(limit):
    with offline([candidate()] * (limit + 1), max_validation_corrections=limit) as (b1, ref, sent, store, model, saver):
        with pytest.raises(ValueError, match="correction.*exhausted.*rollout_summary"):
            b1.start(ref)
        stopped = b1.graph.get_state(b1.config).values
        assert stopped["corrections_used"] == limit and stopped["correction_limit"] == limit
        assert stopped["candidate"]["rollout_summary"] == "甲" * 2100
        assert stopped["files"] == [] and store.search(("q019-memory", b1.reader.document_id)) == []
        restored = ExtractionWorkflow(b1.reader, b1.artifacts, model, saver, max_validation_corrections=limit + 5)
        for _ in range(2):
            with pytest.raises(ValueError, match="correction.*exhausted"):
                restored.resume()
        with pytest.raises(ValueError, match="pending"):
            restored.start(ref)
        assert len(sent) == limit + 1


def test_interrupted_correction_resumes_same_candidate_and_charged_allowance():
    with offline([candidate(), httpx.Response(503, json={"error": {"message": "offline outage", "type": "server_error"}}), candidate()]) as (b1, ref, sent, store, model, saver):
        with pytest.raises(InternalServerError):
            b1.start(ref)
        state = b1.graph.get_state(b1.config)
        assert state.next == ("correct",) and state.values["corrections_used"] == 1
        assert state.values["candidate"]["rollout_summary"] == "甲" * 2100
        assert store.search(("q019-memory", b1.reader.document_id)) == []
        restored = ExtractionWorkflow(b1.reader, b1.artifacts, model, saver)
        with pytest.raises(ValueError, match="correction.*exhausted"):
            restored.resume()
        assert sent[2]["input"] == sent[1]["input"]
        with pytest.raises(ValueError, match="correction.*exhausted"):
            restored.resume()
        assert len(sent) == 3


@pytest.mark.parametrize("failure", ["refusal", "incomplete", "http", "parse"])
def test_non_application_failure_never_spends_format_correction(failure):
    reply = body()
    if failure == "refusal":
        # Even a provider reply also containing valid JSON must remain a refusal.
        reply["output"][0]["content"].append({"type": "refusal", "refusal": "Cannot process"})
    elif failure == "incomplete":
        reply["status"] = "incomplete"
        reply["incomplete_details"] = {"reason": "max_output_tokens"}
    elif failure == "http":
        reply = httpx.Response(503, json={"error": {"message": "offline outage", "type": "server_error"}})
    else:
        reply["output"][0]["content"][0]["text"] = "not JSON"
    with offline([reply, body()]) as (b1, ref, sent, store, model, saver):
        with pytest.raises((ValueError, InternalServerError)):
            b1.start(ref)
        assert len(sent) == 1
        assert b1.graph.get_state(b1.config).values["corrections_used"] == 0
        assert store.search(("q019-memory", b1.reader.document_id)) == []
        assert ExtractionWorkflow(b1.reader, b1.artifacts, model, saver).resume()["files"]
        assert sent[1]["input"] == sent[0]["input"]


def test_new_windows_each_get_bound_without_reextracting_saved_window():
    turns = [("案例A" * 5, "問A"), ("案例B" * 5, "問B"), ("案例C" * 5, "問C")]
    with offline([candidate(), body(), candidate(), body()], turns=turns, max_chars=38, context_chars=20,
                 max_windows=2) as (b1, ref, sent, store, *_):
        result = b1.start(ref)
        assert len(result["files"]) == 2 and len(sent) == 4
        assert sent[0]["input"] == sent[1]["input"][:2]
        assert sent[2]["input"] == sent[3]["input"][:2]
        assert len(sent[2]["input"]) == 2  # no previous window's feedback/candidate
        history = list(b1.graph.get_state_history(b1.config))
        reserved = [s.values for s in history if s.next == ("correct",)]
        assert sorted((s["position"], s["corrections_used"]) for s in reserved) == [(0, 1), (1, 1)]
        assert next(s for s in reserved if s["position"] == 1)["files"] == result["files"][:1]
        assert len(store.search(("q019-memory", b1.reader.document_id, "interviews"))) == 4


def test_lossless_normalization_needs_no_correction_or_markdown_rewrite():
    text = "[案例](https://example.test/a)\r\n```text\r\n保留內容\r\n```"
    with offline([candidate(rollout_summary=text, raw_memory="")]) as (b1, ref, sent, *_):
        result = b1.start(ref)
        saved = b1.artifacts.read_text(result["files"][0]["summary_path"])
        assert saved.endswith("[案例](https://example.test/a)\n```text\n保留內容\n```")
        assert len(sent) == 1


def test_reextraction_exhaustion_preserves_old_artifacts_and_ordinary_state():
    with offline([body(), candidate(), candidate()]) as (b1, ref, sent, store, model, saver):
        ordinary = b1.start(ref)
        old = ordinary["files"][0]["summary_path"]
        original = b1.artifacts.read_text(old)
        with pytest.raises(ValueError, match="correction.*exhausted"):
            b1.reextract(old)
        restored = ExtractionWorkflow(b1.reader, b1.artifacts, model, saver)
        with pytest.raises(ValueError, match="correction.*exhausted"):
            restored.resume_reextraction(old)
        assert restored.start(ref) == ordinary and len(sent) == 3
        assert b1.artifacts.read_text(old) == original
        assert len(store.search(("q019-memory", b1.reader.document_id, "interviews"))) == 2


def test_legacy_partial_checkpoint_stops_without_inventing_a_new_allowance():
    with offline([]) as (b1, ref, sent, *_):
        b1.graph.update_state(b1.config, {"source_reference": ref, "windows": [{"source_reference": ref, "context_reference": None}],
            "position": 0, "files": [], "extracted": None, "raw_response": None}, as_node=START)
        with pytest.raises(ValueError, match="checkpoint.*correction.*metadata"):
            b1.resume()
        assert sent == []
