"""Typed employee lifecycle commands for the one visible current JD.

The browser states intent.  This module owns stable-ID-safe relationship and
ownership changes; it is not exposed to the consultant model as a Tool.
"""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from typing import Annotated, Any, Literal, Union, cast
from uuid import UUID

from pydantic import Field, JsonValue

from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DurableModel,
    NonEmptyText,
)
from app.consultant.workspace_state import Sha256Digest, approved_document_digest


class DocumentCommandError(ValueError):
    pass


class DocumentCommandConfirmationRequired(DocumentCommandError):
    pass


class CreateDuty(DurableModel):
    operation: Literal["create_duty"] = "create_duty"
    name: NonEmptyText


class CreateTask(DurableModel):
    operation: Literal["create_task"] = "create_task"
    duty_id: UUID | None = None
    statement: NonEmptyText
    action: NonEmptyText
    object: NonEmptyText
    competency_level: int | None = Field(default=None, ge=1, le=6)


class CreateOpks(DurableModel):
    operation: Literal["create_opks"] = "create_opks"
    task_id: UUID
    kind: Literal[
        ApprovedOpksKind.OUTPUT,
        ApprovedOpksKind.PERFORMANCE_INDICATOR,
        ApprovedOpksKind.KNOWLEDGE,
        ApprovedOpksKind.SKILL,
    ]
    text: NonEmptyText


class CreateAttitude(DurableModel):
    operation: Literal["create_attitude"] = "create_attitude"
    text: NonEmptyText


class DissolveDuty(DurableModel):
    operation: Literal["dissolve_duty"] = "dissolve_duty"
    duty_id: UUID


class CascadeDeleteDuty(DurableModel):
    operation: Literal["cascade_delete_duty"] = "cascade_delete_duty"
    duty_id: UUID
    preview_digest: Sha256Digest | None = None


class MoveTask(DurableModel):
    operation: Literal["move_task"] = "move_task"
    task_id: UUID
    destination_duty_id: UUID | None = None


class DeleteTask(DurableModel):
    operation: Literal["delete_task"] = "delete_task"
    task_id: UUID


class ReorderEntity(DurableModel):
    operation: Literal["reorder_entity"] = "reorder_entity"
    entity_kind: Literal["duty", "task", "opks"]
    entity_id: UUID
    parent_id: UUID | None = None
    before_entity_id: UUID | None = None


class LinkSharedOpks(DurableModel):
    operation: Literal["link_shared_opks"] = "link_shared_opks"
    item_id: UUID
    task_id: UUID


class UnlinkSharedOpks(DurableModel):
    operation: Literal["unlink_shared_opks"] = "unlink_shared_opks"
    item_id: UUID
    task_id: UUID


class DeleteOwnedOpks(DurableModel):
    operation: Literal["delete_owned_opks"] = "delete_owned_opks"
    item_id: UUID


class DeleteSharedOpks(DurableModel):
    operation: Literal["delete_shared_opks"] = "delete_shared_opks"
    item_id: UUID
    preview_digest: Sha256Digest | None = None


class UndoDocumentCommand(DurableModel):
    operation: Literal["undo"] = "undo"
    undo_token: NonEmptyText


DocumentStructureCommand = Annotated[
    Union[
        CreateDuty,
        CreateTask,
        CreateOpks,
        CreateAttitude,
        DissolveDuty,
        CascadeDeleteDuty,
        MoveTask,
        DeleteTask,
        ReorderEntity,
        LinkSharedOpks,
        UnlinkSharedOpks,
        DeleteOwnedOpks,
        DeleteSharedOpks,
        UndoDocumentCommand,
    ],
    Field(discriminator="operation"),
]


class DocumentCommandBlastRadius(DurableModel):
    preview_digest: Sha256Digest
    confirmation_required: bool = False
    duty_count: int = Field(default=0, ge=0)
    task_count: int = Field(default=0, ge=0)
    output_count: int = Field(default=0, ge=0)
    indicator_count: int = Field(default=0, ge=0)
    shared_item_count: int = Field(default=0, ge=0)
    shared_link_count: int = Field(default=0, ge=0)
    affected_names: tuple[str, ...] = ()


class DocumentStructurePlan(DurableModel):
    current_after: ApprovedJobDocument
    touched_paths: tuple[str, ...]
    blast_radius: DocumentCommandBlastRadius
    inverse_command: dict[str, JsonValue]


def _by_id(values: tuple[Any, ...], field: str) -> dict[UUID, Any]:
    return {getattr(item, field): item for item in values}


def _require(mapping: dict[UUID, Any], identity: UUID, label: str) -> Any:
    try:
        return mapping[identity]
    except KeyError as error:
        raise DocumentCommandError(f"unknown {label} {identity}") from error


def _next_order(values: tuple[Any, ...], *, kind: ApprovedOpksKind | None = None) -> int:
    candidates = (
        [item.display_order for item in values if getattr(item, "kind", None) is kind]
        if kind is not None
        else [item.display_order for item in values]
    )
    return max(candidates, default=-1) + 1


def _command_payload(command: DocumentStructureCommand) -> dict[str, JsonValue]:
    return command.model_dump(mode="json", exclude={"preview_digest"})


def _digest(
    document: ApprovedJobDocument,
    command: DocumentStructureCommand,
) -> Sha256Digest:
    encoded = json.dumps(
        {
            "document_digest": approved_document_digest(document),
            "command": _command_payload(command),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return cast(Sha256Digest, sha256(encoded).hexdigest())


def _shared(item: ApprovedOpksItem) -> bool:
    return item.kind in {ApprovedOpksKind.KNOWLEDGE, ApprovedOpksKind.SKILL}


def _owned(item: ApprovedOpksItem) -> bool:
    return item.kind in {
        ApprovedOpksKind.OUTPUT,
        ApprovedOpksKind.PERFORMANCE_INDICATOR,
        ApprovedOpksKind.ATTITUDE,
    }


def _affected_for_tasks(
    document: ApprovedJobDocument,
    task_ids: set[UUID],
) -> tuple[set[UUID], set[UUID], int, set[UUID]]:
    outputs: set[UUID] = set()
    indicators: set[UUID] = set()
    shared_items: set[UUID] = set()
    shared_links = 0
    for item in document.opks:
        linked = set(item.task_ids) & task_ids
        if item.kind is ApprovedOpksKind.OUTPUT and linked:
            outputs.add(item.item_id)
        elif item.kind is ApprovedOpksKind.PERFORMANCE_INDICATOR and linked:
            indicators.add(item.item_id)
        elif _shared(item) and linked:
            shared_items.add(item.item_id)
            shared_links += len(linked)
    return outputs, indicators, shared_links, shared_items


def preview_document_structure_command(
    document: ApprovedJobDocument,
    command: DocumentStructureCommand,
) -> DocumentCommandBlastRadius:
    duties = _by_id(document.duties, "duty_id")
    tasks = _by_id(document.tasks, "task_id")
    opks = _by_id(document.opks, "item_id")
    duty_count = task_count = output_count = indicator_count = 0
    shared_link_count = 0
    shared_items: set[UUID] = set()
    names: list[str] = []
    confirmation_required = False

    if isinstance(command, (DissolveDuty, CascadeDeleteDuty)):
        duty = _require(duties, command.duty_id, "Duty")
        affected_tasks = {
            item.task_id for item in document.tasks if item.duty_id == command.duty_id
        }
        outputs, indicators, shared_link_count, shared_items = _affected_for_tasks(
            document, affected_tasks
        )
        duty_count = 1
        task_count = len(affected_tasks)
        output_count = len(outputs)
        indicator_count = len(indicators)
        names.append(duty.statement)
        names.extend(
            item.statement for item in document.tasks if item.task_id in affected_tasks
        )
        confirmation_required = isinstance(command, CascadeDeleteDuty) and (
            task_count > 1 or shared_link_count > 0
        )
    elif isinstance(command, DeleteTask):
        task = _require(tasks, command.task_id, "Task")
        outputs, indicators, shared_link_count, shared_items = _affected_for_tasks(
            document, {command.task_id}
        )
        task_count = 1
        output_count = len(outputs)
        indicator_count = len(indicators)
        names.append(task.statement)
    elif isinstance(command, (DeleteOwnedOpks, DeleteSharedOpks)):
        item = _require(opks, command.item_id, "OPKS item")
        names.append(item.text)
        if isinstance(command, DeleteSharedOpks):
            if not _shared(item):
                raise DocumentCommandError("permanent shared delete requires K or S")
            shared_items.add(item.item_id)
            shared_link_count = len(item.task_ids)
            confirmation_required = shared_link_count > 0
        else:
            if not _owned(item):
                raise DocumentCommandError("owned delete requires O, P, or A")
            output_count = int(item.kind is ApprovedOpksKind.OUTPUT)
            indicator_count = int(
                item.kind is ApprovedOpksKind.PERFORMANCE_INDICATOR
            )

    return DocumentCommandBlastRadius(
        preview_digest=_digest(document, command),
        confirmation_required=confirmation_required,
        duty_count=duty_count,
        task_count=task_count,
        output_count=output_count,
        indicator_count=indicator_count,
        shared_item_count=len(shared_items),
        shared_link_count=shared_link_count,
        affected_names=tuple(names),
    )


def _delete_tasks(
    document: ApprovedJobDocument,
    task_ids: set[UUID],
) -> tuple[tuple[ApprovedTask, ...], tuple[ApprovedOpksItem, ...]]:
    deleted_indicators = {
        item.item_id
        for item in document.opks
        if item.kind is ApprovedOpksKind.PERFORMANCE_INDICATOR
        and bool(set(item.task_ids) & task_ids)
    }
    tasks = tuple(item for item in document.tasks if item.task_id not in task_ids)
    opks: list[ApprovedOpksItem] = []
    for item in document.opks:
        linked_to_deleted = bool(set(item.task_ids) & task_ids)
        if item.kind in {
            ApprovedOpksKind.OUTPUT,
            ApprovedOpksKind.PERFORMANCE_INDICATOR,
        } and linked_to_deleted:
            continue
        if _shared(item):
            item = item.model_copy(
                update={
                    "task_ids": tuple(
                        task_id for task_id in item.task_ids if task_id not in task_ids
                    ),
                    "indicator_ids": tuple(
                        indicator_id
                        for indicator_id in item.indicator_ids
                        if indicator_id not in deleted_indicators
                    ),
                }
            )
        opks.append(item)
    return tasks, tuple(opks)


def _reordered(
    values: tuple[Any, ...],
    *,
    entity_id: UUID,
    before_entity_id: UUID | None,
    identity_field: str,
    eligible: Callable[[Any], bool],
) -> tuple[Any, ...]:
    scope = sorted(
        (item for item in values if eligible(item)),
        key=lambda item: (item.display_order, str(getattr(item, identity_field))),
    )
    identities = [getattr(item, identity_field) for item in scope]
    if entity_id not in identities:
        raise DocumentCommandError("reordered entity is outside the selected level")
    if before_entity_id is not None and before_entity_id not in identities:
        raise DocumentCommandError("reorder destination is outside the selected level")
    if before_entity_id == entity_id:
        raise DocumentCommandError("an entity cannot be moved before itself")
    moving = scope.pop(identities.index(entity_id))
    if before_entity_id is None:
        scope.append(moving)
    else:
        destination = next(
            index
            for index, item in enumerate(scope)
            if getattr(item, identity_field) == before_entity_id
        )
        scope.insert(destination, moving)
    slots = sorted(item.display_order for item in scope)
    updates = {
        getattr(item, identity_field): item.model_copy(update={"display_order": slot})
        for item, slot in zip(scope, slots)
    }
    merged = tuple(updates.get(getattr(item, identity_field), item) for item in values)
    return tuple(
        sorted(
            merged,
            key=lambda item: (item.display_order, str(getattr(item, identity_field))),
        )
    )


def _touched(
    command: DocumentStructureCommand,
    document: ApprovedJobDocument,
) -> tuple[str, ...]:
    paths: list[str] = []
    if isinstance(command, (CreateDuty,)):
        return ()
    if isinstance(command, (DissolveDuty, CascadeDeleteDuty)):
        paths.append(f"/duties/{command.duty_id}")
        paths.extend(
            f"/tasks/{item.task_id}"
            for item in document.tasks
            if item.duty_id == command.duty_id
        )
    elif isinstance(command, (MoveTask, DeleteTask)):
        paths.append(f"/tasks/{command.task_id}")
        if isinstance(command, MoveTask) and command.destination_duty_id is not None:
            paths.append(f"/duties/{command.destination_duty_id}")
    elif isinstance(command, ReorderEntity):
        collection = {"duty": "duties", "task": "tasks", "opks": "opks"}[
            command.entity_kind
        ]
        paths.append(f"/{collection}/{command.entity_id}")
        if command.before_entity_id is not None:
            paths.append(f"/{collection}/{command.before_entity_id}")
    elif isinstance(command, (LinkSharedOpks, UnlinkSharedOpks)):
        paths.extend((f"/opks/{command.item_id}", f"/tasks/{command.task_id}"))
    elif isinstance(command, (DeleteOwnedOpks, DeleteSharedOpks)):
        paths.append(f"/opks/{command.item_id}")
    return tuple(dict.fromkeys(paths))


def _changed_entity_paths(
    before: ApprovedJobDocument,
    after: ApprovedJobDocument,
) -> tuple[str, ...]:
    paths: list[str] = []
    for collection, identity_field in (
        ("duties", "duty_id"),
        ("tasks", "task_id"),
        ("opks", "item_id"),
    ):
        before_by_id = _by_id(getattr(before, collection), identity_field)
        after_by_id = _by_id(getattr(after, collection), identity_field)
        for identity in sorted(set(before_by_id) | set(after_by_id), key=str):
            if before_by_id.get(identity) != after_by_id.get(identity):
                paths.append(f"/{collection}/{identity}")
    return tuple(paths)


def plan_document_structure_command(
    document: ApprovedJobDocument,
    command: DocumentStructureCommand,
    *,
    issued_entity_id: UUID,
    employee_source_id: UUID,
    enforce_confirmation: bool = True,
) -> DocumentStructurePlan:
    """Apply one typed intent and return one fully validated current after-state."""

    if isinstance(command, UndoDocumentCommand):
        raise DocumentCommandError("undo requires its persisted inverse record")
    preview = preview_document_structure_command(document, command)
    supplied_preview = getattr(command, "preview_digest", None)
    if enforce_confirmation and preview.confirmation_required:
        if supplied_preview != preview.preview_digest:
            raise DocumentCommandConfirmationRequired(
                "fresh server preview confirmation is required"
            )

    duties = _by_id(document.duties, "duty_id")
    tasks = _by_id(document.tasks, "task_id")
    opks = _by_id(document.opks, "item_id")
    update: dict[str, Any] = {}
    touched = list(_touched(command, document))

    if isinstance(command, CreateDuty):
        if issued_entity_id in duties:
            raise DocumentCommandError("issued Duty identity already exists")
        update["duties"] = (
            *document.duties,
            ApprovedDuty(
                duty_id=issued_entity_id,
                statement=command.name,
                display_order=_next_order(document.duties),
            ),
        )
        touched.extend(("/duties", f"/duties/{issued_entity_id}"))
    elif isinstance(command, CreateTask):
        if issued_entity_id in tasks:
            raise DocumentCommandError("issued Task identity already exists")
        if command.duty_id is not None:
            _require(duties, command.duty_id, "Duty")
        update["tasks"] = (
            *document.tasks,
            ApprovedTask(
                task_id=issued_entity_id,
                duty_id=command.duty_id,
                statement=command.statement,
                action=command.action,
                object=command.object,
                display_order=_next_order(document.tasks),
                competency_level=command.competency_level,
            ),
        )
        touched.extend(("/tasks", f"/tasks/{issued_entity_id}"))
        if command.duty_id is not None:
            touched.append(f"/duties/{command.duty_id}")
    elif isinstance(command, CreateOpks):
        if issued_entity_id in opks:
            raise DocumentCommandError("issued OPKS identity already exists")
        _require(tasks, command.task_id, "Task")
        kind = ApprovedOpksKind(command.kind)
        update["opks"] = (
            *document.opks,
            ApprovedOpksItem(
                item_id=issued_entity_id,
                kind=kind,
                text=command.text,
                display_order=_next_order(document.opks, kind=kind),
                task_ids=(command.task_id,),
                evidence_source_ids=(employee_source_id,),
            ),
        )
        touched.extend(
            (
                "/opks",
                f"/opks/{issued_entity_id}",
                f"/tasks/{command.task_id}",
            )
        )
    elif isinstance(command, CreateAttitude):
        if issued_entity_id in opks:
            raise DocumentCommandError("issued OPKS identity already exists")
        update["opks"] = (
            *document.opks,
            ApprovedOpksItem(
                item_id=issued_entity_id,
                kind=ApprovedOpksKind.ATTITUDE,
                text=command.text,
                display_order=_next_order(
                    document.opks,
                    kind=ApprovedOpksKind.ATTITUDE,
                ),
                evidence_source_ids=(employee_source_id,),
            ),
        )
        touched.extend(("/opks", f"/opks/{issued_entity_id}"))
    elif isinstance(command, DissolveDuty):
        _require(duties, command.duty_id, "Duty")
        update["duties"] = tuple(
            item for item in document.duties if item.duty_id != command.duty_id
        )
        update["tasks"] = tuple(
            item.model_copy(update={"duty_id": None})
            if item.duty_id == command.duty_id
            else item
            for item in document.tasks
        )
    elif isinstance(command, CascadeDeleteDuty):
        _require(duties, command.duty_id, "Duty")
        deleted_task_ids = {
            item.task_id for item in document.tasks if item.duty_id == command.duty_id
        }
        remaining_tasks, remaining_opks = _delete_tasks(document, deleted_task_ids)
        update.update(
            {
                "duties": tuple(
                    item
                    for item in document.duties
                    if item.duty_id != command.duty_id
                ),
                "tasks": remaining_tasks,
                "opks": remaining_opks,
            }
        )
    elif isinstance(command, MoveTask):
        task = _require(tasks, command.task_id, "Task")
        if command.destination_duty_id is not None:
            _require(duties, command.destination_duty_id, "Duty")
        update["tasks"] = tuple(
            item.model_copy(update={"duty_id": command.destination_duty_id})
            if item.task_id == task.task_id
            else item
            for item in document.tasks
        )
    elif isinstance(command, DeleteTask):
        _require(tasks, command.task_id, "Task")
        update["tasks"], update["opks"] = _delete_tasks(
            document,
            {command.task_id},
        )
    elif isinstance(command, LinkSharedOpks):
        item = _require(opks, command.item_id, "OPKS item")
        _require(tasks, command.task_id, "Task")
        if not _shared(item):
            raise DocumentCommandError("only K or S may be linked to another Task")
        if command.task_id in item.task_ids:
            raise DocumentCommandError("K/S item is already linked to the Task")
        linked = tuple(
            sorted((*item.task_ids, command.task_id), key=str)
        )
        update["opks"] = tuple(
            candidate.model_copy(update={"task_ids": linked})
            if candidate.item_id == item.item_id
            else candidate
            for candidate in document.opks
        )
    elif isinstance(command, UnlinkSharedOpks):
        item = _require(opks, command.item_id, "OPKS item")
        _require(tasks, command.task_id, "Task")
        if not _shared(item):
            raise DocumentCommandError("only K or S may be unlinked from a Task")
        if command.task_id not in item.task_ids:
            raise DocumentCommandError("K/S item is not linked to the Task")
        update["opks"] = tuple(
            candidate.model_copy(
                update={
                    "task_ids": tuple(
                        task_id
                        for task_id in candidate.task_ids
                        if task_id != command.task_id
                    )
                }
            )
            if candidate.item_id == item.item_id
            else candidate
            for candidate in document.opks
        )
    elif isinstance(command, DeleteOwnedOpks):
        item = _require(opks, command.item_id, "OPKS item")
        if not _owned(item):
            raise DocumentCommandError("owned delete requires O, P, or A")
        update["opks"] = tuple(
            candidate.model_copy(
                update={
                    "indicator_ids": tuple(
                        identity
                        for identity in candidate.indicator_ids
                        if identity != item.item_id
                    )
                }
            )
            for candidate in document.opks
            if candidate.item_id != item.item_id
        )
    elif isinstance(command, DeleteSharedOpks):
        item = _require(opks, command.item_id, "OPKS item")
        if not _shared(item):
            raise DocumentCommandError("permanent shared delete requires K or S")
        update["opks"] = tuple(
            candidate for candidate in document.opks if candidate.item_id != item.item_id
        )
    elif isinstance(command, ReorderEntity):
        if command.entity_kind == "duty":
            if command.parent_id is not None:
                raise DocumentCommandError("Duty reorder has no parent")
            update["duties"] = _reordered(
                document.duties,
                entity_id=command.entity_id,
                before_entity_id=command.before_entity_id,
                identity_field="duty_id",
                eligible=lambda _item: True,
            )
        elif command.entity_kind == "task":
            if command.parent_id is not None:
                _require(duties, command.parent_id, "Duty")
            update["tasks"] = _reordered(
                document.tasks,
                entity_id=command.entity_id,
                before_entity_id=command.before_entity_id,
                identity_field="task_id",
                eligible=lambda item: item.duty_id == command.parent_id,
            )
        else:
            target = _require(opks, command.entity_id, "OPKS item")
            update["opks"] = _reordered(
                document.opks,
                entity_id=command.entity_id,
                before_entity_id=command.before_entity_id,
                identity_field="item_id",
                eligible=lambda item: item.kind is target.kind
                and (
                    command.parent_id is None
                    or command.parent_id in item.task_ids
                ),
            )
    else:  # pragma: no cover - the discriminated union is exhaustive
        raise DocumentCommandError("unsupported document structure command")

    try:
        after = ApprovedJobDocument.model_validate(
            document.model_copy(update=update).model_dump(mode="json")
        )
    except ValueError as error:
        raise DocumentCommandError(str(error)) from error
    touched.extend(_changed_entity_paths(document, after))
    inverse: dict[str, JsonValue] = {
        "operation": "restore_documents",
        "current_document": document.model_dump(mode="json"),
    }
    return DocumentStructurePlan(
        current_after=after,
        touched_paths=tuple(dict.fromkeys(touched)),
        blast_radius=preview,
        inverse_command=inverse,
    )


__all__ = [
    "CascadeDeleteDuty",
    "CreateAttitude",
    "CreateDuty",
    "CreateOpks",
    "CreateTask",
    "DeleteOwnedOpks",
    "DeleteSharedOpks",
    "DeleteTask",
    "DissolveDuty",
    "DocumentCommandBlastRadius",
    "DocumentCommandConfirmationRequired",
    "DocumentCommandError",
    "DocumentStructureCommand",
    "DocumentStructurePlan",
    "LinkSharedOpks",
    "MoveTask",
    "ReorderEntity",
    "UndoDocumentCommand",
    "UnlinkSharedOpks",
    "plan_document_structure_command",
    "preview_document_structure_command",
]
