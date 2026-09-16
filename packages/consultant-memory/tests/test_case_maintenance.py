"""B1 case staging and native tool contract; zero model/provider/publication."""

import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore

from caliburn_memory import (
    CaseArtifact, CaseMaintenanceAgentState, CaseMaintenanceError, CaseMaintenanceSession,
    MemoryArtifacts, ReplacementInput, case_maintenance_tools,
)
from conftest import ExampleSource


def _ids(count):
    return [str(uuid4()) for _ in range(count)]


def _source():
    source = ExampleSource()
    source.second_reference = "conversation:document-a:second"
    source.material[source.second_reference] = "使用者補充：夜間事件由本人先隔離，再通知主管。"
    return source


def _base(artifacts, contents):
    case_ids = _ids(len(contents))
    guide = "\n".join(
        f"- [{name}](/memory/cases/items/{case_id}.md)"
        for case_id, (name, _content) in zip(case_ids, contents, strict=True)
    )
    version = artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=guide,
        cases=tuple(CaseArtifact(case_id, content, (artifacts.source.reference,))
                    for case_id, (_name, content) in zip(case_ids, contents, strict=True)),
        understanding_guide="",
        understandings=(),
    )
    return version, case_ids


def _session(*, generated=()):
    source = _source()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    iterator = iter(generated)
    return source, artifacts, CaseMaintenanceSession(
        artifacts, id_factory=(lambda: next(iterator)) if generated else None)


def _graph(tools, saver=None):
    builder = StateGraph(CaseMaintenanceAgentState)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    return builder.compile(checkpointer=saver)


def _call(name, arguments, call_id="case-call"):
    return AIMessage("", id=f"message-{call_id}", tool_calls=[{
        "name": name, "args": arguments, "id": call_id, "type": "tool_call",
    }])


def test_open_reads_only_manifest_and_small_guide_until_one_case_is_selected():
    source, artifacts, session = _session()
    version, case_ids = _base(artifacts, [("故障處理", "本人先做故障初判。")])
    source.reads.clear()

    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)

    assert stage.base_case_ids == tuple(case_ids)
    assert stage.upserts == () and stage.changes == ()
    assert source.reads == []
    observed, item = session.observe_case(stage, case_ids[0])
    assert item.content == "本人先做故障初判。"
    assert observed.read_case_ids == (case_ids[0],)
    assert source.reads == [source.reference]


def test_create_case_uses_runtime_identity_source_and_route_then_completes():
    new_id = str(uuid4())
    source, _artifacts, session = _session(generated=[new_id])
    stage = session.open(base_publication_revision=0, base_version=None,
                         source_reference=source.reference)

    changed = session.create_case(
        stage,
        content="## 夜間故障\n本人先隔離設備，再通知主管；尚待確認通知門檻。",
        route_note="夜間故障、設備隔離；通知門檻未確認",
    )
    completed = session.finish(changed, outcome="changed")

    assert completed.current_case_ids == (new_id,)
    assert completed.supersessions == ()
    assert f"/memory/cases/items/{new_id}.md" in completed.case_guide
    assert completed.outcome == "changed"
    assert session.current_cases(completed) == (
        CaseArtifact(new_id, "## 夜間故障\n本人先隔離設備，再通知主管；尚待確認通知門檻。",
                     (source.reference,)),
    )


def test_revise_case_keeps_identity_unmentioned_text_and_both_sources():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [(
        "故障處理", "## 故障處理\n本人蒐集紀錄。\n主管負責跨部門通知。\n例外：夜間先隔離設備。",
    )])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage, _item = session.observe_case(stage, case_id)

    changed = session.revise_case(
        stage,
        case_id=case_id,
        diff="@@\n ## 故障處理\n-本人蒐集紀錄。\n+本人先做故障初判並蒐集紀錄。\n 主管負責跨部門通知。",
        route_note=None,
    )
    revised = session.read_case(changed, case_id)

    assert revised.case_id == case_id
    assert "本人先做故障初判並蒐集紀錄。" in revised.content
    assert "例外：夜間先隔離設備。" in revised.content
    assert revised.source_references == (source.reference, source.second_reference)
    assert changed.case_guide == stage.case_guide


def test_failed_patch_leaves_original_stage_unchanged():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("故障處理", "本人先做故障初判。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage, _item = session.observe_case(stage, case_id)

    with pytest.raises(CaseMaintenanceError, match="nothing from this patch was written"):
        session.revise_case(stage, case_id=case_id,
                            diff="@@\n-不存在的舊句\n+猜測的新句", route_note=None)

    assert stage.upserts == () and stage.changes == ()
    assert session.read_case(stage, case_id).content == "本人先做故障初判。"


def test_split_supersedes_one_published_case_and_preserves_its_sources():
    new_ids = _ids(2)
    source, artifacts, session = _session(generated=new_ids)
    version, (old_id,) = _base(artifacts, [("客服事件", "同一段混合了電話與現場處理。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage, _item = session.observe_case(stage, old_id)

    changed = session.split_case(stage, case_id=old_id, replacements=[
        ReplacementInput(content="電話事件：本人先確認紀錄再回覆。", route_note="電話事件、紀錄確認"),
        ReplacementInput(content="現場事件：本人先隔離設備再回報。", route_note="現場事件、設備隔離"),
    ])
    completed = session.finish(changed, outcome="changed")

    assert completed.current_case_ids == tuple(sorted(new_ids))
    assert completed.supersessions[0].retired_id == old_id
    assert set(completed.supersessions[0].current_ids) == set(new_ids)
    assert f"/{old_id}.md" not in completed.case_guide
    assert all(item.source_references == (source.reference, source.second_reference)
               for item in session.current_cases(completed))


def test_merge_and_retire_keep_current_set_guide_and_supersession_consistent():
    merged_id = str(uuid4())
    source, artifacts, session = _session(generated=[merged_id])
    version, case_ids = _base(artifacts, [
        ("設備告警", "本人確認設備告警。"),
        ("夜間告警", "夜間本人先隔離設備。"),
        ("過時案例", "這不是本人工作。"),
    ])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    for case_id in case_ids:
        stage, _item = session.observe_case(stage, case_id)
    merged = session.merge_cases(
        stage, case_ids=case_ids[:2],
        content="設備告警：本人確認告警；夜間先隔離設備，再通知主管。",
        route_note="設備告警；含夜間隔離例外",
    )
    changed = session.retire_case(merged, case_id=case_ids[2])
    completed = session.finish(changed, outcome="changed")

    assert completed.current_case_ids == (merged_id,)
    assert {item.retired_id for item in completed.supersessions} == set(case_ids)
    assert all(item.current_ids == (merged_id,) for item in completed.supersessions[:2])
    assert completed.supersessions[2].current_ids == ()
    assert completed.case_guide.count(f"/memory/cases/items/{merged_id}.md") == 1
    assert all(f"/{case_id}.md" not in completed.case_guide for case_id in case_ids)


def test_no_op_is_explicit_and_cannot_hide_or_invent_changes():
    source, artifacts, session = _session(generated=[str(uuid4())])
    version, _case_ids = _base(artifacts, [("既有案例", "目前資料與既有案例相同。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)

    completed = session.finish(stage, outcome="no_op")
    assert completed.outcome == "no_op" and not completed.changed
    with pytest.raises(CaseMaintenanceError, match="already complete"):
        session.finish(completed, outcome="no_op")
    with pytest.raises(CaseMaintenanceError, match="must match"):
        session.finish(stage, outcome="changed")

    changed = session.create_case(stage, content="真正的新案例。", route_note="新案例")
    with pytest.raises(CaseMaintenanceError, match="must match"):
        session.finish(changed, outcome="no_op")


def test_mutating_a_published_case_requires_checkpointed_read_evidence():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("既有案例", "本人先做初判。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)

    with pytest.raises(CaseMaintenanceError, match="Read the current case"):
        session.revise_case(stage, case_id=case_id,
                            diff="@@\n-本人先做初判。\n+本人先做初判並留存紀錄。", route_note=None)

    observed, _item = session.observe_case(stage, case_id)
    changed = session.revise_case(observed, case_id=case_id,
                                  diff="@@\n-本人先做初判。\n+本人先做初判並留存紀錄。", route_note=None)
    assert changed.read_case_ids == (case_id,)


def test_wrong_scope_source_is_rejected_before_any_stage_exists():
    _source_value, artifacts, session = _session()
    with pytest.raises(ValueError, match="source|document|reference"):
        session.open(base_publication_revision=0, base_version=None,
                     source_reference="conversation:document-b:original")


def test_tool_schemas_hide_runtime_storage_and_require_nullable_route_choice():
    source, _artifacts, session = _session()
    tools = case_maintenance_tools(session)
    assert [item.name for item in tools] == [
        "read_case", "create_case", "revise_case", "split_case", "merge_cases",
        "retire_case", "set_case_route", "finish_case_maintenance",
    ]
    forbidden = {"runtime", "document_id", "source_reference", "base_revision", "version",
                 "path", "digest", "operation_id", "case_stage"}
    for item in tools:
        schema = item.tool_call_schema.model_json_schema()
        assert forbidden.isdisjoint(schema.get("properties", {}))
        strict = convert_to_openai_tool(item, strict=True)["function"]
        assert strict["strict"] is True
        assert strict["parameters"]["additionalProperties"] is False
    revise = next(item for item in tools if item.name == "revise_case")
    revise_schema = revise.tool_call_schema.model_json_schema()
    assert set(revise_schema["required"]) == {"case_id", "diff", "route_note"}
    split = next(item for item in tools if item.name == "split_case")
    definition = next(iter(split.tool_call_schema.model_json_schema()["$defs"].values()))
    assert definition["additionalProperties"] is False
    assert set(definition["required"]) == {"content", "route_note"}


def test_native_toolnode_checkpoints_created_case_then_finishes_same_stage():
    new_id = str(uuid4())
    source, _artifacts, session = _session(generated=[new_id])
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    saver = InMemorySaver()
    graph = _graph(case_maintenance_tools(session), saver=saver)
    config = {"configurable": {"thread_id": "b1-case-test"}}

    first = graph.invoke({
        "messages": [HumanMessage("合成來源已由 Runtime 固定"), _call("create_case", {
            "content": "本人處理設備告警。", "route_note": "設備告警",
        }, "create")],
        "case_stage": initial.to_dict(),
    }, config, durability="sync")
    staged = session.load(first["case_stage"])
    assert staged.current_case_ids == (new_id,) and not staged.completed
    assert isinstance(first["messages"][-1], ToolMessage)
    assert json.loads(first["messages"][-1].content)["effect"] == "staged"

    second = graph.invoke({
        "messages": [_call("finish_case_maintenance", {"outcome": "changed"}, "finish")],
    }, config, durability="sync")
    completed = session.load(second["case_stage"])
    assert completed.completed and completed.outcome == "changed"
    assert json.loads(second["messages"][-1].content)["effect"] == "stage_complete"
    snapshot = graph.get_state(config)
    assert session.load(snapshot.values["case_stage"]) == completed


def test_native_toolnode_checkpoints_read_before_revising_published_case():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("故障初判", "本人先做故障初判。")])
    initial = session.open(base_publication_revision=1, base_version=version,
                           source_reference=source.second_reference)
    graph = _graph(case_maintenance_tools(session), saver=InMemorySaver())
    config = {"configurable": {"thread_id": "b1-read-before-write"}}

    read = graph.invoke({
        "messages": [_call("read_case", {"case_id": case_id}, "read")],
        "case_stage": initial.to_dict(),
    }, config, durability="sync")
    assert session.load(read["case_stage"]).read_case_ids == (case_id,)

    revised = graph.invoke({
        "messages": [_call("revise_case", {
            "case_id": case_id,
            "diff": "@@\n-本人先做故障初判。\n+本人先做故障初判並留存紀錄。",
            "route_note": None,
        }, "revise")],
    }, config, durability="sync")
    stage = session.load(revised["case_stage"])
    assert "並留存紀錄" in session.read_case(stage, case_id).content
    assert stage.changes[-1].kind == "revise"


def test_tool_error_returns_unchanged_state_and_matching_error_result():
    source, _artifacts, session = _session()
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    graph = _graph(case_maintenance_tools(session))
    result = graph.invoke({
        "messages": [_call("revise_case", {
            "case_id": str(uuid4()), "diff": "@@\n-x\n+y", "route_note": None,
        })],
        "case_stage": initial.to_dict(),
    })

    assert session.load(result["case_stage"]) == initial
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage) and message.status == "error"
    payload = json.loads(message.content)
    assert payload["effect"] == "unchanged" and payload["error"] == "case_not_current"


def test_parallel_case_mutations_are_rejected_without_a_state_race():
    generated = _ids(2)
    source, _artifacts, session = _session(generated=generated)
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    calls = [
        {"name": "create_case", "args": {"content": "案例 A", "route_note": "案例 A"},
         "id": "create-a", "type": "tool_call"},
        {"name": "create_case", "args": {"content": "案例 B", "route_note": "案例 B"},
         "id": "create-b", "type": "tool_call"},
    ]
    result = _graph(case_maintenance_tools(session)).invoke({
        "messages": [AIMessage("", id="parallel", tool_calls=calls)],
        "case_stage": initial.to_dict(),
    })

    assert session.load(result["case_stage"]) == initial
    errors = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(errors) == 2
    assert all(json.loads(message.content)["error"] == "multiple_case_tool_calls" for message in errors)
