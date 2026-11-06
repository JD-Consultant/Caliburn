"""JD 自有來源關係；固定定位不攜帶來源正文。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from caliburn.shared.domain.base_value_object import BaseValueObject

type CitationTargetKind = Literal[
    "job_description",
    "duty",
    "task",
    "knowledge",
    "skill",
    "collaboration",
    "condition",
]


class InterviewReference(BaseValueObject):
    kind: Literal["interview"] = "interview"
    workspace_id: UUID
    message_id: UUID


class MemoryReference(BaseValueObject):
    kind: Literal["memory"] = "memory"
    workspace_id: UUID
    published_version: int = Field(gt=0, le=9007199254740991)
    item_id: UUID


type SourceReference = Annotated[
    InterviewReference | MemoryReference, Field(discriminator="kind")
]


class Citation(BaseValueObject):
    id: UUID
    target_kind: CitationTargetKind
    target_id: UUID
    source: SourceReference
    jd_changed: bool = False
