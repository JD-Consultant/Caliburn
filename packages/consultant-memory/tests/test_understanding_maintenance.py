"""B2 understanding staging and impact contract; zero model/provider/publication."""

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
    CaseArtifact, CaseMaintenanceSession, CaseReworkIssueInput, CaseSourceRead,
    EvidenceExchange, EvidenceMessage, MemoryArtifacts,
    ReplacementInput,
    UnderstandingMaintenanceError, UnderstandingMaintenanceSession,
    UnderstandingMaintenanceAgentState, UnderstandingReplacementInput,
    WorkUnderstandingArtifact, understanding_maintenance_tools,
    understanding_workflow_tools,
)
from conftest import ExampleSource


def _ids(count):
    return [str(uuid4()) for _ in range(count)]


def _graph(tools, saver=None):
    builder = StateGraph(UnderstandingMaintenanceAgentState)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    return builder.compile(checkpointer=saver)


def _call(name, arguments, call_id="understanding-call"):
    return AIMessage("", id=f"message-{call_id}", tool_calls=[{
        "name": name, "args": arguments, "id": call_id, "type": "tool_call",
    }])


def _register_case_evidence(session, stage, *references):
    updated = stage
    for index, reference in enumerate(references):
        updated, _item = session.register_evidence(
            updated,
            EvidenceExchange(reference, (EvidenceMessage(reference, "user"),)),
            order_key=(0, index, 0),
            next_offset=None,
        )
    return updated


def _fixture():
    source = ExampleSource()
    source.second_reference = "conversation:document-a:second"
    source.material[source.second_reference] = (
        "使用者補充：夜間事件由本人先隔離；白天還會處理付款條件核對。"
    )
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_a, case_b, understanding_x, new_case = _ids(4)
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=(
            f"- [故障案例](/memory/cases/items/{case_a}.md)\n"
            f"- [交付案例](/memory/cases/items/{case_b}.md)"
        ),
        cases=(
            CaseArtifact(case_a, "本人先做故障初判。", (source.reference,)),
            CaseArtifact(case_b, "本人核對交付內容。", (source.reference,)),
        ),
        understanding_guide=(
            f"- [事件處理](/memory/understanding/items/{understanding_x}.md)"
        ),
        understandings=(WorkUnderstandingArtifact(
            understanding_x,
            "本人負責事件初判與交付前核對。",
            (case_a, case_b),
        ),),
    )
    case_session = CaseMaintenanceSession(artifacts, id_factory=lambda: new_case)
    case_stage = case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=source.second_reference,
    )
    case_stage = _register_case_evidence(
        case_session, case_stage, source.reference, source.second_reference)
    case_stage, _case = case_session.observe_case(case_stage, case_a)
    case_stage = case_session.revise_case(
        case_stage,
        case_id=case_a,
        diff="@@\n-本人先做故障初判。\n+本人先做故障初判；夜間先隔離設備。",
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    case_stage = case_session.create_case(
        case_stage,
        content="本人核對付款條件與例外。",
        route_note="付款條件核對",
        evidence_keys=["E2"],
    )
    case_stage = case_session.finish(case_stage)
    return source, artifacts, case_session, case_stage, {
        "case_a": case_a,
        "case_b": case_b,
        "new_case": new_case,
        "understanding_x": understanding_x,
        "version": version,
    }


def test_open_derives_changed_current_cases_and_directly_affected_understandings():
    source, artifacts, case_session, case_stage, ids = _fixture()
    source.reads.clear()
    session = UnderstandingMaintenanceSession(artifacts, case_session)

    stage = session.open(case_stage)

    assert stage.base_publication_revision == 1
    assert stage.base_memory_version_id == ids["version"].version_id
    assert stage.required_case_ids == tuple(sorted((ids["case_a"], ids["new_case"])))
    assert stage.required_understanding_ids == (ids["understanding_x"],)
    assert stage.base_understanding_ids == (ids["understanding_x"],)
    assert stage.read_case_ids == () and stage.read_understanding_ids == ()
    assert source.reads == []


def test_open_unions_runtime_repair_impact_without_new_stage_fields():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_a, case_b, understanding_x, understanding_y = _ids(4)
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.reference,
        case_guide=(
            f"- [故障案例](/memory/cases/items/{case_a}.md)\n"
            f"- [交付案例](/memory/cases/items/{case_b}.md)"
        ),
        cases=(
            CaseArtifact(case_a, "本人先做故障初判。", (source.reference,)),
            CaseArtifact(case_b, "本人核對交付內容。", (source.reference,)),
        ),
        understanding_guide=(
            f"- [事件處理](/memory/understanding/items/{understanding_x}.md)\n"
            f"- [交付核對](/memory/understanding/items/{understanding_y}.md)"
        ),
        understandings=(
            WorkUnderstandingArtifact(understanding_x, "本人負責事件初判。", (case_a,)),
            WorkUnderstandingArtifact(understanding_y, "本人負責交付核對。", (case_b,)),
        ),
    )
    case_session = CaseMaintenanceSession(artifacts)
    case_stage = case_session.finish(case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=source.reference,
    ))
    session = UnderstandingMaintenanceSession(artifacts, case_session)

    stage = session.open(
        case_stage,
        additional_required_case_ids=(case_b,),
        additional_required_understanding_ids=(understanding_y,),
    )

    assert stage.required_case_ids == (case_b,)
    assert stage.required_understanding_ids == (understanding_y,)

    invalid_case, invalid_understanding = _ids(2)
    with pytest.raises(UnderstandingMaintenanceError, match="required.*case|current case"):
        session.open(case_stage, additional_required_case_ids=(invalid_case,))
    with pytest.raises(UnderstandingMaintenanceError, match="required.*understanding|current understanding"):
        session.open(
            case_stage,
            additional_required_understanding_ids=(invalid_understanding,),
        )


def test_open_rejects_incomplete_b1_stage_and_cross_document_components():
    _source, artifacts, case_session, completed, ids = _fixture()
    incomplete = case_session.open(
        base_publication_revision=1,
        base_version=ids["version"],
        source_reference="conversation:document-a:second",
    )
    session = UnderstandingMaintenanceSession(artifacts, case_session)

    with pytest.raises(UnderstandingMaintenanceError, match="B1.*complete"):
        session.open(incomplete)

    other_source = ExampleSource("document-b")
    other_artifacts = MemoryArtifacts(InMemoryStore(), other_source.document_id, source=other_source)
    with pytest.raises(ValueError, match="different documents"):
        UnderstandingMaintenanceSession(other_artifacts, case_session)

    assert completed.completed


def test_serialized_b2_stage_rejects_a_tampered_impact_set():
    _source, artifacts, case_session, case_stage, _ids_value = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    tampered = stage.to_dict()
    tampered["required_understanding_ids"] = []

    with pytest.raises(UnderstandingMaintenanceError, match="impact|invalid"):
        session.load(tampered)


def test_source_reference_requires_its_observed_case_and_is_durable_read_evidence():
    source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)

    exchange = EvidenceExchange(
        source.reference, (EvidenceMessage(source.reference, "user"),),
    )
    with pytest.raises(UnderstandingMaintenanceError, match="Read the case"):
        session.register_case_evidence(
            stage, case_id=ids["case_a"], exchange=exchange, order_index=0,
        )

    stage, _case = session.observe_case(stage, ids["case_a"])
    with pytest.raises(UnderstandingMaintenanceError, match="outside"):
        session.register_case_evidence(
            stage, case_id=ids["case_a"], exchange=EvidenceExchange(
                "conversation:document-a:missing",
                (EvidenceMessage("missing", "user"),),
            ), order_index=1,
        )

    staged, evidence = session.register_case_evidence(
        stage, case_id=ids["case_a"], exchange=exchange, order_index=0,
    )
    observed, evidence = session.advance_case_evidence(
        staged, evidence_key=evidence.evidence_key, next_offset=None,
    )

    assert observed.format_version == 3
    assert observed.read_source_references == (
        CaseSourceRead(ids["case_a"], source.reference),
    )
    assert session.load(observed.to_dict()) == observed
    tampered = observed.to_dict()
    tampered["read_source_references"] = [{
        "case_id": ids["case_a"],
        "source_reference": "conversation:document-a:missing",
    }]
    with pytest.raises(UnderstandingMaintenanceError, match="source read evidence"):
        session.load(tampered)


def test_case_rework_requires_read_source_and_never_becomes_publishable():
    source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    stage, _case = session.observe_case(stage, ids["case_a"])
    stage, evidence = session.register_case_evidence(
        stage, case_id=ids["case_a"], exchange=EvidenceExchange(
            source.reference, (EvidenceMessage(source.reference, "user"),),
        ), order_index=0,
    )
    issue = CaseReworkIssueInput(
        evidence_key=evidence.evidence_key,
        reason="原話顯示本人只做初判，案例卻把後續跨部門處理也列為本人責任。",
    )

    with pytest.raises(UnderstandingMaintenanceError, match="Read the cited canonical source"):
        session.request_case_rework(stage, issues=[issue])

    stage, _evidence = session.advance_case_evidence(
        stage, evidence_key=evidence.evidence_key, next_offset=None,
    )
    completed = session.request_case_rework(stage, issues=[issue])

    assert completed.completed
    assert completed.outcome == "case_rework_required"
    assert completed.case_rework_issues[0].case_id == ids["case_a"]
    assert completed.case_rework_issues[0].source_reference == source.reference
    with pytest.raises(UnderstandingMaintenanceError, match="not publishable"):
        session.current_understandings(completed)


def test_case_rework_rejects_duplicate_or_mismatched_issue_evidence():
    source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    stage, _case = session.observe_case(stage, ids["case_a"])
    stage, evidence_a = session.register_case_evidence(
        stage, case_id=ids["case_a"], exchange=EvidenceExchange(
            source.reference, (EvidenceMessage(source.reference, "user"),),
        ), order_index=0,
    )
    stage, _evidence = session.advance_case_evidence(
        stage, evidence_key=evidence_a.evidence_key, next_offset=None,
    )
    issue = CaseReworkIssueInput(
        evidence_key=evidence_a.evidence_key,
        reason="原話與案例責任範圍不一致。",
    )

    with pytest.raises(UnderstandingMaintenanceError, match="distinct"):
        session.request_case_rework(stage, issues=[issue, issue])

    stage, _case = session.observe_case(stage, ids["case_b"])
    stage, evidence_b = session.register_case_evidence(
        stage, case_id=ids["case_b"], exchange=EvidenceExchange(
            source.reference, (EvidenceMessage(source.reference, "user"),),
        ), order_index=0,
    )
    wrong_case = CaseReworkIssueInput(
        evidence_key=evidence_b.evidence_key,
        reason="不得把 CASE-A 的來源冒充 CASE-B 已核對來源。",
    )
    with pytest.raises(UnderstandingMaintenanceError, match="Read the cited canonical source"):
        session.request_case_rework(stage, issues=[wrong_case])


@pytest.mark.parametrize(
    ("operation", "expected_case_count", "affected_count"),
    [("split", 2, 1), ("merge", 1, 2), ("retire", 0, 1), ("route", 0, 0)],
)
def test_impact_covers_case_lifecycle_and_ignores_route_only_changes(
        operation, expected_case_count, affected_count):
    source = ExampleSource()
    source.second_reference = "conversation:document-a:second"
    source.material[source.second_reference] = "使用者補充了案例邊界與分類。"
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_a, case_b, understanding_x, understanding_y, replacement_a, replacement_b = _ids(6)
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=(
            f"- [故障案例](/memory/cases/items/{case_a}.md)\n"
            f"- [交付案例](/memory/cases/items/{case_b}.md)"
        ),
        cases=(
            CaseArtifact(case_a, "本人先做故障初判。", (source.reference,)),
            CaseArtifact(case_b, "本人核對交付內容。", (source.reference,)),
        ),
        understanding_guide=(
            f"- [事件處理](/memory/understanding/items/{understanding_x}.md)\n"
            f"- [交付核對](/memory/understanding/items/{understanding_y}.md)"
        ),
        understandings=(
            WorkUnderstandingArtifact(understanding_x, "本人負責事件初判。", (case_a,)),
            WorkUnderstandingArtifact(understanding_y, "本人負責交付核對。", (case_b,)),
        ),
    )
    allocated = iter((replacement_a, replacement_b))
    case_session = CaseMaintenanceSession(artifacts, id_factory=lambda: next(allocated))
    case_stage = case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=source.second_reference,
    )
    case_stage = _register_case_evidence(
        case_session, case_stage, source.reference, source.second_reference)

    if operation == "split":
        case_stage, _item = case_session.observe_case(case_stage, case_a)
        case_stage = case_session.split_case(
            case_stage,
            case_id=case_a,
            replacements=[
                ReplacementInput(content="本人進行故障初判。", route_note="故障初判",
                                 evidence_keys=["E1", "E2"]),
                ReplacementInput(content="本人隔離夜間設備。", route_note="夜間設備隔離",
                                 evidence_keys=["E1", "E2"]),
            ],
            discarded_evidence=[],
        )
    elif operation == "merge":
        for case_id in (case_a, case_b):
            case_stage, _item = case_session.observe_case(case_stage, case_id)
        case_stage = case_session.merge_cases(
            case_stage,
            case_ids=[case_a, case_b],
            content="本人完成事件初判與交付核對。",
            route_note="事件與交付處理",
            add_evidence_keys=["E2"],
            remove_evidence_keys=[],
        )
    elif operation == "retire":
        case_stage, _item = case_session.observe_case(case_stage, case_a)
        case_stage = case_session.retire_case(case_stage, case_id=case_a)
    else:
        case_stage = case_session.set_case_route(
            case_stage, case_id=case_a, route_note="故障事件初判",
        )
    case_stage = case_session.finish(case_stage)

    stage = UnderstandingMaintenanceSession(artifacts, case_session).open(case_stage)

    assert len(stage.required_case_ids) == expected_case_count
    assert len(stage.required_understanding_ids) == affected_count
    if operation == "split":
        assert stage.required_case_ids == tuple(sorted((replacement_a, replacement_b)))
        assert stage.required_understanding_ids == (understanding_x,)
    elif operation == "merge":
        assert stage.required_case_ids == (replacement_a,)
        assert stage.required_understanding_ids == tuple(sorted((
            understanding_x, understanding_y,
        )))
    elif operation == "retire":
        assert stage.required_understanding_ids == (understanding_x,)


def test_create_understanding_requires_observed_current_support_and_runtime_identity():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    new_understanding = str(uuid4())
    session = UnderstandingMaintenanceSession(
        artifacts, case_session, id_factory=lambda: new_understanding,
    )
    stage = session.open(case_stage)

    with pytest.raises(UnderstandingMaintenanceError, match="Read.*supporting case"):
        session.create_understanding(
            stage,
            content="本人負責核對付款條件與例外。",
            supporting_case_ids=[ids["new_case"]],
            route_note="付款條件與例外核對",
        )

    stage, observed = session.observe_case(stage, ids["new_case"])
    assert observed.case_id == ids["new_case"]
    changed = session.create_understanding(
        stage,
        content="本人負責核對付款條件與例外。",
        supporting_case_ids=[ids["new_case"]],
        route_note="付款條件與例外核對",
    )

    assert changed.current_understanding_ids == tuple(sorted((
        ids["understanding_x"], new_understanding,
    )))
    created = session.read_understanding(changed, new_understanding)
    assert created == WorkUnderstandingArtifact(
        new_understanding,
        "本人負責核對付款條件與例外。",
        (ids["new_case"],),
    )
    assert f"/memory/understanding/items/{new_understanding}.md" in changed.understanding_guide


def test_revise_understanding_requires_reading_it_and_every_current_support():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    stage, _case = session.observe_case(stage, ids["case_a"])
    stage, _case = session.observe_case(stage, ids["case_b"])

    with pytest.raises(UnderstandingMaintenanceError, match="Read the current work understanding"):
        session.revise_understanding(
            stage,
            understanding_id=ids["understanding_x"],
            diff=("@@\n-本人負責事件初判與交付前核對。\n"
                  "+本人負責事件初判、夜間隔離與交付前核對。"),
            supporting_case_ids=[ids["case_a"], ids["case_b"]],
            route_note=None,
        )

    stage, current = session.observe_understanding(stage, ids["understanding_x"])
    assert current.supporting_case_ids == tuple(sorted((ids["case_a"], ids["case_b"])))
    revised = session.revise_understanding(
        stage,
        understanding_id=ids["understanding_x"],
        diff=("@@\n-本人負責事件初判與交付前核對。\n"
              "+本人負責事件初判、夜間隔離與交付前核對。"),
        supporting_case_ids=[ids["case_a"], ids["case_b"]],
        route_note=None,
    )

    assert "夜間隔離" in session.read_understanding(
        revised, ids["understanding_x"],
    ).content
    assert revised.changes[-1].kind == "revise"


def test_revalidate_refreshes_support_without_creating_a_semantic_change():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    for case_id in (ids["case_a"], ids["case_b"]):
        stage, _case = session.observe_case(stage, case_id)
    stage, _understanding = session.observe_understanding(stage, ids["understanding_x"])

    revalidated = session.revalidate_understanding(
        stage,
        understanding_id=ids["understanding_x"],
        supporting_case_ids=[ids["case_a"], ids["case_b"]],
    )

    assert not revalidated.changed
    assert revalidated.upserts == ()
    assert revalidated.binding_updates[0].supporting_case_ids == tuple(sorted((
        ids["case_a"], ids["case_b"],
    )))
    assert revalidated.changes[-1].kind == "revalidate"


def _two_understandings_fixture():
    source = ExampleSource()
    source.second_reference = "conversation:document-a:second"
    source.material[source.second_reference] = "使用者補充：夜間事件需要先隔離設備。"
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_a, case_b, understanding_x, understanding_y, merged_id = _ids(5)
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.second_reference,
        case_guide=(
            f"- [故障案例](/memory/cases/items/{case_a}.md)\n"
            f"- [交付案例](/memory/cases/items/{case_b}.md)"
        ),
        cases=(
            CaseArtifact(case_a, "本人先做故障初判。", (source.reference,)),
            CaseArtifact(case_b, "本人核對交付內容。", (source.reference,)),
        ),
        understanding_guide=(
            f"- [事件處理](/memory/understanding/items/{understanding_x}.md)\n"
            f"- [交付核對](/memory/understanding/items/{understanding_y}.md)"
        ),
        understandings=(
            WorkUnderstandingArtifact(understanding_x, "本人負責事件初判。", (case_a,)),
            WorkUnderstandingArtifact(understanding_y, "本人負責交付核對。", (case_b,)),
        ),
    )
    case_session = CaseMaintenanceSession(artifacts)
    case_stage = case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=source.second_reference,
    )
    case_stage = _register_case_evidence(
        case_session, case_stage, source.reference, source.second_reference)
    case_stage, _case = case_session.observe_case(case_stage, case_a)
    case_stage = case_session.revise_case(
        case_stage,
        case_id=case_a,
        diff="@@\n-本人先做故障初判。\n+本人先做故障初判；夜間先隔離設備。",
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    case_stage = case_session.finish(case_stage)
    return artifacts, case_session, case_stage, {
        "case_a": case_a,
        "case_b": case_b,
        "understanding_x": understanding_x,
        "understanding_y": understanding_y,
        "merged_id": merged_id,
    }


def test_split_and_merge_replace_published_understanding_ids_and_routes():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    split_ids = _ids(2)
    split_iter = iter(split_ids)
    split_session = UnderstandingMaintenanceSession(
        artifacts, case_session, id_factory=lambda: next(split_iter),
    )
    stage = split_session.open(case_stage)
    for case_id in (ids["case_a"], ids["case_b"]):
        stage, _case = split_session.observe_case(stage, case_id)
    stage, _understanding = split_session.observe_understanding(
        stage, ids["understanding_x"],
    )

    split = split_session.split_understanding(
        stage,
        understanding_id=ids["understanding_x"],
        replacements=[
            UnderstandingReplacementInput(
                content="本人負責事件初判與夜間隔離。",
                supporting_case_ids=[ids["case_a"]],
                route_note="事件初判與夜間隔離",
            ),
            UnderstandingReplacementInput(
                content="本人負責交付前核對。",
                supporting_case_ids=[ids["case_b"]],
                route_note="交付前核對",
            ),
        ],
    )

    assert split.current_understanding_ids == tuple(sorted(split_ids))
    assert split.supersessions[0].retired_id == ids["understanding_x"]
    assert set(split.supersessions[0].current_ids) == set(split_ids)
    assert f"/{ids['understanding_x']}.md" not in split.understanding_guide

    artifacts2, case_session2, case_stage2, ids2 = _two_understandings_fixture()
    merge_session = UnderstandingMaintenanceSession(
        artifacts2, case_session2, id_factory=lambda: ids2["merged_id"],
    )
    merge_stage = merge_session.open(case_stage2)
    for case_id in (ids2["case_a"], ids2["case_b"]):
        merge_stage, _case = merge_session.observe_case(merge_stage, case_id)
    for understanding_id in (ids2["understanding_x"], ids2["understanding_y"]):
        merge_stage, _item = merge_session.observe_understanding(
            merge_stage, understanding_id,
        )
    merged = merge_session.merge_understandings(
        merge_stage,
        understanding_ids=[ids2["understanding_x"], ids2["understanding_y"]],
        content="本人負責事件初判、夜間隔離與交付前核對。",
        supporting_case_ids=[ids2["case_a"], ids2["case_b"]],
        route_note="事件處理與交付核對",
    )

    assert merged.current_understanding_ids == (ids2["merged_id"],)
    assert {item.retired_id for item in merged.supersessions} == {
        ids2["understanding_x"], ids2["understanding_y"],
    }
    assert all(item.current_ids == (ids2["merged_id"],)
               for item in merged.supersessions)


def test_finish_requires_changed_cases_and_direct_impacts_then_allows_semantic_no_op():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)

    with pytest.raises(UnderstandingMaintenanceError, match="changed B1 cases"):
        session.finish(stage)

    for case_id in stage.required_case_ids:
        stage, _case = session.observe_case(stage, case_id)
    with pytest.raises(UnderstandingMaintenanceError, match="affected work understandings"):
        session.finish(stage)

    stage, _item = session.observe_understanding(stage, ids["understanding_x"])
    stage, _case = session.observe_case(stage, ids["case_b"])
    stage = session.revalidate_understanding(
        stage,
        understanding_id=ids["understanding_x"],
        supporting_case_ids=[ids["case_a"], ids["case_b"]],
    )
    completed = session.finish(stage)

    assert completed.completed and completed.outcome == "no_op"
    assert session.current_understandings(completed) == (
        WorkUnderstandingArtifact(
            ids["understanding_x"],
            "本人負責事件初判與交付前核對。",
            tuple(sorted((ids["case_a"], ids["case_b"]))),
        ),
    )


def test_retire_and_route_are_controlled_and_outcome_must_match_semantic_change():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    for case_id in stage.required_case_ids:
        stage, _case = session.observe_case(stage, case_id)
    stage, _item = session.observe_understanding(stage, ids["understanding_x"])

    routed = session.set_understanding_route(
        stage,
        understanding_id=ids["understanding_x"],
        route_note="事件初判、交付核對；夜間隔離待整合",
    )
    with pytest.raises(UnderstandingMaintenanceError, match="affected work understandings"):
        session.finish(routed)

    routed, _case = session.observe_case(routed, ids["case_b"])
    routed = session.revalidate_understanding(
        routed,
        understanding_id=ids["understanding_x"],
        supporting_case_ids=[ids["case_a"], ids["case_b"]],
    )
    completed_route = session.finish(routed)
    assert completed_route.outcome == "changed"

    retired = session.retire_understanding(stage, understanding_id=ids["understanding_x"])
    completed = session.finish(retired)
    assert completed.current_understanding_ids == ()
    assert completed.understanding_guide == ""


def test_route_update_requires_reading_the_published_understanding():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)

    with pytest.raises(UnderstandingMaintenanceError, match="Read the current work understanding"):
        session.set_understanding_route(
            stage,
            understanding_id=ids["understanding_x"],
            route_note="事件初判、交付核對與夜間隔離",
        )

    stage, _item = session.observe_understanding(stage, ids["understanding_x"])
    routed = session.set_understanding_route(
        stage,
        understanding_id=ids["understanding_x"],
        route_note="事件初判、交付核對與夜間隔離",
    )

    assert "事件初判、交付核對與夜間隔離" in routed.understanding_guide


def test_tool_schemas_hide_runtime_fields_and_expose_only_semantic_operations():
    _source, artifacts, case_session, _case_stage, _ids_value = _fixture()
    tools = understanding_maintenance_tools(
        _source,
        UnderstandingMaintenanceSession(artifacts, case_session),
    )

    assert [item.name for item in tools] == [
        "read_case", "read_work_understanding", "create_work_understanding",
        "revise_work_understanding", "revalidate_work_understanding",
        "split_work_understanding", "merge_work_understandings",
        "retire_work_understanding", "set_work_understanding_route",
        "finish_understanding_maintenance",
    ]
    forbidden = {
        "runtime", "document_id", "base_revision", "version", "path", "digest",
        "operation_id", "understanding_stage", "case_stage", "source_reference",
        "offset", "outcome",
    }
    for item in tools:
        schema = item.tool_call_schema.model_json_schema()
        assert forbidden.isdisjoint(schema.get("properties", {}))
        strict = convert_to_openai_tool(item, strict=True)["function"]
        assert strict["strict"] is True
        assert strict["parameters"]["additionalProperties"] is False
    assert tools[-1].tool_call_schema.model_json_schema().get("properties") == {}

    source_tools = understanding_workflow_tools(
        _source, UnderstandingMaintenanceSession(artifacts, case_session),
    )
    read_schema = source_tools[0].tool_call_schema.model_json_schema()
    assert set(read_schema["properties"]) == {"evidence_key"}
    rework_schema = json.dumps(
        source_tools[1].tool_call_schema.model_json_schema(), ensure_ascii=False,
    )
    assert '"evidence_key"' in rework_schema and '"reason"' in rework_schema
    assert '"source_reference"' not in rework_schema
    assert '"case_id"' not in rework_schema
    assert '"offset"' not in rework_schema


@pytest.mark.parametrize("factory", [
    understanding_maintenance_tools,
    understanding_workflow_tools,
])
def test_understanding_tools_reject_a_source_reader_from_another_document(factory):
    _source, artifacts, case_session, _case_stage, _ids_value = _fixture()

    with pytest.raises(ValueError, match="different documents"):
        factory(
            ExampleSource("document-b"),
            UnderstandingMaintenanceSession(artifacts, case_session),
        )


@pytest.mark.parametrize("name,args", [
    ("finish_understanding_maintenance", {"outcome": "no_op"}),
    ("read_case_source", {"evidence_key": "E1", "offset": 0}),
    ("request_case_rework", {"issues": [{
        "evidence_key": "E1", "source_reference": "conversation:document-a:original",
        "reason": "不應接受 Runtime 欄位。",
    }]}),
])
def test_b2_toolnode_rejects_model_supplied_runtime_fields(name, args):
    source, artifacts, case_session, case_stage, _ids_value = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    stage = session.open(case_stage)
    tools = [
        *understanding_maintenance_tools(source, session),
        *understanding_workflow_tools(source, session),
    ]

    result = _graph(tools).invoke({
        "messages": [_call(name, args, f"invalid-{name}")],
        "understanding_stage": stage.to_dict(),
    })

    assert session.load(result["understanding_stage"]) == stage
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage) and message.status == "error"


def test_native_toolnode_checkpoints_reads_then_create_on_the_same_b2_stage():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    new_understanding = str(uuid4())
    session = UnderstandingMaintenanceSession(
        artifacts, case_session, id_factory=lambda: new_understanding,
    )
    saver = InMemorySaver()
    graph = _graph(understanding_maintenance_tools(_source, session), saver=saver)
    config = {"configurable": {"thread_id": "b2-understanding-test"}}
    initial = session.open(case_stage)

    read = graph.invoke({
        "messages": [HumanMessage("B1 candidate fixed by Runtime"), _call(
            "read_case", {"case_id": ids["new_case"]}, "read-case",
        )],
        "understanding_stage": initial.to_dict(),
    }, config, durability="sync")
    observed = session.load(read["understanding_stage"])
    assert ids["new_case"] in observed.read_case_ids

    created = graph.invoke({
        "messages": [_call("create_work_understanding", {
            "content": "本人負責核對付款條件與例外。",
            "supporting_case_ids": [ids["new_case"]],
            "route_note": "付款條件與例外核對",
        }, "create")],
    }, config, durability="sync")
    staged = session.load(created["understanding_stage"])
    assert new_understanding in staged.current_understanding_ids
    assert isinstance(created["messages"][-1], ToolMessage)
    assert json.loads(created["messages"][-1].content)["effect"] == "staged"
    assert session.load(graph.get_state(config).values["understanding_stage"]) == staged


def test_tool_error_and_parallel_calls_leave_the_b2_stage_unchanged():
    _source, artifacts, case_session, case_stage, ids = _fixture()
    session = UnderstandingMaintenanceSession(artifacts, case_session)
    initial = session.open(case_stage)
    tools = understanding_maintenance_tools(_source, session)

    failed = _graph(tools).invoke({
        "messages": [_call("create_work_understanding", {
            "content": "不應成功。",
            "supporting_case_ids": [ids["new_case"]],
            "route_note": "未讀案例",
        })],
        "understanding_stage": initial.to_dict(),
    })
    assert session.load(failed["understanding_stage"]) == initial
    assert json.loads(failed["messages"][-1].content)["effect"] == "unchanged"

    calls = [
        {"name": "read_case", "args": {"case_id": ids["case_a"]},
         "id": "read-a", "type": "tool_call"},
        {"name": "read_case", "args": {"case_id": ids["new_case"]},
         "id": "read-b", "type": "tool_call"},
    ]
    parallel = _graph(tools).invoke({
        "messages": [AIMessage("", id="parallel", tool_calls=calls)],
        "understanding_stage": initial.to_dict(),
    })
    assert session.load(parallel["understanding_stage"]) == initial
    errors = [item for item in parallel["messages"] if isinstance(item, ToolMessage)]
    assert len(errors) == 2
    assert all(json.loads(item.content)["error"] == "multiple_understanding_tool_calls"
               for item in errors)
