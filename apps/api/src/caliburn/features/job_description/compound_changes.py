"""複合 JD 編輯先使用既有純規則算出最終內容與來源，再交保存邊界。"""

from dataclasses import replace

from caliburn.features.job_description.area_changes import apply_area_change
from caliburn.features.job_description.areas import CreateArea, ResponsibilityArea, ReviseArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CreateCapability,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.capability_changes import apply_capability_change
from caliburn.features.job_description.collaborator_changes import apply_collaborator_change
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CreateCollaborator,
    ReviseCollaborator,
)
from caliburn.features.job_description.compound_edits import (
    BoundItemSources,
    CompoundItem,
    CompoundJdEdit,
    CreateItemWithSources,
    CreateTaskWithSources,
    ItemContentRevision,
    ItemCreation,
    JdEditEffect,
    ReviseProfileWithSources,
)
from caliburn.features.job_description.condition_changes import apply_condition_change
from caliburn.features.job_description.conditions import (
    JobCondition,
)
from caliburn.features.job_description.edit_changes import JdEditChanges
from caliburn.features.job_description.models import JdProfile, apply_profile_changes
from caliburn.features.job_description.source_changes import apply_source_changes
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InvalidJdSourceError,
    JdSourceReference,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
    carry_source_references,
)
from caliburn.features.job_description.task_changes import apply_task_edit
from caliburn.features.job_description.tasks import CreateTask, ReviseTask, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def apply_content_change(
    work: JdWorkRevision, change: ItemCreation | ItemContentRevision | CreateTask
) -> tuple[JdWorkRevision, CompoundItem | None]:
    """回傳既有規則產生的新內容；建立身分直接取這個結果，不比較 DB 快照。"""
    if isinstance(change, CreateArea | ReviseArea):
        areas, area = apply_area_change(work.areas, change)
        return replace(work, areas=areas), area
    if isinstance(change, CreateTask | ReviseTask):
        tasks, task = apply_task_edit(work.tasks, tuple(a.area_id for a in work.areas), change)
        return replace(work, tasks=tasks), task
    if isinstance(change, CreateCapability | ReviseCapability):
        capabilities, links, capability = apply_capability_change(
            work.capabilities, work.task_links, tuple(t.task_id for t in work.tasks), change
        )
        return replace(work, capabilities=capabilities, task_links=links), capability
    if isinstance(change, CreateCollaborator | ReviseCollaborator):
        collaborators, collaborator = apply_collaborator_change(work.collaborators, change)
        return replace(work, collaborators=collaborators), collaborator
    conditions, condition = apply_condition_change(work.conditions, change)
    return replace(work, conditions=conditions), condition


def item_source_target(item: CompoundItem) -> JdSourceTarget:
    match item:
        case ResponsibilityArea():
            return JdSourceTarget(SourceTargetKind.AREA, item_id=item.area_id)
        case WorkTask():
            return JdSourceTarget(SourceTargetKind.TASK, item_id=item.task_id)
        case Capability():
            return JdSourceTarget(SourceTargetKind.CAPABILITY, item_id=item.capability_id)
        case Collaborator():
            return JdSourceTarget(SourceTargetKind.COLLABORATOR, item_id=item.collaborator_id)
        case JobCondition():
            return JdSourceTarget(SourceTargetKind.CONDITION, item_id=item.condition_id)


def compound_effect(command: CompoundJdEdit, *, changed: bool) -> JdEditEffect:
    if not changed:
        return "unchanged"
    if isinstance(command, CreateTaskWithSources | CreateItemWithSources):
        return "created"
    content_changed = (
        bool(command.changes)
        if isinstance(command, ReviseProfileWithSources)
        else command.content is not None or bool(command.capabilities)
    )
    if not content_changed and all(
        isinstance(c, AlignJdSource) for g in command.sources for c in g.changes
    ):
        return "aligned"
    return "updated"


def apply_compound_changes(
    profile: JdProfile,
    work: JdWorkRevision,
    references: tuple[JdSourceReference, ...],
    command: CompoundJdEdit,
) -> JdEditChanges:
    before_profile, before_work = profile, work
    changed_content = created = None
    groups: tuple[BoundItemSources, ...]
    if isinstance(command, ReviseProfileWithSources):
        if command.changes:
            profile = apply_profile_changes(profile, command.changes)
        groups = tuple(
            BoundItemSources(
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=g.field), g.changes
            )
            for g in command.sources
        )
    elif isinstance(command, CreateItemWithSources):
        work, changed_content = apply_content_change(work, command.item)
        created = changed_content
        assert created is not None
        groups = (
            (
                BoundItemSources(
                    item_source_target(created), tuple(AddJdSource(s) for s in command.sources)
                ),
            )
            if command.sources
            else ()
        )
    elif isinstance(command, CreateTaskWithSources):
        work, changed_content = apply_content_change(work, command.task)
        assert isinstance(changed_content, WorkTask)
        created = changed_content
        for link in command.capabilities:
            _, links, _ = apply_capability_change(
                work.capabilities,
                work.task_links,
                tuple(t.task_id for t in work.tasks),
                SetTaskCapability(created.task_id, link.capability_id, True),
            )
            work = replace(work, task_links=links)
        groups = (
            (
                BoundItemSources(
                    item_source_target(created), tuple(AddJdSource(s) for s in command.task_sources)
                ),
            )
            if command.task_sources
            else ()
        )
    else:
        if command.content is not None:
            work, changed_content = apply_content_change(work, command.content)
        groups = command.sources
        for change in command.capabilities:
            _, links, _ = apply_capability_change(
                work.capabilities, work.task_links, tuple(t.task_id for t in work.tasks), change
            )
            work = replace(work, task_links=links)
    targets = source_target_contents(profile, work)
    references = carry_source_references(
        references,
        source_target_contents(before_profile, before_work),
        targets,
        review_changed_content=True,
    )
    for group in groups:
        if group.target not in targets:
            raise InvalidJdSourceError("The selected JD source target does not exist")
        references = apply_source_changes(
            references,
            ReviseJdSources(
                command.command_id, command.expected_revision_id, group.target, group.changes
            ),
        )
    return JdEditChanges(profile, work, references, changed_content, created)
