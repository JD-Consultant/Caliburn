"""歷史內容與兩個版本的結構化淨差異。"""

from typing import Literal
from uuid import UUID

from pydantic import PositiveInt

from caliburn.modules.job_description.application.content import (
    CollectionKind,
    ContentValue,
    ItemKind,
    JobDescriptionContent,
)
from caliburn.modules.job_description.application.history_types import (
    HistoryEntry,
)
from caliburn.shared.application.base_dto import BaseDTO


class JobDescriptionHistoryResult(BaseDTO):
    content: JobDescriptionContent
    entry: HistoryEntry


class FieldDifference(BaseDTO):
    field: str
    before: ContentValue
    after: ContentValue


class ItemDifference(BaseDTO):
    kind: ItemKind
    id: UUID
    change: Literal["added", "removed", "modified"]
    fields: tuple[FieldDifference, ...]


class CollectionDifference(BaseDTO):
    collection: CollectionKind
    owner_id: UUID
    group: UUID | str | None = None
    before_ids: tuple[UUID, ...]
    after_ids: tuple[UUID, ...]


class JobDescriptionDifference(BaseDTO):
    job_description_id: UUID
    before_version: PositiveInt
    after_version: PositiveInt
    items: tuple[ItemDifference, ...]
    collections: tuple[CollectionDifference, ...]
