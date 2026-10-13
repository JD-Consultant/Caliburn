"""Manual changes await review; consultant analysis updates only changed JD support."""

from dataclasses import replace
from uuid import UUID

import pytest

from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityField,
    CapabilityFieldChange,
    CapabilityKind,
    ReviseCapability,
    TaskCapabilityLink,
)
from caliburn.features.job_description.compound_changes import apply_compound_changes
from caliburn.features.job_description.compound_edits import ReviseItemWithSources
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


def test_deleted_task_evidence_does_not_move_to_another_task() -> None:
    task = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=1))
    other = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=2))
    source = InterviewSource(UUID(int=7))
    task_ref = JdSourceReference(UUID(int=10), task, source)
    other_ref = JdSourceReference(UUID(int=11), other, source)
    before = {task: ("前端",), other: ("後端",)}
    after = {other: ("後端",)}
    assert carry_source_references((task_ref, other_ref), before, after) == (other_ref,)


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
        JdSourceTarget(SourceTargetKind.TASK, field=ProfileField.PURPOSE)
    target = JdSourceTarget(SourceTargetKind.TASK, item_id=UUID(int=1))
    citation = JdSourceReference(UUID(int=2), target, InterviewSource(UUID(int=3)))
    with pytest.raises(InvalidJdSourceError):
        carry_source_references((citation,), {}, {target: ("名稱",)})


def _task_support_work() -> JdWorkRevision:
    task = WorkTask(
        UUID(int=1),
        UUID(int=2),
        None,
        "網站交付",
        "前端部分",
        (TaskDetail(UUID(int=3), DetailKind.OUTCOME, "可驗收頁面"),),
    )
    capability = Capability(UUID(int=4), UUID(int=5), CapabilityKind.SKILL, "頁面實作", "元件化")
    return JdWorkRevision(
        UUID(int=6),
        (),
        (task,),
        (capability,),
        (TaskCapabilityLink(task.task_id, capability.capability_id),),
        (),
        (),
    )


def test_task_support_includes_details_and_linked_capability_content() -> None:
    work = _task_support_work()
    task, capability = work.tasks[0], work.capabilities[0]
    target = JdSourceTarget(SourceTargetKind.TASK, task.task_id)
    before = source_target_contents(JdProfile(), work)[target]
    for changed in (
        replace(
            work,
            tasks=(
                replace(
                    task,
                    details=(
                        *task.details,
                        TaskDetail(UUID(int=8), DetailKind.REQUIREMENT, "三日內交付"),
                    ),
                ),
            ),
        ),
        replace(
            work, tasks=(replace(task, details=(replace(task.details[0], text="經驗收頁面"),)),)
        ),
        replace(work, tasks=(replace(task, details=()),)),
        replace(work, task_links=()),
        replace(
            work,
            capabilities=(*work.capabilities, replace(capability, capability_id=UUID(int=9))),
            task_links=(*work.task_links, TaskCapabilityLink(task.task_id, UUID(int=9))),
        ),
        replace(work, capabilities=(replace(capability, description="後端實作"),)),
    ):
        assert source_target_contents(JdProfile(), changed)[target] != before


def test_task_support_ignores_order_and_area() -> None:
    work = _task_support_work()
    task, capability = work.tasks[0], work.capabilities[0]
    second_detail = TaskDetail(UUID(int=8), DetailKind.REQUIREMENT, "三日內交付")
    second_capability = replace(capability, capability_id=UUID(int=9), name="測試")
    work = replace(
        work,
        tasks=(replace(task, details=(*task.details, second_detail)),),
        capabilities=(capability, second_capability),
        task_links=(
            *work.task_links,
            TaskCapabilityLink(task.task_id, second_capability.capability_id),
        ),
    )
    task = work.tasks[0]
    changed = replace(
        work,
        revision_id=UUID(int=100),
        tasks=(
            replace(
                task,
                area_id=UUID(int=10),
                content_revision_id=UUID(int=11),
                details=task.details[::-1],
            ),
        ),
        task_links=work.task_links[::-1],
        capabilities=tuple(
            replace(c, content_revision_id=UUID(int=12)) for c in work.capabilities[::-1]
        ),
    )
    target = JdSourceTarget(SourceTargetKind.TASK, task.task_id)
    assert (
        source_target_contents(JdProfile(), changed)[target]
        == source_target_contents(JdProfile(), work)[target]
    )


def test_shared_capability_change_rechecks_only_its_uses() -> None:
    work = _task_support_work()
    task, capability = work.tasks[0], work.capabilities[0]
    other = replace(task, task_id=UUID(int=20), details=())
    unrelated = replace(task, task_id=UUID(int=21), details=())
    work = replace(
        work,
        tasks=(task, other, unrelated),
        task_links=(*work.task_links, TaskCapabilityLink(other.task_id, capability.capability_id)),
    )
    changed = replace(work, capabilities=(replace(capability, description="新定義"),))
    targets = tuple(JdSourceTarget(SourceTargetKind.TASK, t.task_id) for t in work.tasks)
    refs = tuple(
        JdSourceReference(UUID(int=30 + i), t, InterviewSource(UUID(int=40)))
        for i, t in enumerate(targets)
    )
    pending = carry_source_references(
        refs,
        source_target_contents(JdProfile(), work),
        source_target_contents(JdProfile(), changed),
    )
    assert tuple(r.needs_review for r in pending) == (True, True, False)
    assert align_source_reference(pending[0], pending[0].source).needs_review is False
    assert pending[1].needs_review is True


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("kind", [CapabilityKind.KNOWLEDGE, CapabilityKind.SKILL])
def test_consultant_capability_revision_reviews_affected_support_only(
    pending: bool, kind: CapabilityKind
) -> None:
    work = _task_support_work()
    task, capability = work.tasks[0], work.capabilities[0]
    capability = replace(capability, kind=kind)
    work = replace(work, capabilities=(capability,))
    other = replace(task, task_id=UUID(int=20), details=())
    unrelated = replace(task, task_id=UUID(int=21), details=())
    work = replace(
        work,
        tasks=(task, other, unrelated),
        task_links=(*work.task_links, TaskCapabilityLink(other.task_id, capability.capability_id)),
    )
    source = MemorySource(
        MemorySourceLayer.WORK_SITUATION, UUID(int=70), UUID(int=71), UUID(int=72)
    )
    targets = (
        *(JdSourceTarget(SourceTargetKind.TASK, t.task_id) for t in work.tasks),
        JdSourceTarget(SourceTargetKind.CAPABILITY, capability.capability_id),
    )
    references = tuple(
        JdSourceReference(
            UUID(int=30 + i),
            target,
            source,
            needs_review=pending,
            reviewed_revision_id=UUID(int=50),
        )
        for i, target in enumerate(targets)
    )
    command = ReviseItemWithSources(
        UUID(int=80),
        work.revision_id,
        ReviseCapability(
            capability.capability_id,
            (CapabilityFieldChange(CapabilityField.DESCRIPTION, "新定義"),),
        ),
        (),
        (),
    )
    changed = apply_compound_changes(JdProfile(), work, references, command)
    assert tuple(r.needs_review for r in changed.references) == (False, False, pending, False)
    assert tuple(r.reviewed_revision_id for r in changed.references) == (
        None,
        None,
        UUID(int=50),
        None,
    )
    assert all(r.source == source for r in changed.references)
    assert changed.references[2] == references[2]
    # A repeated value cannot review pre-existing pending evidence.
    unchanged = apply_compound_changes(JdProfile(), changed.work, references, command)
    assert unchanged.references == references
