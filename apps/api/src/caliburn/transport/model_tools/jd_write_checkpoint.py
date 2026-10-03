"""JSON-only checkpoint representation of fully bound JD write commands."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from caliburn.workflows.jd_item_creation import PreparedItemCreation
from caliburn.workflows.jd_item_deletion import PreparedItemDeletion
from caliburn.workflows.jd_item_movement import PreparedItemMovement
from caliburn.workflows.jd_item_revision import PreparedItemRevision
from caliburn.workflows.jd_profile_writes import PreparedProfileWrite
from caliburn.workflows.jd_task_writes import PreparedTaskWrite


class JdWriteCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal[
        "profile", "task", "item_creation", "item_revision", "item_deletion", "item_movement"
    ]
    payload: str


type PreparedJdWrite = (
    PreparedProfileWrite
    | PreparedTaskWrite
    | PreparedItemCreation
    | PreparedItemRevision
    | PreparedItemDeletion
    | PreparedItemMovement
)

_PROFILE = TypeAdapter(PreparedProfileWrite)
_TASK = TypeAdapter(PreparedTaskWrite)
_CREATION = TypeAdapter(PreparedItemCreation)
_REVISION = TypeAdapter(PreparedItemRevision)
_DELETION = TypeAdapter(PreparedItemDeletion)
_MOVEMENT = TypeAdapter(PreparedItemMovement)


def snapshot_jd_write(prepared: PreparedJdWrite) -> dict[str, object]:
    if isinstance(prepared, PreparedProfileWrite):
        checkpoint = JdWriteCheckpoint(
            kind="profile", payload=_PROFILE.dump_json(prepared).decode()
        )
    elif isinstance(prepared, PreparedItemCreation):
        checkpoint = JdWriteCheckpoint(
            kind="item_creation", payload=_CREATION.dump_json(prepared).decode()
        )
    elif isinstance(prepared, PreparedItemRevision):
        checkpoint = JdWriteCheckpoint(
            kind="item_revision", payload=_REVISION.dump_json(prepared).decode()
        )
    elif isinstance(prepared, PreparedItemDeletion):
        checkpoint = JdWriteCheckpoint(
            kind="item_deletion", payload=_DELETION.dump_json(prepared).decode()
        )
    elif isinstance(prepared, PreparedItemMovement):
        checkpoint = JdWriteCheckpoint(
            kind="item_movement", payload=_MOVEMENT.dump_json(prepared).decode()
        )
    else:
        checkpoint = JdWriteCheckpoint(kind="task", payload=_TASK.dump_json(prepared).decode())
    return checkpoint.model_dump(mode="json")


def restore_jd_write(value: object) -> PreparedJdWrite:
    checkpoint = JdWriteCheckpoint.model_validate(value)
    # Parse JSON to reconstruct every nested dataclass/enum/UUID, not just the outer
    # instance. The official saver need only retain ordinary JSON-safe values.
    if checkpoint.kind == "profile":
        return _PROFILE.validate_json(checkpoint.payload, strict=True)
    if checkpoint.kind == "item_creation":
        return _CREATION.validate_json(checkpoint.payload, strict=True)
    if checkpoint.kind == "item_revision":
        return _REVISION.validate_json(checkpoint.payload, strict=True)
    if checkpoint.kind == "item_deletion":
        return _DELETION.validate_json(checkpoint.payload, strict=True)
    if checkpoint.kind == "item_movement":
        return _MOVEMENT.validate_json(checkpoint.payload, strict=True)
    return _TASK.validate_json(checkpoint.payload, strict=True)
