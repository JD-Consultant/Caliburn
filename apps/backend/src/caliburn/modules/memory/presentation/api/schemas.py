"""Memory 發布查讀投影；不暴露目前整理資格。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION

type PublishedVersion = Annotated[int, Field(ge=1, le=MAX_MEMORY_VERSION)]


class MemoryMapEntryResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    item_id: UUID
    kind: Literal["situation", "understanding"]
    title: str
    description: str
    changed_version: PublishedVersion


class MemoryMapResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    workspace_id: UUID
    published_version: PublishedVersion | None
    covered_through_message_id: UUID | None
    items: list[MemoryMapEntryResponse]


class MemoryItemResponse(MemoryMapEntryResponse):
    workspace_id: UUID
    published_version: PublishedVersion
    body: str
    source_ids: list[UUID] = Field(
        description="情境指向同 Workspace 訪談訊息；理解指向此發布版的情境。"
    )
