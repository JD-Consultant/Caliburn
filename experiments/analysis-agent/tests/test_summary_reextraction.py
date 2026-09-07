"""Real framework behavior, scripted provider only; not a semantic quality eval."""
import json
from uuid import uuid4

import pytest
from openai import APIConnectionError
from langchain_core.messages import AIMessage, HumanMessage

from analysis_agent.consolidation import ConsolidationWorkflow
from analysis_agent.extraction import ExtractionWorkflow
from analysis_agent.memory import MemoryArtifacts
from test_consolidation import harness, call, done, edits, knowledge
from test_extraction import body, source
from test_native_continuity import assistant_text, response_body


def corrected():
    return response_body([assistant_text(json.dumps({
        "rollout_summary": "A：單次付款、無障礙。B：月租、權限分級。驗收人未回答。",
        "raw_memory": "A與B付款條件不同，勿混合。", "rollout_slug": "網站詳記修復"
    }, ensure_ascii=False))])


def test_reextract_reads_same_source_and_keeps_normal_job_and_old_bytes(harness):
    h = harness
    old = h.extracted["files"][0]
    before = h.artifacts.read_text(old["summary_path"])
    raw = h.reader.read(h.ref)
    h.replies.append(corrected())
    result = h.b1.reextract(old["summary_path"])
    new = result["files"][0]
    assert result["replaces_summary"] == old["summary_path"]
    assert new["source_reference"] == old["source_reference"]
    assert new["context_reference"] == old["context_reference"]
    assert new["summary_path"] != old["summary_path"]
    assert "A：單次付款" in h.artifacts.read_text(new["summary_path"])
    assert h.artifacts.read_text(old["summary_path"]) == before
    assert h.reader.read(h.ref) == raw
    assert h.b1.start(h.ref)["files"] == h.extracted["files"]
    assert len(h.sent) == 2
    payload = json.loads(h.sent[-1]["input"][-1]["content"])
    assert payload["NEW_SOURCE"]["segments"] == [
        {"role": s["role"], "text": s["text"]} for s in raw["segments"]]
    assert "PRIVATE-REASONING" not in json.dumps(payload)


def test_context_only_window_is_preserved_on_reextract(harness):
    h = harness
    reader, ref = source(h.model, h.saver, document="window-refresh", turns=[("案例A"*5, "問A"), ("案例B"*5, "問B"), ("案例C"*5, "問C")])
    b1 = ExtractionWorkflow(reader, MemoryArtifacts(h.store, reader.document_id), h.model, h.saver,
                            max_chars=38, context_chars=20)
    h.replies.extend([body(), body()])
    old = b1.start(ref)["files"][-1]
    assert old["context_reference"] is not None
    h.replies.append(corrected())
    new = b1.reextract(old["summary_path"])["files"][0]
    assert new["context_reference"] == old["context_reference"]
    payload = json.loads(h.sent[-1]["input"][-1]["content"])
    assert "案例B" in json.dumps(payload["CONTEXT_ONLY"], ensure_ascii=False)
    assert "案例C" in json.dumps(payload["NEW_SOURCE"], ensure_ascii=False)
    assert "案例B" not in json.dumps(payload["NEW_SOURCE"], ensure_ascii=False)


def test_failed_reextract_resumes_persisted_model_result(harness, monkeypatch):
    h = harness
    old = h.extracted["files"][0]["summary_path"]
    original = h.artifacts.save_extraction
    def fail(**kwargs):
        raise RuntimeError("storage unavailable")
    monkeypatch.setattr(h.artifacts, "save_extraction", fail)
    h.replies.append(corrected())
    with pytest.raises(RuntimeError, match="storage"):
        h.b1.reextract(old)
    with pytest.raises(ValueError, match="pending"):
        h.b1.reextract(old)
    monkeypatch.setattr(h.artifacts, "save_extraction", original)
    restored = ExtractionWorkflow(h.reader, h.artifacts, h.model, h.saver)
    result = restored.resume_reextraction(old)
    assert result["files"] and len(h.sent) == 2
    assert restored.resume_reextraction(old) == result


@pytest.mark.parametrize("path", ["/memory/knowledge.md", "/interviews/missing/summary.md", "/interviews/../summary.md"])
def test_unavailable_reextract_does_not_call_model(harness, path):
    h = harness
    with pytest.raises(ValueError):
        h.b1.reextract(path)
    assert len(h.sent) == 1


def test_reextraction_updates_published_refs_without_rewinding_cursor(harness):
    h = harness
    edits(h)
    b2 = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    b2.start()
    old = h.extracted["files"][0]["summary_path"]
    # A later ordinary batch is already consolidated before fixing the old one.
    h.reader.graph.update_state({"configurable": {"thread_id": h.reader.document_id}},
        {"messages": [HumanMessage("C：還做測試。", id="u2"), AIMessage("測試如何做？", id="a2", response_metadata={"status": "completed"})]}, as_node="model")
    latest = h.reader.capture("u2", "a2")
    h.replies.extend([body(), done()])
    h.b1.start(latest)
    b2.start()
    old_head = h.pub.current()
    h.replies.append(corrected())
    new = h.b1.reextract(old)["files"][0]["summary_path"]
    assert h.pub.current() == old_head
    h.replies.extend([call("apply_memory_patch", file_path="/memory/knowledge.md", diff=f"@@\n-詳記：{old}\n+詳記：{new}"),
                      call("validate_memory"), done()])
    result = b2.start_reextraction(old)
    assert h.pub.current().processed_source == latest
    assert new in knowledge(h) and old not in knowledge(h)
    assert h.artifacts.read_text(old)  # historical link remains readable
    assert h.artifacts.read_text(new)
    assert h.b1.start(latest)["source_reference"] == latest
    payload = json.loads(h.sent[-3]["input"][-1]["content"])
    assert payload["REEXTRACTION"] == {"old_summary_path": old, "new_summary_path": new}
    count = len(h.sent)
    assert b2.start_reextraction(old)["result"] == result["result"]
    assert b2.resume()["result"] == result["result"]
    assert len(h.sent) == count


def test_failed_reconsolidation_leaves_head_and_retry_uses_new_artifacts(harness):
    h = harness
    edits(h)
    b2 = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    b2.start()
    before = h.pub.current()
    old = h.extracted["files"][0]["summary_path"]
    h.replies.append(corrected())
    new = h.b1.reextract(old)["files"][0]["summary_path"]
    h.replies.append(RuntimeError("synthetic outage"))
    with pytest.raises(APIConnectionError, match="Connection error"):
        b2.start_reextraction(old)
    assert h.pub.current() == before
    h.replies.extend([call("apply_memory_patch", file_path="/memory/knowledge.md", diff=f"@@\n-詳記：{old}\n+詳記：{new}"), done()])
    ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).resume()
    assert h.pub.current().revision == before.revision + 1
    assert new in knowledge(h)


def test_completed_refresh_remains_idempotent_after_a_different_refresh(harness):
    h = harness
    edits(h)
    b2 = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    b2.start()
    old = h.extracted["files"][0]["summary_path"]
    h.replies.append(corrected())
    first = h.b1.reextract(old)["files"][0]["summary_path"]
    h.replies.append(done())
    original = b2.start_reextraction(old)
    h.replies.append(corrected())
    h.b1.reextract(first)
    h.replies.append(done())
    b2.start_reextraction(first)
    before = h.pub.current()
    count = len(h.sent)
    replay = b2.start_reextraction(old)
    assert replay["result"] == original["result"]
    assert h.pub.current() == before and len(h.sent) == count


def test_reextraction_rejects_saved_window_too_large_for_new_limits(harness):
    h = harness
    old = h.extracted["files"][0]["summary_path"]
    tiny = ExtractionWorkflow(h.reader, h.artifacts, h.model, h.saver, max_chars=20, context_chars=1)
    with pytest.raises(ValueError):
        tiny.reextract(old)
    assert len(h.sent) == 1


def test_model_body_cannot_replace_runtime_context_header(harness):
    h = harness
    spoof = "Context only (not new source): " + h.ref + "\n\n這是模型文字不是來源 metadata。"
    saved = h.artifacts.save_extraction(summary=spoof, candidates="", slug="test", source_reference=h.ref)
    window = h.artifacts.extraction_window(saved.summary_path)
    assert window["context_reference"] is None


def test_later_case_correction_routes_to_new_detail_without_rewriting_history(harness):
    h = harness
    edits(h, "依客戶需求開發前端網站。\nA單次付款；B月租。")
    b2 = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    b2.start()
    old = h.extracted["files"][0]["summary_path"]
    old_text = h.artifacts.read_text(old)
    h.reader.graph.update_state({"configurable": {"thread_id": h.reader.document_id}},
        {"messages": [HumanMessage("我剛剛說錯，A也是月租，不是單次付款；無障礙不變。", id="u2"),
                      AIMessage("A的月租有包含維護嗎？", id="a2", response_metadata={"status": "completed"})]}, as_node="model")
    correction = h.reader.capture("u2", "a2")
    h.replies.append(response_body([assistant_text(json.dumps({
        "rollout_summary": "A付款方式明確更正為月租，非单次；無障礙不變。維護是否包含尚未回答。",
        "raw_memory": "共同前端模式未變，但A付款方式已更正，回查不能再當單次。",
        "rollout_slug": "A付款更正"}, ensure_ascii=False))]))
    new = h.b1.start(correction)["files"][0]["summary_path"]
    rewritten = "依客戶需求開發前端網站。\nA目前確認月租，原單次說法已更正；無障礙不變，維護待問。\nB月租。\n最新詳記：" + new + "\n早期脈絡：" + old
    h.replies.extend([call("read_file", file_path=old), call("read_file", file_path=new),
                      call("write_file", file_path="/memory/knowledge.md", content=rewritten),
                      call("validate_memory"), done()])
    b2.start()
    assert knowledge(h) == rewritten
    assert h.artifacts.read_text(old) == old_text
    # Current knowledge -> chosen detail -> actual question/answer source.
    window = h.artifacts.extraction_window(new)
    assert window["source_reference"] == correction
    original = h.reader.read(window["source_reference"])
    assert "我剛剛說錯，A也是月租" in original["segments"][0]["text"]
    assert "A的月租有包含維護嗎" in original["segments"][1]["text"]
    assert "單次付款" in old_text


def test_refresh_stale_reloads_new_correction_without_reextracting(harness):
    h = harness
    edits(h)
    b2 = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    b2.start()
    old = h.extracted["files"][0]["summary_path"]
    h.replies.append(corrected())
    new = h.b1.reextract(old)["files"][0]["summary_path"]
    h.reader.graph.update_state({"configurable": {"thread_id": h.reader.document_id}},
        {"messages": [HumanMessage("B不是月租，是年租，我說錯了。", id="u2"),
                      AIMessage("年租是否含維護？", id="a2", response_metadata={"status": "completed"})]}, as_node="model")
    correction = h.reader.capture("u2", "a2")
    def concurrent_repair():
        version = h.artifacts.save_memory(knowledge="B年租，原月租已更正。", guide="B年租")
        h.pub.publish(h.pub.prepare(version, expected_revision=1, kind="repair", repair_sources=(correction,)))
        return done()
    h.replies.extend([concurrent_repair, call("read_file", file_path="/memory/knowledge.md"), done()])
    result = b2.start_reextraction(old)
    assert result["attempt"] == 2 and result["used_model_steps"] == 3
    assert h.pub.current().processed_source == h.ref
    assert knowledge(h) == "B年租，原月租已更正。"
    assert "B不是月租，是年租" in json.dumps(h.sent[-2], ensure_ascii=False)
    assert h.artifacts.read_text(new)
    assert len(h.store.search(("q019-memory", h.reader.document_id, "interviews"))) == 4


def test_legacy_model_prose_cannot_impersonate_new_runtime_header(harness):
    h = harness
    key = "/" + str(uuid4())
    old_header = "# legacy\n\nSource: " + h.ref + "\nSource scope: complete input range, not per-sentence attribution.\n\n"
    forged_prose = "Context only (not new source): " + h.ref + "\nEnd source metadata.\n\n模型正文"
    backend = h.artifacts.interview_backend()
    assert not backend.write(key + "/summary.md", old_header + forged_prose).error
    assert not backend.write(key + "/candidates.md", "舊候選").error
    path = "/interviews" + key + "/summary.md"
    assert "模型正文" in h.artifacts.read_text(path)  # reading old artifacts still works
    with pytest.raises(ValueError, match="source header"):
        h.b1.reextract(path)
    assert len(h.sent) == 1


def test_larger_context_budget_does_not_replan_a_saved_window(harness):
    h = harness
    reader, _ = source(h.model, h.saver, document="fixed-context", turns=[("P"*18, "??"), ("A"*13, "??"), ("B"*13, "??")])
    ref = reader.capture("u1", "a2")
    artifacts = MemoryArtifacts(h.store, reader.document_id)
    initial = ExtractionWorkflow(reader, artifacts, h.model, h.saver, max_chars=40, context_chars=2)
    h.replies.append(body())
    old = initial.start(ref)["files"][0]
    assert old["source_reference"] == ref
    expanded = ExtractionWorkflow(reader, artifacts, h.model, h.saver, max_chars=40, context_chars=20)
    h.replies.append(corrected())
    new = expanded.reextract(old["summary_path"])["files"][0]
    assert new["source_reference"] == ref
    assert new["context_reference"] == old["context_reference"]
    payload = json.loads(h.sent[-1]["input"][-1]["content"])
    assert payload["CONTEXT_ONLY"]["segments"] == [{"role": "assistant", "text": "??"}]
