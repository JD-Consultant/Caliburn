"""Layered C repair: one full bundle, existing identities only, zero model calls."""
from dataclasses import asdict
from uuid import uuid4

from langgraph.store.memory import InMemoryStore
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from caliburn_memory import (
    CaseArtifact, LayeredRepairWorkflow, MemoryArtifacts, MemoryVersion,
    PublicationStore, PublishRequest, WorkUnderstandingArtifact,
)
from conftest import ExampleSource


def harness():
    document = "document-a"
    source = ExampleSource(document)
    artifacts = MemoryArtifacts(InMemoryStore(), document, source=source)
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    publication = PublicationStore(engine, artifacts)
    publication.setup()
    case_id, peer_id, understanding_id, other_id = (str(uuid4()) for _ in range(4))
    case_path = f"/memory/cases/items/{case_id}.md"
    peer_path = f"/memory/cases/items/{peer_id}.md"
    understanding_path = f"/memory/understanding/items/{understanding_id}.md"
    other_path = f"/memory/understanding/items/{other_id}.md"
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=source.context_reference,
        case_guide=(
            f"- [設備異常]({case_path}) — 通報與維修\n"
            f"- [日常巡檢]({peer_path}) — 固定巡查"
        ),
        cases=(
            CaseArtifact(case_id, "本人通報異常並負責設備維修。", (source.reference,)),
            CaseArtifact(peer_id, "本人每日巡查設備。", (source.reference,)),
        ),
        understanding_guide=(
            f"- [異常處理]({understanding_path}) — 異常處理責任\n"
            f"- [例行巡檢]({other_path}) — 巡檢責任"
        ),
        understandings=(
            WorkUnderstandingArtifact(
                understanding_id, "本人穩定負責異常通報與維修。", (case_id, peer_id),
            ),
            WorkUnderstandingArtifact(other_id, "本人穩定負責每日巡檢。", (peer_id,)),
        ),
    )
    head = publication.publish(publication.prepare(
        version, expected_revision=0, kind="consolidation",
        processed_source=source.reference,
    ))
    workflow = LayeredRepairWorkflow(artifacts, publication, source)
    return {
        "engine": engine, "source": source, "artifacts": artifacts,
        "publication": publication, "head": head, "workflow": workflow,
        "case_id": case_id, "peer_id": peer_id,
        "understanding_id": understanding_id, "other_id": other_id,
    }


def repair(item, *, action="revise"):
    update = {
        "understanding_id": item["understanding_id"],
        "action": action,
        "diff": (
            "@@\n-本人穩定負責異常通報與維修。\n+本人穩定負責異常通報；設備維修由外包負責。"
            if action == "revise" else None
        ),
        "supporting_case_ids": [item["case_id"], item["peer_id"]],
        "route_note": None,
    }
    return {
        "case_id": item["case_id"],
        "case_diff": (
            "@@\n-本人通報異常並負責設備維修。\n+本人通報異常並負責設備維修；完成後補記結果。"
            if action == "revalidate" else
            "@@\n-本人通報異常並負責設備維修。\n+本人只通報異常；設備維修由外包負責。"
        ),
        "case_route_note": None,
        "remove_source_references": [],
        "understanding_updates": [update],
    }


def invoke(item, value):
    return item["workflow"].graph.invoke({
        "operation_id": str(uuid4()),
        "base": asdict(item["head"]),
        "source_reference": item["source"].context_reference,
        "repair": value,
    })


def test_case_and_every_direct_understanding_publish_as_one_bundle():
    item = harness()
    try:
        result = invoke(item, repair(item))

        assert result["outcome"]["status"] == "applied"
        assert item["publication"].current().revision == item["head"].revision + 1
        applied = item["publication"].current().memory
        case = item["artifacts"].case(applied, item["case_id"])
        understanding = item["artifacts"].understanding(applied, item["understanding_id"])
        other = item["artifacts"].understanding(applied, item["other_id"])
        assert "只通報異常" in case.content
        assert case.source_references == (
            item["source"].reference, item["source"].context_reference,
        )
        assert "維修由外包" in understanding.content
        assert {binding.case_id for binding in understanding.case_bindings} == {
            item["case_id"], item["peer_id"],
        }
        assert other.content == "本人穩定負責每日巡檢。"
        saved = dict(result["request"])
        saved["memory"] = MemoryVersion(**saved["memory"])
        saved["repair_sources"] = tuple(saved["repair_sources"])
        reconciled = item["workflow"].reconcile(PublishRequest(**saved))
        assert reconciled["status"] == "applied"
        assert reconciled["applied_head"] == result["outcome"]["applied_head"]
    finally:
        item["engine"].dispose()


def test_revalidate_refreshes_binding_without_fabricating_a_text_change():
    item = harness()
    try:
        result = invoke(item, repair(item, action="revalidate"))

        assert result["outcome"]["status"] == "applied"
        applied = item["publication"].current().memory
        understanding = item["artifacts"].understanding(applied, item["understanding_id"])
        assert understanding.content == "本人穩定負責異常通報與維修。"
        manifest = item["artifacts"].bundle_manifest(applied)
        expected = next(entry.digest for entry in manifest.cases
                        if entry.case_id == item["case_id"])
        actual = next(binding.case_digest for binding in understanding.case_bindings
                      if binding.case_id == item["case_id"])
        assert actual == expected
    finally:
        item["engine"].dispose()


def test_missing_direct_understanding_action_fails_without_partial_publication():
    item = harness()
    try:
        attempted = repair(item)
        attempted["understanding_updates"] = []

        result = invoke(item, attempted)

        assert result["outcome"]["status"] == "scope_too_broad"
        assert item["publication"].current() == item["head"]
        assert item["publication"].receipt(result["operation_id"]) is None
    finally:
        item["engine"].dispose()


def test_stale_base_is_rejected_before_any_candidate_is_published():
    item = harness()
    try:
        competing = item["artifacts"].save_bundle(
            base_publication_revision=1,
            base_version=item["head"].memory,
            evidence_through_reference=item["source"].context_reference,
            case_guide=item["artifacts"].case_guide(item["head"].memory),
            cases=tuple(CaseArtifact(entry.case_id,
                item["artifacts"].case(item["head"].memory, entry.case_id).content,
                item["artifacts"].case(item["head"].memory, entry.case_id).source_references)
                for entry in item["artifacts"].bundle_manifest(item["head"].memory).cases),
            understanding_guide=item["artifacts"].understanding_guide(item["head"].memory),
            understandings=tuple(WorkUnderstandingArtifact(entry.understanding_id,
                item["artifacts"].understanding(item["head"].memory, entry.understanding_id).content,
                tuple(binding.case_id for binding in item["artifacts"].understanding(
                    item["head"].memory, entry.understanding_id).case_bindings))
                for entry in item["artifacts"].bundle_manifest(item["head"].memory).understandings),
        )
        newer = item["publication"].publish(item["publication"].prepare(
            competing, expected_revision=1, kind="repair",
            repair_sources=(item["source"].context_reference,),
        ))

        result = invoke(item, repair(item))

        assert result["outcome"]["status"] == "stale"
        assert item["publication"].current() == newer
    finally:
        item["engine"].dispose()


def test_an_already_attached_explicit_correction_source_cannot_be_removed():
    item = harness()
    try:
        assert invoke(item, repair(item))["outcome"]["status"] == "applied"
        item["head"] = item["publication"].current()
        attempted = {
            "case_id": item["case_id"],
            "case_diff": (
                "@@\n-本人只通報異常；設備維修由外包負責。\n"
                "+本人只通報異常；設備維修由外包負責，並記錄結果。"
            ),
            "case_route_note": None,
            "remove_source_references": [item["source"].context_reference],
            "understanding_updates": [{
                "understanding_id": item["understanding_id"],
                "action": "revalidate",
                "diff": None,
                "supporting_case_ids": [item["case_id"], item["peer_id"]],
                "route_note": None,
            }],
        }

        result = invoke(item, attempted)

        assert result["outcome"]["status"] == "invalid_edit"
        assert item["publication"].current() == item["head"]
    finally:
        item["engine"].dispose()
