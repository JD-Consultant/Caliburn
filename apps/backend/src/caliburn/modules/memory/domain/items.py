"""依據訪談的工作情境及依據情境的工作理解。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field

from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.errors import (
    DuplicateMemoryTitleError,
    InvalidMemorySnapshotError,
    InvalidMemorySourceError,
)
from caliburn.shared.domain.base_entity import BaseEntity


def _ordered_sources(source_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
    if len(set(source_ids)) != len(source_ids):
        raise InvalidMemorySourceError("Memory item sources must be unique")
    return tuple(sorted(source_ids, key=lambda source_id: source_id.int))


type _SourceIds = Annotated[tuple[UUID, ...], AfterValidator(_ordered_sources)]
type MemoryKind = Literal["situation", "understanding"]


class WorkSituation(BaseEntity[UUID]):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    workspace_id: UUID
    content: MemoryContent
    interview_message_ids: _SourceIds
    changed_version: int = Field(gt=0)

    @property
    def kind(self) -> Literal["situation"]:
        return "situation"


class WorkUnderstanding(BaseEntity[UUID]):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    workspace_id: UUID
    content: MemoryContent
    situation_ids: _SourceIds
    changed_version: int = Field(gt=0)

    @property
    def kind(self) -> Literal["understanding"]:
        return "understanding"


type MemoryItem = WorkSituation | WorkUnderstanding


def validate_memory_items(
    *, workspace_id: UUID, version: int, items: tuple[MemoryItem, ...]
) -> None:
    """檢查目前稿或快照都必須具備的完整內容圖。"""
    item_ids: set[UUID] = set()
    titles: set[tuple[MemoryKind, str]] = set()
    situation_ids = {item.id for item in items if isinstance(item, WorkSituation)}
    for item in items:
        if item.workspace_id != workspace_id or item.id in item_ids:
            raise InvalidMemorySnapshotError("Memory item identity is inconsistent")
        if not 0 < item.changed_version <= version:
            raise InvalidMemorySnapshotError("Memory item version is out of range")
        title_key = (item.kind, item.content.title)
        if title_key in titles:
            raise DuplicateMemoryTitleError("Memory title already exists in this layer")
        if isinstance(item, WorkUnderstanding) and not situation_ids.issuperset(
            item.situation_ids
        ):
            raise InvalidMemorySourceError("Understanding source is not a situation")
        item_ids.add(item.id)
        titles.add(title_key)


def same_memory_item(left: MemoryItem, right: MemoryItem) -> bool:
    """比較身分、內容、來源與 stamp，保留 Entity 本身的身分 equality。"""
    if (
        left.id != right.id
        or left.workspace_id != right.workspace_id
        or left.content != right.content
        or left.changed_version != right.changed_version
    ):
        return False
    if isinstance(left, WorkSituation) and isinstance(right, WorkSituation):
        return left.interview_message_ids == right.interview_message_ids
    if isinstance(left, WorkUnderstanding) and isinstance(right, WorkUnderstanding):
        return left.situation_ids == right.situation_ids
    return False
