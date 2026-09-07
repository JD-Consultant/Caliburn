"""B2 real agent/Store/publication integration; only external HTTP is synthetic."""
import importlib.util
import json
from types import SimpleNamespace

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine

from analysis_agent.extraction import ExtractionWorkflow
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.publication import PublicationStore
from test_extraction import source, body
from test_native_continuity import assistant_text, response_body


def workflow_class():
    assert importlib.util.find_spec("analysis_agent.consolidation"), "Missing B2 consolidation workflow"
    from analysis_agent.consolidation import ConsolidationWorkflow
    return ConsolidationWorkflow


def call(name, **arguments):
    return response_body([{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                          "name": name, "arguments": json.dumps(arguments, ensure_ascii=False), "status": "completed"}])


def done():
    return response_body([assistant_text("整併完成。")])


def with_guide(reply):
    """A completed body repair also supplies its guide, in the same model step."""
    reply["output"].extend(call("write_file", file_path="/memory/guide.md",
                                content="網站案例：見 /memory/knowledge.md")["output"])
    return reply


@pytest.fixture
def harness():
    sent, replies = [], [body()]
    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, "Unexpected extra model request"
        answer = replies.pop(0)
        if callable(answer):
            answer = answer()
        if isinstance(answer, Exception):
            raise answer
        # Provider item identities must differ across requests.
        answer["id"] = f"resp_{len(sent)}"
        for i, item in enumerate(answer["output"]):
            item["id"] = f"item_{len(sent)}_{i}"
            if item["type"] == "function_call":
                item["call_id"] = f"call_{len(sent)}_{i}"
        return httpx.Response(200, json=answer)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
        saver, store = InMemorySaver(), InMemoryStore()
        reader, ref = source(model, saver)
        artifacts = MemoryArtifacts(store, reader.document_id, source=reader)
        b1 = ExtractionWorkflow(reader, artifacts, model, saver)
        extracted = b1.start(ref)
        pub = PublicationStore(engine, artifacts)
        pub.setup()
        yield SimpleNamespace(model=model, saver=saver, store=store, reader=reader, ref=ref,
                              artifacts=artifacts, b1=b1, extracted=extracted, pub=pub, sent=sent, replies=replies)
    engine.dispose()


def edits(h, text="依客戶需求開發前端網站；案例計費及權限不同。"):
    path = h.extracted["files"][0]["summary_path"]
    h.replies.extend([call("write_file", file_path="/memory/knowledge.md", content=text+"\n詳記："+path),
                      call("write_file", file_path="/memory/guide.md", content="網站案例：見 /memory/knowledge.md"),
                      call("validate_memory"), done()])


def knowledge(h):
    return h.artifacts.read_text("/memory/knowledge.md", h.pub.current().memory)


def test_saved_candidates_detail_read_and_atomic_publication(harness):
    cls = workflow_class()
    h = harness
    path = h.extracted["files"][0]["summary_path"]
    h.replies.append(call("read_file", file_path=path))
    edits(h)
    workflow = cls(h.b1, h.pub, h.model, h.saver)
    result = workflow.start()
    assert result["result"]["processed_source"] == h.ref
    assert h.pub.current().revision == 1 and path in knowledge(h)
    assert "A網站：單次付款" in json.dumps(h.sent[2], ensure_ascii=False)
    assert "PRIVATE-REASONING" not in json.dumps(h.sent[1:], ensure_ascii=False)
    assert result["used_model_steps"] == 5 and result["used_tool_calls"] == 4
    assert {t["name"] for t in h.sent[1]["tools"]} == {"ls", "grep", "read_file", "write_file", "apply_memory_patch", "validate_memory"}
    assert h.sent[1]["max_output_tokens"] == 4096
    count = len(h.sent)
    assert workflow.start()["result"] == result["result"]
    assert workflow.resume()["result"] == result["result"]
    assert len(h.sent) == count


def test_invalid_reference_returns_tool_error_then_model_can_repair(harness):
    cls = workflow_class()
    h = harness
    path = h.extracted["files"][0]["summary_path"]
    h.replies.extend([call("write_file", file_path="/memory/knowledge.md", content="見 /interviews/missing/summary.md"),
                      call("validate_memory"),
                      with_guide(call("apply_memory_patch", file_path="/memory/knowledge.md", diff=f"@@\n-見 /interviews/missing/summary.md\n+見 {path}")),
                      call("validate_memory"), done()])
    cls(h.b1, h.pub, h.model, h.saver).start()
    assert "missing" in json.dumps(h.sent[3], ensure_ascii=False)
    assert path in knowledge(h) and "missing" not in knowledge(h)


def test_patch_handles_display_separator_spaces_preserving_real_indent(harness):
    # CT06 failure adapted to SDK patch. This is a deterministic wire fixture,
    # not evidence that a real model always supplies the right patch.
    h = harness
    content = "# 工作\n- 維護每月一次\n  - 正式資料由後端處理"
    h.replies.extend([
        with_guide(call("write_file", file_path="/memory/knowledge.md", content=content)),
        call("read_file", file_path="/memory/knowledge.md"),
        call("apply_memory_patch", file_path="/memory/knowledge.md",
             diff="@@\n # 工作\n-  - 維護每月一次\n+- 維護每月第一個工作日\n   - 正式資料由後端處理"),
        done(),
    ])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    assert "2  - 維護每月一次" in json.dumps(h.sent[3], ensure_ascii=False)
    assert "Patch applied to staging" in json.dumps(h.sent[4], ensure_ascii=False)
    assert knowledge(h) == "# 工作\n- 維護每月第一個工作日\n  - 正式資料由後端處理"


def test_known_summary_path_is_read_directly_without_discovery_instruction(harness):
    # This checks the real tool wire contract/execution, not model compliance.
    # Removing the description override must restore the conflicting default.
    h = harness
    path = h.extracted["files"][0]["summary_path"]
    h.replies.extend([call("read_file", file_path=path), done()])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    listed = next(t for t in h.sent[1]["tools"] if t["name"] == "ls")
    assert "almost ALWAYS" not in listed["description"]
    assert "Runtime-provided" in listed["description"]
    assert "A網站：單次付款" in json.dumps(h.sent[2], ensure_ascii=False)
    assert h.pub.current().revision == 1


@pytest.mark.parametrize("path", ["/interviews/forged.md", "/other-doc/memory.md"])
def test_tools_cannot_write_outside_staging(harness, path):
    cls = workflow_class()
    h = harness
    h.replies.extend([call("write_file", file_path=path, content="not allowed"), done()])
    cls(h.b1, h.pub, h.model, h.saver).start()
    assert "not allowed" not in knowledge(h)
    assert len(h.store.search(("q019-memory", h.reader.document_id, "interviews"))) == 2
    assert any("error" in json.dumps(x).lower() or "denied" in json.dumps(x).lower() for x in h.sent[2]["input"])


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_incomplete_result_never_publishes(harness, status):
    cls = workflow_class()
    h = harness
    answer = done()
    answer["status"] = status
    h.replies.append(answer)
    with pytest.raises(ValueError, match="complete"):
        cls(h.b1, h.pub, h.model, h.saver).start()
    assert h.pub.current() is None


def test_store_failure_resumes_without_recalling_model(harness, monkeypatch):
    cls = workflow_class()
    h = harness
    edits(h)
    original = h.artifacts.save_memory
    def fail(**kwargs):
        raise RuntimeError("Store temporarily unavailable")
    monkeypatch.setattr(h.artifacts, "save_memory", fail)
    workflow = cls(h.b1, h.pub, h.model, h.saver)
    with pytest.raises(RuntimeError, match="Store"):
        workflow.start()
    count = len(h.sent)
    assert h.pub.current() is None
    monkeypatch.setattr(h.artifacts, "save_memory", original)
    cls(h.b1, h.pub, h.model, h.saver).resume()
    assert len(h.sent) == count and h.pub.current().revision == 1


def test_no_semantic_change_still_advances_source(harness):
    cls = workflow_class()
    h = harness
    version = h.artifacts.save_memory(knowledge="既有知識", guide="既有導覽")
    h.pub.publish(h.pub.prepare(version, expected_revision=0, kind="repair"))
    h.replies.append(done())
    result = cls(h.b1, h.pub, h.model, h.saver).start()
    assert h.pub.current().revision == 2 and h.pub.current().processed_source == h.ref
    assert knowledge(h) == "既有知識"
    assert result["used_model_steps"] == 1 and result["used_tool_calls"] == 0
    assert len(h.sent) == 2


def test_model_budget_stops_and_resume_does_not_reset_it(harness):
    cls = workflow_class()
    h = harness
    h.replies.extend([call("ls", path="/memory/")]*3)
    workflow = cls(h.b1, h.pub, h.model, h.saver, max_model_steps=2)
    with pytest.raises(Exception, match="limit"):
        workflow.start()
    assert len(h.sent) == 3
    with pytest.raises(Exception, match="limit"):
        cls(h.b1, h.pub, h.model, h.saver, max_model_steps=2).resume()
    assert len(h.sent) == 3 and h.pub.current() is None


def test_stale_reloads_new_memory_and_correction_source_without_reextracting(harness):
    cls = workflow_class()
    h = harness
    # A newer correction is saved to the canonical interview while B2 uses
    # the already-completed B1 batch from the preceding two turns.
    from langchain_core.messages import HumanMessage, AIMessage
    h.reader.graph.update_state({"configurable": {"thread_id": h.reader.document_id}},
        {"messages": [HumanMessage("我剛才說錯，B網站是年租，非月租。", id="u2"),
                      AIMessage("收到更正，年租是否預收？", id="a2", response_metadata={"status": "completed"})]}, as_node="model")
    correction = h.reader.capture("u2", "a2")
    def publish_repair():
        v = h.artifacts.save_memory(knowledge="B網站年租；已更正月租。", guide="網站案例")
        h.pub.publish(h.pub.prepare(v, expected_revision=0, kind="repair", repair_sources=(correction,)))
        return done()
    edits(h, "舊版月租")
    h.replies[-1] = publish_repair
    h.replies.extend([call("read_file", file_path="/memory/knowledge.md"), done()])
    workflow = cls(h.b1, h.pub, h.model, h.saver)
    result = workflow.start()
    assert result["attempt"] == 2 and result["used_model_steps"] == 6
    assert h.pub.current().revision == 2 and "年租" in knowledge(h) and "舊版月租" not in knowledge(h)
    assert len(h.store.search(("q019-memory", h.reader.document_id, "interviews"))) == 2
    retry_wire = json.dumps(h.sent[5], ensure_ascii=False)
    assert "我剛才說錯，B網站是年租" in retry_wire and "年租是否預收" in retry_wire
    assert correction in retry_wire and "PRIVATE-REASONING" not in retry_wire
    assert h.pub.current().processed_source == h.ref


def test_stale_retry_only_gets_remaining_job_budget(harness):
    cls = workflow_class()
    h = harness
    def newer():
        v = h.artifacts.save_memory(knowledge="新修補", guide="新導覽")
        h.pub.publish(h.pub.prepare(v, expected_revision=0, kind="repair"))
        return done()
    h.replies.extend([call("ls", path="/memory/"), newer, call("ls", path="/memory/"), done()])
    workflow = cls(h.b1, h.pub, h.model, h.saver, max_model_steps=3)
    with pytest.raises(Exception, match="limit"):
        workflow.start()
    assert len(h.sent) == 4  # one B1, two old B2, one new B2
    assert knowledge(h) == "新修補" and h.pub.current().processed_source is None
    with pytest.raises(Exception, match="limit"):
        cls(h.b1, h.pub, h.model, h.saver, max_model_steps=3).resume()
    assert len(h.sent) == 4


def test_commit_response_loss_replays_same_receipt_without_model(harness, monkeypatch):
    cls = workflow_class()
    h = harness
    h.replies.append(done())
    original = h.pub.publish
    def lost_response(request):
        original(request)
        raise RuntimeError("response lost after commit")
    monkeypatch.setattr(h.pub, "publish", lost_response)
    workflow = cls(h.b1, h.pub, h.model, h.saver)
    with pytest.raises(RuntimeError, match="response lost"):
        workflow.start()
    request = workflow.graph.get_state(workflow.config).values["request"]
    assert h.pub.receipt(request["operation_id"]) is not None
    count = len(h.sent)
    monkeypatch.setattr(h.pub, "publish", original)
    result = cls(h.b1, h.pub, h.model, h.saver).resume()
    assert len(h.sent) == count and h.pub.current().revision == 1
    assert result["request"]["operation_id"] == request["operation_id"]


def test_candidate_limit_stops_before_b2_model(harness):
    cls = workflow_class()
    h = harness
    workflow = cls(h.b1, h.pub, h.model, h.saver, max_candidate_chars=1)
    with pytest.raises(ValueError, match="Candidate input limit"):
        workflow.start()
    assert len(h.sent) == 1 and h.pub.current() is None
    assert not workflow.graph.get_state(workflow.config).values
    h.replies.append(done())
    assert cls(h.b1, h.pub, h.model, h.saver).start()["result"] is not None


def test_invalid_final_stage_cannot_publish_when_correction_budget_exhausted(harness):
    cls = workflow_class()
    h = harness
    h.replies.extend([call("write_file", file_path="/memory/knowledge.md", content="/interviews/missing/summary.md"), done()])
    with pytest.raises(Exception, match="limit"):
        cls(h.b1, h.pub, h.model, h.saver, max_model_steps=2).start()
    assert h.pub.current() is None


def test_global_tool_budget_blocks_execution_and_resume(harness):
    cls = workflow_class()
    h = harness
    h.replies.extend([call("ls", path="/memory/"), call("write_file", file_path="/memory/knowledge.md", content="not executed")])
    workflow = cls(h.b1, h.pub, h.model, h.saver, max_tool_calls=1)
    with pytest.raises(Exception, match="limit"):
        workflow.start()
    with pytest.raises(Exception, match="limit"):
        cls(h.b1, h.pub, h.model, h.saver, max_tool_calls=1).resume()
    assert len(h.sent) == 3 and h.pub.current() is None


def test_provider_refusal_does_not_publish_empty_memory(harness):
    cls = workflow_class()
    h = harness
    refusal = done()
    refusal["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot perform consolidation"}]
    h.replies.append(refusal)
    with pytest.raises(ValueError, match="refus"):
        cls(h.b1, h.pub, h.model, h.saver).start()
    assert h.pub.current() is None


def test_b1_pending_is_not_a_valid_handoff(harness):
    cls = workflow_class()
    h = harness
    from langchain_core.messages import HumanMessage, AIMessage
    h.reader.graph.update_state({"configurable": {"thread_id": h.reader.document_id}},
        {"messages": [HumanMessage("新案例", id="u2"), AIMessage("具體？", id="a2", response_metadata={"status": "completed"})]}, as_node="model")
    h.replies.append(done())  # malformed B1 structured response
    with pytest.raises(ValueError):
        h.b1.start(h.reader.capture("u2", "a2"))
    with pytest.raises(ValueError, match="B1 must have completed"):
        cls(h.b1, h.pub, h.model, h.saver).start()
    assert len(h.sent) == 2 and h.pub.current() is None


def test_component_document_mismatch_is_rejected(harness):
    cls = workflow_class()
    h = harness
    foreign = PublicationStore(h.pub.engine, MemoryArtifacts(h.store, "other-doc"))
    with pytest.raises(ValueError, match="different documents"):
        cls(h.b1, foreign, h.model, h.saver)
    assert len(h.sent) == 1


def test_large_correction_does_not_get_truncated_and_overwritten(harness):
    cls = workflow_class()
    h = harness
    def correction():
        v = h.artifacts.save_memory(knowledge="最新修補", guide="新導覽")
        h.pub.publish(h.pub.prepare(v, expected_revision=0, kind="repair", repair_sources=(h.ref,)))
        return done()
    h.replies.append(correction)
    with pytest.raises(ValueError, match="Repair input limit"):
        cls(h.b1, h.pub, h.model, h.saver, max_repair_chars=1).start()
    assert len(h.sent) == 2 and knowledge(h) == "最新修補"
    assert h.pub.current().processed_source is None


def test_invalid_tool_arguments_are_not_a_successful_noop(harness):
    cls = workflow_class()
    h = harness
    invalid = call("write_file", file_path="/memory/knowledge.md", content="unparsed")
    invalid["output"][0]["arguments"] = '{"file_path":'
    h.replies.append(invalid)
    with pytest.raises(ValueError, match="invalid tool"):
        cls(h.b1, h.pub, h.model, h.saver).start()
    assert len(h.sent) == 2 and h.pub.current() is None
    assert h.store.search(("q019-memory", h.reader.document_id, "versions")) == []


@pytest.mark.parametrize("bad_step", ["mixed-invalid", "incomplete-tool"])
def test_later_completed_answer_does_not_erase_prior_response_failure(harness, bad_step):
    cls = workflow_class()
    h = harness
    response = call("write_file", file_path="/memory/knowledge.md", content="partial work")
    if bad_step == "mixed-invalid":
        invalid = dict(response["output"][0], arguments='{"file_path":', call_id="bad-call")
        response["output"].append(invalid)
    else:
        response["status"] = "incomplete"
    h.replies.extend([response, done()])
    with pytest.raises(ValueError, match="invalid tool|not complete"):
        cls(h.b1, h.pub, h.model, h.saver).start()
    assert h.pub.current() is None
