"""Async SQL repositories implementing the application persistence ports (V2-B §6).

Rules enforced here, not trusted from callers:
- every lookup/update is tenant-scoped;
- reads hydrate Pydantic contracts via ``serialization`` and re-verify the
  normalized row columns against the nested payload (dual check, §6.4);
- state/checkpoint writes are explicit CAS ``UPDATE … WHERE <token> RETURNING``;
  0 rows returns False — classification (duplicate vs stale) happens in the
  use case after rollback, never here;
- repositories only ``flush``/``execute``; commit/rollback belong to the UoW;
- immutable tables never get UPDATE/DELETE statements from this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview_vnext.application.persistence import (
    CommandRecord,
    OperationAttempt,
    AttemptStatus,
    RunStatus,
    WorkflowRun,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    ArtifactStorage,
)
from app.interview_vnext.observability.checkpoint import OperationCheckpoint

from . import serialization as ser
from .errors import (
    ArtifactConflict,
    ArtifactNotFound,
    CheckpointConflict,
    ExecutionEventConflict,
    ExternalArtifactStoreUnavailable,
    IdempotencyConflict,
    PersistedDataCorruption,
    PersistenceError,
    SessionNotFound,
)
from .models import (
    VNextArtifactRow,
    VNextAttemptRow,
    VNextCheckpointRow,
    VNextCommandRow,
    VNextRunRow,
    VNextSessionRow,
)


def translate_integrity_error(exc: IntegrityError) -> PersistenceError | None:
    """Named-constraint → stable error(application 不得斷言 SQLSTATE/英文訊息)。
    回 None = 不認得,呼叫端包成一般 PersistenceError。"""
    message = str(exc.orig or exc)
    for fragment, factory in (
        ("uq_ivn_commands_tenant_session_command",
         lambda: IdempotencyConflict("duplicate command id raced another writer")),
        ("uq_ivn_commands_request_key",
         lambda: IdempotencyConflict("duplicate request key raced another writer")),
        ("uq_ivn_artifacts_tenant_artifact",
         lambda: ArtifactConflict("artifact id raced another writer")),
        ("interview_vnext_artifacts_pkey",
         lambda: ArtifactConflict("artifact id raced another writer")),
        ("uq_ivn_events_tenant_run_sequence",
         lambda: ExecutionEventConflict("event sequence raced another writer")),
        ("interview_vnext_execution_events_pkey",
         lambda: ExecutionEventConflict("event id raced another writer")),
        ("uq_ivn_ckpt_tenant_operation",
         lambda: CheckpointConflict("operation id raced another writer")),
        ("uq_ivn_ckpt_idempotency",
         lambda: CheckpointConflict("operation idempotency key raced another writer")),
        ("uq_ivn_attempts_operation_attempt",
         lambda: CheckpointConflict("attempt number raced another writer")),
    ):
        if fragment in message:
            return factory()
    return None


# ── sessions ──────────────────────────────────────────────────────────────────


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, tenant_id: UUID, state: InterviewState) -> None:
        state = InterviewState.model_validate(state.model_dump())
        if state.session.tenant_id != tenant_id:
            raise PersistenceError("state tenant does not match authoritative tenant_id",
                                   tenant_id=tenant_id,
                                   state_tenant_id=state.session.tenant_id)
        s = state.session
        self._s.add(VNextSessionRow(
            session_id=s.session_id, tenant_id=tenant_id, profile_id=s.profile_id,
            architecture_id=s.architecture_id, workflow_version=s.workflow_version,
            reference_snapshot_id=s.reference_snapshot_id, status=s.status.value,
            state_version=s.state_version, state_schema_version=state.schema_version,
            state_json=ser.dump_model(state), state_hash=canonical_hash(state),
            initial_state_artifact_id=None,
            created_at=s.created_at, updated_at=s.updated_at,
        ))
        await self._s.flush()

    async def _row(self, tenant_id: UUID, session_id: UUID) -> VNextSessionRow:
        row = (await self._s.execute(
            sa.select(VNextSessionRow).where(
                VNextSessionRow.tenant_id == tenant_id,
                VNextSessionRow.session_id == session_id))).scalar_one_or_none()
        if row is None:
            raise SessionNotFound("interview session not found",
                                  tenant_id=tenant_id, session_id=session_id)
        return row

    async def get(self, *, tenant_id: UUID, session_id: UUID) -> InterviewState:
        row = await self._row(tenant_id, session_id)
        state = ser.load_state(row.state_json, row.state_hash,
                               session_id=row.session_id, state_version=row.state_version)
        s = state.session
        mismatches = [
            name for name, row_value, nested in (
                ("tenant_id", row.tenant_id, s.tenant_id),
                ("profile_id", row.profile_id, s.profile_id),
                ("architecture_id", row.architecture_id, s.architecture_id),
                ("workflow_version", row.workflow_version, s.workflow_version),
                ("reference_snapshot_id", row.reference_snapshot_id,
                 s.reference_snapshot_id),
                ("status", row.status, s.status.value),
                ("state_schema_version", row.state_schema_version, state.schema_version),
                ("created_at", row.created_at, s.created_at),
                ("updated_at", row.updated_at, s.updated_at),
            ) if row_value != nested
        ]
        if mismatches:
            raise PersistedDataCorruption(
                "session row columns do not match nested state",
                session_id=session_id, mismatched=",".join(mismatches))
        if s.state_version > 0:
            pointer = row.initial_state_artifact_id
            if pointer is None:
                raise PersistedDataCorruption(
                    "session has committed commands but no initial-state snapshot",
                    session_id=session_id, state_version=s.state_version)
            await self._verify_initial_snapshot(tenant_id, session_id, pointer)
        return state

    async def _verify_initial_snapshot(self, tenant_id: UUID, session_id: UUID,
                                       artifact_id: UUID) -> None:
        row = (await self._s.execute(
            sa.select(VNextArtifactRow.kind, VNextArtifactRow.session_id).where(
                VNextArtifactRow.tenant_id == tenant_id,
                VNextArtifactRow.artifact_id == artifact_id))).one_or_none()
        if row is None or row.kind != "state.snapshot.initial" or \
                row.session_id != session_id:
            raise PersistedDataCorruption(
                "initial-state pointer does not reference a session snapshot artifact",
                session_id=session_id, artifact_id=artifact_id)

    async def initial_state_artifact_id(self, *, tenant_id: UUID,
                                        session_id: UUID) -> UUID | None:
        row = await self._row(tenant_id, session_id)
        return row.initial_state_artifact_id

    async def set_initial_state_artifact(self, *, tenant_id: UUID, session_id: UUID,
                                         artifact_id: UUID) -> bool:
        """只允許在 state_version = 0 且 pointer 尚空時設定(§7.2 step 3)。"""
        result = await self._s.execute(
            sa.update(VNextSessionRow)
            .where(VNextSessionRow.tenant_id == tenant_id,
                   VNextSessionRow.session_id == session_id,
                   VNextSessionRow.state_version == 0,
                   VNextSessionRow.initial_state_artifact_id.is_(None))
            .values(initial_state_artifact_id=artifact_id)
            .returning(VNextSessionRow.session_id))
        return result.first() is not None

    async def save_cas(self, *, tenant_id: UUID, old_version: int,
                       new_state: InterviewState) -> bool:
        new_state = InterviewState.model_validate(new_state.model_dump())
        s = new_state.session
        if s.tenant_id != tenant_id:
            raise PersistenceError("state tenant does not match authoritative tenant_id",
                                   tenant_id=tenant_id, state_tenant_id=s.tenant_id)
        result = await self._s.execute(
            sa.update(VNextSessionRow)
            .where(VNextSessionRow.tenant_id == tenant_id,
                   VNextSessionRow.session_id == s.session_id,
                   VNextSessionRow.state_version == old_version)
            .values(status=s.status.value, state_version=s.state_version,
                    state_schema_version=new_state.schema_version,
                    state_json=ser.dump_model(new_state),
                    state_hash=canonical_hash(new_state),
                    updated_at=s.updated_at)
            .returning(VNextSessionRow.session_id))
        return result.first() is not None


# ── artifacts ─────────────────────────────────────────────────────────────────


_ARTIFACT_COLUMNS = tuple(VNextArtifactRow.__table__.columns.keys())


def _artifact_values(tenant_id: UUID, record: ArtifactRecord) -> dict:
    return {
        "artifact_id": record.ref.artifact_id, "tenant_id": tenant_id,
        "record_schema_version": record.schema_version,
        "run_id": record.run_id, "session_id": record.session_id,
        "turn_id": record.turn_id, "operation_id": record.operation_id,
        "attempt_id": record.attempt_id, "kind": record.ref.kind,
        "media_type": record.ref.media_type, "schema_id": record.ref.schema_id,
        "content_hash": record.ref.content_hash, "byte_size": record.ref.byte_size,
        "storage": record.storage.value, "inline_content": record.inline_content,
        "external_uri": record.external_uri,
        "retention_class": record.retention_class,
        "redaction_status": record.redaction_status.value,
        "contains_test_data": record.contains_test_data,
        "created_at": record.created_at,
    }


class SqlAlchemyArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def put(self, *, tenant_id: UUID, record: ArtifactRecord) -> ArtifactRecord:
        record = ArtifactRecord.model_validate(record.model_dump())
        if record.storage == ArtifactStorage.EXTERNAL:
            raise ExternalArtifactStoreUnavailable(
                "V2-B only accepts inline artifact writes",
                artifact_id=record.ref.artifact_id)
        stmt = (pg_insert(VNextArtifactRow)
                .values(**_artifact_values(tenant_id, record))
                .on_conflict_do_nothing(index_elements=["artifact_id"])
                .returning(VNextArtifactRow.artifact_id))
        inserted = (await self._s.execute(stmt)).first()
        if inserted is not None:
            return record
        # conflict → 讀既有列比完整 record;跨 tenant 的 ID 重用一律 conflict
        row = (await self._s.execute(
            sa.select(VNextArtifactRow).where(
                VNextArtifactRow.artifact_id == record.ref.artifact_id)
        )).scalar_one()
        if row.tenant_id != tenant_id:
            raise ArtifactConflict("artifact id already used by another tenant",
                                   artifact_id=record.ref.artifact_id)
        existing = ser.load_artifact(row)
        if existing != record:
            raise ArtifactConflict("artifact id already exists with different content",
                                   artifact_id=record.ref.artifact_id)
        return existing

    async def get(self, *, tenant_id: UUID, artifact_id: UUID) -> ArtifactRecord:
        row = (await self._s.execute(
            sa.select(VNextArtifactRow).where(
                VNextArtifactRow.tenant_id == tenant_id,
                VNextArtifactRow.artifact_id == artifact_id))).scalar_one_or_none()
        if row is None:
            raise ArtifactNotFound("artifact not found",
                                   tenant_id=tenant_id, artifact_id=artifact_id)
        return ser.load_artifact(row)

    async def get_many(self, *, tenant_id: UUID,
                       refs: Sequence[ArtifactRef]) -> tuple[ArtifactRecord, ...]:
        wanted = [ref.artifact_id for ref in refs]
        rows = (await self._s.execute(
            sa.select(VNextArtifactRow).where(
                VNextArtifactRow.tenant_id == tenant_id,
                VNextArtifactRow.artifact_id.in_(wanted)))).scalars().all()
        by_id = {row.artifact_id: row for row in rows}
        out: list[ArtifactRecord] = []
        for ref in refs:                      # 保序 + 逐 ref 完整比對
            row = by_id.get(ref.artifact_id)
            if row is None:
                raise ArtifactNotFound("referenced artifact does not exist",
                                       tenant_id=tenant_id, artifact_id=ref.artifact_id)
            record = ser.load_artifact(row)
            if record.ref != ref:
                raise ArtifactNotFound(
                    "artifact ref metadata does not match stored record",
                    tenant_id=tenant_id, artifact_id=ref.artifact_id)
            out.append(record)
        return tuple(out)


# ── commands ──────────────────────────────────────────────────────────────────


def _command_record_from_row(row: VNextCommandRow) -> CommandRecord:
    try:
        return CommandRecord(
            command_id=row.command_id, session_id=row.session_id, run_id=row.run_id,
            request_idempotency_key=row.request_idempotency_key,
            command_schema_id=row.command_schema_id,
            command_artifact_id=row.command_artifact_id, command_hash=row.command_hash,
            reduction_artifact_id=row.reduction_artifact_id,
            reduction_hash=row.reduction_hash,
            expected_state_version=row.expected_state_version,
            result_state_version=row.result_state_version,
            result_state_hash=row.result_state_hash,
            result_reason_code=row.result_reason_code,
            occurred_at=row.occurred_at, committed_at=row.committed_at,
        )
    except Exception as exc:  # noqa: BLE001  (ValidationError → corruption)
        raise PersistedDataCorruption("persisted command row failed validation",
                                      command_id=row.command_id) from exc


class SqlAlchemyCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_command_id(self, *, tenant_id: UUID, session_id: UUID,
                                command_id: UUID) -> CommandRecord | None:
        row = (await self._s.execute(
            sa.select(VNextCommandRow).where(
                VNextCommandRow.tenant_id == tenant_id,
                VNextCommandRow.session_id == session_id,
                VNextCommandRow.command_id == command_id))).scalar_one_or_none()
        return None if row is None else _command_record_from_row(row)

    async def get_by_request_key(self, *, tenant_id: UUID, session_id: UUID,
                                 request_idempotency_key: str) -> CommandRecord | None:
        row = (await self._s.execute(
            sa.select(VNextCommandRow).where(
                VNextCommandRow.tenant_id == tenant_id,
                VNextCommandRow.session_id == session_id,
                VNextCommandRow.request_idempotency_key == request_idempotency_key,
            ))).scalar_one_or_none()
        return None if row is None else _command_record_from_row(row)

    async def add(self, *, tenant_id: UUID, record: CommandRecord) -> None:
        record = CommandRecord.model_validate(record.model_dump())
        self._s.add(VNextCommandRow(
            command_id=record.command_id, tenant_id=tenant_id,
            session_id=record.session_id, run_id=record.run_id,
            request_idempotency_key=record.request_idempotency_key,
            command_schema_id=record.command_schema_id,
            command_artifact_id=record.command_artifact_id,
            command_hash=record.command_hash,
            reduction_artifact_id=record.reduction_artifact_id,
            reduction_hash=record.reduction_hash,
            expected_state_version=record.expected_state_version,
            result_state_version=record.result_state_version,
            result_state_hash=record.result_state_hash,
            result_reason_code=record.result_reason_code,
            occurred_at=record.occurred_at, committed_at=record.committed_at,
        ))
        await self._s.flush()


# ── runs ──────────────────────────────────────────────────────────────────────


def _run_from_row(row: VNextRunRow) -> WorkflowRun:
    """Hydrate;terminal + null manifest 在此被 DTO validator 拒絕 →
    PersistedDataCorruption(§5.2 裁決:DB 允許 cleanup 暫態,runtime 拒讀)。"""
    try:
        return WorkflowRun(
            run_id=row.run_id, session_id=row.session_id,
            architecture_id=row.architecture_id, workflow_version=row.workflow_version,
            taxonomy_id=row.taxonomy_id, taxonomy_version=row.taxonomy_version,
            taxonomy_hash=row.taxonomy_hash, status=row.status,
            event_count=row.event_count, first_event_hash=row.first_event_hash,
            last_event_hash=row.last_event_hash,
            manifest_artifact_id=row.manifest_artifact_id,
            started_at=row.started_at, completed_at=row.completed_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise PersistedDataCorruption("persisted run row failed validation",
                                      run_id=row.run_id) from exc


class SqlAlchemyRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, tenant_id: UUID, run: WorkflowRun) -> None:
        run = WorkflowRun.model_validate(run.model_dump())
        self._s.add(VNextRunRow(
            run_id=run.run_id, tenant_id=tenant_id, session_id=run.session_id,
            architecture_id=run.architecture_id, workflow_version=run.workflow_version,
            taxonomy_id=run.taxonomy_id, taxonomy_version=run.taxonomy_version,
            taxonomy_hash=run.taxonomy_hash, status=run.status.value,
            event_count=run.event_count, first_event_hash=run.first_event_hash,
            last_event_hash=run.last_event_hash,
            manifest_artifact_id=run.manifest_artifact_id,
            started_at=run.started_at, completed_at=run.completed_at,
        ))
        await self._s.flush()

    async def get(self, *, tenant_id: UUID, run_id: UUID) -> WorkflowRun | None:
        row = (await self._s.execute(
            sa.select(VNextRunRow).where(
                VNextRunRow.tenant_id == tenant_id,
                VNextRunRow.run_id == run_id))).scalar_one_or_none()
        return None if row is None else _run_from_row(row)

    async def lock(self, *, tenant_id: UUID, run_id: UUID) -> None:
        row = (await self._s.execute(
            sa.select(VNextRunRow.run_id)
            .where(VNextRunRow.tenant_id == tenant_id, VNextRunRow.run_id == run_id)
            .with_for_update())).first()
        if row is None:
            from .errors import RunConflict
            raise RunConflict("run does not exist",
                              tenant_id=tenant_id, run_id=run_id)

    async def finalize(self, *, tenant_id: UUID, run: WorkflowRun) -> None:
        run = WorkflowRun.model_validate(run.model_dump())
        if run.status not in (RunStatus.COMPLETED, RunStatus.FAILED):
            raise PersistenceError("finalize requires a terminal WorkflowRun",
                                   run_id=run.run_id, status=run.status.value)
        result = await self._s.execute(
            sa.update(VNextRunRow)
            .where(VNextRunRow.tenant_id == tenant_id,
                   VNextRunRow.run_id == run.run_id,
                   VNextRunRow.status == RunStatus.OPEN.value,
                   VNextRunRow.event_count == run.event_count,
                   VNextRunRow.last_event_hash == run.last_event_hash)
            .values(status=run.status.value, completed_at=run.completed_at,
                    manifest_artifact_id=run.manifest_artifact_id)
            .returning(VNextRunRow.run_id))
        if result.first() is None:
            from .errors import RunConflict
            raise RunConflict("run is not open at the expected chain position",
                              tenant_id=tenant_id, run_id=run.run_id)


# ── checkpoints ───────────────────────────────────────────────────────────────


def _checkpoint_columns(tenant_id: UUID, run_id: UUID,
                        cp: OperationCheckpoint) -> dict:
    return {
        "checkpoint_id": cp.checkpoint_id, "tenant_id": tenant_id, "run_id": run_id,
        "session_id": cp.session_id, "turn_id": cp.turn_id,
        "operation_id": cp.operation_id, "operation_name": cp.operation_name,
        "operation_definition_hash": cp.operation_definition_hash,
        "idempotency_key": cp.idempotency_key, "status": cp.status.value,
        "revision": cp.revision, "checkpoint_schema_version": cp.schema_version,
        "checkpoint_json": ser.dump_model(cp),
        "request_artifact_id": cp.request_artifact.artifact_id,
        "active_attempt_id": cp.active_attempt_id, "active_attempt": cp.active_attempt,
        "provider_result_artifact_id":
            cp.provider_result_artifact.artifact_id if cp.provider_result_artifact else None,
        "verification_artifact_id":
            cp.verification_artifact.artifact_id if cp.verification_artifact else None,
        "domain_result_artifact_id":
            cp.domain_result_artifact.artifact_id if cp.domain_result_artifact else None,
        "response_artifact_id":
            cp.response_artifact.artifact_id if cp.response_artifact else None,
        "failure_artifact_id":
            cp.failure_artifact.artifact_id if cp.failure_artifact else None,
        "failure_reason_code": cp.failure_reason_code,
        "state_before_hash": cp.state_before_hash,
        "state_after_hash": cp.state_after_hash,
        "created_at": cp.created_at, "updated_at": cp.updated_at,
    }


def _checkpoint_from_row(row: VNextCheckpointRow) -> OperationCheckpoint:
    cp = ser.load_checkpoint(row.checkpoint_json,
                             operation_id=row.operation_id, revision=row.revision)
    mismatches = [
        name for name, row_value, nested in (
            ("checkpoint_id", row.checkpoint_id, cp.checkpoint_id),
            ("run_id", row.run_id, cp.run_id),
            ("session_id", row.session_id, cp.session_id),
            ("status", row.status, cp.status.value),
            ("operation_name", row.operation_name, cp.operation_name),
            ("idempotency_key", row.idempotency_key, cp.idempotency_key),
            ("active_attempt_id", row.active_attempt_id, cp.active_attempt_id),
            ("request_artifact_id", row.request_artifact_id,
             cp.request_artifact.artifact_id),
            ("state_before_hash", row.state_before_hash, cp.state_before_hash),
        ) if row_value != nested
    ]
    if mismatches:
        raise PersistedDataCorruption(
            "checkpoint row columns do not match nested checkpoint",
            operation_id=row.operation_id, mismatched=",".join(mismatches))
    return cp


class SqlAlchemyCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, tenant_id: UUID, checkpoint: OperationCheckpoint) -> None:
        checkpoint = OperationCheckpoint.model_validate(checkpoint.model_dump())
        self._s.add(VNextCheckpointRow(
            **_checkpoint_columns(tenant_id, checkpoint.run_id, checkpoint)))
        await self._s.flush()

    async def get_by_operation(self, *, tenant_id: UUID,
                               operation_id: UUID) -> OperationCheckpoint | None:
        row = (await self._s.execute(
            sa.select(VNextCheckpointRow).where(
                VNextCheckpointRow.tenant_id == tenant_id,
                VNextCheckpointRow.operation_id == operation_id))).scalar_one_or_none()
        return None if row is None else _checkpoint_from_row(row)

    async def get_by_idempotency(self, *, tenant_id: UUID, session_id: UUID,
                                 operation_name: str,
                                 idempotency_key: str) -> OperationCheckpoint | None:
        row = (await self._s.execute(
            sa.select(VNextCheckpointRow).where(
                VNextCheckpointRow.tenant_id == tenant_id,
                VNextCheckpointRow.session_id == session_id,
                VNextCheckpointRow.operation_name == operation_name,
                VNextCheckpointRow.idempotency_key == idempotency_key,
            ))).scalar_one_or_none()
        return None if row is None else _checkpoint_from_row(row)

    async def save_cas(self, *, tenant_id: UUID, expected_revision: int,
                       checkpoint: OperationCheckpoint) -> bool:
        checkpoint = OperationCheckpoint.model_validate(checkpoint.model_dump())
        values = _checkpoint_columns(tenant_id, checkpoint.run_id, checkpoint)
        for immutable in ("checkpoint_id", "tenant_id", "run_id", "session_id",
                          "turn_id", "operation_id", "operation_name",
                          "operation_definition_hash", "idempotency_key",
                          "request_artifact_id", "created_at"):
            values.pop(immutable)
        result = await self._s.execute(
            sa.update(VNextCheckpointRow)
            .where(VNextCheckpointRow.tenant_id == tenant_id,
                   VNextCheckpointRow.checkpoint_id == checkpoint.checkpoint_id,
                   VNextCheckpointRow.revision == expected_revision)
            .values(**values)
            .returning(VNextCheckpointRow.checkpoint_id))
        return result.first() is not None


# ── attempts ──────────────────────────────────────────────────────────────────


def _attempt_from_row(row: VNextAttemptRow) -> OperationAttempt:
    try:
        return OperationAttempt(
            attempt_id=row.attempt_id, run_id=row.run_id, session_id=row.session_id,
            operation_id=row.operation_id, attempt=row.attempt, status=row.status,
            request_artifact_id=row.request_artifact_id,
            result_artifact_id=row.result_artifact_id, provider=row.provider,
            requested_model=row.requested_model,
            provider_execution_ref_kind=row.provider_execution_ref_kind,
            provider_execution_ref=row.provider_execution_ref,
            deadline_at=row.deadline_at, started_at=row.started_at,
            updated_at=row.updated_at, completed_at=row.completed_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise PersistedDataCorruption("persisted attempt row failed validation",
                                      attempt_id=row.attempt_id) from exc


class SqlAlchemyAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def start(self, *, tenant_id: UUID, attempt: OperationAttempt) -> None:
        attempt = OperationAttempt.model_validate(attempt.model_dump())
        if attempt.status != AttemptStatus.CALLING:
            raise PersistenceError("new attempt rows must start in calling status",
                                   attempt_id=attempt.attempt_id)
        self._s.add(VNextAttemptRow(
            attempt_id=attempt.attempt_id, tenant_id=tenant_id, run_id=attempt.run_id,
            session_id=attempt.session_id, operation_id=attempt.operation_id,
            attempt=attempt.attempt, status=attempt.status.value,
            request_artifact_id=attempt.request_artifact_id,
            result_artifact_id=None, provider=attempt.provider,
            requested_model=attempt.requested_model,
            provider_execution_ref_kind=attempt.provider_execution_ref_kind,
            provider_execution_ref=attempt.provider_execution_ref,
            deadline_at=attempt.deadline_at, started_at=attempt.started_at,
            updated_at=attempt.updated_at, completed_at=None,
        ))
        await self._s.flush()

    async def get(self, *, tenant_id: UUID, attempt_id: UUID) -> OperationAttempt | None:
        row = (await self._s.execute(
            sa.select(VNextAttemptRow).where(
                VNextAttemptRow.tenant_id == tenant_id,
                VNextAttemptRow.attempt_id == attempt_id))).scalar_one_or_none()
        return None if row is None else _attempt_from_row(row)

    async def record_result(self, *, tenant_id: UUID,
                            attempt: OperationAttempt) -> None:
        attempt = OperationAttempt.model_validate(attempt.model_dump())
        if attempt.status != AttemptStatus.RESULT_RECORDED:
            raise PersistenceError("record_result requires a result_recorded attempt",
                                   attempt_id=attempt.attempt_id)
        result = await self._s.execute(
            sa.update(VNextAttemptRow)
            .where(VNextAttemptRow.tenant_id == tenant_id,
                   VNextAttemptRow.attempt_id == attempt.attempt_id,
                   VNextAttemptRow.status == AttemptStatus.CALLING.value)
            .values(status=attempt.status.value,
                    result_artifact_id=attempt.result_artifact_id,
                    provider_execution_ref_kind=attempt.provider_execution_ref_kind,
                    provider_execution_ref=attempt.provider_execution_ref,
                    updated_at=attempt.updated_at, completed_at=attempt.completed_at)
            .returning(VNextAttemptRow.attempt_id))
        if result.first() is not None:
            return
        existing = await self.get(tenant_id=tenant_id, attempt_id=attempt.attempt_id)
        if existing is None:
            raise CheckpointConflict("attempt does not exist",
                                     attempt_id=attempt.attempt_id)
        if existing == attempt:
            return                      # idempotent re-record of the same result
        raise CheckpointConflict(
            "attempt result is already recorded with a different artifact",
            attempt_id=attempt.attempt_id)
