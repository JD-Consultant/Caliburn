"""Layered bundle authority tests; no model, prompt, dispatcher, or UI."""

from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine

from caliburn_memory import (
    CaseArtifact, MemoryArtifacts, PublicationStore, StalePublication, Supersession,
    WorkUnderstandingArtifact,
)
from caliburn_memory.bundle import CASE_GUIDE_PATH
from conftest import ExampleSource


def ids():
    return str(uuid4()), str(uuid4()), str(uuid4())


def save_example(artifacts: MemoryArtifacts, *, base_revision: int = 0, base_version=None,
                 case_text: str = "本人先做故障初判。"):
    if base_version is None:
        case_id, understanding_id, _unused = ids()
    else:
        manifest = artifacts.bundle_manifest(base_version)
        case_id = manifest.cases[0].case_id
        understanding_id = manifest.understandings[0].understanding_id
    case_path = f"/memory/cases/items/{case_id}.md"
    understanding_path = f"/memory/understanding/items/{understanding_id}.md"
    return artifacts.save_bundle(
        base_publication_revision=base_revision,
        case_guide=f"故障處理：[{case_id}]({case_path})",
        cases=(CaseArtifact(case_id, case_text, (artifacts.source.reference,)),),
        understanding_guide=f"故障初判：[{understanding_id}]({understanding_path})",
        understandings=(WorkUnderstandingArtifact(
            understanding_id,
            f"穩定責任：先做初判；證據案例 [{case_id}]({case_path})。",
            (case_id,),
        ),),
        base_version=base_version,
    ), case_id, understanding_id


def test_bundle_round_trip_keeps_sources_and_exact_case_bindings():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    version, case_id, understanding_id = save_example(artifacts)

    manifest = artifacts.bundle_manifest(version)
    case = artifacts.case(version, case_id)
    understanding = artifacts.understanding(version, understanding_id)

    assert manifest.document_id == source.document_id
    assert manifest.base_publication_revision == 0
    assert artifacts.case_guide(version).startswith("故障處理")
    assert artifacts.understanding_guide(version).startswith("故障初判")
    assert case.content == "本人先做故障初判。"
    assert case.source_references == (source.reference,)
    assert len(understanding.case_bindings) == 1
    assert understanding.case_bindings[0].case_id == case_id
    assert understanding.case_bindings[0].case_digest == manifest.cases[0].digest
    assert artifacts.reader(version).read(CASE_GUIDE_PATH).file_data["content"].startswith("故障處理")

    source.reads.clear()
    artifacts.bundle_manifest(version)
    artifacts.understanding(version, understanding_id)
    assert source.reads == []  # manifest/understanding lookup does not deep-read case evidence
    artifacts.case(version, case_id)
    assert source.reads == [source.reference]


def test_bundle_rejects_unknown_support_source_scope_and_model_chosen_identity():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_id, understanding_id, unknown_case_id = ids()
    case = CaseArtifact(case_id, "案例", (source.reference,))

    with pytest.raises(ValueError, match="Unknown supporting"):
        artifacts.save_bundle(base_publication_revision=0, case_guide="案例", cases=(case,),
            understanding_guide="理解", understandings=(
                WorkUnderstandingArtifact(understanding_id, "理解", (unknown_case_id,)),))
    with pytest.raises(ValueError, match="reference|document"):
        artifacts.save_bundle(base_publication_revision=0, case_guide="案例", cases=(
            replace(case, source_references=("conversation:document-b:original",)),),
            understanding_guide="理解", understandings=(
                WorkUnderstandingArtifact(understanding_id, "理解", (case_id,)),))
    with pytest.raises(ValueError, match="runtime UUID"):
        artifacts.save_bundle(base_publication_revision=0, case_guide="案例", cases=(
            replace(case, case_id="CASE-A"),), understanding_guide="", understandings=())
    with pytest.raises(ValueError, match="guide does not route"):
        artifacts.save_bundle(base_publication_revision=0, case_guide="沒有案例入口", cases=(case,),
            understanding_guide="", understandings=())


def test_bundle_supersession_only_targets_current_same_kind_identity():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    retired_case_id, retired_understanding_id, _unused = ids()
    retired_case_path = f"/memory/cases/items/{retired_case_id}.md"
    retired_understanding_path = f"/memory/understanding/items/{retired_understanding_id}.md"
    base = artifacts.save_bundle(
        base_publication_revision=0,
        case_guide=f"舊案例：[{retired_case_id}]({retired_case_path})",
        cases=(CaseArtifact(retired_case_id, "舊案例", (source.reference,)),),
        understanding_guide=f"舊理解：[{retired_understanding_id}]({retired_understanding_path})",
        understandings=(WorkUnderstandingArtifact(
            retired_understanding_id, "舊理解", (retired_case_id,)),),
    )
    case_id, understanding_id, _unused = ids()
    case_path = f"/memory/cases/items/{case_id}.md"
    understanding_path = f"/memory/understanding/items/{understanding_id}.md"
    version = artifacts.save_bundle(
        base_publication_revision=1,
        case_guide=f"目前案例：[{case_id}]({case_path})",
        cases=(CaseArtifact(case_id, "目前案例", (source.reference,)),),
        understanding_guide=f"目前理解：[{understanding_id}]({understanding_path})",
        understandings=(WorkUnderstandingArtifact(understanding_id, "目前理解", (case_id,)),),
        supersessions=(
            Supersession("case", retired_case_id, (case_id,)),
            Supersession("understanding", retired_understanding_id, (understanding_id,)),
        ),
        base_version=base,
    )
    assert artifacts.bundle_manifest(version).supersessions == (
        Supersession("case", retired_case_id, (case_id,)),
        Supersession("understanding", retired_understanding_id, (understanding_id,)),
    )
    retired_without_replacement = artifacts.save_bundle(
        base_publication_revision=1,
        case_guide=f"舊案例：[{retired_case_id}]({retired_case_path})",
        cases=(CaseArtifact(retired_case_id, "舊案例", (source.reference,)),),
        understanding_guide="",
        understandings=(),
        supersessions=(Supersession("understanding", retired_understanding_id, ()),),
        base_version=base,
    )
    assert artifacts.bundle_manifest(retired_without_replacement).supersessions == (
        Supersession("understanding", retired_understanding_id, ()),)
    with pytest.raises(ValueError, match="unknown current"):
        artifacts.save_bundle(
            base_publication_revision=1, case_guide=f"目前案例：[{case_id}]({case_path})",
            cases=(CaseArtifact(case_id, "目前案例", (source.reference,)),),
            understanding_guide=f"目前理解：[{understanding_id}]({understanding_path})",
            understandings=(WorkUnderstandingArtifact(understanding_id, "目前理解", (case_id,)),),
            supersessions=(
                Supersession("case", retired_case_id, (str(uuid4()),)),
                Supersession("understanding", retired_understanding_id, (understanding_id,)),
            ),
            base_version=base,
        )


def test_bundle_bytes_are_verified_before_atomic_publication_and_stale_loses():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    publication = PublicationStore(engine, artifacts)
    publication.setup()
    try:
        first_version, _case_id, _understanding_id = save_example(artifacts)
        first = publication.publish(publication.prepare(first_version, expected_revision=0, kind="repair"))
        with pytest.raises(ValueError, match="different base"):
            publication.prepare(first_version, expected_revision=first.revision, kind="repair")
        unrelated_base, _case_id, _understanding_id = save_example(artifacts)
        wrong_lineage, _case_id, _understanding_id = save_example(
            artifacts, base_revision=first.revision, base_version=unrelated_base,
            case_text="建立在錯誤 bundle 上")
        with pytest.raises(StalePublication) as lineage_error:
            publication.publish(publication.prepare(
                wrong_lineage, expected_revision=first.revision, kind="repair"))
        assert lineage_error.value.current == first
        stale_version, _case_id, _understanding_id = save_example(
            artifacts, base_revision=first.revision, base_version=first.memory, case_text="背景候選")
        stale = publication.prepare(stale_version, expected_revision=first.revision, kind="repair")
        winner_version, _case_id, _understanding_id = save_example(
            artifacts, base_revision=first.revision, base_version=first.memory, case_text="即時更正")
        winner = publication.publish(publication.prepare(
            winner_version, expected_revision=first.revision, kind="repair",
            repair_sources=(source.reference,)))
        with pytest.raises(StalePublication) as error:
            publication.publish(stale)
        assert error.value.current == winner
        assert publication.current() == winner
        assert publication.receipt(stale.operation_id) is None
    finally:
        engine.dispose()


def test_bundle_tamper_and_cross_document_reads_are_rejected():
    store, source = InMemoryStore(), ExampleSource()
    artifacts = MemoryArtifacts(store, source.document_id, source=source)
    version, case_id, _understanding_id = save_example(artifacts)
    other = MemoryArtifacts(store, "document-b")
    with pytest.raises(ValueError, match="document"):
        other.bundle_manifest(version)

    backend = artifacts._backend("versions", version.version_id)
    assert not backend.write(f"/memory/cases/items/{case_id}.md", "遭到竄改").error
    with pytest.raises(ValueError, match="changed|invalid"):
        artifacts.verify_version(version)
