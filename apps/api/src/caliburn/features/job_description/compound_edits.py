"""JD 擁有者的四種複合意圖；來源已由 workflow 固定，不包含交易或外部資格。"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from caliburn.features.job_description.areas import CreateArea, ResponsibilityArea, ReviseArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CreateCapability,
    ReorderTaskCapability,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CreateCollaborator,
    ReviseCollaborator,
)
from caliburn.features.job_description.conditions import (
    CreateCondition,
    JobCondition,
    ReviseCondition,
)
from caliburn.features.job_description.models import ProfileChange, ProfileField, ReviseJdProfile
from caliburn.features.job_description.sources import JdSource, JdSourceChange, JdSourceTarget
from caliburn.features.job_description.tasks import CreateTask, DetailKind, ReviseTask, WorkTask

type ItemCreation = CreateArea | CreateCapability | CreateCollaborator | CreateCondition
type ItemContentRevision = (
    ReviseArea | ReviseTask | ReviseCapability | ReviseCollaborator | ReviseCondition
)
type CompoundItem = ResponsibilityArea | WorkTask | Capability | Collaborator | JobCondition
type JdEditEffect = Literal["created", "updated", "aligned", "unchanged"]


@dataclass(frozen=True, slots=True)
class BoundProfileSources:
    field: ProfileField
    changes: tuple[JdSourceChange, ...]


@dataclass(frozen=True, slots=True)
class BoundTaskCapability:
    capability_id: UUID
    sources: tuple[JdSource, ...]


@dataclass(frozen=True, slots=True)
class BoundItemSources:
    target: JdSourceTarget
    changes: tuple[JdSourceChange, ...]


@dataclass(frozen=True, slots=True)
class AddedDetailSources:
    kind: DetailKind
    sources: tuple[JdSource, ...]


@dataclass(frozen=True, slots=True)
class ReviseProfileWithSources:
    command_id: UUID
    expected_revision_id: UUID
    changes: tuple[ProfileChange, ...]
    sources: tuple[BoundProfileSources, ...]

    def __post_init__(self) -> None:
        if self.changes:
            ReviseJdProfile(self.command_id, self.expected_revision_id, self.changes)


@dataclass(frozen=True, slots=True)
class CreateTaskWithSources:
    command_id: UUID
    expected_revision_id: UUID
    task: CreateTask
    task_sources: tuple[JdSource, ...]
    detail_sources: tuple[tuple[JdSource, ...], ...]
    capabilities: tuple[BoundTaskCapability, ...]


@dataclass(frozen=True, slots=True)
class CreateItemWithSources:
    command_id: UUID
    expected_revision_id: UUID
    item: ItemCreation
    sources: tuple[JdSource, ...]


@dataclass(frozen=True, slots=True)
class ReviseItemWithSources:
    command_id: UUID
    expected_revision_id: UUID
    content: ItemContentRevision | None
    capabilities: tuple[SetTaskCapability | ReorderTaskCapability, ...]
    sources: tuple[BoundItemSources, ...]
    added_details: tuple[AddedDetailSources, ...]


type CompoundJdEdit = (
    ReviseProfileWithSources | CreateTaskWithSources | CreateItemWithSources | ReviseItemWithSources
)


@dataclass(frozen=True, slots=True)
class JdCompoundEditResult:
    revision_id: UUID
    effect: JdEditEffect
    created_item: CompoundItem | None = None
