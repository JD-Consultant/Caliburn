"""Generated revise-item wire to bounded application choices, without database access."""

from caliburn.contracts.generated.tools import revise_jd_item_arguments as wire
from caliburn.features.job_description.sources import MemorySourceLayer
from caliburn.features.job_description.tasks import DetailKind
from caliburn.workflows.jd_item_revision import (
    AddItemDetail,
    AddItemSource,
    AlignItemSource,
    CapabilitySourceTarget,
    DetailSourceTarget,
    ItemFieldChange,
    ItemRevisionChange,
    ItemSourceSelection,
    ItemSourceTarget,
    RemoveItemDetail,
    RemoveItemSource,
    ReorderItemCapability,
    ReviseItemDetail,
    ReviseItemInput,
    SetItemCapability,
)
from caliburn.workflows.jd_sources import (
    CurrentInputSourceSelection,
    InterviewSourceSelection,
    JdSourceSelection,
    MemorySourceSelection,
)


def parse_item_revision(arguments: str) -> ReviseItemInput:
    parsed = wire.ReviseJdItemArguments.model_validate_json(arguments)
    changes: list[ItemRevisionChange] = []
    for change in parsed.changes:
        if isinstance(change, wire.SetItemText):
            changes.append(ItemFieldChange(change.field.value, change.value))
        elif isinstance(change, wire.ClearItemText):
            changes.append(ItemFieldChange(change.field.value, None))
        elif isinstance(change, wire.SetConditionKind):
            changes.append(ItemFieldChange("kind", change.value.value))
        elif isinstance(change, wire.AddTaskDetail):
            changes.append(
                AddItemDetail(
                    DetailKind(change.kind.value),
                    change.text,
                    tuple(_source(source) for source in change.supporting_sources),
                )
            )
        elif isinstance(change, wire.ReviseTaskDetail):
            changes.append(ReviseItemDetail(change.detail_read_ref, change.text))
        elif isinstance(change, wire.RemoveTaskDetail):
            changes.append(RemoveItemDetail(change.detail_read_ref))
        elif isinstance(change, wire.LinkCapability):
            changes.append(
                SetItemCapability(
                    change.capability_read_ref,
                    True,
                    tuple(_source(source) for source in change.supporting_sources),
                )
            )
        elif isinstance(change, wire.UnlinkCapability):
            changes.append(SetItemCapability(change.capability_read_ref, False))
        elif isinstance(change, wire.ReorderCapability):
            position = change.position
            if isinstance(position, wire.EdgePosition):
                changes.append(
                    ReorderItemCapability(
                        change.capability_read_ref,
                        "first" if position.kind.value == "first" else "last",
                    )
                )
            else:
                changes.append(
                    ReorderItemCapability(
                        change.capability_read_ref,
                        "before" if position.kind.value == "before" else "after",
                        position.capability_read_ref,
                    )
                )
        elif isinstance(change, wire.AddSource):
            changes.append(AddItemSource(_target(change.target), _source(change.source)))
        elif isinstance(change, wire.RemoveSource):
            changes.append(RemoveItemSource(_target(change.target), change.citation_ref))
        else:
            changes.append(AlignItemSource(_target(change.target), change.citation_ref))
    return ReviseItemInput(parsed.read_ref, tuple(changes))


def _source(value: wire.Source) -> JdSourceSelection:
    source = value.root
    if isinstance(source, wire.CurrentInputSource):
        return CurrentInputSourceSelection()
    if isinstance(source, wire.InterviewSource):
        return InterviewSourceSelection(source.interview_sequence)
    return MemorySourceSelection(MemorySourceLayer(source.kind.value), source.target_title)


def _target(value: wire.SourceTarget) -> ItemSourceSelection:
    target = value.root
    if isinstance(target, wire.ItemTarget):
        return ItemSourceTarget()
    if isinstance(target, wire.DetailTarget):
        return DetailSourceTarget(target.detail_read_ref)
    return CapabilitySourceTarget(target.capability_read_ref)
