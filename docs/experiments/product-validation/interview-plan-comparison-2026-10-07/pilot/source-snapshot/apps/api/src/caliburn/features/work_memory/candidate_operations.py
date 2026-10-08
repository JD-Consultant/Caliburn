"""Memory-owned original operation results, not a generic receipt framework."""

import hashlib
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    MemoryBatchPosition,
    MemoryCommandConflictError,
    MemoryEdit,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.revisions import MemoryLayer


def position_fields(position: MemoryBatchPosition) -> dict[str, str]:
    return {
        "job_file_id": str(position.job_file_id),
        "execution_id": str(position.execution_id),
        "generation_id": str(position.generation_id),
        "stage_id": str(position.stage_id),
        "phase": position.phase.value,
        "position_id": str(position.position_id),
    }


def result_position(payload: dict[str, object]) -> MemoryBatchPosition:
    return MemoryBatchPosition(
        stored_uuid(payload, "job_file_id"),
        stored_uuid(payload, "execution_id"),
        stored_uuid(payload, "generation_id"),
        stored_uuid(payload, "stage_id"),
        MemoryLayer(stored_text(payload, "phase")),
        stored_uuid(payload, "position_id"),
    )


def stored_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise MemoryCommandConflictError("The saved operation result is incomplete")
    return value


def stored_uuid(payload: dict[str, object], key: str) -> UUID:
    return UUID(stored_text(payload, key))


def edit_payload(command: MemoryEdit) -> dict[str, object]:
    payload: dict[str, object] = {
        "position": position_fields(command.position),
        "layer": command.layer.value,
    }
    if isinstance(command, CreateMemoryObject):
        payload.update(
            {
                "action": "create",
                "title": command.content.title,
                "description": command.content.description,
                "body": command.content.body,
                "reference_ids": sorted(str(identity) for identity in command.reference_ids),
            }
        )
    else:
        payload["object_id"] = str(command.object_id)
        payload["action"] = "revise" if isinstance(command, ReviseMemoryObject) else "delete"
        if isinstance(command, ReviseMemoryObject):
            if command.content_changes is not None:
                payload["content_changes"] = {
                    "title": command.content_changes.title,
                    "description": command.content_changes.description,
                    "body": command.content_changes.body,
                }
            if command.reference_changes is not None:
                payload["reference_changes"] = {
                    "add": sorted(str(identity) for identity in command.reference_changes.add),
                    "remove": sorted(
                        str(identity) for identity in command.reference_changes.remove
                    ),
                }
    # Native-request retention belongs to execution recovery; the domain receipt
    # needs equality, not another copy of potentially long Markdown.
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {"position": position_fields(command.position), "intent_digest": digest}


async def recover(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    command_id: UUID,
    kind: str,
    payload: dict[str, object],
) -> dict[str, object] | None:
    record = await batch_persistence.read_operation(session, job_file_id, command_id)
    if record is None:
        return None
    if (
        record.execution_id != execution_id
        or record.kind != kind
        or record.request_payload != payload
    ):
        raise MemoryCommandConflictError("command_id was used for another Memory operation")
    result = record.result_payload
    if not isinstance(result, dict) or not all(isinstance(key, str) for key in result):
        raise MemoryCommandConflictError("The saved operation result is not an object")
    return {key: value for key, value in result.items()}


async def record_result(
    session: AsyncSession,
    position: MemoryBatchPosition,
    command_id: UUID,
    kind: str,
    payload: dict[str, object],
    *,
    object_id: UUID | None = None,
    snapshot_id: UUID | None = None,
) -> None:
    result: dict[str, object] = dict(position_fields(position))
    if object_id is not None:
        result["object_id"] = str(object_id)
    if snapshot_id is not None:
        result["snapshot_id"] = str(snapshot_id)
    session.add(
        batch_persistence.MemoryOperationRecord(
            job_file_id=position.job_file_id,
            execution_id=position.execution_id,
            command_id=command_id,
            kind=kind,
            request_payload=payload,
            result_payload=result,
        )
    )
    await session.flush()
