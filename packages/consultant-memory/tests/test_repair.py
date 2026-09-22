"""Native six-node C workflow, real staging/SQLite receipts, no model/provider."""
from dataclasses import asdict, replace
from types import SimpleNamespace
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from caliburn_memory.publication import PublicationStore, PublicationUncertain, PublishRequest
from caliburn_memory.repair import RepairState, RepairWorkflow
from caliburn_memory.staging import StagedMemoryValidationError
import caliburn_memory.repair as repair_module
from conftest import ExampleSource


def edit(old="主管", new="處長", path="/memory/knowledge.md"):
    content = "例外由{}核准。" if path.endswith("knowledge.md") else "{}核准：/memory/knowledge.md"
    return {"path": path, "diff": f"@@\n-{content.format(old)}\n+{content.format(new)}"}


@pytest.fixture
def fixture():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    publication = PublicationStore(engine, artifacts)
    publication.setup()
    memory = artifacts.save_memory(knowledge="例外由主管核准。", guide="主管核准：/memory/knowledge.md")
    head = publication.publish(publication.prepare(memory, expected_revision=0, kind="consolidation",
        processed_source=source.reference))
    yield SimpleNamespace(source=source, artifacts=artifacts, pub=publication, head=head)
    engine.dispose()


def payload(fixture, edits=None, **changes):
    return {"operation_id": str(uuid4()), "base": asdict(fixture.head),
            "source_reference": fixture.source.context_reference,
            "edits": edits if edits is not None else [edit()], **changes}


def parent(workflow, *, saver=None):
    builder = StateGraph(RepairState)
    builder.add_node("repair", workflow.graph)
    builder.add_edge(START, "repair")
    builder.add_edge("repair", END)
    return builder.compile(checkpointer=saver or InMemorySaver())


def config():
    return {"configurable": {"thread_id": "document-a"}}


def saved_request(result):
    data = dict(result["request"])
    data["memory"] = MemoryVersion(**data["memory"])
    data["repair_sources"] = tuple(data["repair_sources"])
    return PublishRequest(**data)


@pytest.mark.parametrize("error", [ValueError("SOURCE_IO"), ValueError("STORE_IO"), RuntimeError("STORE_IO")])
def test_unknown_validation_failure_propagates_instead_of_invalid_edit(fixture, monkeypatch, error):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    def fail(_artifacts): raise error
    monkeypatch.setattr(repair_module, "staged_texts", fail)
    with pytest.raises(type(error)) as raised:
        workflow._validate({})
    assert raised.value is error
    assert fixture.pub.current() == fixture.head


def test_known_staged_validation_is_feedback_without_publication(fixture, monkeypatch):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    def invalid(_artifacts): raise StagedMemoryValidationError("guide needs readable detail")
    monkeypatch.setattr(repair_module, "staged_texts", invalid)
    result = workflow._validate({})
    assert result["outcome"]["status"] == "invalid_edit"
    assert result["outcome"]["detail"] == "guide needs readable detail"
    assert fixture.pub.current() == fixture.head


def test_six_native_nodes_publish_one_receipt_and_leave_background_cursor(fixture):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    assert set(workflow.graph.nodes) == {"__start__", "seed", "edit", "validate", "save", "prepare", "publish"}
    original = payload(fixture, [edit(), edit(path="/memory/guide.md")])
    result = parent(workflow).invoke(original, config(), durability="sync")
    assert result["outcome"]["status"] == "applied"
    current = fixture.pub.current()
    assert current.revision == 2 and current.processed_source == fixture.head.processed_source
    assert current.processed_source != original["source_reference"]
    assert fixture.artifacts.read_text("/memory/knowledge.md", current.memory) == "例外由處長核准。"
    assert fixture.artifacts.guide(current.memory) == "處長核准：/memory/knowledge.md"
    receipt = fixture.pub.receipt(original["operation_id"])
    assert receipt.result == current and receipt.kind == "repair"
    assert receipt.repair_sources == (original["source_reference"],)
    assert result["outcome"]["changes"] == original["edits"]
    assert result["outcome"]["applied_head"] == result["outcome"]["head"] == asdict(current)


@pytest.mark.parametrize("edits", [[], [edit()] * 9,
    [{"path": "/memory/knowledge.md", "old_text": "主管", "new_text": "處長"}],
    [{"path": "/interviews/other/summary.md", "diff": "@@\n-A\n+B"}],
    [{"path": "/memory/knowledge.md", "diff": " "}],
    [{"path": "/memory/knowledge.md", "diff": "a" * 12001}]])
def test_invalid_edit_admission_never_reads_source_or_publishes(fixture, edits):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    fixture.source.reads.clear()
    original = payload(fixture, edits)
    result = parent(workflow).invoke(original, config(), durability="sync")
    assert result["outcome"]["status"] == "invalid_edit"
    assert fixture.source.reads == [] and fixture.pub.current() == fixture.head
    assert fixture.pub.receipt(original["operation_id"]) is None


def test_second_bad_patch_does_not_publish_the_successful_first_patch(fixture):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    original = payload(fixture, [edit(), {"path": "/memory/guide.md", "diff": "@@\n-不存在\n+錯改"}])
    result = parent(workflow).invoke(original, config(), durability="sync")
    assert result["index"] == 1 and result["outcome"]["status"] == "invalid_edit"
    assert fixture.pub.current() == fixture.head
    assert fixture.artifacts.read_text("/memory/knowledge.md", fixture.head.memory) == "例外由主管核准。"
    assert fixture.pub.receipt(original["operation_id"]) is None


def test_stale_head_is_read_back_without_reapplying_candidate(fixture):
    version = fixture.artifacts.save_memory(knowledge="後來有效補充", guide="後來導覽")
    later = fixture.pub.publish(fixture.pub.prepare(version, expected_revision=1, kind="repair"))
    fixture.source.reads.clear()
    result = parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(payload(fixture), config())
    assert result["outcome"]["status"] == "stale" and result["outcome"]["head"] == asdict(later)
    assert fixture.source.reads == [] and fixture.pub.current() == later


def test_missing_turn_start_memory_refreshes_when_background_has_initialized(fixture):
    result = parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(
        payload(fixture, base={}), config())
    assert result["outcome"]["status"] == "stale"
    assert result["outcome"]["head"] == asdict(fixture.head)
    assert fixture.pub.current() == fixture.head


def test_missing_turn_start_and_current_memory_stays_no_memory(fixture, monkeypatch):
    monkeypatch.setattr(fixture.pub, "current", lambda: None)
    result = parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(
        payload(fixture, base={}), config())
    assert result["outcome"]["status"] == "no_memory"
    assert result["outcome"]["head"] is None and result["outcome"]["guide"] == ""


def test_source_port_read_can_return_an_opaque_object(fixture, monkeypatch):
    opaque = object()
    monkeypatch.setattr(fixture.source, "read", lambda reference: opaque)
    result = parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(payload(fixture), config())
    assert result["outcome"]["status"] == "applied"


def test_source_failure_aborts_before_any_staged_edit(fixture, monkeypatch):
    def fail(reference): raise ValueError("SOURCE_IO")
    monkeypatch.setattr(fixture.source, "read", fail)
    original = payload(fixture)
    with pytest.raises(ValueError) as raised:
        parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(original, config())
    assert str(raised.value) == "SOURCE_IO"
    assert fixture.pub.current() == fixture.head and fixture.pub.receipt(original["operation_id"]) is None


def test_source_io_during_real_staged_reference_validation_stops_c(fixture, monkeypatch):
    original_read = fixture.source.read
    attempts = []
    def fail_during_validation(reference):
        attempts.append(reference)
        if len(attempts) > 1:
            raise ValueError("SOURCE_IO_VALIDATING_LINK")
        return original_read(reference)
    monkeypatch.setattr(fixture.source, "read", fail_during_validation)
    linked = edit()
    linked["diff"] += f" [原話]({fixture.source.context_reference})"
    original = payload(fixture, [linked])
    with pytest.raises(ValueError):
        parent(RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)).invoke(original, config())
    assert len(attempts) == 2
    assert fixture.pub.current() == fixture.head and fixture.pub.receipt(original["operation_id"]) is None


def test_checkpoint_between_edits_resumes_staging_without_repeating_first(fixture, monkeypatch):
    class PausedRepair(RepairWorkflow):
        def _edit(self, state):
            if state["index"] == 1:
                interrupt("before_second_edit")
            return super()._edit(state)
    applied = []
    apply = repair_module.apply_staged_patch
    def counted(path, diff):
        applied.append(path)
        return apply(path, diff)
    monkeypatch.setattr(repair_module, "apply_staged_patch", counted)
    saver = InMemorySaver()
    original = payload(fixture, [edit(), edit(path="/memory/guide.md")])
    graph = parent(PausedRepair(fixture.artifacts, fixture.pub, fixture.source), saver=saver)
    graph.invoke(original, config(), durability="sync")
    snapshot = graph.get_state(config(), subgraphs=True)
    child = snapshot.tasks[0].state
    assert child.values["index"] == 1 and child.next == ("edit",)
    assert fixture.pub.current() == fixture.head and applied == ["/memory/knowledge.md"]
    reopened = parent(PausedRepair(fixture.artifacts, fixture.pub, fixture.source), saver=saver)
    result = reopened.invoke(Command(resume=True), config(), durability="sync")
    assert result["outcome"]["status"] == "applied"
    assert applied == ["/memory/knowledge.md", "/memory/guide.md"]
    assert fixture.pub.receipt(original["operation_id"]).result.revision == 2


def test_reconcile_historical_receipt_never_regresses_current_or_publishes(fixture, monkeypatch):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    original = payload(fixture)
    result = parent(workflow).invoke(original, config())
    applied = result["outcome"]["applied_head"]
    version = fixture.artifacts.save_memory(knowledge="後續有效工作", guide="新導覽")
    later = fixture.pub.publish(fixture.pub.prepare(version, expected_revision=2, kind="repair"))
    def forbidden(*args, **kwargs): pytest.fail("Reconcile must never publish")
    monkeypatch.setattr(fixture.pub, "publish", forbidden)
    request = saved_request(result)
    recovered = workflow.reconcile(request)
    assert recovered["applied_head"] == applied
    assert recovered["head"] == applied
    assert recovered["guide"] == fixture.artifacts.guide(MemoryVersion(**applied["memory"]))
    assert "changes" not in recovered and recovered["source_reference"] == original["source_reference"]
    assert fixture.pub.current() == later
    with pytest.raises(PublicationUncertain):
        workflow.reconcile(replace(request, operation_id=str(uuid4())))
    with pytest.raises(PublicationUncertain):
        workflow.reconcile(replace(request, repair_sources=(fixture.source.reference,)))


def test_reconcile_no_longer_accepts_or_echoes_unverified_caller_edits(fixture):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    original = payload(fixture)
    parent(workflow).invoke(original, config())
    with pytest.raises(TypeError):
        workflow.reconcile(original["operation_id"], original["source_reference"],
            [edit("主管", "捏造的另一項工作")])


@pytest.mark.parametrize("changed", ["digest", "document", "kind", "source", "base"])
def test_reconcile_rejects_mismatching_saved_request_without_source_read_or_publish(fixture, monkeypatch, changed):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    result = parent(workflow).invoke(payload(fixture), config())
    request = saved_request(result)
    if changed == "digest": request = replace(request, artifact_digest="0" * 64)
    elif changed == "document": request = replace(request, memory=replace(request.memory, document_id="other-document"))
    elif changed == "kind": request = replace(request, kind="consolidation")
    elif changed == "source": request = replace(request, repair_sources=(fixture.source.reference,))
    else: request = replace(request, expected_revision=9)
    def forbidden(*args, **kwargs): pytest.fail("Reconcile must only read receipt/current/guide")
    monkeypatch.setattr(fixture.source, "read", forbidden)
    monkeypatch.setattr(fixture.pub, "publish", forbidden)
    with pytest.raises(PublicationUncertain):
        workflow.reconcile(request)


def test_reconcile_receipt_read_failure_is_uncertain_and_hides_raw_error(fixture, monkeypatch):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    result = parent(workflow).invoke(payload(fixture), config())
    def failed(*args): raise ValueError("PRIVATE_DATABASE_FAILURE")
    monkeypatch.setattr(fixture.pub, "receipt", failed)
    with pytest.raises(PublicationUncertain) as raised:
        workflow.reconcile(saved_request(result))
    assert "PRIVATE" not in str(raised.value)


def test_lost_publication_reply_uses_saved_native_request_without_retry(fixture, monkeypatch):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    actual_publish = fixture.pub.publish
    attempts = []
    def commit_then_lose_reply(request):
        attempts.append(request.operation_id)
        actual_publish(request)
        raise PublicationUncertain("synthetic_reply_lost")
    monkeypatch.setattr(fixture.pub, "publish", commit_then_lose_reply)
    original = payload(fixture)
    graph = parent(workflow)
    with pytest.raises(PublicationUncertain):
        graph.invoke(original, config(), durability="sync")
    root = graph.get_state(config(), subgraphs=True)
    child = root.tasks[0].state
    assert child.next == ("publish",) and "request" in child.values
    request = saved_request(child.values)
    assert request.operation_id == original["operation_id"]
    recovered = workflow.reconcile(request)
    assert recovered["status"] == "applied" and recovered["applied_head"]["revision"] == 2
    assert attempts == [original["operation_id"]] and fixture.pub.current().revision == 2
    # Reading a receipt does not silently resume or erase the native pending node.
    assert graph.get_state(config(), subgraphs=True).tasks[0].state.next == ("publish",)


@pytest.mark.parametrize("current", ["none", "older", "other-document"])
def test_publish_does_not_claim_applied_with_unconfirmed_current_head(fixture, monkeypatch, current):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    result = parent(workflow).invoke(payload(fixture), config())
    applied = fixture.pub.current()
    observed = None if current == "none" else fixture.head if current == "older" else replace(
        applied, memory=replace(applied.memory, document_id="other-document"))
    monkeypatch.setattr(fixture.pub, "current", lambda: observed)
    with pytest.raises(PublicationUncertain):
        workflow._publish(result)


def test_publish_replayed_receipt_keeps_the_applied_turn_baseline(fixture):
    workflow = RepairWorkflow(fixture.artifacts, fixture.pub, fixture.source)
    original = payload(fixture)
    result = parent(workflow).invoke(original, config())
    applied = result["outcome"]["applied_head"]
    version = fixture.artifacts.save_memory(knowledge="後續有效工作", guide="新版導覽")
    later = fixture.pub.publish(fixture.pub.prepare(version, expected_revision=2, kind="consolidation",
        processed_source=fixture.source.context_reference))
    replayed = workflow._publish(result)["outcome"]
    assert replayed["status"] == "applied" and replayed["applied_head"] == applied
    assert replayed["head"] == applied
    assert replayed["guide"] == fixture.artifacts.guide(MemoryVersion(**applied["memory"]))
    assert fixture.pub.current() == later


def test_components_must_share_document(fixture):
    source = ExampleSource("other-document")
    with pytest.raises(ValueError, match="different documents"):
        RepairWorkflow(fixture.artifacts, fixture.pub, source)
