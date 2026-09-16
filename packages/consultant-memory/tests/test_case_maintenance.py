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
    EvidenceDiscardInput, EvidenceExchange, EvidenceMessage, MemoryArtifacts, ReplacementInput,
    case_maintenance_tools,
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
        evidence_through_reference=artifacts.source.reference,
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


def _register(session, stage, *references):
    updated = stage
    for index, reference in enumerate(references):
        updated, _item = session.register_evidence(
            updated,
            EvidenceExchange(reference, (EvidenceMessage(reference, "user"),)),
            order_key=(0, index, 0),
            next_offset=None,
        )
    return updated


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
    stage = _register(session, stage, source.reference)

    changed = session.create_case(
        stage,
        content="## 夜間故障\n本人先隔離設備，再通知主管；尚待確認通知門檻。",
        route_note="夜間故障、設備隔離；通知門檻未確認",
        evidence_keys=["E1"],
    )
    completed = session.finish(changed)

    assert completed.current_case_ids == (new_id,)
    assert completed.supersessions == ()
    assert f"/memory/cases/items/{new_id}.md" in completed.case_guide
    assert completed.outcome == "changed"
    assert session.current_cases(completed) == (
        CaseArtifact(new_id, "## 夜間故障\n本人先隔離設備，再通知主管；尚待確認通知門檻。",
                     (source.reference,)),
    )


def test_create_case_resolves_model_keys_and_saves_owner_order_not_key_order():
    new_id = str(uuid4())
    source, _artifacts, session = _session(generated=[new_id])
    stage = session.open(base_publication_revision=0, base_version=None,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)

    changed = session.create_case(
        stage,
        content="本人先確認告警，再留存紀錄。",
        route_note="告警確認與紀錄",
        evidence_keys=["E2", "E1"],
    )

    assert session.read_case(changed, new_id).source_references == (
        source.reference, source.second_reference,
    )
    assert session.evidence_keys(changed, (source.reference, source.second_reference)) == (
        "E1", "E2",
    )


def test_invalid_create_evidence_does_not_consume_a_runtime_identity():
    first_id, second_id = _ids(2)
    source, _artifacts, session = _session(generated=[first_id, second_id])
    stage = session.open(base_publication_revision=0, base_version=None,
                         source_reference=source.reference)
    stage = _register(session, stage, source.reference)

    with pytest.raises(CaseMaintenanceError, match="already supplied"):
        session.create_case(
            stage, content="案例。", route_note="案例", evidence_keys=["E9"])

    changed = session.create_case(
        stage, content="案例。", route_note="案例", evidence_keys=["E1"])
    assert changed.current_case_ids == (first_id,)


def test_revise_case_can_change_only_evidence_but_rejects_an_empty_revision():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("故障處理", "本人先做故障初判。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, case_id)

    changed = session.revise_case(
        stage,
        case_id=case_id,
        diff=None,
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    assert session.read_case(changed, case_id) == CaseArtifact(
        case_id, "本人先做故障初判。", (source.reference, source.second_reference),
    )

    with pytest.raises(CaseMaintenanceError, match="no change"):
        session.revise_case(
            stage,
            case_id=case_id,
            diff=None,
            route_note=None,
            add_evidence_keys=[],
            remove_evidence_keys=[],
        )

    with pytest.raises(CaseMaintenanceError, match="set_case_route"):
        session.revise_case(
            stage,
            case_id=case_id,
            diff=None,
            route_note="故障初判、導覽更新",
            add_evidence_keys=[],
            remove_evidence_keys=[],
        )


@pytest.mark.parametrize(
    ("added", "removed", "message"),
    [
        (["E2", "E2"], [], "repeat"),
        (["E9"], [], "already supplied"),
        (["E2"], ["E2"], "same evidence"),
        ([], ["E1"], "at least one evidence"),
    ],
)
def test_invalid_evidence_delta_is_rejected_without_changing_the_stage(
        added, removed, message):
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("故障處理", "本人先做故障初判。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, case_id)

    with pytest.raises(CaseMaintenanceError, match=message):
        session.revise_case(
            stage,
            case_id=case_id,
            diff=None,
            route_note=None,
            add_evidence_keys=added,
            remove_evidence_keys=removed,
        )

    assert stage.upserts == () and stage.changes == ()


def test_finish_computes_outcome_without_model_input():
    source, _artifacts, session = _session()
    stage = session.open(base_publication_revision=0, base_version=None,
                         source_reference=source.reference)

    completed = session.finish(stage)

    assert completed.completed and completed.outcome == "no_op"


def test_revise_case_keeps_identity_unmentioned_text_and_both_sources():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [(
        "故障處理", "## 故障處理\n本人蒐集紀錄。\n主管負責跨部門通知。\n例外：夜間先隔離設備。",
    )])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, case_id)

    changed = session.revise_case(
        stage,
        case_id=case_id,
        diff="@@\n ## 故障處理\n-本人蒐集紀錄。\n+本人先做故障初判並蒐集紀錄。\n 主管負責跨部門通知。",
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
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
    stage = _register(session, stage, source.reference)
    stage, _item = session.observe_case(stage, case_id)

    with pytest.raises(CaseMaintenanceError, match="nothing from this patch was written"):
        session.revise_case(stage, case_id=case_id,
                            diff="@@\n-不存在的舊句\n+猜測的新句", route_note=None,
                            add_evidence_keys=[], remove_evidence_keys=[])

    assert stage.upserts == () and stage.changes == ()
    assert session.read_case(stage, case_id).content == "本人先做故障初判。"


def test_split_supersedes_one_published_case_and_preserves_its_sources():
    new_ids = _ids(2)
    source, artifacts, session = _session(generated=new_ids)
    version, (old_id,) = _base(artifacts, [("客服事件", "同一段混合了電話與現場處理。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, old_id)

    changed = session.split_case(stage, case_id=old_id, replacements=[
        ReplacementInput(content="電話事件：本人先確認紀錄再回覆。", route_note="電話事件、紀錄確認",
                         evidence_keys=["E1", "E2"]),
        ReplacementInput(content="現場事件：本人先隔離設備再回報。", route_note="現場事件、設備隔離",
                         evidence_keys=["E1", "E2"]),
    ], discarded_evidence=[])
    completed = session.finish(changed)

    assert completed.current_case_ids == tuple(sorted(new_ids))
    assert completed.supersessions[0].retired_id == old_id
    assert set(completed.supersessions[0].current_ids) == set(new_ids)
    assert f"/{old_id}.md" not in completed.case_guide
    assert all(item.source_references == (source.reference, source.second_reference)
               for item in session.current_cases(completed))


def test_split_assigns_evidence_per_replacement_and_requires_explicit_old_discards():
    new_ids = _ids(2)
    source, artifacts, session = _session(generated=new_ids)
    old_id = str(uuid4())
    guide = f"- [客服事件](/memory/cases/items/{old_id}.md) — 電話與現場事件"
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=guide,
        cases=(CaseArtifact(old_id, "同一段混合了電話與現場處理。",
                            (source.reference, source.second_reference)),),
        understanding_guide="",
        understandings=(),
    )
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, old_id)

    with pytest.raises(CaseMaintenanceError, match="explicitly account"):
        session.split_case(
            stage,
            case_id=old_id,
            replacements=[
                ReplacementInput(content="電話事件。", route_note="電話", evidence_keys=["E1"]),
                ReplacementInput(content="另一電話事件。", route_note="電話例外", evidence_keys=["E1"]),
            ],
            discarded_evidence=[],
        )

    changed = session.split_case(
        stage,
        case_id=old_id,
        replacements=[
            ReplacementInput(content="電話事件。", route_note="電話", evidence_keys=["E1"]),
            ReplacementInput(content="現場事件。", route_note="現場", evidence_keys=["E2"]),
        ],
        discarded_evidence=[],
    )
    cases = {item.content: item.source_references for item in session.current_cases(session.finish(changed))}
    assert cases == {
        "電話事件。": (source.reference,),
        "現場事件。": (source.second_reference,),
    }


def test_split_accepts_a_reasoned_discard_without_copying_it_to_replacements():
    new_ids = _ids(2)
    source, artifacts, session = _session(generated=new_ids)
    old_id = str(uuid4())
    guide = f"- [混合案例](/memory/cases/items/{old_id}.md) — 待拆分"
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=guide,
        cases=(CaseArtifact(old_id, "混合案例。", (source.reference, source.second_reference)),),
        understanding_guide="",
        understandings=(),
    )
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    stage, _item = session.observe_case(stage, old_id)

    changed = session.split_case(
        stage,
        case_id=old_id,
        replacements=[
            ReplacementInput(content="案例甲。", route_note="甲", evidence_keys=["E1"]),
            ReplacementInput(content="案例乙。", route_note="乙", evidence_keys=["E1"]),
        ],
        discarded_evidence=[EvidenceDiscardInput(
            evidence_key="E2", reason="這段只是在更正原本混合案例的錯誤分類。")],
    )

    assert all(item.source_references == (source.reference,)
               for item in session.current_cases(session.finish(changed)))


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
    stage = _register(session, stage, source.reference, source.second_reference)
    for case_id in case_ids:
        stage, _item = session.observe_case(stage, case_id)
    merged = session.merge_cases(
        stage, case_ids=case_ids[:2],
        content="設備告警：本人確認告警；夜間先隔離設備，再通知主管。",
        route_note="設備告警；含夜間隔離例外",
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    changed = session.retire_case(merged, case_id=case_ids[2])
    completed = session.finish(changed)

    assert completed.current_case_ids == (merged_id,)
    assert {item.retired_id for item in completed.supersessions} == set(case_ids)
    assert all(item.current_ids == (merged_id,) for item in completed.supersessions[:2])
    assert completed.supersessions[2].current_ids == ()
    assert completed.case_guide.count(f"/memory/cases/items/{merged_id}.md") == 1
    assert all(f"/{case_id}.md" not in completed.case_guide for case_id in case_ids)


def test_merge_starts_from_read_case_evidence_union_then_applies_add_remove_delta():
    merged_id = str(uuid4())
    source, artifacts, session = _session(generated=[merged_id])
    third = "conversation:document-a:third"
    source.material[third] = "補充來源。"
    first_id, second_id = _ids(2)
    guide = "\n".join((
        f"- [案例甲](/memory/cases/items/{first_id}.md) — 甲",
        f"- [案例乙](/memory/cases/items/{second_id}.md) — 乙",
    ))
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=guide,
        cases=(
            CaseArtifact(first_id, "案例甲。", (source.reference,)),
            CaseArtifact(second_id, "案例乙。", (source.second_reference,)),
        ),
        understanding_guide="",
        understandings=(),
    )
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=third)
    stage = _register(session, stage, source.reference, source.second_reference, third)
    for case_id in (first_id, second_id):
        stage, _item = session.observe_case(stage, case_id)

    changed = session.merge_cases(
        stage,
        case_ids=[first_id, second_id],
        content="合併後案例。",
        route_note="合併案例",
        add_evidence_keys=["E3"],
        remove_evidence_keys=["E1"],
    )

    assert session.read_case(changed, merged_id).source_references == (
        source.second_reference, third,
    )


def test_invalid_merge_evidence_does_not_consume_a_runtime_identity():
    first_id, second_id = _ids(2)
    source, artifacts, session = _session(generated=[first_id, second_id])
    version, case_ids = _base(artifacts, [
        ("案例甲", "案例甲。"),
        ("案例乙", "案例乙。"),
    ])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)
    for case_id in case_ids:
        stage, _item = session.observe_case(stage, case_id)

    with pytest.raises(CaseMaintenanceError, match="already supplied"):
        session.merge_cases(
            stage,
            case_ids=case_ids,
            content="合併案例。",
            route_note="合併案例",
            add_evidence_keys=["E9"],
            remove_evidence_keys=[],
        )

    changed = session.merge_cases(
        stage,
        case_ids=case_ids,
        content="合併案例。",
        route_note="合併案例",
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    assert changed.current_case_ids == (first_id,)


def test_finish_computes_outcome_and_cannot_run_twice():
    source, artifacts, session = _session(generated=[str(uuid4())])
    version, _case_ids = _base(artifacts, [("既有案例", "目前資料與既有案例相同。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)

    completed = session.finish(stage)
    assert completed.outcome == "no_op" and not completed.changed
    with pytest.raises(CaseMaintenanceError, match="already complete"):
        session.finish(completed)

    stage = _register(session, stage, source.second_reference)
    changed = session.create_case(
        stage, content="真正的新案例。", route_note="新案例", evidence_keys=["E1"])
    assert session.finish(changed).outcome == "changed"


def test_mutating_a_published_case_requires_checkpointed_read_evidence():
    source, artifacts, session = _session()
    version, (case_id,) = _base(artifacts, [("既有案例", "本人先做初判。")])
    stage = session.open(base_publication_revision=1, base_version=version,
                         source_reference=source.second_reference)
    stage = _register(session, stage, source.reference, source.second_reference)

    with pytest.raises(CaseMaintenanceError, match="Read the current case"):
        session.revise_case(stage, case_id=case_id,
                            diff="@@\n-本人先做初判。\n+本人先做初判並留存紀錄。", route_note=None,
                            add_evidence_keys=["E2"], remove_evidence_keys=[])

    observed, _item = session.observe_case(stage, case_id)
    changed = session.revise_case(observed, case_id=case_id,
                                  diff="@@\n-本人先做初判。\n+本人先做初判並留存紀錄。", route_note=None,
                                  add_evidence_keys=["E2"], remove_evidence_keys=[])
    assert changed.read_case_ids == (case_id,)


def test_wrong_scope_source_is_rejected_before_any_stage_exists():
    _source_value, artifacts, session = _session()
    with pytest.raises(ValueError, match="source|document|reference"):
        session.open(base_publication_revision=0, base_version=None,
                     source_reference="conversation:document-b:original")


def test_tool_schemas_hide_runtime_storage_and_require_nullable_route_choice():
    source, _artifacts, session = _session()
    tools = case_maintenance_tools(source, session)
    assert [item.name for item in tools] == [
        "read_case", "browse_interview_history", "read_more_evidence",
        "create_case", "revise_case", "split_case", "merge_cases",
        "retire_case", "set_case_route", "finish_case_maintenance",
    ]
    forbidden = {"runtime", "document_id", "source_reference", "source_references", "offset",
                 "base_revision", "version", "path", "digest", "operation_id", "case_stage"}
    for item in tools:
        schema = item.tool_call_schema.model_json_schema()
        assert forbidden.isdisjoint(schema.get("properties", {}))
        strict = convert_to_openai_tool(item, strict=True)["function"]
        assert strict["strict"] is True
        assert strict["parameters"]["additionalProperties"] is False
    revise = next(item for item in tools if item.name == "revise_case")
    revise_schema = revise.tool_call_schema.model_json_schema()
    assert set(revise_schema["required"]) == {
        "case_id", "diff", "route_note", "add_evidence_keys", "remove_evidence_keys",
    }
    split = next(item for item in tools if item.name == "split_case")
    split_schema = split.tool_call_schema.model_json_schema()
    definition = split_schema["$defs"]["ReplacementInput"]
    assert definition["additionalProperties"] is False
    assert set(definition["required"]) == {"content", "route_note", "evidence_keys"}
    discard_definition = split_schema["$defs"]["EvidenceDiscardInput"]
    assert discard_definition["additionalProperties"] is False
    assert set(discard_definition["required"]) == {"evidence_key", "reason"}
    assert set(split_schema["required"]) == {"case_id", "replacements", "discarded_evidence"}
    finish = next(item for item in tools if item.name == "finish_case_maintenance")
    assert finish.tool_call_schema.model_json_schema().get("properties", {}) == {}
    browse = next(item for item in tools if item.name == "browse_interview_history")
    assert browse.tool_call_schema.model_json_schema().get("properties", {}) == {}
    more = next(item for item in tools if item.name == "read_more_evidence")
    assert set(more.tool_call_schema.model_json_schema()["properties"]) == {"evidence_key"}


def test_native_toolnode_checkpoints_created_case_then_finishes_same_stage():
    new_id = str(uuid4())
    source, _artifacts, session = _session(generated=[new_id])
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    initial = _register(session, initial, source.reference)
    saver = InMemorySaver()
    graph = _graph(case_maintenance_tools(source, session), saver=saver)
    config = {"configurable": {"thread_id": "b1-case-test"}}

    first = graph.invoke({
        "messages": [HumanMessage("合成來源已由 Runtime 固定"), _call("create_case", {
            "content": "本人處理設備告警。", "route_note": "設備告警", "evidence_keys": ["E1"],
        }, "create")],
        "case_stage": initial.to_dict(),
    }, config, durability="sync")
    staged = session.load(first["case_stage"])
    assert staged.current_case_ids == (new_id,) and not staged.completed
    assert isinstance(first["messages"][-1], ToolMessage)
    assert json.loads(first["messages"][-1].content)["effect"] == "staged"

    second = graph.invoke({
        "messages": [_call("finish_case_maintenance", {}, "finish")],
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
    graph = _graph(case_maintenance_tools(source, session), saver=InMemorySaver())
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
            "add_evidence_keys": [],
            "remove_evidence_keys": [],
        }, "revise")],
    }, config, durability="sync")
    stage = session.load(revised["case_stage"])
    assert "並留存紀錄" in session.read_case(stage, case_id).content
    assert stage.changes[-1].kind == "revise"


def test_tool_error_returns_unchanged_state_and_matching_error_result():
    source, _artifacts, session = _session()
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    graph = _graph(case_maintenance_tools(source, session))
    result = graph.invoke({
        "messages": [_call("revise_case", {
            "case_id": str(uuid4()), "diff": "@@\n-x\n+y", "route_note": None,
            "add_evidence_keys": [], "remove_evidence_keys": [],
        })],
        "case_stage": initial.to_dict(),
    })

    assert session.load(result["case_stage"]) == initial
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage) and message.status == "error"
    payload = json.loads(message.content)
    assert payload["effect"] == "unchanged" and payload["error"] == "case_not_current"


def test_runtime_rejects_a_direct_reference_even_if_provider_strict_is_absent():
    source, _artifacts, session = _session(generated=[str(uuid4())])
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    initial = _register(session, initial, source.reference)
    result = _graph(case_maintenance_tools(source, session)).invoke({
        "messages": [_call("create_case", {
            "content": "案例。",
            "route_note": "案例",
            "evidence_keys": ["E1"],
            "source_reference": source.reference,
        })],
        "case_stage": initial.to_dict(),
    })

    assert session.load(result["case_stage"]) == initial
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage) and message.status == "error"


def test_parallel_case_mutations_are_rejected_without_a_state_race():
    generated = _ids(2)
    source, _artifacts, session = _session(generated=generated)
    initial = session.open(base_publication_revision=0, base_version=None,
                           source_reference=source.reference)
    calls = [
        {"name": "create_case", "args": {"content": "案例 A", "route_note": "案例 A",
                                             "evidence_keys": ["E1"]},
         "id": "create-a", "type": "tool_call"},
        {"name": "create_case", "args": {"content": "案例 B", "route_note": "案例 B",
                                             "evidence_keys": ["E1"]},
         "id": "create-b", "type": "tool_call"},
    ]
    result = _graph(case_maintenance_tools(source, session)).invoke({
        "messages": [AIMessage("", id="parallel", tool_calls=calls)],
        "case_stage": initial.to_dict(),
    })

    assert session.load(result["case_stage"]) == initial
    errors = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(errors) == 2
    assert all(json.loads(message.content)["error"] == "multiple_case_tool_calls" for message in errors)
