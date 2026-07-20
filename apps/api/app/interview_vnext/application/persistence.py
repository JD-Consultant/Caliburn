"""Async persistence ports for vNext durable workflows (V2-B reference §6).

Application code depends on these Protocols/DTOs only; SQLAlchemy rows live in
``interview_vnext.persistence`` and never cross this seam. Every port method
takes an authoritative ``tenant_id`` — looking rows up by ``session_id`` alone
is forbidden (reference §2.3). The sync in-memory fakes in ``observability``
keep their own contracts; async SQL adapters implement these ports instead.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.domain.identifiers import (
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
    UtcDatetime,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import ArtifactRecord, ArtifactRef
from app.interview_vnext.observability.checkpoint import OperationCheckpoint
from app.interview_vnext.observability.events import ExecutionEvent, ExecutionStatus


# ── Durable run / command / attempt DTOs(§5.2/§5.4/§5.8 row contracts)──────
# tenant_id 不進 DTO：與 ArtifactRecord/OperationCheckpoint 一致,tenant 是
# persistence-only scope,由 port 參數傳遞,不混進 domain-facing payload。


class RunStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED})


class WorkflowRun(DomainModel):
    """One durable workflow run: event hash-chain owner and delivery ordering group."""

    run_id: UUID
    session_id: UUID
    architecture_id: StableName
    workflow_version: SemVer
    taxonomy_id: StableName
    taxonomy_version: SemVer
    taxonomy_hash: Sha256
    status: RunStatus = RunStatus.OPEN
    event_count: int = Field(default=0, ge=0)
    first_event_hash: Sha256 | None = None
    last_event_hash: Sha256 | None = None
    manifest_artifact_id: UUID | None = None
    started_at: UtcDatetime
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def counters_and_terminal_fields_are_coherent(self) -> "WorkflowRun":
        if self.event_count == 0:
            if self.first_event_hash is not None or self.last_event_hash is not None:
                raise ValueError("run with zero events cannot carry event hashes")
        elif self.first_event_hash is None or self.last_event_hash is None:
            raise ValueError("run with events requires first and last event hash")
        if self.status == RunStatus.OPEN:
            if self.completed_at is not None or self.manifest_artifact_id is not None:
                raise ValueError("open run cannot carry completion or manifest")
        else:
            # finalize 協定(§7.3)同 transaction 設齊三者;terminal run 至少有
            # started event,因此 event_count >= 1。
            if self.completed_at is None or self.manifest_artifact_id is None:
                raise ValueError("terminal run requires completed_at and manifest artifact")
            if self.event_count < 1:
                raise ValueError("terminal run requires at least one execution event")
            if self.completed_at < self.started_at:
                raise ValueError("run completed_at cannot precede started_at")
        return self


class CommandRecord(DomainModel):
    """Idempotency record for one successfully applied domain command (§5.4)."""

    command_id: UUID
    session_id: UUID
    run_id: UUID
    request_idempotency_key: NonEmptyText | None = None
    command_schema_id: NonEmptyText
    command_artifact_id: UUID
    command_hash: Sha256
    reduction_artifact_id: UUID
    reduction_hash: Sha256
    expected_state_version: int = Field(ge=0)
    result_state_version: int = Field(ge=1)
    result_state_hash: Sha256
    result_reason_code: StableName
    occurred_at: UtcDatetime
    committed_at: UtcDatetime

    @model_validator(mode="after")
    def result_version_increments_once(self) -> "CommandRecord":
        if self.result_state_version != self.expected_state_version + 1:
            raise ValueError("command result state version must equal expected + 1")
        return self


class AttemptStatus(StrEnum):
    CALLING = "calling"
    RESULT_RECORDED = "result_recorded"


class OperationAttempt(DomainModel):
    """Durable per-attempt record; retry inserts a new row, never rewrites one (§5.8)."""

    attempt_id: UUID
    run_id: UUID
    session_id: UUID
    operation_id: UUID
    attempt: int = Field(ge=1)
    status: AttemptStatus = AttemptStatus.CALLING
    request_artifact_id: UUID
    result_artifact_id: UUID | None = None
    provider: StableName
    requested_model: NonEmptyText
    provider_execution_ref_kind: StableName | None = None
    provider_execution_ref: NonEmptyText | None = None
    deadline_at: UtcDatetime
    started_at: UtcDatetime
    updated_at: UtcDatetime
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def result_fields_match_status(self) -> "OperationAttempt":
        if self.updated_at < self.started_at:
            raise ValueError("attempt updated_at cannot precede started_at")
        if (self.provider_execution_ref_kind is None) != (self.provider_execution_ref is None):
            raise ValueError("provider execution ref kind and value must be set together")
        if self.status == AttemptStatus.CALLING:
            if self.result_artifact_id is not None or self.completed_at is not None:
                raise ValueError("calling attempt cannot carry a result")
        else:
            if self.result_artifact_id is None or self.completed_at is None:
                raise ValueError("recorded attempt requires result artifact and completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("attempt completed_at cannot precede started_at")
        return self


class ExecutionEventDraft(DomainModel):
    """Logical event fields supplied by the caller; ``append_event`` assigns the
    run-owned sequence/previous-hash/taxonomy identity inside one transaction,
    so callers can never guess the chain position (§5.5/§7.2)."""

    event_id: UUID
    occurred_at: UtcDatetime
    session_id: UUID          # DB adapter deliberately narrows the optional envelope shape
    turn_id: UUID | None = None
    operation_id: UUID | None = None
    parent_operation_id: UUID | None = None
    attempt_id: UUID | None = None
    attempt: int | None = Field(default=None, ge=1)
    event_type: StableName
    stage: StableName
    status: ExecutionStatus
    input_artifacts: tuple[ArtifactRef, ...] = ()
    output_artifacts: tuple[ArtifactRef, ...] = ()
    state_before_hash: Sha256 | None = None
    state_after_hash: Sha256 | None = None
    metadata_json: str = "{}"

    @field_validator("metadata_json")
    @classmethod
    def metadata_is_canonical_json_object(cls, value: str) -> str:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("metadata_json must encode an object")
        if value != canonical_json(parsed):
            raise ValueError("metadata_json must use canonical JSON")
        return value

    @model_validator(mode="after")
    def attempt_fields_are_paired(self) -> "ExecutionEventDraft":
        if (self.attempt is None) != (self.attempt_id is None):
            raise ValueError("attempt and attempt_id must be set together")
        if self.attempt is not None and self.operation_id is None:
            raise ValueError("attempt requires operation_id")
        return self


# ── Async repository ports(§4.2;僅 Protocol,不 import SQLAlchemy)──────────


class SessionRepository(Protocol):
    async def create(self, *, tenant_id: UUID, state: InterviewState) -> None: ...

    async def get(self, *, tenant_id: UUID, session_id: UUID) -> InterviewState: ...

    async def save_cas(
        self, *, tenant_id: UUID, old_version: int, new_state: InterviewState
    ) -> bool:
        """單一 UPDATE … WHERE state_version = old_version RETURNING。
        回 False = 0 rows;呼叫端必須 rollback 後用**新 transaction**分辨
        duplicate command 或 stale conflict,不得在此層自行 commit/retry。"""
        ...

    async def initial_state_artifact_id(
        self, *, tenant_id: UUID, session_id: UUID
    ) -> UUID | None:
        """version-0 snapshot pointer(§5.1);任何 command 前 application 必須
        確認非 null。"""
        ...

    async def set_initial_state_artifact(
        self, *, tenant_id: UUID, session_id: UUID, artifact_id: UUID
    ) -> bool:
        """只允許在 state_version = 0 且 pointer 尚空時設定(§7.2 step 3);
        回 False = 前置條件不成立(0 rows)。"""
        ...


class ArtifactRepository(Protocol):
    async def put(self, *, tenant_id: UUID, record: ArtifactRecord) -> ArtifactRecord: ...

    async def get(self, *, tenant_id: UUID, artifact_id: UUID) -> ArtifactRecord: ...

    async def get_many(
        self, *, tenant_id: UUID, refs: Sequence[ArtifactRef]
    ) -> tuple[ArtifactRecord, ...]:
        """依 caller refs 順序回傳;每個 ref 的 kind/media/schema/hash/size
        與存檔不符即錯誤,不靜默容忍。"""
        ...


class CommandRepository(Protocol):
    async def get_by_command_id(
        self, *, tenant_id: UUID, session_id: UUID, command_id: UUID
    ) -> CommandRecord | None: ...

    async def get_by_request_key(
        self, *, tenant_id: UUID, session_id: UUID, request_idempotency_key: str
    ) -> CommandRecord | None: ...

    async def add(self, *, tenant_id: UUID, record: CommandRecord) -> None: ...


class RunRepository(Protocol):
    async def create(self, *, tenant_id: UUID, run: WorkflowRun) -> None: ...

    async def get(self, *, tenant_id: UUID, run_id: UUID) -> WorkflowRun | None: ...

    async def lock(self, *, tenant_id: UUID, run_id: UUID) -> None:
        """取得 run row 鎖(SELECT … FOR UPDATE)。command commit 在寫入前先鎖
        run,建立一致鎖序(run → session/artifacts)——否則 FK KEY SHARE 鎖與
        CAS/append 的鎖會在併發下互等死鎖。transaction 必須短、無 network I/O。"""
        ...

    async def finalize(self, *, tenant_id: UUID, run: WorkflowRun) -> None:
        """open → completed|failed 一次性轉換(含 completed_at/manifest ref)。"""
        ...


class CheckpointRepository(Protocol):
    async def create(self, *, tenant_id: UUID, checkpoint: OperationCheckpoint) -> None: ...

    async def get_by_operation(
        self, *, tenant_id: UUID, operation_id: UUID
    ) -> OperationCheckpoint | None: ...

    async def get_by_operation_for_update(
        self, *, tenant_id: UUID, operation_id: UUID
    ) -> OperationCheckpoint | None:
        """Serialize attempt claims before inserting the operation's child row."""
        ...

    async def get_by_idempotency(
        self, *, tenant_id: UUID, session_id: UUID, operation_name: str, idempotency_key: str
    ) -> OperationCheckpoint | None: ...

    async def save_cas(
        self, *, tenant_id: UUID, expected_revision: int, checkpoint: OperationCheckpoint
    ) -> bool:
        """UPDATE … WHERE revision = expected RETURNING;False = 0 rows,
        呼叫端 rollback/reload 後比對 idempotent transition 或 CheckpointConflict。"""
        ...


class AttemptRepository(Protocol):
    async def start(self, *, tenant_id: UUID, attempt: OperationAttempt) -> None: ...

    async def get(self, *, tenant_id: UUID, attempt_id: UUID) -> OperationAttempt | None: ...

    async def record_result(self, *, tenant_id: UUID, attempt: OperationAttempt) -> None:
        """calling → result_recorded 的一次性 UPDATE;已記錄結果不可換 artifact,
        retry 一律 INSERT 新 attempt row。"""
        ...


class CaptureWriter(Protocol):
    async def append_event(
        self, *, tenant_id: UUID, run_id: UUID, draft: ExecutionEventDraft
    ) -> ExecutionEvent:
        """同一 transaction:lock run → 以 event_count+1/last_event_hash 建
        event → insert immutable event + pending outbox → 更新 run counters。"""
        ...

    async def build_and_store_manifest(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        manifest_artifact_id: UUID,
        completed_at: datetime,
        root_artifacts: tuple[ArtifactRef, ...] = (),
        limitations: tuple[str, ...] = (),
    ) -> ArtifactRef:
        """以 transaction 內完整 chain 建/驗 RunManifest 並存為 artifact(§7.3)。"""
        ...

    async def finalize_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        final_status: RunStatus,
        terminal_event_id: UUID,
        manifest_artifact_id: UUID,
        completed_at: datetime,
        root_artifacts: tuple[ArtifactRef, ...] = (),
        limitations: tuple[str, ...] = (),
        event_status: ExecutionStatus = ExecutionStatus.OK,
    ) -> tuple[WorkflowRun, ArtifactRef]:
        """§7.3:append terminal event → 以完整 chain 建/驗 manifest → run
        open→terminal 一次性轉換;三者同一 transaction,冪等回既有 manifest。"""
        ...


class VNextUnitOfWork(Protocol):
    """一個 instance = 一個 AsyncSession/transaction,單一 task 使用,不可重入。
    Repository 只 flush,commit/rollback 唯一擁有者是 UoW;provider/exporter
    network call 不得發生在 UoW block 內。"""

    sessions: SessionRepository
    artifacts: ArtifactRepository
    commands: CommandRepository
    runs: RunRepository
    checkpoints: CheckpointRepository
    attempts: AttemptRepository
    capture: CaptureWriter

    async def __aenter__(self) -> "VNextUnitOfWork": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
