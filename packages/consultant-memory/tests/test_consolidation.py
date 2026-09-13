"""B2 admission, budgets and publication identity, with no model loop.

The consolidation attempt itself is an agent loop over a real provider
binding, so it is covered where that binding lives: in the App. What this file
pins down is everything B2 decides around that loop -- which B1 output it may
take at all, what it refuses to load rather than shorten, how its operation
identity is derived from the exact artifacts, and how an already published
result is read back instead of being produced a second time.

Real Store, real artifacts, real publication on SQLite; zero provider.
"""
from dataclasses import replace

import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from caliburn_memory import MemoryArtifacts, PublicationStore
from caliburn_memory.consolidation import ConsolidationWorkflow
from caliburn_memory.extraction import ExtractionWorkflow
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from test_extraction import FakeStructured, WindowSource, accepted, outcome


class NoModel:
    """Every path in this file must decide before a model is ever needed."""

    def model_copy(self, **_):
        raise AssertionError("B2 reached the model in a path that must not need one")


@pytest.fixture
def b2():
    source = WindowSource()
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, source.document_id, source=source)
    saver = InMemorySaver()
    first = source.plan(source.window("alpha", "第一批原話"), [
        {"source_reference": source.window("alphaone", "第一批原話"), "context_reference": None}])
    second = source.plan(source.window("beta", "第二批原話"), [
        {"source_reference": source.window("betaone", "第二批原話"), "context_reference": None}])
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False},
                              poolclass=StaticPool)
    try:
        publication = PublicationStore(engine, artifacts)
        publication.setup()

        def extract(reference, *outcomes):
            b1 = ExtractionWorkflow(source, artifacts, FakeStructured(*outcomes), accepted, saver)
            return b1, b1.start(reference)

        def consolidate(b1, **options):
            return ConsolidationWorkflow(b1, publication, NoModel(), InMemorySaver(), **options)

        yield source, artifacts, publication, extract, consolidate, first, second
    finally:
        engine.dispose()


def published(publication, artifacts, *, revision, source_reference):
    version = artifacts.save_memory(knowledge="已發布的工作理解。", guide="工作理解")
    return publication.publish(publication.prepare(version, expected_revision=revision,
        kind="consolidation", processed_source=source_reference))


def test_consolidation_refuses_b1_output_that_is_not_complete(b2):
    """Handing over half a batch would consolidate detail nobody finished."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    untouched = ExtractionWorkflow(source, artifacts, FakeStructured(), accepted, InMemorySaver())
    with pytest.raises(ValueError, match="B1 must have completed"):
        consolidate(untouched).start()
    refused = ExtractionWorkflow(source, artifacts,
                                 FakeStructured(outcome(status="incomplete")), accepted, InMemorySaver())
    with pytest.raises(ValueError, match="Extraction refused, incomplete or invalid"):
        refused.start(first)
    with pytest.raises(ValueError, match="B1 must have completed"):
        consolidate(refused).start()


def test_an_already_published_batch_is_read_back_rather_than_consolidated_again(b2):
    """Same artifacts, same intent: the recorded result answers, not the model."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    b1, extracted = extract(first)
    workflow = consolidate(b1)
    operation = workflow._operation_id({"source_reference": extracted["source_reference"],
                                        "files": extracted["files"], "replaces_summary": None})
    version = artifacts.save_memory(knowledge="第一批的工作理解。", guide="工作理解")
    request = replace(publication.prepare(version, expected_revision=0, kind="consolidation",
        processed_source=extracted["source_reference"]), operation_id=operation)
    head = publication.publish(request)
    assert workflow.start()["result"]["revision"] == head.revision


def test_a_head_already_covering_this_source_reports_it_without_a_new_attempt(b2):
    """A cursor that already names this range is done, not a reason to redo it."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    b1, extracted = extract(first)
    head = published(publication, artifacts, revision=0,
                     source_reference=extracted["source_reference"])
    assert consolidate(b1).start()["result"]["revision"] == head.revision


def test_a_batch_that_is_not_after_the_published_cursor_is_refused(b2):
    """Admission order is the source owner's rule, and B2 asks it every load."""
    source, artifacts, publication, extract, consolidate, first, second = b2
    published(publication, artifacts, revision=0, source_reference=second)
    b1, _ = extract(first)
    with pytest.raises(ValueError, match="not after the previously extracted range"):
        consolidate(b1).start()


def test_oversize_candidates_fail_before_a_job_is_reserved(b2):
    """Too much material is a smaller batch, never a shortened one."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    b1, _ = extract(first, outcome(candidates="候" * 400))
    with pytest.raises(ValueError, match="Candidate input limit exceeded"):
        consolidate(b1, max_candidate_chars=100).start()
    assert publication.current() is None


def test_an_exhausted_budget_refuses_a_new_attempt_instead_of_resetting(b2):
    """A used-up job stops; reopening it never buys a fresh allowance."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    b1, extracted = extract(first)
    workflow = consolidate(b1)
    with pytest.raises(ValueError, match="Consolidation job limit reached"):
        workflow._load({"source_reference": extracted["source_reference"], "files": extracted["files"],
                        "replaces_summary": None, "attempt": 1, "base_revision": 0,
                        "used_model_steps": workflow.max_model_steps, "used_tool_calls": 0})


def test_the_operation_identity_is_the_exact_artifacts_not_the_source_alone(b2):
    """Two batches of the same range are two jobs; one receipt cannot answer both."""
    source, artifacts, publication, extract, consolidate, first, _ = b2
    b1, extracted = extract(first)
    workflow = consolidate(b1)
    state = {"source_reference": extracted["source_reference"], "files": extracted["files"],
             "replaces_summary": None}
    assert workflow._operation_id(state) == workflow._operation_id(dict(state))
    regenerated = {**state, "files": [{**extracted["files"][0], "summary_path": "/interviews/other/summary.md"}]}
    assert workflow._operation_id(regenerated) != workflow._operation_id(state)
    assert workflow._operation_id({**state, "replaces_summary": "/interviews/x/summary.md"}) \
        != workflow._operation_id(state)
