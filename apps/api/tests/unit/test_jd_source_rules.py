"""Evidence stays precise and pending until explicit alignment, even after a text revert."""

from dataclasses import replace
from uuid import UUID

import pytest

from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import (
    InterviewSource,
    InvalidJdSourceError,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
    add_source_reference,
    align_source_reference,
    carry_source_references,
)
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def test_text_changes_remain_pending_after_revert_until_explicit_alignment() -> None:
    target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
    original = JdSourceReference(UUID(int=1), target, InterviewSource(UUID(int=2)))
    before = {target: ("提供前端交付",)}
    changed = {target: ("負責全部系統",)}
    pending = carry_source_references((original,), before, changed)
    reverted = carry_source_references(pending, changed, before)
    assert pending[0].needs_review and reverted[0].needs_review
    assert reverted[0].source == original.source
    assert align_source_reference(reverted[0], original.source) == original


def test_detail_and_relation_evidence_is_not_inherited_or_moved_to_parent() -> None:
    task = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=1))
    detail = JdSourceTarget(SourceTargetKind.DETAIL, item_id=UUID(int=2), task_id=UUID(int=1))
    relation = JdSourceTarget(
        SourceTargetKind.TASK_CAPABILITY, item_id=UUID(int=3), task_id=UUID(int=1)
    )
    source = InterviewSource(UUID(int=7))
    task_ref = JdSourceReference(UUID(int=10), task, source)
    detail_ref = JdSourceReference(UUID(int=11), detail, source)
    relation_ref = JdSourceReference(UUID(int=12), relation, source)
    before = {task: ("前端",), detail: ("可以驗收",), relation: ("介面知識",)}
    after = {task: ("前端",), relation: ("介面知識",)}
    assert carry_source_references((task_ref, detail_ref, relation_ref), before, after) == (
        task_ref,
        relation_ref,
    )


def test_adding_existing_memory_source_does_not_refresh_old_basis() -> None:
    target = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=1))
    old = MemorySource(MemorySourceLayer.WORK_SITUATION, UUID(int=2), UUID(int=3), UUID(int=4))
    new = replace(old, snapshot_id=UUID(int=5), revision_id=UUID(int=6))
    original = JdSourceReference(UUID(int=7), target, old, needs_review=True)
    assert add_source_reference((original,), JdSourceReference(UUID(int=8), target, new)) == (
        original,
    )
    aligned = align_source_reference(original, new)
    assert aligned.citation_id == original.citation_id
    assert aligned.source == new and not aligned.needs_review
    with pytest.raises(InvalidJdSourceError):
        align_source_reference(original, replace(new, object_id=UUID(int=9)))


def test_source_can_support_multiple_distinct_targets_with_distinct_citations() -> None:
    source = InterviewSource(UUID(int=1))
    first = JdSourceReference(
        UUID(int=2), JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=3)), source
    )
    second = JdSourceReference(
        UUID(int=4), JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=5)), source
    )
    assert add_source_reference((first,), second) == (first, second)
    with pytest.raises(InvalidJdSourceError):
        add_source_reference((first,), replace(second, citation_id=first.citation_id))


def test_unrelated_target_fields_and_missing_existing_owner_are_rejected() -> None:
    with pytest.raises(InvalidJdSourceError):
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, item_id=UUID(int=1))
    with pytest.raises(InvalidJdSourceError):
        JdSourceTarget(SourceTargetKind.DETAIL, item_id=UUID(int=1))
    target = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=1))
    citation = JdSourceReference(UUID(int=2), target, InterviewSource(UUID(int=3)))
    with pytest.raises(InvalidJdSourceError):
        carry_source_references((citation,), {}, {target: ("名稱",)})


def test_projection_separates_task_detail_definition_and_relation_meanings() -> None:
    task = WorkTask(
        UUID(int=1),
        UUID(int=2),
        None,
        "網站交付",
        "前端部分",
        (TaskDetail(UUID(int=3), DetailKind.OUTCOME, "可驗收頁面"),),
    )
    capability = Capability(UUID(int=4), UUID(int=5), CapabilityKind.SKILL, "頁面實作", "元件化")
    work = JdWorkRevision(
        UUID(int=6),
        (),
        (task,),
        (capability,),
        (TaskCapabilityLink(task.task_id, capability.capability_id),),
        (),
        (),
    )
    before = source_target_contents(JdProfile(), work)
    changed = replace(task, details=(replace(task.details[0], text="經驗收頁面"),))
    after = source_target_contents(JdProfile(), replace(work, tasks=(changed,)))
    task_target = JdSourceTarget(SourceTargetKind.TASK, task.task_id)
    detail_target = JdSourceTarget(SourceTargetKind.DETAIL, UUID(int=3), task_id=task.task_id)
    relation_target = JdSourceTarget(
        SourceTargetKind.TASK_CAPABILITY, capability.capability_id, task_id=task.task_id
    )
    assert before[task_target] == after[task_target] == ("網站交付", "前端部分")
    assert before[detail_target] != after[detail_target]
    assert before[relation_target] == after[relation_target]
    capability_changed = source_target_contents(
        JdProfile(), replace(work, capabilities=(replace(capability, description="後端實作"),))
    )
    assert capability_changed[relation_target] != before[relation_target]
