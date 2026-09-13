"""Independent review probes at c1c9f8f7. Synthetic native Saver, zero provider.

Run from experiments/jd-relational-app with PYTHONPATH=src;tests and pytest
pointed at this file. Assertions express the required behavior (red on baseline).
"""
import pytest
from langchain_core.messages import AIMessage

from test_chat_history import native
from test_interview_window_source import interview, settled
from jd_relational.ai_history import AiRunHistory
from jd_relational.conversation_sources import ConversationSourceError


def test_every_publicly_planned_window_can_be_revalidated(interview, native):
    windows, document, first, _ = interview
    third = settled(native, [AIMessage(id="review-third", content="第三輪回覆")], text="第三輪原話")
    planned = windows.plan_windows(document, first_run_id=first,
        last_run_id=third.record.run_id, max_chars=20, context_chars=10)
    assert len(planned) > 1
    for pair in planned:
        windows.read_window(pair["source_reference"], document)
        windows.validate_saved_window(pair["source_reference"], pair["context_reference"],
            document, max_chars=20, context_chars=10)


def test_follows_rejects_a_publicly_issued_candidate_on_a_sibling_branch(interview, native):
    windows, document, first, second = interview
    graph, dataset, *_ = native
    previous = windows.capture_window(document, first_run_id=first, last_run_id=first)
    parent = windows._codec._resolve_window(windows.capture_window(
        document, first_run_id=second, last_run_id=second), document).root_config()
    branch_a = graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    candidate = windows.capture_window(document, first_run_id=second, last_run_id=second)
    position = windows._codec._resolve_window(candidate, document)
    assert position.root_checkpoint_id == branch_a["configurable"]["checkpoint_id"]
    branch_b = graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    assert not AiRunHistory(windows._checkpoints).ancestor_of(
        document, position.root_checkpoint_id, branch_b)
    windows.read_window(candidate, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.follows(candidate, previous, document)
