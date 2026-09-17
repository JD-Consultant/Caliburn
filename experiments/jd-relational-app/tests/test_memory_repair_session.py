"""Actual native tool handoff and C staging; synthetic SQLite, no provider."""
from dataclasses import replace
import json
from types import SimpleNamespace
from threading import Event
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from caliburn_memory import CaseArtifact, PublicationStore, WorkUnderstandingArtifact

from jd_relational.ai_checkpoints import AiRunCheckpoints, new_run_record
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError, _pending_calls
from jd_relational.consultant_context import ConsultantState
from jd_relational.consultant_tools import BINDING_NODE, AiToolError, AiToolMiddleware, AiToolSession
from jd_relational.memory_context import build_consultant_tools
from jd_relational.memory_repair_session import MemoryRepairSession, repair_progress
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import build_document_graph
from test_chat_history import native
from test_consultant_memory_context import memory
from test_consultant_context import FixedModel


def call(number, old="只做初步確認。", new="維修由外包負責。", *, args=None):
    return AIMessage(id=f"repair-{number}", content="", tool_calls=[{
        "name": "repair_memory", "id": f"repair-call-{number}", "args": args if args is not None else {
        "edits": [{"path": "/memory/knowledge.md", "diff": f"@@\n-{old}\n+{new}"}]}}])


def setup_repair(memory, replies, *, layered=False):
    store, pub, publish, pin = memory
    if layered:
        _, _, _, source = publish.bundle(0)
    else:
        publish(0, "只做初步確認。")
        source = pub.current().processed_source
    selected = pin()
    repair = MemoryRepairSession(selected, pub)
    stop = Event()
    permit = SimpleNamespace(identity=SimpleNamespace(document_id=selected.document_id,
        run_id=selected.run_id, request_digest="a" * 64), stop_event=stop)
    tool_session = AiToolSession(
        SimpleNamespace(execute_foreground=lambda *_: pytest.fail("unexpected JD write")),
        permit,
        SimpleNamespace(read_revision=lambda *_: pytest.fail("unexpected JD history read")),
        SimpleNamespace(read=lambda *_: pytest.fail("unexpected JD read")),
        SimpleNamespace(read=lambda *_: pytest.fail("unexpected JD change read")),
        ReferenceCodec(b"s" * 32, selected.dataset_id),
    )
    context = SimpleNamespace(dataset_id=selected.dataset_id, document_id=selected.document_id,
        run_id=selected.run_id, memory_session=selected, memory_repair_session=repair,
        tool_session=tool_session, stop_event=stop,
        source_notice=lambda messages: {"source_ref": source})
    model = FixedModel(replies=replies(selected, source) if callable(replies) else replies)
    child = create_agent(model, tools=build_consultant_tools(), middleware=[AiToolMiddleware()],
        state_schema=ConsultantState)
    root = build_document_graph(child, InMemorySaver(), store=store)
    payload = {"messages": [HumanMessage(id=selected.run_id, content="更正：維修由外包負責。")],
        "jd_memory_view": selected.view, "jd_ai_bindings": [], "jd_ai_read": None,
        "jd_memory_repair_bindings": []}
    config = {"configurable": {"thread_id": selected.document_id}, "max_concurrency": 1}
    return root, model, selected, repair, pub, context, payload, config


def layered_replies(initial, source_reference, *, updates=True, include_reads=True):
    manifest = initial.artifacts.bundle_manifest(initial.head.memory)
    case_id = manifest.cases[0].case_id
    understanding_id = manifest.understandings[0].understanding_id
    case = initial.artifacts.case(initial.head.memory, case_id)
    understanding = initial.artifacts.understanding(initial.head.memory, understanding_id)
    messages = []
    if include_reads:
        messages.extend([
            AIMessage(id="layered-case-read", content="", tool_calls=[{
                "name": "read_case", "id": "layered-case-read-call",
                "args": {"case_id": case_id},
            }]),
            AIMessage(id="layered-source-read", content="", tool_calls=[{
                "name": "read_conversation", "id": "layered-source-read-call",
                "args": {"reference": case.source_references[0]},
            }]),
            AIMessage(id="layered-understanding-read", content="", tool_calls=[{
                "name": "read_work_understanding", "id": "layered-understanding-read-call",
                "args": {"understanding_id": understanding_id},
            }]),
        ])
    messages.extend([
        AIMessage(id="layered-repair", content="", tool_calls=[{
            "name": "repair_memory", "id": "layered-repair-call", "args": {
                "case_id": case_id,
                "case_diff": ("@@\n-本人先做設備故障初判。\n"
                              "+本人只通報設備故障，維修由外包負責。"),
                "case_route_note": None,
                "remove_evidence_keys": [],
                "understanding_updates": ([{
                    "understanding_id": understanding_id,
                    "action": "revise",
                    "diff": (f"@@\n-{understanding.content}\n"
                             "+本人穩定負責設備故障通報；維修由外包負責。"),
                    "supporting_case_ids": [case_id],
                    "route_note": None,
                }] if updates else []),
            },
        }]),
        AIMessage(content="已完成明確更正。"),
    ])
    return messages


def test_layered_memory_repair_reads_then_publishes_one_complete_bundle(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, layered_replies, layered=True)
    monkeypatch.setattr(repair.workflow, "_seed", lambda state: pytest.fail("no legacy C for bundle"))

    result = root.invoke(payload, config, context=context, durability="sync")

    tools = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert [message.name for message in tools] == [
        "read_case", "read_conversation", "read_work_understanding", "repair_memory",
    ]
    assert json.loads(tools[-1].content)["status"] == "applied"
    assert "read_paths" not in json.loads(tools[-1].content)
    assert pub.current().revision == initial.head.revision + 1
    current = repair.current_read(result)
    assert current.head == pub.current()
    manifest = current.artifacts.bundle_manifest(current.head.memory)
    case = current.artifacts.case(current.head.memory, manifest.cases[0].case_id)
    understanding = current.artifacts.understanding(
        current.head.memory, manifest.understandings[0].understanding_id,
    )
    assert "維修由外包" in case.content and "維修由外包" in understanding.content
    assert context.source_notice([])["source_ref"] in case.source_references
    assert len(model.requests) == 5


def test_a_new_legacy_two_file_call_cannot_bypass_the_layered_tool_schema(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, [call(1), AIMessage(content="改由分層工具處理。")],
    )
    monkeypatch.setattr(repair.workflow, "_seed",
                        lambda state: pytest.fail("new calls cannot enter legacy C"))

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [message for message in result["messages"]
                if isinstance(message, ToolMessage)]
    content = json.loads(feedback[0].content)
    assert content["status"] == "invalid_edit"
    assert "read_paths" not in content
    assert feedback[0].artifact["format_version"] == 2
    assert pub.current() == initial.head and len(model.requests) == 2


def test_a_valid_layered_call_requires_a_layered_publication(memory, monkeypatch):
    def replies(initial, _source):
        args = {
            "case_id": str(uuid4()),
            "case_diff": "@@\n-舊案例\n+新案例",
            "case_route_note": None,
            "remove_evidence_keys": [],
            "understanding_updates": [],
        }
        return [call(1, args=args), AIMessage(content="尚無可修補的分層 Memory。")]

    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, replies,
    )
    monkeypatch.setattr(repair.workflow, "_seed",
                        lambda state: pytest.fail("new calls cannot enter legacy C"))

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [message for message in result["messages"]
                if isinstance(message, ToolMessage)]
    content = json.loads(feedback[0].content)
    assert content["status"] == "no_memory"
    assert "read_paths" not in content
    assert feedback[0].artifact["format_version"] == 2
    assert pub.current() == initial.head and len(model.requests) == 2


def test_layered_repair_without_saved_exact_reads_returns_read_required(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory,
        lambda selected, source: layered_replies(
            selected, source, include_reads=False,
        ),
        layered=True,
    )
    monkeypatch.setattr(repair.layered_workflow, "_seed",
                        lambda state: pytest.fail("admission must stop before child"))

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [json.loads(message.content) for message in result["messages"]
                if isinstance(message, ToolMessage)]
    assert feedback[0]["status"] == "read_required" and feedback[0]["retryable"] is True
    assert pub.current() == initial.head and len(model.requests) == 2


def test_layered_repair_requires_every_direct_understanding_action(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory,
        lambda selected, source: layered_replies(selected, source, updates=False),
        layered=True,
    )
    monkeypatch.setattr(repair.layered_workflow, "_seed",
                        lambda state: pytest.fail("scope admission must stop before child"))

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [json.loads(message.content) for message in result["messages"]
                if isinstance(message, ToolMessage)]
    assert feedback[-1]["status"] == "scope_too_broad"
    assert feedback[-1]["retryable"] is False
    assert pub.current() == initial.head


def advance_layered_head(repair, head, source_reference):
    artifacts = repair.layered_workflow.artifacts
    manifest = artifacts.bundle_manifest(head.memory)
    version = artifacts.save_bundle(
        base_publication_revision=head.revision,
        base_version=head.memory,
        evidence_through_reference=source_reference,
        case_guide=artifacts.case_guide(head.memory),
        cases=tuple(CaseArtifact(
            item.case_id,
            artifacts.case(head.memory, item.case_id).content,
            artifacts.case(head.memory, item.case_id).source_references,
        ) for item in manifest.cases),
        understanding_guide=artifacts.understanding_guide(head.memory),
        understandings=tuple(WorkUnderstandingArtifact(
            item.understanding_id,
            artifacts.understanding(head.memory, item.understanding_id).content,
            tuple(binding.case_id for binding in artifacts.understanding(
                head.memory, item.understanding_id).case_bindings),
        ) for item in manifest.understandings),
    )
    publication = repair.layered_workflow.publication
    return publication.publish(publication.prepare(
        version, expected_revision=head.revision, kind="repair",
        repair_sources=(source_reference,),
    ))


def test_layered_repair_refreshes_stale_head_before_resolving_old_edits(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory,
        lambda selected, source: layered_replies(
            selected, source, include_reads=False,
        ),
        layered=True,
    )
    latest = advance_layered_head(
        repair, initial.head, context.source_notice([])["source_ref"],
    )
    monkeypatch.setattr(repair.layered_workflow, "_seed",
                        lambda state: pytest.fail("stale input must not enter child"))

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [json.loads(message.content) for message in result["messages"]
                if isinstance(message, ToolMessage)]
    assert feedback[0]["status"] == "stale" and feedback[0]["retryable"] is True
    assert repair.current_read(result).head == latest
    assert pub.current() == latest and len(model.requests) == 2


def test_layered_memory_generic_file_tools_cannot_bypass_typed_reads(memory):
    manifest_call = AIMessage(id="manifest-read", content="", tool_calls=[{
        "name": "read_file", "id": "manifest-read-call",
        "args": {"file_path": "/memory/manifest.json", "offset": 0, "limit": 100},
    }])
    root, model, initial, _, pub, context, payload, config = setup_repair(
        memory, [manifest_call, AIMessage(content="改用分層讀取工具。")], layered=True)

    result = root.invoke(payload, config, context=context, durability="sync")

    feedback = [message.content for message in result["messages"]
                if isinstance(message, ToolMessage)]
    assert len(feedback) == 1
    assert "layered_memory_requires_typed_read" in feedback[0]
    assert "schema_version" not in feedback[0]
    assert pub.current() == initial.head and len(model.requests) == 2


def two_layered_repairs(initial, source_reference):
    first = layered_replies(initial, source_reference)[:-1]
    manifest = initial.artifacts.bundle_manifest(initial.head.memory)
    case_id = manifest.cases[0].case_id
    understanding_id = manifest.understandings[0].understanding_id
    return [*first,
        AIMessage(id="layered-case-read-2", content="", tool_calls=[{
            "name": "read_case", "id": "layered-case-read-call-2",
            "args": {"case_id": case_id},
        }]),
        AIMessage(id="layered-source-read-2", content="", tool_calls=[{
            "name": "read_conversation", "id": "layered-source-read-call-2",
            "args": {"reference": source_reference},
        }]),
        AIMessage(id="layered-understanding-read-2", content="", tool_calls=[{
            "name": "read_work_understanding", "id": "layered-understanding-read-call-2",
            "args": {"understanding_id": understanding_id},
        }]),
        AIMessage(id="layered-repair-2", content="", tool_calls=[{
            "name": "repair_memory", "id": "layered-repair-call-2", "args": {
                "case_id": case_id,
                "case_diff": ("@@\n-本人只通報設備故障，維修由外包負責。\n"
                              "+本人只通報設備異常，維修由外包負責。"),
                "case_route_note": None,
                "remove_evidence_keys": [],
                "understanding_updates": [{
                    "understanding_id": understanding_id,
                    "action": "revise",
                    "diff": ("@@\n-本人穩定負責設備故障通報；維修由外包負責。\n"
                             "+本人穩定負責設備異常通報；維修由外包負責。"),
                    "supporting_case_ids": [case_id],
                    "route_note": None,
                }],
            },
        }]),
        AIMessage(content="已完成兩次明確更正。"),
    ]


def test_two_native_repairs_refresh_only_this_turn_and_keep_staging_off_root(memory):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, two_layered_repairs, layered=True,
    )
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 3 and len(model.requests) == 9
    assert result["jd_memory_view"] == initial.view
    assert not {"files", "request", "material", "version", "outcome"} & result.keys()
    progress = repair_progress(result, dataset_id=initial.dataset_id,
        document_id=initial.document_id, run_id=initial.run_id)
    assert progress.failures == 0 and progress.outcome["head"]["revision"] == 3
    results = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    repair_results = [message for message in results if message.name == "repair_memory"]
    assert len(repair_results) == 2 and all(m.status == "success" for m in repair_results)
    assert repair_results[0].artifact["request"]["expected_revision"] == 1
    assert repair_results[1].artifact["request"]["expected_revision"] == 2
    assert "operation_id" not in json.loads(repair_results[0].content)
    current = repair.current_read(result)
    manifest = current.artifacts.bundle_manifest(current.head.memory)
    loaded = current.artifacts.case(current.head.memory, manifest.cases[0].case_id)
    assert "只通報設備異常" in loaded.content
    new_run = dict(payload, messages=result["messages"], jd_memory_repair_bindings=[])
    assert repair.current_read(new_run) is initial


def test_two_bad_calls_stop_repair_without_entering_core_or_sending_internal_ids(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory,
        [call(1, args={"edits": []}), call(2, args={"edits": []}), call(3), AIMessage(content="先釐清。")])
    monkeypatch.setattr(repair.workflow, "_seed", lambda state: pytest.fail("no C on invalid/limit"))
    result = root.invoke(payload, config, context=context, durability="sync")
    feedback = [json.loads(m.content) for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m["status"] for m in feedback] == ["invalid_edit", "invalid_edit", "repair_limit"]
    assert [m["retryable"] for m in feedback] == [True, False, False]
    assert pub.current().revision == 1


def test_native_memory_read_keeps_applied_repair_when_rebased_background_publishes_later(
        memory, monkeypatch):
    def replies(initial, source_reference):
        values = layered_replies(initial, source_reference)[:-1]
        case_id = initial.artifacts.bundle_manifest(initial.head.memory).cases[0].case_id
        return [*values, AIMessage(id="post-repair-read", content="", tool_calls=[{
            "name": "read_case", "id": "post-repair-read-call",
            "args": {"case_id": case_id},
        }]), AIMessage(content="已核對新版。")]

    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, replies, layered=True,
    )
    publication = repair.layered_workflow.publication
    actual_publish = publication.publish
    later = []

    def publish_then_rebased_background(request):
        applied = actual_publish(request)
        if request.kind == "repair" and not later:
            artifacts = repair.layered_workflow.artifacts
            manifest = artifacts.bundle_manifest(applied.memory)
            version = artifacts.save_bundle(
                base_publication_revision=applied.revision,
                base_version=applied.memory,
                evidence_through_reference=context.source_notice([])["source_ref"],
                case_guide=artifacts.case_guide(applied.memory),
                cases=tuple(CaseArtifact(
                    item.case_id,
                    artifacts.case(applied.memory, item.case_id).content + "背景補充。",
                    artifacts.case(applied.memory, item.case_id).source_references,
                ) for item in manifest.cases),
                understanding_guide=artifacts.understanding_guide(applied.memory),
                understandings=tuple(WorkUnderstandingArtifact(
                    item.understanding_id,
                    artifacts.understanding(applied.memory, item.understanding_id).content,
                    tuple(binding.case_id for binding in artifacts.understanding(
                        applied.memory, item.understanding_id).case_bindings),
                ) for item in manifest.understandings),
            )
            later.append(actual_publish(publication.prepare(
                version, expected_revision=applied.revision, kind="consolidation",
                processed_source=applied.processed_source,
            )))
        return applied

    monkeypatch.setattr(publication, "publish", publish_then_rebased_background)
    result = root.invoke(payload, config, context=context, durability="sync")
    feedback = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in feedback][-2:] == ["repair_memory", "read_case"]
    assert feedback[-2].status == "success" and "維修由外包" in feedback[-1].content
    assert "背景補充" not in feedback[-1].content
    assert result["jd_memory_view"] == initial.view
    assert later and pub.current() == later[0] and pub.current().revision == 3
    assert repair.current_read(result).head.revision == 2


def test_wrong_scope_and_stop_are_checked_before_starting_c(memory):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, layered_replies, layered=True,
    )
    context.stop_event.set()
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 1 and len(model.requests) == 0
    assert not result.get("jd_memory_repair_bindings")


def test_cancel_during_c_drains_started_save_and_stops_next_model_work(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, layered_replies, layered=True,
    )
    original = repair.layered_workflow._prepare
    def prepare(state):
        context.stop_event.set()
        return original(state)
    monkeypatch.setattr(repair.layered_workflow, "_prepare", prepare)
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 2
    assert next(m for m in result["messages"] if isinstance(m, ToolMessage)).status == "success"
    assert len(model.requests) == 4, "A stop raised during C must block the next model request."


def parallel_calls(initial, source_reference):
    """One invalid response that puts a repair call beside another call."""
    message = layered_replies(initial, source_reference)[-2]
    case_id = initial.artifacts.bundle_manifest(initial.head.memory).cases[0].case_id
    message.tool_calls.append({"name": "read_case", "id": "parallel-read-call",
        "args": {"case_id": case_id},
        "type": "tool_call"})
    return message


def stopped(memory, monkeypatch, fault, replies=None):
    """Reproduce one real native stop that precedes C, then observe it.

    `binding` stops inside the App's own binding handler and `parallel_calls`
    stops there through an invalid multi-call response, both before any binding
    exists. `tool_handoff` stops on the consultant's own tool node and
    `child_start` on the fixed child's own START, both after the binding was
    saved. None of them may start the core.
    """
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, replies if replies is not None else layered_replies, layered=True,
    )
    record, human = new_run_record(initial.dataset_id, initial.document_id, initial.run_id,
        "合成停止收尾", start_revision_id=str(uuid4()))
    payload.update(jd_ai_run=record.model_dump(mode="json"), messages=[human])
    monkeypatch.setattr(repair.layered_workflow, "_seed",
        lambda state: pytest.fail("A stop proven before C must never start the core"))
    expected = OSError
    if fault == "parallel_calls":
        # The invalid response itself is the fault: the binding handler refuses
        # it before any C material exists, and never reaches the repair session.
        expected = AiToolError
    elif fault == "binding":
        def unavailable(_messages):
            raise OSError("synthetic source notice failure")
        context.source_notice = unavailable
    elif fault == "tool_handoff":
        # The native tool wrapper converts the injected dependency failure to
        # the App's fixed public error while preserving the tool-node stop.
        expected = AiToolError
        def refuse(self, runtime):
            raise OSError("synthetic tool handoff failure")
        monkeypatch.setattr(MemoryRepairSession, "handoff", refuse)
    else:
        original_put = root.checkpointer.put
        def fail_first_child_loop(cfg, checkpoint, metadata, versions):
            if (metadata["source"] == "loop"
                    and cfg["configurable"].get("checkpoint_ns", "").startswith("memory_repair:")):
                raise OSError("synthetic first child loop save failure")
            return original_put(cfg, checkpoint, metadata, versions)
        monkeypatch.setattr(root.checkpointer, "put", fail_first_child_loop)
    with pytest.raises(expected):
        root.invoke(payload, config, context=context, durability="sync")
    runtime = AiRuntime.__new__(AiRuntime)
    runtime.graph, runtime.memory_engine = root, pub.engine
    runtime.conversation_sources = initial.source.service
    observed = AiRunCheckpoints(root).observe(initial.document_id, initial.run_id, initial.dataset_id)
    expected_requests = 1 if fault == "parallel_calls" else 4
    assert len(model.requests) == expected_requests and pub.current().revision == 1
    return runtime, observed


def recovered(runtime, observed):
    return runtime._recover_pending_repair(observed, observed.messages,
                                           _pending_calls(observed.messages))


def stopped_layered_at_child_start(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, layered_replies, layered=True,
    )
    record, human = new_run_record(initial.dataset_id, initial.document_id, initial.run_id,
        "合成分層停止收尾", start_revision_id=str(uuid4()))
    payload.update(jd_ai_run=record.model_dump(mode="json"), messages=[human])
    original_put = root.checkpointer.put

    def fail_first_child_loop(cfg, checkpoint, metadata, versions):
        if (metadata["source"] == "loop"
                and cfg["configurable"].get("checkpoint_ns", "").startswith("memory_repair:")):
            raise OSError("synthetic layered first child loop save failure")
        return original_put(cfg, checkpoint, metadata, versions)

    monkeypatch.setattr(root.checkpointer, "put", fail_first_child_loop)
    with pytest.raises(OSError):
        root.invoke(payload, config, context=context, durability="sync")
    runtime = AiRuntime.__new__(AiRuntime)
    runtime.graph, runtime.memory_engine = root, pub.engine
    runtime.conversation_sources = initial.source.service
    observed = AiRunCheckpoints(root).observe(
        initial.document_id, initial.run_id, initial.dataset_id,
    )
    assert len(model.requests) == 4 and pub.current() == initial.head
    assert observed.repair_bindings[-1]["format_version"] == 2
    assert observed.repair_checkpoint["next"] == ["__start__"]
    return runtime, observed


def test_layered_child_start_recovery_matches_the_runtime_resolved_repair(memory, monkeypatch):
    runtime, observed = stopped_layered_at_child_start(memory, monkeypatch)

    message = recovered(runtime, observed)

    assert message.status == "error"
    assert json.loads(message.content)["status"] == "not_executed"
    assert message.artifact["format_version"] == 2


def test_layered_child_start_recovery_rejects_a_changed_resolved_repair(memory, monkeypatch):
    runtime, observed = stopped_layered_at_child_start(memory, monkeypatch)
    checkpoint = observed.repair_checkpoint
    checkpoint["input"]["repair"]["case_diff"] += "\n+偷換內容"
    changed = replace(observed, _repair_checkpoint_json=json.dumps(checkpoint))

    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, changed)


@pytest.mark.parametrize("fault", ["binding", "child_start"])
def test_a_stop_proven_before_c_closes_the_same_original_call_as_not_executed(memory, monkeypatch, fault):
    runtime, observed = stopped(memory, monkeypatch, fault)
    message = recovered(runtime, observed)
    content = json.loads(message.content)
    assert message.name == "repair_memory" and message.tool_call_id == "layered-repair-call"
    assert message.status == "error" and message.artifact["request"] is None
    assert content["status"] == "not_executed" and content["retryable"] is False
    if fault == "binding":
        assert observed.consultant_next == [BINDING_NODE] and observed.repair_checkpoint is None
        assert observed.repair_bindings == [] and message.artifact["operation_id"] is None
    else:
        assert observed.consultant_next is None and observed.repair_checkpoint["next"] == ["__start__"]
        assert message.artifact["operation_id"] == observed.repair_bindings[0]["operation_id"]


@pytest.mark.parametrize("step", ["tools", "model", "__start__"])
def test_an_unbound_call_stopped_outside_the_binding_node_keeps_the_gate(memory, monkeypatch, step):
    runtime, observed = stopped(memory, monkeypatch, "binding")
    elsewhere = replace(observed, _consultant_next_json=json.dumps([step]))
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, elsewhere)


@pytest.mark.parametrize("mutation",
    ["operation_id", "base", "source_reference", "repair", "missing_key", "absent"])
def test_a_child_start_input_that_disagrees_with_the_original_call_keeps_the_gate(
        memory, monkeypatch, mutation):
    runtime, observed = stopped(memory, monkeypatch, "child_start")
    checkpoint = observed.repair_checkpoint
    payload = checkpoint["input"]
    if mutation == "operation_id":
        payload["operation_id"] = str(uuid4())
    elif mutation == "base":
        payload["base"] = dict(payload["base"], revision=payload["base"]["revision"] + 1)
    elif mutation == "source_reference":
        payload["source_reference"] = "conversation:synthetic-other-document"
    elif mutation == "repair":
        payload["repair"]["case_diff"] += "\n+偷換內容"
    elif mutation == "missing_key":
        payload.pop("repair")
    else:
        checkpoint["input"] = None
    changed = replace(observed, _repair_checkpoint_json=json.dumps(checkpoint))
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, changed)


def test_a_receipt_at_the_child_start_position_is_never_called_not_executed(memory, monkeypatch):
    runtime, observed = stopped(memory, monkeypatch, "child_start")
    operation = observed.repair_bindings[0]["operation_id"]
    # A START position proves no node ran, but an actual receipt outranks it.
    monkeypatch.setattr(PublicationStore, "receipt",
        lambda self, value: {"operation_id": value} if value == operation else None)
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, observed)


def test_a_stop_on_the_consultants_own_tool_node_is_not_executed_not_merely_unpublished(
        memory, monkeypatch):
    """A bound call whose tool never returned to root never started C.

    The root's pending task is still the consultant subgraph, so the fixed
    `memory_repair` node has not run. Without that position this would rest on
    a missing child checkpoint plus a missing receipt, which proves nothing.
    """
    runtime, observed = stopped(memory, monkeypatch, "tool_handoff")
    assert observed.consultant_next == ["tools"] and observed.repair_checkpoint is None
    assert len(observed.repair_bindings) == 1
    message = recovered(runtime, observed)
    content = json.loads(message.content)
    assert content["status"] == "not_executed" and content["retryable"] is False
    assert message.artifact["operation_id"] == observed.repair_bindings[0]["operation_id"]
    assert message.artifact["request"] is None


def test_an_unknown_stop_without_any_position_evidence_keeps_the_gate(memory, monkeypatch):
    runtime, observed = stopped(memory, monkeypatch, "tool_handoff")
    blind = replace(observed, _consultant_next_json="null")
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, blind)


def test_an_invalid_parallel_response_still_closes_its_repair_call(memory, monkeypatch):
    """A repair call beside another call must not lock the document forever.

    The binding handler refuses the whole response, so nothing was bound and C
    never started; the original repair call still owes this turn a terminal.
    """
    runtime, observed = stopped(memory, monkeypatch, "parallel_calls",
                                replies=lambda initial, source: [parallel_calls(initial, source)])
    pending = _pending_calls(observed.messages)
    assert len(pending) == 2 and observed.repair_bindings == []
    assert observed.consultant_next == [BINDING_NODE]
    message = recovered(runtime, observed)
    assert message.tool_call_id == "layered-repair-call"
    assert json.loads(message.content)["status"] == "not_executed"
    assert message.artifact["operation_id"] is None
