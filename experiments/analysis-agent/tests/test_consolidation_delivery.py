"""MP-02f: real B2 tools, final feedback and publication; synthetic HTTP only."""
import json

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError

from analysis_agent.consolidation import ConsolidationWorkflow
from test_consolidation import harness, call, done, knowledge
from test_consolidation_feedback import assert_paired, assert_unpublished, runtime_feedback


BODY = "/memory/knowledge.md"
GUIDE = "/memory/guide.md"


def guide(h):
    return h.artifacts.read_text(GUIDE, h.pub.current().memory)


@pytest.mark.parametrize("empty_guide", ["", " \n\t"])
def test_body_without_guide_returns_final_feedback_and_repairs_before_publishing(harness, empty_guide):
    h = harness
    body = "依客戶需求開發前端網站。\n詳記：" + h.extracted["files"][0]["summary_path"]
    # Both are legitimate initial staged writes, but not a completed pair yet.
    h.replies.extend([call("write_file", file_path=BODY, content=body),
                      call("write_file", file_path=GUIDE, content=empty_guide), done()])

    def repair():
        assert_unpublished(h)
        return call("write_file", file_path=GUIDE, content="網站工作：見 /memory/knowledge.md")

    h.replies.extend([repair, done()])
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    assert guide(h) == "網站工作：見 /memory/knowledge.md"
    assert knowledge(h) == body
    assert result["used_model_steps"] == 5 and result["used_tool_calls"] == 3
    assert h.pub.current().revision == 1
    feedback = json.dumps(runtime_feedback(h.sent[4]), ensure_ascii=False)
    assert BODY in feedback and GUIDE in feedback and "empty" in feedback
    assert len(feedback) < 1000
    assert not any(item.get("name") == "validate_memory" for wire in h.sent[1:]
                   for item in wire["input"] if item.get("type") == "function_call")
    for wire in h.sent[1:]:
        assert_paired(wire)


def test_optional_preflight_reports_missing_guide_as_tool_error(harness):
    h = harness
    h.replies.extend([call("write_file", file_path=BODY, content="網站工作"),
                      call("validate_memory"),
                      call("write_file", file_path=GUIDE, content="網站主題"), done()])
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    error = next(item["output"] for item in h.sent[3]["input"]
                 if item.get("type") == "function_call_output" and "empty" in item["output"])
    assert BODY in error and GUIDE in error
    assert knowledge(h) == "網站工作" and guide(h) == "網站主題"
    assert result["used_model_steps"] == 4 and result["used_tool_calls"] == 3
    assert not any(runtime_feedback(wire) for wire in h.sent)


@pytest.mark.parametrize("cap", [2, 4])
def test_missing_guide_exhausts_existing_budget_without_publication_or_fresh_resume(harness, cap):
    h = harness
    h.replies.extend([call("write_file", file_path=BODY, content="網站工作"),
                      *(done() for _ in range(cap - 1))])
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_model_steps=cap)
    with pytest.raises(ModelCallLimitExceededError):
        workflow.start()
    assert_unpublished(h)
    count = len(h.sent)
    with pytest.raises(ModelCallLimitExceededError):
        ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_model_steps=cap).resume()
    assert len(h.sent) == count == cap + 1
    assert_unpublished(h)


def test_initial_empty_noop_still_finishes_without_tool_calls(harness):
    h = harness
    h.replies.append(done())
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    assert knowledge(h) == guide(h) == ""
    assert result["used_model_steps"] == 1 and result["used_tool_calls"] == 0
    assert h.pub.current().processed_source == h.ref


def test_short_read_then_native_overwrite_preserves_other_case_and_reuses_guide(harness):
    h = harness
    original = "共同工作：依客戶需求開發前端網站。\nA：單次付款，保留購物車。\nB：月租課程，營運主管驗收。"
    updated = "共同工作：依客戶需求開發前端網站。\nA：單次付款，保留購物車與已填資料。\nB：月租課程，營運主管驗收。"
    version = h.artifacts.save_memory(knowledge=original, guide="A／B 網站案例")
    h.pub.publish(h.pub.prepare(version, expected_revision=0, kind="repair"))
    h.replies.extend([call("read_file", file_path=BODY),
                      call("write_file", file_path=BODY, content=updated), done()])
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    read_result = next(item["output"] for item in h.sent[2]["input"]
                       if item.get("type") == "function_call_output")
    assert "A：單次付款，保留購物車。" in read_result
    assert "B：月租課程，營運主管驗收。" in read_result
    assert knowledge(h) == updated and guide(h) == "A／B 網站案例"
    assert h.pub.current().revision == 2
    assert h.artifacts.read_text(BODY, version) == original
    assert result["used_model_steps"] == 3 and result["used_tool_calls"] == 2


@pytest.mark.parametrize("detail_size", [0, 1200])
def test_partial_read_then_exact_edit_preserves_unread_long_body(harness, detail_size):
    h = harness
    original = "\n".join(f"案例 {i}：保留獨特細節" + "細" * detail_size for i in range(120))
    version = h.artifacts.save_memory(knowledge=original, guide="案例目錄")
    h.pub.publish(h.pub.prepare(version, expected_revision=0, kind="repair"))
    h.replies.extend([call("read_file", file_path=BODY),
                      call("edit_file", file_path=BODY, old_string="案例 10：保留獨特細節",
                           new_string="案例 10：保留獨特細節；補充驗收條件"), done()])
    ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    read_result = next(item["output"] for item in h.sent[2]["input"]
                       if item.get("type") == "function_call_output")
    assert "案例 10：保留獨特細節" in read_result
    assert "案例 119：保留獨特細節" not in read_result
    if detail_size:
        assert "truncated" in read_result.lower()
    lines = knowledge(h).splitlines()
    assert len(lines) == 120 and lines[10] == "案例 10：保留獨特細節；補充驗收條件" + "細" * detail_size
    assert lines[:10] == original.splitlines()[:10]
    assert lines[11:] == original.splitlines()[11:]
    assert guide(h) == "案例目錄"
