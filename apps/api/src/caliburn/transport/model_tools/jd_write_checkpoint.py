"""已綁定 JD 命令的 JSON checkpoint；外層標籤選定具體解碼型別。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from caliburn.features.job_description.compound_edits import (
    CompoundJdEdit,
    CreateItemWithSources,
    CreateTaskWithSources,
    ReviseItemWithSources,
    ReviseProfileWithSources,
)
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.job_description.item_deletion import PreparedItemDeletion
from caliburn.workflows.job_description.item_movement import PreparedItemMovement


class JdWriteCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal[
        "profile", "task", "item_creation", "item_revision", "item_deletion", "item_movement"
    ]
    payload: str


type PreparedJdWrite = PreparedJdEdit[CompoundJdEdit] | PreparedItemDeletion | PreparedItemMovement

_PROFILE = TypeAdapter(PreparedJdEdit[ReviseProfileWithSources])
_TASK = TypeAdapter(PreparedJdEdit[CreateTaskWithSources])
_CREATION = TypeAdapter(PreparedJdEdit[CreateItemWithSources])
_REVISION = TypeAdapter(PreparedJdEdit[ReviseItemWithSources])
_DELETION = TypeAdapter(PreparedItemDeletion)
_MOVEMENT = TypeAdapter(PreparedItemMovement)
_COMPOUND = TypeAdapter(PreparedJdEdit[CompoundJdEdit])


def snapshot_jd_write(prepared: PreparedJdWrite) -> dict[str, object]:
    if isinstance(prepared, PreparedItemDeletion):
        checkpoint = JdWriteCheckpoint(
            kind="item_deletion", payload=_DELETION.dump_json(prepared).decode()
        )
    elif isinstance(prepared, PreparedItemMovement):
        checkpoint = JdWriteCheckpoint(
            kind="item_movement", payload=_MOVEMENT.dump_json(prepared).decode()
        )
    else:
        kind: Literal["profile", "task", "item_creation", "item_revision"]
        match prepared.command:
            case ReviseProfileWithSources():
                kind = "profile"
            case CreateItemWithSources():
                kind = "item_creation"
            case ReviseItemWithSources():
                kind = "item_revision"
            case CreateTaskWithSources():
                kind = "task"
        # Union 僅序列化實際命令；讀取仍由 kind 選定具體 adapter。
        checkpoint = JdWriteCheckpoint(kind=kind, payload=_COMPOUND.dump_json(prepared).decode())
    return checkpoint.model_dump(mode="json")


def restore_jd_write(value: object) -> PreparedJdWrite:
    checkpoint = JdWriteCheckpoint.model_validate(value)
    # 外層 kind 選定具體命令；完整解碼所有巢狀值，不由 compound union 猜類型。
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
