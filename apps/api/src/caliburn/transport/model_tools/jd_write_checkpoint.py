"""JSON-only checkpoint representation of fully bound JD write commands."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from caliburn.workflows.jd_profile_writes import PreparedProfileWrite
from caliburn.workflows.jd_task_writes import PreparedTaskWrite


class JdWriteCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["profile", "task"]
    payload: str


type PreparedJdWrite = PreparedProfileWrite | PreparedTaskWrite

_PROFILE = TypeAdapter(PreparedProfileWrite)
_TASK = TypeAdapter(PreparedTaskWrite)


def snapshot_jd_write(prepared: PreparedJdWrite) -> dict[str, object]:
    if isinstance(prepared, PreparedProfileWrite):
        checkpoint = JdWriteCheckpoint(
            kind="profile", payload=_PROFILE.dump_json(prepared).decode()
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
    return _TASK.validate_json(checkpoint.payload, strict=True)
