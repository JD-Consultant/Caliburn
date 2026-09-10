"""Internal JD ports; no transport DTO or second document owner."""
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

Value = list[dict[str, Any]]
Origin = Literal['initial', 'ai', 'manual']


@dataclass(frozen=True)
class JdScope:
    document_id: str


@dataclass(frozen=True)
class JdRevision:
    scope: JdScope
    id: UUID
    parent_id: UUID | None
    origin: Origin
    value: Value


@dataclass(frozen=True)
class JdReadQuery:
    revision_id: UUID | None = None
    target_id: str | None = None
    selection: dict | None = None


@dataclass(frozen=True)
class JdReadView:
    revision: JdRevision | None = None
    fragment: list = field(default_factory=list)
    status: str = 'ok'


@dataclass(frozen=True)
class JdManualIntent:
    scope: JdScope
    operation_id: UUID
    base_id: UUID
    digest: str
    value: Value
    origin: Literal['manual'] = 'manual'


@dataclass(frozen=True)
class JdEditIntent:
    scope: JdScope
    operation_id: UUID
    base_id: UUID
    digest: str
    commands: list[dict[str, Any]]
    origin: Literal['ai'] = 'ai'


@dataclass(frozen=True)
class JdCandidate:
    value: Value
    operations: list[dict] | None
    affected_ids: list[str]


@dataclass(frozen=True)
class JdWriteOutcome:
    scope: JdScope
    operation_id: UUID | None
    base_id: UUID | None
    result_id: UUID | None
    status: str
    origin: Origin
    durability: str = 'confirmed'
    operations: list[dict] | None = None
    affected_ids: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    command_index: int | None = None
    next_action: str = 'continue'


@dataclass(frozen=True)
class JdChangeQuery:
    before_id: UUID | None = None
    after_id: UUID | None = None
    operation_id: UUID | None = None


@dataclass(frozen=True)
class JdChangeView:
    before: JdRevision | None = None
    after: JdRevision | None = None
    outcome: JdWriteOutcome | None = None
    status: str = 'ok'


@dataclass(frozen=True)
class JdHistory:
    total: int
    ai: int
    manual: int
    latest: tuple[JdWriteOutcome, ...]


class JdMissing(LookupError):
    """Catalog, revision, or head was authoritatively absent in this scope."""


class JdStorageFailure(RuntimeError):
    """Known storage failure; never expose driver diagnostics on the wire."""
