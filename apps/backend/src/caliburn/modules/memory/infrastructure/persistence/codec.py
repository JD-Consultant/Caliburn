"""復水目前列、發布快照與整理狀態。"""

import json
from uuid import UUID

from pydantic import ConfigDict, Field

from caliburn.modules.memory.application.errors import MemoryDataError
from caliburn.modules.memory.domain.analysis import MemoryAnalysis, MemoryFailure
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.items import (
    MemoryItem,
    MemoryKind,
    WorkSituation,
    WorkUnderstanding,
)
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION, MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.modules.memory.infrastructure.persistence.orm_models import (
    MemoryItemRow,
    MemorySnapshotRow,
    WorkMemoryRow,
)
from caliburn.shared.domain.base_value_object import BaseValueObject
from caliburn.shared.domain.domain_error import DomainError

SCHEMA_VERSION = 1


class Payload(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)


class ItemPayload(Payload):
    item_id: UUID
    kind: MemoryKind
    title: str
    description: str
    body: str
    source_ids: tuple[UUID, ...]
    changed_version: int = Field(gt=0, le=MAX_MEMORY_VERSION)

    @classmethod
    def from_domain(cls, item: MemoryItem) -> ItemPayload:
        source_ids = (
            item.interview_message_ids
            if isinstance(item, WorkSituation)
            else item.situation_ids
        )
        return cls(
            item_id=item.id,
            kind=item.kind,
            title=item.content.title,
            description=item.content.description,
            body=item.content.body,
            source_ids=source_ids,
            changed_version=item.changed_version,
        )

    def to_domain(self, *, workspace_id: UUID) -> MemoryItem:
        content = MemoryContent(
            title=self.title, description=self.description, body=self.body
        )
        if self.kind == "situation":
            return WorkSituation(
                id=self.item_id,
                workspace_id=workspace_id,
                content=content,
                changed_version=self.changed_version,
                interview_message_ids=self.source_ids,
            )
        return WorkUnderstanding(
            id=self.item_id,
            workspace_id=workspace_id,
            content=content,
            changed_version=self.changed_version,
            situation_ids=self.source_ids,
        )


class SnapshotContent(Payload):
    items: tuple[ItemPayload, ...]


def decode_current(root: WorkMemoryRow, rows: tuple[MemoryItemRow, ...]) -> WorkMemory:
    try:
        analysis = (
            MemoryAnalysis.model_validate_json(_json_object(root.analysis))
            if root.analysis is not None
            else None
        )
        failure = (
            MemoryFailure.model_validate_json(_json_object(root.failure))
            if root.failure is not None
            else None
        )
        items = tuple(
            ItemPayload.model_validate(
                {
                    "item_id": row.item_id,
                    "kind": row.kind,
                    "title": row.title,
                    "description": row.description,
                    "body": row.body,
                    "source_ids": tuple(row.source_ids),
                    "changed_version": row.changed_version,
                }
            ).to_domain(workspace_id=root.workspace_id)
            for row in rows
        )
        return WorkMemory(
            id=root.workspace_id,
            version=root.version,
            items=items,
            published_version=root.published_version,
            analysis=analysis,
            failure=failure,
        )
    except (DomainError, ValueError, TypeError) as error:
        raise MemoryDataError("Memory 目前稿無法重建") from error


def encode_snapshot(snapshot: MemorySnapshot) -> dict[str, object]:
    return SnapshotContent(
        items=tuple(ItemPayload.from_domain(item) for item in snapshot.items)
    ).model_dump(mode="json")


def decode_snapshot(row: MemorySnapshotRow) -> MemorySnapshot:
    try:
        _require_schema_version(row.schema_version)
        content = SnapshotContent.model_validate_json(_json_object(row.content))
        return MemorySnapshot(
            workspace_id=row.workspace_id,
            version=row.version,
            covered_through_message_id=row.covered_through_message_id,
            published_at=row.published_at,
            items=tuple(
                item.to_domain(workspace_id=row.workspace_id) for item in content.items
            ),
        )
    except (DomainError, ValueError, TypeError) as error:
        raise MemoryDataError("Memory 發布快照無法重建") from error


def _json_object(value: object) -> str:
    if not isinstance(value, dict):
        raise ValueError("保存資料須為 JSON object")
    return json.dumps(value, allow_nan=False)


def _require_schema_version(version: int) -> None:
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ValueError("未知的保存資料格式")
