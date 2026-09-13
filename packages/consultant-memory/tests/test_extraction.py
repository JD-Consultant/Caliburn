"""B1 core: completed window -> three fields -> durable artifacts, zero provider.

The graph, prompt, output contract, correction allowance and resume rules are
adopted from the verified workflow. What is a double here is only the provider
call and the source owner: the structured runnable returns the same
`{raw, parsed, parsing_error}` LangChain contract, and artifacts use the real
Store backend. No publication, scheduler, consolidation or JD tool is involved.
"""
import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from caliburn_memory import MemoryArtifacts
from caliburn_memory.extraction import INSTRUCTIONS, ExtractionOutput, ExtractionWorkflow

from conftest import ExampleSource


class WindowSource(ExampleSource):
    """Source owner double: fixed plans, paged reads, admission by given order."""

    def __init__(self, document_id="document-a"):
        super().__init__(document_id)
        self.plans = {}
        self.pages = {}
        self.order = []
        self.saved_windows = []
        self.planned = []
        self.pairs = set()

    def window(self, name, text, *, turns=None):
        reference = f"conversation:{self.document_id}:{name}"
        self.material[reference] = text
        self.pages[reference] = {"text": text, "turns": turns if turns is not None else
                                 [{"input_id": name, "status": "completed", "answer_succeeded": True}]}
        self.order.append(reference)
        return reference

    def plan(self, reference, windows):
        self.plans[reference] = windows
        self.pairs.update((window["source_reference"], window["context_reference"])
                          for window in windows if window["context_reference"])
        return reference

    def validate_pair(self, source_reference, context_reference):
        """Model the owner: only a pair this planner issued together."""
        self.validate_reference(source_reference)
        self.validate_reference(context_reference)
        if (source_reference, context_reference) not in self.pairs:
            raise ValueError("Context was not planned for this source")

    def extraction_windows(self, reference, *, max_chars, context_chars):
        self.validate_reference(reference)
        self.planned.append((reference, max_chars, context_chars))
        return [dict(window) for window in self.plans[reference]]

    def read(self, reference, offset=0):
        self.validate_reference(reference)
        self.reads.append((reference, offset))
        if self.unavailable or reference not in self.pages:
            raise ValueError("Source unavailable")
        page = self.pages[reference]
        text, limit = page["text"], 12
        fragment = text[offset:offset + limit]
        end = offset + len(fragment)
        return {"reference": reference,
                "segments": [{"message_id": reference, "role": "user", "text": fragment,
                              "text_offset": 0}] if fragment else [],
                "turns": page["turns"], "omitted_content_types": ["thinking"],
                "next_offset": end if end < len(text) else None}

    def validate_saved_window(self, source_reference, context_reference, *, max_chars, context_chars):
        self.saved_windows.append((source_reference, context_reference, max_chars, context_chars))
        self.validate_reference(source_reference)
        if context_reference is not None:
            self.validate_reference(context_reference)

    def require_new_source_after(self, reference, previous):
        self.validate_reference(reference)
        self.validate_reference(previous)
        if self.order.index(reference) <= self.order.index(previous):
            raise ValueError("Source is not after the previously extracted range")


def outcome(summary="甲案：單次付款。\n乙案：月租與權限分級。", candidates="兩案計費與權限條件不同。",
            slug="案例", *, status="completed"):
    raw = AIMessage(summary, id="raw-1", response_metadata={"status": status})
    return {"raw": raw, "parsed": {"rollout_summary": summary, "raw_memory": candidates,
                                   "rollout_slug": slug}, "parsing_error": None}


class FakeStructured:
    """Returns the queued outcomes; a queued exception raises where B1 calls."""

    def __init__(self, *outcomes):
        self.queue = list(outcomes)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        item = self.queue.pop(0) if self.queue else outcome()
        if isinstance(item, Exception):
            raise item
        return item


def accepted(raw):
    """Provider terminal/refusal evidence port; the App owns the real one."""
    return raw.response_metadata.get("status") == "completed"


@pytest.fixture
def harness():
    source = WindowSource()
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, source.document_id, source=source)
    saver = InMemorySaver()

    def build(structured, **options):
        return ExtractionWorkflow(source, artifacts, structured, accepted, saver, **options)

    return source, artifacts, build


def single(source):
    first = source.window("first", "甲案原話，單次付款。")
    context = source.window("context", "前一個問題。")
    return source.plan(first, [{"source_reference": first, "context_reference": context}])


def test_three_fields_become_artifacts_without_publication(harness):
    source, artifacts, build = harness
    reference = single(source)
    structured = FakeStructured()
    result = build(structured).start(reference)
    assert len(structured.calls) == 1 and len(result["files"]) == 1
    summary_path = result["files"][0]["summary_path"]
    assert artifacts.read_text(summary_path).endswith("甲案：單次付款。\n乙案：月租與權限分級。")
    assert artifacts.source_window(summary_path) == {
        "source_reference": reference, "context_reference": source.reference.replace("original", "context")}


def test_the_prompt_carries_both_ranges_separately(harness):
    source, _, build = harness
    reference = single(source)
    structured = FakeStructured()
    build(structured).start(reference)
    system, human = structured.calls[0]
    assert system.content == INSTRUCTIONS
    assert '"CONTEXT_ONLY"' in human.content and '"NEW_SOURCE"' in human.content
    assert "前一個問題。" in human.content and "甲案原話，單次付款。" in human.content


def test_every_planned_window_is_extracted_once(harness):
    source, _, build = harness
    first = source.window("first", "甲案原話。")
    second = source.window("second", "乙案原話。")
    reference = source.plan(first, [{"source_reference": first, "context_reference": None},
                                    {"source_reference": second, "context_reference": first}])
    structured = FakeStructured()
    result = build(structured).start(reference)
    assert len(structured.calls) == 2 and len(result["files"]) == 2
    assert [file["source_reference"] for file in result["files"]] == [first, second]


def test_a_later_failure_resumes_without_repeating_the_first_window(harness):
    source, _, build = harness
    first = source.window("first", "甲案原話。")
    second = source.window("second", "乙案原話。")
    reference = source.plan(first, [{"source_reference": first, "context_reference": None},
                                    {"source_reference": second, "context_reference": None}])
    structured = FakeStructured(outcome(), RuntimeError("synthetic transport fault"))
    workflow = build(structured)
    with pytest.raises(RuntimeError):
        workflow.start(reference)
    resumed = workflow.resume()
    assert len(structured.calls) == 3 and len(resumed["files"]) == 2


def test_an_invalid_source_stops_before_any_model_call(harness):
    source, _, build = harness
    structured = FakeStructured()
    with pytest.raises(ValueError):
        build(structured).start("conversation:other-document:first")
    assert structured.calls == []


def test_too_many_windows_is_bounded_before_any_model_call(harness):
    source, _, build = harness
    first = source.window("first", "甲案原話。")
    reference = source.plan(first, [{"source_reference": first, "context_reference": None}] * 3)
    structured = FakeStructured()
    with pytest.raises(ValueError):
        build(structured, max_windows=2).start(reference)
    assert structured.calls == []


def test_empty_candidates_is_a_saved_success(harness):
    source, artifacts, build = harness
    reference = single(source)
    structured = FakeStructured(outcome(candidates=""))
    result = build(structured).start(reference)
    candidates_path = result["files"][0]["candidates_path"]
    assert artifacts.read_text(candidates_path).endswith("End source metadata.\n\n")


def test_a_refused_or_incomplete_outcome_never_becomes_an_empty_success(harness):
    source, _, build = harness
    reference = single(source)
    structured = FakeStructured(outcome(status="incomplete"))
    with pytest.raises(ValueError, match="^Extraction refused, incomplete or invalid"):
        build(structured).start(reference)


def test_a_parsing_error_never_becomes_an_empty_success(harness):
    source, _, build = harness
    reference = single(source)
    broken = outcome()
    broken["parsing_error"] = ValueError("synthetic parse failure")
    with pytest.raises(ValueError, match="^Extraction refused, incomplete or invalid"):
        build(FakeStructured(broken)).start(reference)


def test_a_shape_the_native_contract_forbids_never_becomes_an_empty_success(harness):
    source, _, build = harness
    reference = single(source)
    broken = outcome()
    broken["parsed"] = {"rollout_summary": "只有一個欄位"}
    with pytest.raises(ValueError, match="^Extraction refused, incomplete or invalid"):
        build(FakeStructured(broken)).start(reference)


def test_an_unreadable_artifact_format_is_corrected_once_then_persisted(harness):
    source, artifacts, build = harness
    reference = single(source)
    structured = FakeStructured(outcome(summary="甲" * 2100), outcome(summary="甲案：單次付款。"))
    result = build(structured).start(reference)
    assert len(structured.calls) == 2
    assert artifacts.read_text(result["files"][0]["summary_path"]).endswith("甲案：單次付款。")
    feedback = structured.calls[1][-1]
    assert "Runtime validation feedback (not employee speech): rollout_summary" in feedback.content


def test_an_exhausted_correction_allowance_fails_instead_of_saving(harness):
    source, _, build = harness
    reference = single(source)
    structured = FakeStructured(outcome(summary="甲" * 2100))
    with pytest.raises(ValueError, match="^Extraction correction allowance exhausted"):
        build(structured, max_validation_corrections=0).start(reference)


def test_an_older_or_overlapping_source_is_rejected_without_reextracting(harness):
    source, _, build = harness
    first = source.window("first", "甲案原話。")
    second = source.window("second", "乙案原話。")
    earlier = source.plan(first, [{"source_reference": first, "context_reference": None}])
    later = source.plan(second, [{"source_reference": second, "context_reference": None}])
    structured = FakeStructured()
    workflow = build(structured)
    workflow.start(later)
    with pytest.raises(ValueError, match="not after"):
        workflow.start(earlier)
    assert len(structured.calls) == 1


def test_repeating_the_same_source_returns_the_saved_job_without_calling_the_model(harness):
    source, _, build = harness
    reference = single(source)
    structured = FakeStructured()
    workflow = build(structured)
    first = workflow.start(reference)
    assert workflow.start(reference) == first and len(structured.calls) == 1


def test_reextraction_reads_the_saved_window_and_leaves_normal_state(harness):
    source, _, build = harness
    reference = single(source)
    structured = FakeStructured()
    workflow = build(structured)
    saved = workflow.start(reference)["files"][0]["summary_path"]
    before = workflow.graph.get_state(workflow.config).values["source_reference"]
    again = workflow.reextract(saved)
    assert len(structured.calls) == 2
    assert source.saved_windows[-1][:2] == (reference, source.reference.replace("original", "context"))
    assert again["replaces_summary"] == saved and again["files"][0]["summary_path"] != saved
    assert workflow.graph.get_state(workflow.config).values["source_reference"] == before


def test_a_context_planned_for_another_window_is_never_saved(harness):
    """The artifact may only record the pair the planner issued together."""
    source, artifacts, build = harness
    first = source.window("first", "75326848539f8a713002")
    second = source.window("second", "4e596848539f8a713002")
    other = source.window("other", "4e196848539f8a713002")
    source.plan(first, [{"source_reference": first, "context_reference": other}])
    with pytest.raises(ValueError, match="not planned for this source"):
        artifacts.save_extraction(summary="8a738a18", candidates="50199078", slug="4ea453c9",
                                  source_reference=second, context_reference=other)


def test_the_three_output_fields_are_the_adopted_contract():
    assert list(ExtractionOutput.model_fields) == ["rollout_summary", "raw_memory", "rollout_slug"]
    assert "NEW_SOURCE" in INSTRUCTIONS and "CONTEXT_ONLY" in INSTRUCTIONS
