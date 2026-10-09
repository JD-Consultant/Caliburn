"""Canonical generated movement arguments to bounded application intentions."""

from caliburn.contracts.generated.tools import move_jd_item_arguments as wire
from caliburn.contracts.validation import parse_contract
from caliburn.features.job_description.tasks import DetailKind
from caliburn.workflows.jd_item_movement import (
    CurrentItemContainer,
    ItemPosition,
    MoveItemInput,
    MovementDetailAddition,
    MovementTextChange,
    TaskParentDestination,
)


def parse_item_movement(arguments: str) -> MoveItemInput:
    parsed = parse_contract(wire.MoveJdItemArguments, arguments)
    destination = (
        CurrentItemContainer()
        if isinstance(parsed.destination, wire.CurrentContainer)
        else TaskParentDestination(parsed.destination.parent_read_ref)
    )
    position = parsed.position
    if isinstance(position, wire.EdgePosition):
        placement = ItemPosition("first" if position.kind.value == "first" else "last")
    else:
        placement = ItemPosition(
            "before" if position.kind.value == "before" else "after",
            position.neighbor_read_ref,
        )
    changes: list[MovementTextChange | MovementDetailAddition] = []
    for change in parsed.content_changes:
        if isinstance(change, wire.AddMovementDetail):
            changes.append(MovementDetailAddition(DetailKind(change.kind.value), change.text))
        else:
            changes.append(
                MovementTextChange(
                    change.read_ref,
                    change.field.value,
                    change.value if isinstance(change, wire.SetMovementText) else None,
                )
            )
    return MoveItemInput(parsed.read_ref, destination, placement, tuple(changes))
