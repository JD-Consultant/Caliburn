"""Pure changes preserve condition identity and order independently within each kind."""

from dataclasses import replace
from uuid import uuid4

from caliburn.features.job_description.conditions import (
    ConditionChange,
    ConditionKindChange,
    ConditionNotFoundError,
    ConditionTextChange,
    CreateCondition,
    DeleteCondition,
    JobCondition,
    ReorderCondition,
    ReviseCondition,
)


def apply_condition_change(
    conditions: tuple[JobCondition, ...],
    change: ConditionChange,
) -> tuple[tuple[JobCondition, ...], JobCondition | None]:
    if isinstance(change, CreateCondition):
        created = JobCondition(uuid4(), uuid4(), change.kind, change.text)
        return (*conditions, created), created
    target = next((item for item in conditions if item.condition_id == change.condition_id), None)
    if target is None:
        raise ConditionNotFoundError("Condition is not in the selected JD")
    if isinstance(change, ReviseCondition):
        kind, text = target.kind, target.text
        for item in change.changes:
            match item:
                case ConditionTextChange():
                    text = item.text
                case ConditionKindChange():
                    kind = item.kind
        revised = replace(target, kind=kind, text=text)
        if revised == target:
            return conditions, None
        revised = replace(revised, content_revision_id=uuid4())
        if kind != target.kind:
            # Reclassification retains identity and appends to the destination kind.
            return (*[item for item in conditions if item != target], revised), revised
        return tuple(revised if item == target else item for item in conditions), revised
    if isinstance(change, DeleteCondition):
        return tuple(item for item in conditions if item != target), None
    if isinstance(change, ReorderCondition):
        if change.before_condition_id == target.condition_id:
            return conditions, None
        group = [item for item in conditions if item.kind == target.kind and item != target]
        if change.before_condition_id is None:
            group.append(target)
        else:
            index = next(
                (
                    index
                    for index, item in enumerate(group)
                    if item.condition_id == change.before_condition_id
                ),
                None,
            )
            if index is None:
                raise ConditionNotFoundError("Ordering neighbour is not in this condition kind")
            group.insert(index, target)
        reordered = iter(group)
        return tuple(
            next(reordered) if item.kind == target.kind else item for item in conditions
        ), None
    raise TypeError("Unsupported condition change")
