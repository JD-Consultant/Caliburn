"""Bounded item revision joins existing JD owners atomically and replays their receipts."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.areas import CreateArea, EditJdAreas
from caliburn.features.job_description.capabilities import (
    CapabilityKind,
    CreateCapability,
    EditJdCapabilities,
)
from caliburn.features.job_description.collaborators import CreateCollaborator, EditJdCollaborators
from caliburn.features.job_description.conditions import (
    ConditionKind,
    CreateCondition,
    EditJdConditions,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import InvalidJdSourceError, SourceTargetKind
from caliburn.features.job_description.tasks import CreateTask, DetailKind, EditJdTasks
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_item_revision import (
    AddItemDetail,
    AddItemSource,
    AlignItemSource,
    CapabilitySourceTarget,
    DetailSourceTarget,
    ItemFieldChange,
    ItemSourceTarget,
    JdItemRevisionWorkflow,
    PreparedItemRevision,
    RemoveItemDetail,
    ReorderItemCapability,
    ReviseItemDetail,
    ReviseItemInput,
    SetItemCapability,
)
from caliburn.workflows.jd_sources import CurrentInputSourceSelection
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.fixtures.consultant_turn import start_consultant_turn as start
from tests.fixtures.consultant_turn import transact

pytestmark = pytest.mark.postgres


def setup_item(client):
    writer = start(client)
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    initial = client.portal.call(candidates.start, writer)
    position = client.portal.call(
        candidates.edit,
        writer,
        initial.scope,
        EditJdTasks(
            uuid4(), initial.revision_id, CreateTask(None, "頁面", "原描述", ("舊成果",), ())
        ),
    )
    for name in ("React", "React"):
        position = client.portal.call(
            candidates.edit,
            writer,
            position.scope,
            EditJdCapabilities(
                uuid4(), position.revision_id, CreateCapability(CapabilityKind.SKILL, name, None)
            ),
        )
    return writer, candidates, client.portal.call(candidates.read, writer.scope)


def revise(client, writer, intent):
    workflow = JdItemRevisionWorkflow(client.app.state.database.sessions)

    async def prepare():
        return await workflow.prepare(
            PublishedMemoryRead(writer.scope, None, 1),
            command_id=uuid4(),
            intent=intent,
        )

    prepared = client.portal.call(prepare)
    return workflow, prepared, client.portal.call(workflow.execute, writer, prepared)


def sources(client, writer, preview):
    return transact(
        client,
        lambda s: source_persistence.read_source_references(
            s,
            writer.scope.job_file_id,
            preview.position.revision_id,
        ),
    )


def test_task_revision_preserves_identity_precise_evidence_and_original_replay(client: TestClient):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    first, second = before.work.capabilities
    source = CurrentInputSourceSelection()
    workflow, prepared, result = revise(
        client,
        writer,
        ReviseItemInput(
            jd_read_ref(task),
            (
                ItemFieldChange("description", "新描述"),
                ReviseItemDetail(jd_read_ref(task.details[0]), "修訂成果"),
                AddItemDetail(DetailKind.REQUIREMENT, "需求", (source,)),
                AddItemDetail(DetailKind.OUTCOME, "成果", (source,)),
                SetItemCapability(jd_read_ref(first), True, (source,)),
                SetItemCapability(jd_read_ref(second), True),
                AddItemSource(ItemSourceTarget(), source),
                AddItemSource(DetailSourceTarget(jd_read_ref(task.details[0])), source),
            ),
        ),
    )
    after = client.portal.call(candidates.read, writer.scope)
    assert result.effect == "updated"
    revised = after.work.tasks[0]
    assert revised.task_id == task.task_id
    assert revised.description == "新描述"
    assert revised.details[0].detail_id == task.details[0].detail_id
    assert [d.text for d in revised.details] == ["修訂成果", "成果", "需求"]
    refs = sources(client, writer, after)
    assert len(refs) == 5
    assert {r.target.kind for r in refs} == {
        SourceTargetKind.TASK,
        SourceTargetKind.DETAIL,
        SourceTargetKind.TASK_CAPABILITY,
    }
    assert all(not r.needs_review for r in refs)
    # A later edit must not turn original replay into current-head interpretation.
    revise(client, writer, ReviseItemInput(jd_read_ref(task), (ItemFieldChange("title", "後續"),)))
    later = client.portal.call(candidates.read, writer.scope)
    checkpoint = TypeAdapter(PreparedItemRevision)
    restored = checkpoint.validate_json(checkpoint.dump_json(prepared), strict=True)
    assert restored == prepared
    assert client.portal.call(workflow.execute, writer, restored) == result
    assert client.portal.call(candidates.read, writer.scope).position == later.position


def test_text_and_alignment_apply_to_final_content_then_unlink_cleans_only_relation(
    client: TestClient,
):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    first, second = before.work.capabilities
    source = CurrentInputSourceSelection()
    revise(
        client,
        writer,
        ReviseItemInput(
            jd_read_ref(task),
            (
                AddItemSource(ItemSourceTarget(), source),
                SetItemCapability(jd_read_ref(first), True, (source,)),
                SetItemCapability(jd_read_ref(second), True),
            ),
        ),
    )
    before = client.portal.call(candidates.read, writer.scope)
    citation = next(
        r for r in sources(client, writer, before) if r.target.kind == SourceTargetKind.TASK
    )
    revise(
        client,
        writer,
        ReviseItemInput(
            jd_read_ref(task),
            (
                AlignItemSource(ItemSourceTarget(), f"citation_{citation.citation_id.hex}"),
                ItemFieldChange("description", "已重評的文字"),
                ReorderItemCapability(jd_read_ref(second), "first"),
            ),
        ),
    )
    after = client.portal.call(candidates.read, writer.scope)
    refs = sources(client, writer, after)
    assert not next(r for r in refs if r.citation_id == citation.citation_id).needs_review
    assert next(r for r in refs if r.target.kind == SourceTargetKind.TASK_CAPABILITY).needs_review
    assert [link.capability_id for link in after.work.task_links] == [
        second.capability_id,
        first.capability_id,
    ]
    revise(
        client,
        writer,
        ReviseItemInput(jd_read_ref(task), (SetItemCapability(jd_read_ref(first), False),)),
    )
    after = client.portal.call(candidates.read, writer.scope)
    assert len(after.work.capabilities) == 2
    assert len(sources(client, writer, after)) == 1


def test_late_domain_rejection_rolls_back_text_and_rejects_conflicting_effects(client: TestClient):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    source = CurrentInputSourceSelection()
    # Existing-but-unlinked relation: shape and source are valid, the final source owner is not.
    with pytest.raises(InvalidJdSourceError):
        revise(
            client,
            writer,
            ReviseItemInput(
                jd_read_ref(task),
                (
                    ItemFieldChange("description", "不得留下"),
                    AddItemSource(
                        CapabilitySourceTarget(jd_read_ref(before.work.capabilities[0])), source
                    ),
                ),
            ),
        )
    assert client.portal.call(candidates.read, writer.scope).position == before.position
    for changes in (
        (ItemFieldChange("title", "甲"), ItemFieldChange("title", "乙")),
        (
            RemoveItemDetail(jd_read_ref(task.details[0])),
            AddItemSource(DetailSourceTarget(jd_read_ref(task.details[0])), source),
        ),
        (
            SetItemCapability(jd_read_ref(before.work.capabilities[0]), True),
            SetItemCapability(jd_read_ref(before.work.capabilities[0]), False),
        ),
    ):
        with pytest.raises(ValueError):
            revise(client, writer, ReviseItemInput(jd_read_ref(task), changes))
        assert client.portal.call(candidates.read, writer.scope).position == before.position


def test_other_item_families_route_to_existing_owners_and_detail_delete_is_local(
    client: TestClient,
):
    writer, candidates, before = setup_item(client)
    position = before.position
    for command in (
        EditJdAreas(uuid4(), position.revision_id, CreateArea("職責", "原範圍")),
        EditJdCollaborators(uuid4(), position.revision_id, CreateCollaborator("協作", "原範圍")),
        EditJdConditions(
            uuid4(), position.revision_id, CreateCondition(ConditionKind.QUALIFICATION, "原條件")
        ),
    ):
        # Each edit uses the prior owner's actual revision, not an invented version.
        from dataclasses import replace

        position = client.portal.call(
            candidates.edit,
            writer,
            position.scope,
            replace(command, expected_revision_id=position.revision_id),
        )
    work = client.portal.call(candidates.read, writer.scope).work
    for item, field, value in (
        (work.areas[0], "scope_text", "新職責範圍"),
        (work.capabilities[0], "description", "新能力說明"),
        (work.collaborators[0], "scope_text", "新協作範圍"),
        (work.conditions[0], "text", "新条件"),
    ):
        _, _, result = revise(
            client,
            writer,
            ReviseItemInput(
                jd_read_ref(item),
                (
                    ItemFieldChange(field, value),
                    AddItemSource(ItemSourceTarget(), CurrentInputSourceSelection()),
                ),
            ),
        )
        assert result.effect == "updated"
    after = client.portal.call(candidates.read, writer.scope)
    assert after.work.areas[0].area_id == work.areas[0].area_id
    assert after.work.areas[0].scope_text == "新職責範圍"
    assert after.work.capabilities[0].description == "新能力說明"
    assert after.work.collaborators[0].scope_text == "新協作範圍"
    assert after.work.conditions[0].text == "新条件"
    assert {r.target.kind for r in sources(client, writer, after)} == {
        SourceTargetKind.AREA,
        SourceTargetKind.CAPABILITY,
        SourceTargetKind.COLLABORATOR,
        SourceTargetKind.CONDITION,
    }
    task = work.tasks[0]
    revise(
        client,
        writer,
        ReviseItemInput(jd_read_ref(task), (RemoveItemDetail(jd_read_ref(task.details[0])),)),
    )
    after = client.portal.call(candidates.read, writer.scope)
    assert after.work.tasks[0].task_id == task.task_id
    assert not after.work.tasks[0].details
    assert len(sources(client, writer, after)) == 4


def test_detail_reference_cannot_escape_its_outer_task(client: TestClient):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    client.portal.call(
        candidates.edit,
        writer,
        before.position.scope,
        EditJdTasks(
            uuid4(),
            before.position.revision_id,
            CreateTask(None, "另一任務", None, ("舊成果",), ()),
        ),
    )
    before = client.portal.call(candidates.read, writer.scope)
    other = next(t for t in before.work.tasks if t.task_id != task.task_id)
    with pytest.raises(ValueError, match="selected task"):
        revise(
            client,
            writer,
            ReviseItemInput(
                jd_read_ref(task), (ReviseItemDetail(jd_read_ref(other.details[0]), "不可跨任務"),)
            ),
        )
    assert client.portal.call(candidates.read, writer.scope).position == before.position
