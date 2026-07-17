"""Durable capture writer: hash-chained events + transactional outbox (V2-B §7.2).

``append_event`` 是 §7.3 atomic command commit 的 step 7,因此隨 V2-B-3 落地;
run 建立/finalize/manifest(§7.2/§7.3)在 V2-B-4 補齊。所有步驟同一 UoW
transaction:lock run → 以 ``event_count + 1``/``last_event_hash`` 建 event →
insert immutable event + pending outbox(message_id = event_id)→ 更新 run
counters。sequence 永遠不由 caller 提供。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview_vnext.application.persistence import ExecutionEventDraft
from app.interview_vnext.observability.artifacts import ArtifactRef
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    ExecutionEventBody,
    build_execution_event,
)
from app.interview_vnext.observability.taxonomy import resolve_execution_taxonomy

from . import serialization as ser
from .errors import ExecutionEventConflict, PersistedDataCorruption, RunConflict
from .models import VNextExecutionEventRow, VNextOutboxRow, VNextRunRow
from .repositories import SqlAlchemyArtifactRepository


class DurableCaptureWriter:
    """CaptureWriter port 的 SQL 實作;與 repositories 共用同一 AsyncSession。"""

    def __init__(self, session: AsyncSession,
                 artifacts: SqlAlchemyArtifactRepository) -> None:
        self._s = session
        self._artifacts = artifacts

    async def append_event(self, *, tenant_id: UUID, run_id: UUID,
                           draft: ExecutionEventDraft) -> ExecutionEvent:
        draft = ExecutionEventDraft.model_validate(draft.model_dump())

        # ② 相同 event ID:logical fields 全等 → 回既有(確保 outbox 存在,
        #    不推進 sequence);不同 → conflict。
        existing_row = (await self._s.execute(
            sa.select(VNextExecutionEventRow).where(
                VNextExecutionEventRow.event_id == draft.event_id))
        ).scalar_one_or_none()
        if existing_row is not None:
            if existing_row.tenant_id != tenant_id or existing_row.run_id != run_id:
                raise ExecutionEventConflict(
                    "event id already used by another run/tenant",
                    event_id=draft.event_id)
            existing = ser.load_event(existing_row.event_json, existing_row.event_hash,
                                      event_id=existing_row.event_id,
                                      run_id=existing_row.run_id,
                                      sequence=existing_row.sequence)
            if not _same_logical_fields(existing, draft):
                raise ExecutionEventConflict(
                    "event id already exists with a different logical payload",
                    event_id=draft.event_id)
            await self._ensure_outbox(tenant_id, existing)
            await self._s.flush()
            return existing

        # ③ 批次驗 artifact refs(kind/media/schema/hash/size 全比)
        refs: tuple[ArtifactRef, ...] = (*draft.input_artifacts, *draft.output_artifacts)
        if refs:
            await self._artifacts.get_many(tenant_id=tenant_id, refs=refs)

        # ④ lock run row(短 transaction;provider call 永遠在外)
        run_row = (await self._s.execute(
            sa.select(VNextRunRow)
            .where(VNextRunRow.tenant_id == tenant_id, VNextRunRow.run_id == run_id)
            .with_for_update())).scalar_one_or_none()
        if run_row is None:
            raise RunConflict("run does not exist", tenant_id=tenant_id, run_id=run_id)

        # ⑤ run open + identity 檢查
        if run_row.status != "open":
            raise RunConflict("terminal run refuses further events",
                              run_id=run_id, status=run_row.status)
        if run_row.session_id != draft.session_id:
            raise RunConflict("event session does not match run session",
                              run_id=run_id, session_id=draft.session_id)
        taxonomy = resolve_execution_taxonomy(run_row.taxonomy_id,
                                              run_row.taxonomy_version)
        if taxonomy.content_hash != run_row.taxonomy_hash:
            raise PersistedDataCorruption("run taxonomy hash mismatch", run_id=run_id)
        # ① taxonomy allowlist(open StableName,由 version-addressed 名單驗)
        taxonomy.validate_names(event_type=draft.event_type, stage=draft.stage)

        # ⑥ 以 run counters 建 event(hash chain 由此層唯一擁有)
        body = ExecutionEventBody(
            event_id=draft.event_id, occurred_at=draft.occurred_at,
            architecture_id=run_row.architecture_id,
            workflow_version=run_row.workflow_version,
            taxonomy_id=run_row.taxonomy_id, taxonomy_version=run_row.taxonomy_version,
            taxonomy_hash=run_row.taxonomy_hash,
            run_id=run_id, session_id=draft.session_id, turn_id=draft.turn_id,
            operation_id=draft.operation_id,
            parent_operation_id=draft.parent_operation_id,
            attempt_id=draft.attempt_id, attempt=draft.attempt,
            event_type=draft.event_type, stage=draft.stage, status=draft.status,
            sequence=run_row.event_count + 1,
            previous_event_hash=run_row.last_event_hash,
            input_artifacts=draft.input_artifacts,
            output_artifacts=draft.output_artifacts,
            state_before_hash=draft.state_before_hash,
            state_after_hash=draft.state_after_hash,
            metadata_json=draft.metadata_json,
        )
        event = build_execution_event(body)
        event_json = ser.dump_model(event)

        # ⑦ immutable event
        self._s.add(VNextExecutionEventRow(
            event_id=event.event_id, tenant_id=tenant_id, run_id=run_id,
            session_id=draft.session_id, turn_id=draft.turn_id,
            operation_id=draft.operation_id,
            parent_operation_id=draft.parent_operation_id,
            attempt_id=draft.attempt_id, attempt=draft.attempt,
            event_schema_version=event.event_schema_version,
            event_type=event.event_type, stage=event.stage,
            status=event.status.value, sequence=event.sequence,
            previous_event_hash=event.previous_event_hash,
            event_hash=event.event_hash, event_json=event_json,
            occurred_at=event.occurred_at, created_at=datetime.now(UTC),
        ))

        # ⑧ pending outbox(同 transaction;message ID = event ID)
        self._s.add(VNextOutboxRow(
            message_id=event.event_id, tenant_id=tenant_id, run_id=run_id,
            event_sequence=event.sequence, event_hash=event.event_hash,
            event_json=event_json, status="pending", delivery_attempts=0,
            created_at=event.occurred_at, updated_at=event.occurred_at,
        ))

        # ⑨ run counters 前進(任何一步失敗整筆 rollback,counter 不前進)
        run_row.event_count = event.sequence
        run_row.last_event_hash = event.event_hash
        if event.sequence == 1:
            run_row.first_event_hash = event.event_hash

        # ⑩ flush;commit 由外層 UoW 擁有
        await self._s.flush()
        return event

    async def build_and_store_manifest(self, *, tenant_id: UUID, run_id: UUID,
                                       manifest_artifact_id: UUID,
                                       completed_at: datetime,
                                       root_artifacts: tuple[ArtifactRef, ...] = (),
                                       limitations: tuple[str, ...] = ()) -> ArtifactRef:
        raise NotImplementedError(
            "run finalize/manifest lands in V2-B-4 (plan §7.3)")

    async def _ensure_outbox(self, tenant_id: UUID, event: ExecutionEvent) -> None:
        exists = (await self._s.execute(
            sa.select(VNextOutboxRow.message_id).where(
                VNextOutboxRow.message_id == event.event_id))).first()
        if exists is None:
            self._s.add(VNextOutboxRow(
                message_id=event.event_id, tenant_id=tenant_id, run_id=event.run_id,
                event_sequence=event.sequence, event_hash=event.event_hash,
                event_json=ser.dump_model(event), status="pending",
                delivery_attempts=0,
                created_at=event.occurred_at, updated_at=event.occurred_at,
            ))


def _same_logical_fields(existing: ExecutionEvent, draft: ExecutionEventDraft) -> bool:
    """比較 caller 供給的 logical fields(sequence/chain/taxonomy 由 run 決定,不比)。"""
    return (
        existing.occurred_at == draft.occurred_at
        and existing.session_id == draft.session_id
        and existing.turn_id == draft.turn_id
        and existing.operation_id == draft.operation_id
        and existing.parent_operation_id == draft.parent_operation_id
        and existing.attempt_id == draft.attempt_id
        and existing.attempt == draft.attempt
        and existing.event_type == draft.event_type
        and existing.stage == draft.stage
        and existing.status == draft.status
        and existing.input_artifacts == draft.input_artifacts
        and existing.output_artifacts == draft.output_artifacts
        and existing.state_before_hash == draft.state_before_hash
        and existing.state_after_hash == draft.state_after_hash
        and existing.metadata_json == draft.metadata_json
    )
