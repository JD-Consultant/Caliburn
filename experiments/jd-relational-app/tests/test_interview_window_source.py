"""Completed-window reference purpose isolation; no DB, provider or new table.

Window content reads and planning are a later slice. What this file pins down
is the boundary the B2 publication path depends on: a completed-window
reference must be validatable by the same source owner without ever becoming
usable as a current-turn source for C or the read tools.
"""
import hashlib
from uuid import uuid4

from caliburn_memory import MemoryArtifacts, PublicationStore
from caliburn_memory.requests import REQUEST_KIND, REQUEST_TOOL_NAME, has_saved_request
from caliburn_memory.sources import InvalidSourceReference
from itsdangerous import URLSafeSerializer
from langgraph.store.memory import InMemoryStore
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from jd_relational.ai_history import MAX_PARENT_LOOKUPS, AiRunHistory
from jd_relational.conversation_sources import (
    _CONTEXT_PREFIX,
    ConversationSourceError, WindowBudgetExceeded, _ContextPosition, _WindowPosition,
)

from jd_relational.memory_sources import MemorySourceReader
from langchain_core.messages import AIMessage, ToolMessage

from test_chat_history import append, native
from test_conversation_sources import KEY, seed, service


def window_ref(sources, document, *, first, last, first_run, last_run, root="root-checkpoint-1"):
    """Issue directly: the public issuing path belongs with the window planner."""
    position = _WindowPosition(format_version=1, purpose="window",
        dataset_id=sources.dataset_id, document_id=document, root_checkpoint_id=root,
        first=first, last=last, root_run_id=last_run, first_run_id=first_run, last_run_id=last_run)
    return sources._codec._issue_window(position)


@pytest.fixture
def issued(native):
    observed, _ = seed(native)
    _, dataset, document, *_ = native
    sources = service(native)
    run = observed.record.run_id
    source_ref = sources.capture(document, run).source_ref
    return sources, document, dataset, source_ref, window_ref(
        sources, document, first=run, last="this-run-reply", first_run=run, last_run=run)


def test_a_window_reference_is_never_accepted_as_a_current_turn_source(issued):
    sources, document, _, source_ref, window = issued
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        sources.validate_reference(window, document)
    sources.validate_window_reference(window, document)


def test_a_turn_source_is_never_accepted_as_a_completed_window(issued):
    sources, document, _, source_ref, _ = issued
    sources.validate_reference(source_ref, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        sources.validate_window_reference(source_ref, document)


def test_the_two_purposes_share_the_codec_but_not_the_signature_domain(issued):
    sources, document, _, source_ref, window = issued
    source_domain = URLSafeSerializer(KEY, salt="caliburn.jd.conversation-source.v1",
        signer_kwargs={"digest_method": hashlib.sha256})
    with pytest.raises(Exception):
        source_domain.loads(window.split(":", 1)[1])


@pytest.mark.parametrize("change", ["key", "dataset", "document"])
def test_a_window_reference_from_another_owner_scope_is_rejected(native, issued, change):
    sources, document, dataset, _, window = issued
    other = service(native, key=b"another-synthetic-source-key-32bytes") if change == "key" \
        else service(native, dataset=str(uuid4())) if change == "dataset" else sources
    target = str(uuid4()) if change == "document" else document
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        other.validate_window_reference(window, target)


def test_the_memory_reader_validates_windows_only_when_the_owner_grants_them(issued):
    sources, document, _, source_ref, window = issued
    turn_only = MemorySourceReader(sources, document)
    with_windows = MemorySourceReader(sources, document, window_references=True)
    turn_only.validate_reference(source_ref)
    with_windows.validate_reference(source_ref)
    with pytest.raises(InvalidSourceReference):
        turn_only.validate_reference(window)
    with_windows.validate_reference(window)


def test_consolidation_publishes_its_completed_window_only_through_a_granting_reader(issued):
    sources, document, _, _, window = issued
    store = InMemoryStore()
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False},
                              poolclass=StaticPool)
    try:
        blocked = PublicationStore(engine, MemoryArtifacts(store, document,
            source=MemorySourceReader(sources, document)))
        blocked.setup()
        artifacts = MemoryArtifacts(store, document,
            source=MemorySourceReader(sources, document, window_references=True))
        publication = PublicationStore(engine, artifacts)
        version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
        with pytest.raises(InvalidSourceReference):
            blocked.prepare(version, expected_revision=0, kind="consolidation",
                            processed_source=window)
        head = publication.publish(publication.prepare(version, expected_revision=0,
            kind="consolidation", processed_source=window))
        assert head.revision == 1 and head.processed_source == window
        assert publication.current().processed_source == window
    finally:
        engine.dispose()


def settled(native, replies, *, text, status="completed"):
    """Append one turn and give it the App's own settled terminal record."""
    graph, dataset, document, pending, _, _ = native
    observed = append(native, replies, text=text, pause=True)
    adapter = AiRunCheckpoints(graph)
    observed = adapter.discover(document, dataset)
    return adapter.close(observed, status=status, messages=observed.messages,
        bindings=observed.bindings, model_view=observed.model_view,
        read_binding=observed.read_binding)


@pytest.fixture
def interview(native):
    graph, dataset, document, *_ = native
    first = settled(native, [AIMessage(id="a1", content="第一輪回覆")], text="第一輪原話")
    second = settled(native, [
        ToolMessage(id="t1", tool_call_id="c1", content="PRIVATE_TOOL"),
        AIMessage(id="a2", content=[
            {"type": "thinking", "thinking": "PRIVATE", "signature": "S"},
            {"type": "text", "text": "第二輪回覆"}])],
        text="第二輪原話😀", status="cancelled")
    sources = service(native)
    windows = sources
    return windows, document, first.record.run_id, second.record.run_id


def test_safe_turns_report_each_terminal_and_stop_before_an_unfinished_turn(interview, native):
    windows, document, first_run, second_run = interview
    append(native, [AIMessage(id="a3", content="尚未收尾")], text="第三輪原話", pause=True)
    turns = windows.safe_turns(document)
    assert [t["input_id"] for t in turns] == [first_run, second_run]
    assert [t["status"] for t in turns] == ["completed", "cancelled"]
    assert [t["answer_succeeded"] for t in turns] == [True, False]


def test_a_settled_cancelled_turn_keeps_its_speech_in_the_window(interview):
    windows, document, first_run, second_run = interview
    page = windows.read_window(windows.capture_window(
        document, first_run_id=first_run, last_run_id=second_run), document)
    spoken = [s for s in page["segments"] if s["role"] == "user"]
    assert [s["text"] for s in spoken] == ["第一輪原話", "第二輪原話😀"]
    assert [t["answer_succeeded"] for t in page["turns"]] == [True, False]
    assert page["omitted_content_types"] == ["thinking", "tool"]
    assert page["next_offset"] is None


def test_a_window_pages_by_unicode_code_points_and_repeats_turns(interview, native):
    windows, document, first_run, _ = interview
    # Each emoji is one code point but four UTF-8 bytes: a byte-based pager
    # would cut this window in a different place.
    long_turn = settled(native, [AIMessage(id="a9", content="是")], text="😀" * 3300)
    ref = windows.capture_window(document, first_run_id=first_run,
                                 last_run_id=long_turn.record.run_id)
    first_page = windows.read_window(ref, document)
    assert first_page["next_offset"] == 3000
    assert sum(len(s["text"]) for s in first_page["segments"]) == 3000
    second_page = windows.read_window(ref, document, offset=first_page["next_offset"])
    assert [t["input_id"] for t in second_page["turns"]] == [t["input_id"] for t in first_page["turns"]]
    joined = "".join(s["text"] for s in (*first_page["segments"], *second_page["segments"]))
    assert "😀" * 3300 in joined and second_page["next_offset"] is None


def test_capture_window_refuses_an_unfinished_end_or_a_gap(interview, native):
    windows, document, first_run, second_run = interview
    running = append(native, [AIMessage(id="a4", content="仍在跑")], text="第三輪", pause=True)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.capture_window(document, first_run_id=first_run,
                               last_run_id=running.record.run_id)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.capture_window(document, first_run_id=second_run, last_run_id=first_run)


def test_a_window_whose_bounds_do_not_match_the_fixed_position_is_invalid(interview):
    windows, document, first_run, second_run = interview
    issued_ref = windows.capture_window(document, first_run_id=first_run, last_run_id=second_run)
    position = windows._codec._resolve_window(issued_ref, document)
    forged = window_ref(windows, document, first=first_run, last="no-such-message",
                        first_run=first_run, last_run=second_run,
                        root=position.root_checkpoint_id)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.read_window(forged, document)
    absent_root = window_ref(windows, document, first=first_run, last=position.last,
                             first_run=first_run, last_run=second_run, root="no-such-root")
    with pytest.raises(ConversationSourceError, match="^source_not_available$"):
        windows.read_window(absent_root, document)


def asked(number="c1"):
    """One real, unambiguous saved request pair, as the verified tool emits it."""
    return [AIMessage(id=f"ai-{number}", content="", tool_calls=[{
                "name": REQUEST_TOOL_NAME, "id": number, "args": {}, "type": "tool_call"}]),
            ToolMessage(id=f"tm-{number}", tool_call_id=number, name=REQUEST_TOOL_NAME,
                        content="收到整理請求", status="success", artifact={"kind": REQUEST_KIND})]


def test_settled_turns_without_any_request_trigger_nothing(interview, native):
    windows, document, first_run, second_run = interview
    assert windows.pending_windows(document) == ()
    assert windows.unprocessed_source(document) == {
        "first_run_id": first_run, "last_run_id": second_run}


def test_a_request_only_triggers_while_the_batch_still_covers_quiet_turns(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [*asked(), AIMessage(id="a5", content="好")], text="第三輪原話")
    fourth = settled(native, [AIMessage(id="a6", content="沒有請求")], text="第四輪原話")
    assert [t["input_id"] for t in windows.pending_windows(document)] == [third.record.run_id]
    # The quiet fourth turn is still part of the contiguous batch to process.
    assert windows.unprocessed_source(document) == {
        "first_run_id": first_run, "last_run_id": fourth.record.run_id}


def test_a_request_after_an_unfinished_turn_is_not_admitted_yet(interview, native):
    windows, document, first_run, second_run = interview
    append(native, [AIMessage(id="a7", content="仍在跑")], text="第三輪原話", pause=True)
    assert windows.pending_windows(document) == ()
    assert windows.unprocessed_source(document) == {
        "first_run_id": first_run, "last_run_id": second_run}


@pytest.mark.parametrize("broken", ["call_only", "text_only", "error_result"])
def test_only_a_real_saved_request_pair_counts(interview, native, broken):
    windows, document, *_ = interview
    call, result = asked()
    replies = ([call] if broken == "call_only"
               else [AIMessage(id="a8", content="我已經請系統整理記憶了")] if broken == "text_only"
               else [call, result.model_copy(update={"status": "error"})])
    settled(native, replies, text="第三輪原話")
    assert windows.pending_windows(document) == ()


def test_an_ambiguous_request_is_refused_before_it_could_ever_be_saved():
    """The App's own closure already refuses a duplicated call id.

    Recognition keeps its own ambiguity rule anyway, so a conversation that
    somehow carried one would still not count as a request.
    """
    call, result = asked()
    assert has_saved_request([call, result]) is True
    assert has_saved_request([call, result, call.model_copy(update={"id": "ai-again"}),
                              result.model_copy(update={"id": "tm-again"})]) is False


def test_a_published_cursor_moves_the_batch_and_a_turn_source_is_never_one(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [*asked(), AIMessage(id="a5", content="好")], text="第三輪原話")
    processed = windows.capture_window(document, first_run_id=first_run, last_run_id=second_run)
    assert windows.pending_windows(document, processed) == windows.pending_windows(document)
    assert windows.unprocessed_source(document, processed) == {
        "first_run_id": third.record.run_id, "last_run_id": third.record.run_id}
    covered = windows.capture_window(document, first_run_id=first_run,
                                     last_run_id=third.record.run_id)
    assert windows.unprocessed_source(document, covered) is None
    assert windows.pending_windows(document, covered) == ()
    turn_source = windows.capture(document, third.record.run_id).source_ref
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.unprocessed_source(document, turn_source)


def test_an_off_lineage_cursor_stops_admission_instead_of_resetting(interview, native):
    windows, document, first_run, second_run = interview
    position = windows._codec._resolve_window(
        windows.capture_window(document, first_run_id=first_run, last_run_id=second_run), document)
    stray = window_ref(windows, document, first=first_run, last="not-in-this-conversation",
                       first_run=first_run, last_run=second_run, root=position.root_checkpoint_id)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.unprocessed_source(document, stray)


def plain(native, count, *, size=10, start=1):
    return [settled(native, [AIMessage(id=f"pa{start + i}", content="回" * size)],
                    text="問" * size) for i in range(count)]


def test_planned_windows_pair_each_range_with_its_disambiguating_context(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [AIMessage(id="pa9", content="第三輪回覆")], text="第三輪原話")
    planned = windows.plan_windows(document, first_run_id=first_run,
                                   last_run_id=third.record.run_id, max_chars=20, context_chars=10)
    assert len(planned) > 1
    assert planned[0]["context_reference"] is None, "The first window has no prior question."
    for window in planned[1:]:
        assert window["context_reference"] is not None
        context = windows.read_context(window["context_reference"], document)
        assert context["segments"][0]["role"] == "assistant"
    covered = [windows.read_window(w["source_reference"], document) for w in planned]
    assert [t["input_id"] for page in covered for t in page["turns"]] == [
        t["input_id"] for t in windows.safe_turns(document)]


def test_an_oversize_turn_fails_instead_of_losing_its_middle(interview, native):
    windows, document, first_run, _ = interview
    big = settled(native, [AIMessage(id="pa8", content="長" * 200)], text="長" * 200)
    with pytest.raises(WindowBudgetExceeded):
        windows.plan_windows(document, first_run_id=first_run,
                             last_run_id=big.record.run_id, max_chars=100, context_chars=20)


def test_a_context_that_does_not_fit_is_reported_not_truncated(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [AIMessage(id="pa7", content="第三輪回覆")], text="第三輪原話")
    with pytest.raises(WindowBudgetExceeded):
        windows.plan_windows(document, first_run_id=first_run,
                             last_run_id=third.record.run_id, max_chars=30, context_chars=1)


def test_a_bounded_batch_keeps_its_unprocessed_tail(interview, native):
    windows, document, first_run, _ = interview
    tail = plain(native, 3)
    batch = windows.plan_batch(document, first_run_id=first_run,
                               last_run_id=tail[-1].record.run_id, max_chars=40, context_chars=20, max_windows=2)
    assert len(batch["windows"]) == 2 and batch["covers_whole_range"] is False
    whole = windows.plan_batch(document, first_run_id=first_run,
                               last_run_id=tail[-1].record.run_id, max_chars=40, context_chars=20, max_windows=99)
    assert whole["covers_whole_range"] is True


def test_a_saved_window_is_revalidated_without_being_replanned(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [AIMessage(id="pa6", content="第三輪回覆")], text="第三輪原話")
    planned = windows.plan_windows(document, first_run_id=first_run,
                                   last_run_id=third.record.run_id, max_chars=40, context_chars=20)
    saved = planned[-1]
    windows.validate_saved_window(saved["source_reference"], saved["context_reference"],
                                  document, max_chars=40, context_chars=20)
    with pytest.raises(WindowBudgetExceeded):
        windows.validate_saved_window(saved["source_reference"], saved["context_reference"],
                                      document, max_chars=5, context_chars=1)


def test_every_planned_window_in_a_batch_keeps_its_own_pair(interview, native):
    """One batch pins every window on one root, yet only the last ends there.

    Each pair is re-checked at the position it was issued, so a window in the
    middle of the batch stays as readable as the final one, and a later turn
    never moves what an already planned pair reads back.
    """
    windows, document, first_run, _ = interview
    third = settled(native, [AIMessage(id="rv1", content="第三輪回覆")], text="第三輪原話")
    planned = windows.plan_windows(document, first_run_id=first_run,
                                   last_run_id=third.record.run_id, max_chars=20, context_chars=10)
    assert len(planned) > 1
    pages = []
    for pair in planned:
        pages.append(windows.read_window(pair["source_reference"], document))
        windows.validate_saved_window(pair["source_reference"], pair["context_reference"],
                                      document, max_chars=20, context_chars=10)
    settled(native, [AIMessage(id="rv2", content="第四輪回覆")], text="第四輪原話")
    for pair, page in zip(planned, pages):
        assert windows.read_window(pair["source_reference"], document) == page
        windows.validate_saved_window(pair["source_reference"], pair["context_reference"],
                                      document, max_chars=20, context_chars=10)


def test_planning_inside_a_saved_window_stays_at_its_own_root(interview, native):
    """The saved reference decides where planning reads, not what is latest."""
    windows, document, first_run, second_run = interview
    saved = windows.capture_window(document, first_run_id=first_run, last_run_id=second_run)
    before = windows.plan_saved_windows(saved, document, max_chars=24, context_chars=12)
    settled(native, [AIMessage(id="later1", content="第三輪回覆")], text="第三輪原話")
    assert windows.plan_saved_windows(saved, document, max_chars=24, context_chars=12) == before
    for pair in before:
        page = windows.read_window(pair["source_reference"], document)
        assert {turn["input_id"] for turn in page["turns"]} <= {first_run, second_run}
        assert "第三輪原話" not in "".join(segment["text"] for segment in page["segments"])


def test_a_window_from_an_abandoned_branch_is_never_replanned_on_the_current_one(interview, native):
    """A readable history reference is still not an admissible planning input.

    Both siblings hold the same turns, so only the chain distinguishes them. A
    token pinned to the abandoned one must fail rather than quietly produce
    pairs cut from the branch that happens to be current.
    """
    graph, dataset, document, *_ = native
    windows, _, first_run, second_run = interview
    parent = windows._codec._resolve_window(windows.capture_window(
        document, first_run_id=second_run, last_run_id=second_run), document).root_config()
    graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    abandoned = windows.capture_window(document, first_run_id=first_run, last_run_id=second_run)
    graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    windows.read_window(abandoned, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.plan_saved_windows(abandoned, document, max_chars=24, context_chars=12)


def test_a_context_belongs_to_one_planned_source_and_never_another(interview, native):
    """Same root and same budget is not proof of the same planned pair.

    Re-extraction must continue from the pair that was issued together. A
    context cut for a different window would disambiguate the wrong speech,
    so it is refused even though both tokens are legitimate here.
    """
    windows, document, first_run, _ = interview
    third = settled(native, [AIMessage(id="pair3", content="第三輪回覆")], text="第三輪原話")
    planned = windows.plan_windows(document, first_run_id=first_run,
                                   last_run_id=third.record.run_id, max_chars=24, context_chars=12)
    assert len(planned) > 1 and planned[-1]["context_reference"]
    for pair in planned:
        windows.validate_saved_window(pair["source_reference"], pair["context_reference"],
                                      document, max_chars=24, context_chars=12)
        if pair["context_reference"]:
            windows.validate_window_pair(pair["source_reference"], pair["context_reference"], document)
    crossed = (planned[0]["source_reference"], planned[-1]["context_reference"])
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.validate_saved_window(*crossed, document, max_chars=24, context_chars=12)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.validate_window_pair(*crossed, document)


def test_a_context_from_another_root_is_never_paired(interview, native):
    """A context planned at one fixed position cannot serve another."""
    windows, document, first_run, second_run = interview
    early = windows.plan_windows(document, first_run_id=first_run, last_run_id=second_run,
                                 max_chars=20, context_chars=10)
    third = settled(native, [AIMessage(id="pair4", content="第三輪回覆")], text="第三輪原話")
    later = windows.plan_windows(document, first_run_id=first_run,
                                 last_run_id=third.record.run_id, max_chars=24, context_chars=12)
    context = next(pair["context_reference"] for pair in early if pair["context_reference"])
    source = next(pair["source_reference"] for pair in later if pair["context_reference"])
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.validate_window_pair(source, context, document)


def test_a_context_issued_before_the_pair_proof_is_refused(interview):
    """An older context format carries no pair proof, so it cannot be trusted."""
    windows, document, first_run, second_run = interview
    legacy = _CONTEXT_PREFIX + windows._codec._context_serializer.dumps({
        "format_version": 1, "purpose": "context", "dataset_id": windows.dataset_id,
        "document_id": document, "root_checkpoint_id": "root-checkpoint-1",
        "root_run_id": second_run, "first": first_run, "last": "a2"})
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.validate_context_reference(legacy, document)


def test_a_context_range_reports_exactly_the_settled_turns_it_covers(interview, native):
    """Context is never a new source, but its terminals stay provable.

    A disambiguation range that reaches back over a whole turn still says how
    that turn ended, so a cancelled or failed answer can never be read as a
    successful one. A range holding only a leading question reports none,
    because it contains none.
    """
    windows, document, first_run, second_run = interview
    third = settled(native, [AIMessage(id="ctx3", content="第三輪回覆")], text="第三輪原話")
    settled(native, [AIMessage(id="ctx4", content="第四輪回覆")], text="第四輪原話")
    stopped = settled(native, [AIMessage(id="ctx5", content="第五輪回覆")],
                      text="第五輪原話", status="failed")
    sixth = settled(native, [AIMessage(id="ctx6", content="第六輪回覆")], text="第六輪原話")
    settled_turns = {turn["input_id"]: turn for turn in windows.safe_turns(document)}
    seen, questions_only = {}, 0
    for max_chars, context_chars in ((20, 10), (24, 12), (60, 40), (400, 200)):
        for pair in windows.plan_windows(document, first_run_id=first_run,
                                         last_run_id=sixth.record.run_id,
                                         max_chars=max_chars, context_chars=context_chars):
            if pair["context_reference"] is None:
                continue
            page = windows.read_context(pair["context_reference"], document)
            spoken = [segment["message_id"] for segment in page["segments"]]
            reported = {turn["input_id"]: turn for turn in page["turns"]}
            assert set(reported) == {identifier for identifier in settled_turns if identifier in spoken}
            assert bool(reported) == any(segment["role"] == "user" for segment in page["segments"])
            questions_only += not reported
            seen.update(reported)
    # A context reaching over a whole turn keeps that turn's own terminal, for
    # a settled failure as much as for a success; a question-only range has none.
    assert questions_only
    assert seen[second_run]["status"] == "cancelled"
    assert seen[second_run]["answer_succeeded"] is False
    assert seen[third.record.run_id]["status"] == "completed"
    assert seen[third.record.run_id]["answer_succeeded"] is True
    assert seen[stopped.record.run_id]["status"] == "failed"
    assert seen[stopped.record.run_id]["answer_succeeded"] is False


def test_admission_refuses_an_earlier_or_skipping_range(interview, native):
    windows, document, first_run, second_run = interview
    third = settled(native, [AIMessage(id="pa5", content="第三輪回覆")], text="第三輪原話")
    processed = windows.capture_window(document, first_run_id=first_run, last_run_id=second_run)
    ahead = windows.capture_window(document, first_run_id=third.record.run_id,
                                   last_run_id=third.record.run_id)
    windows.follows(ahead, processed, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.follows(processed, processed, document)
    skipping = windows.capture_window(document, first_run_id=first_run,
                                      last_run_id=third.record.run_id)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.follows(skipping, processed, document)


def test_the_memory_reader_grants_window_and_context_separately(issued, native):
    sources, document, _, source_ref, window = issued
    context = sources._codec._issue_context(_ContextPosition(format_version=2, purpose="context",
        dataset_id=sources.dataset_id, document_id=document,
        root_checkpoint_id="r1", root_run_id=str(uuid4()), first="m1", last="m2",
        source_first="m1", source_last="m3"))
    publication_only = MemorySourceReader(sources, document, window_references=True)
    extraction = MemorySourceReader(sources, document, window_references=True,
                                    context_references=True)
    publication_only.validate_reference(window)
    with pytest.raises(InvalidSourceReference):
        publication_only.validate_reference(context)
    extraction.validate_reference(context)


def test_a_broken_ancestor_chain_is_reported_not_read_as_no_earlier_turns(interview, native):
    graph, dataset, document, pending, _, _ = native
    windows, _, first_run, second_run = interview
    assert len(windows.safe_turns(document)) == 2
    record, human = new_run_record(dataset, document, str(uuid4()), "第三輪原話",
                                   start_revision_id=str(uuid4()))
    put, failed = graph.checkpointer.put, []
    def break_the_chain(conf, checkpoint, metadata, versions):
        if not failed and not conf["configurable"].get("checkpoint_ns") and metadata["source"] == "input":
            failed.append(True)
            raise OSError("synthetic private fault")
        return put(conf, checkpoint, metadata, versions)
    graph.checkpointer.put = break_the_chain
    try:
        with pytest.raises(OSError):
            graph.invoke({"jd_ai_run": record.model_dump(mode="json"), "messages": [human],
                          "jd_ai_bindings": [], "jd_ai_read": None},
                         {"configurable": {"thread_id": document}}, durability="sync")
    finally:
        graph.checkpointer.put = put
    # The limit is surfaced; it never degrades into "there are no earlier turns".
    with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
        windows.safe_turns(document)
    with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
        windows.unprocessed_source(document)


def test_a_cursor_stopping_mid_turn_never_counts_as_processed(interview, native):
    """A legal signature is not a complete boundary.

    Turn two holds a tool message before its final reply. A cursor ending
    there would otherwise move admission past the whole turn and silently drop
    the employee speech that follows it.
    """
    windows, document, first_run, second_run = interview
    position = windows._codec._resolve_window(
        windows.capture_window(document, first_run_id=first_run, last_run_id=second_run), document)
    mid_turn = window_ref(windows, document, first=first_run, last="t1",
                          first_run=first_run, last_run=second_run,
                          root=position.root_checkpoint_id)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.unprocessed_source(document, mid_turn)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.pending_windows(document, mid_turn)


def test_a_cursor_whose_own_root_is_unreachable_is_refused(interview, native):
    """The cursor must be read at its own fixed position, not assumed."""
    windows, document, first_run, second_run = interview
    real = windows._codec._resolve_window(
        windows.capture_window(document, first_run_id=first_run, last_run_id=second_run), document)
    unreachable = window_ref(windows, document, first=real.first, last=real.last,
                             first_run=first_run, last_run=second_run,
                             root="1f000000-0000-0000-0000-000000000000")
    with pytest.raises(ConversationSourceError):
        windows.unprocessed_source(document, unreachable)


def test_a_cursor_from_another_branch_is_not_an_ancestor(interview, native):
    """Identical content on a sibling chain is not the canonical lineage.

    Two updates from the same root produce siblings that hold exactly the same
    messages. Only one is an ancestor of the head, so matching identifiers and
    matching content are both insufficient: the chain has to reach it.
    """
    graph, dataset, document, *_ = native
    windows, _, first_run, second_run = interview
    position = windows._codec._resolve_window(
        windows.capture_window(document, first_run_id=first_run, last_run_id=second_run), document)
    abandoned = graph.update_state(position.root_config(), {"jd_manual_pending": None},
                                   as_node="consultant")
    graph.update_state(position.root_config(), {"jd_manual_pending": None}, as_node="consultant")
    sibling = window_ref(windows, document, first=position.first, last=position.last,
                         first_run=first_run, last_run=second_run,
                         root=abandoned["configurable"]["checkpoint_id"])
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.unprocessed_source(document, sibling)


def test_a_chain_deeper_than_the_lookup_bound_is_reported_not_assumed(interview, native):
    """Beyond the bound nothing is proven, so the limit is surfaced.

    The bound is a lookup limit, never evidence that an earlier turn or its
    speech does not exist.
    """
    graph, dataset, document, *_ = native
    windows, _, first_run, second_run = interview
    assert len(windows.safe_turns(document)) == 2
    for _ in range(MAX_PARENT_LOOKUPS + 4):
        graph.update_state({"configurable": {"thread_id": document}},
                           {"jd_manual_pending": None}, as_node="consultant")
    with pytest.raises(AiCheckpointError, match="^original_run_lookup_required$"):
        windows.safe_turns(document)


def test_a_candidate_window_on_a_sibling_branch_is_never_admitted(interview, native):
    """Readable history is not an admissible input for the next batch.

    Both siblings hold the same messages and the published cursor is a common
    ancestor of each, so proving the cursor against whatever is latest says
    nothing about where the candidate itself is pinned. Admission has to reach
    the candidate's own position on this chain.
    """
    graph, dataset, document, *_ = native
    windows, _, first_run, second_run = interview
    previous = windows.capture_window(document, first_run_id=first_run, last_run_id=first_run)
    parent = windows._codec._resolve_window(windows.capture_window(
        document, first_run_id=second_run, last_run_id=second_run), document).root_config()
    abandoned = graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    candidate = windows.capture_window(document, first_run_id=second_run, last_run_id=second_run)
    position = windows._codec._resolve_window(candidate, document)
    assert position.root_checkpoint_id == abandoned["configurable"]["checkpoint_id"]
    head = graph.update_state(parent, {"jd_manual_pending": None}, as_node="consultant")
    assert not AiRunHistory(windows._checkpoints).ancestor_of(
        document, position.root_checkpoint_id, head)
    windows.read_window(candidate, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        windows.follows(candidate, previous, document)
