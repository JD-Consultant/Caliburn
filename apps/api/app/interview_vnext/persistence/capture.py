"""Durable capture writer: hash-chained events + transactional outbox (V2-B §7.2/§7.3).

``append_event`` 是 §7.3 atomic command commit 的 step 7(隨 V2-B-3 落地);
``create_run``/``finalize_run``/``build_and_store_manifest`` 補齊 §7.2/§7.3 的
run 生命週期。所有步驟同一 UoW transaction:lock run → 以 ``event_count + 1``/
``last_event_hash`` 建 event → insert immutable event + pending outbox
(message_id = event_id)→ 更新 run counters。sequence 永遠不由 caller 提供;
commit 永遠由外層 UoW 擁有。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.interview_vnext.application.persistence import (
    ExecutionEventDraft,
    RunStatus,
    WorkflowRun,
)
from app.interview_vnext.observability.artifacts import (
    ArtifactRef,
    build_inline_artifact,
)
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    ExecutionEventBody,
    ExecutionStatus,
    RunManifest,
    build_execution_event,
    validate_event_chain,
)
from app.interview_vnext.observability.taxonomy import resolve_execution_taxonomy

from . import serialization as ser
from .errors import ExecutionEventConflict, PersistedDataCorruption, RunConflict
from .models import VNextExecutionEventRow, VNextOutboxRow, VNextRunRow
from .repositories import (
    SqlAlchemyArtifactRepository,
    SqlAlchemyRunRepository,
    SqlAlchemySessionRepository,
)

INTERVIEW_STATE_SCHEMA_ID = (
    "https://caliburn.local/schemas/interview-state.v2.schema.json")
RUN_MANIFEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/capture-run-manifest.v1.schema.json")


class DurableCaptureWriter:
    """CaptureWriter port 的 SQL 實作;與 repositories 共用同一 AsyncSession。"""

    def __init__(self, session: AsyncSession,
                 artifacts: SqlAlchemyArtifactRepository,
                 runs: SqlAlchemyRunRepository,
                 sessions: SqlAlchemySessionRepository) -> None:
        self._s = session
        self._artifacts = artifacts
        self._runs = runs
        self._sessions = sessions

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

        # ⑦ immutable event(created_at=persistence time,用 DB 時鐘避免 app/DB skew)
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
            occurred_at=event.occurred_at, created_at=sa.func.now(),
        ))

        # ⑧ pending outbox(同 transaction;message ID = event ID)。enqueue time
        # =持久化時間且必須是 DB 時鐘——lease/mark 的 updated_at 用 CURRENT_TIMESTAMP,
        # 混用 domain occurred_at 會在時鐘差下撞 updated_at >= created_at CHECK。
        self._s.add(VNextOutboxRow(
            message_id=event.event_id, tenant_id=tenant_id, run_id=run_id,
            event_sequence=event.sequence, event_hash=event.event_hash,
            event_json=event_json, status="pending", delivery_attempts=0,
            created_at=sa.func.now(), updated_at=sa.func.now(),
        ))

        # ⑨ run counters 前進(任何一步失敗整筆 rollback,counter 不前進)
        run_row.event_count = event.sequence
        run_row.last_event_hash = event.event_hash
        if event.sequence == 1:
            run_row.first_event_hash = event.event_hash

        # ⑩ flush;commit 由外層 UoW 擁有
        await self._s.flush()
        return event

    async def create_run(self, *, tenant_id: UUID, run: WorkflowRun,
                         snapshot_artifact_id: UUID,
                         started_event_id: UUID) -> WorkflowRun:
        """§7.2:duplicate 檢查 → insert open run → 確保 version-0 snapshot +
        session pointer → append ``workflow.run.started``(chain 推進到 1)。
        任何 committed run 至少有 started event;session 在第一個 command 前
        已有 immutable snapshot。commit 由外層 UoW。"""
        run = WorkflowRun.model_validate(run.model_dump())
        if run.status != RunStatus.OPEN or run.event_count != 0:
            raise RunConflict("create_run requires a fresh open run",
                              run_id=run.run_id)

        existing = await self._runs.get(tenant_id=tenant_id, run_id=run.run_id)
        if existing is not None:
            same_identity = (
                existing.session_id == run.session_id
                and existing.architecture_id == run.architecture_id
                and existing.workflow_version == run.workflow_version
                and existing.taxonomy_id == run.taxonomy_id
                and existing.taxonomy_version == run.taxonomy_version
                and existing.taxonomy_hash == run.taxonomy_hash
                and existing.started_at == run.started_at)
            if not same_identity:
                raise RunConflict("run id already used with a different identity",
                                  run_id=run.run_id)
            return existing

        await self._runs.create(tenant_id=tenant_id, run=run)

        # version-0 snapshot(§7.2 step 3):pointer 缺席只允許在 state_version=0
        # 時補;version > 0 仍缺 pointer 由 sessions.get 判 corruption,不可拿
        # 當前 state 偽裝 initial state。
        pointer = await self._sessions.initial_state_artifact_id(
            tenant_id=tenant_id, session_id=run.session_id)
        if pointer is None:
            state = await self._sessions.get(tenant_id=tenant_id,
                                             session_id=run.session_id)
            if state.session.state_version > 0:
                raise PersistedDataCorruption(
                    "session advanced past version 0 without an initial snapshot",
                    session_id=run.session_id,
                    state_version=state.session.state_version)
            snapshot = await self._artifacts.put(
                tenant_id=tenant_id,
                record=build_inline_artifact(
                    artifact_id=snapshot_artifact_id, kind="state.snapshot.initial",
                    media_type="application/json", payload=state,
                    schema_id=INTERVIEW_STATE_SCHEMA_ID, run_id=run.run_id,
                    session_id=run.session_id, created_at=run.started_at))
            claimed = await self._sessions.set_initial_state_artifact(
                tenant_id=tenant_id, session_id=run.session_id,
                artifact_id=snapshot.ref.artifact_id)
            if not claimed:
                # 併發 create_run 搶先設好 pointer;確認已存在即可
                raced = await self._sessions.initial_state_artifact_id(
                    tenant_id=tenant_id, session_id=run.session_id)
                if raced is None:
                    raise PersistedDataCorruption(
                        "initial snapshot pointer could not be established",
                        session_id=run.session_id)

        await self.append_event(
            tenant_id=tenant_id, run_id=run.run_id,
            draft=ExecutionEventDraft(
                event_id=started_event_id, occurred_at=run.started_at,
                session_id=run.session_id, event_type="workflow.run.started",
                stage="workflow.run", status=ExecutionStatus.OK))
        refreshed = await self._runs.get(tenant_id=tenant_id, run_id=run.run_id)
        assert refreshed is not None
        return refreshed

    async def finalize_run(self, *, tenant_id: UUID, run_id: UUID,
                           final_status: RunStatus, terminal_event_id: UUID,
                           manifest_artifact_id: UUID, completed_at: datetime,
                           root_artifacts: tuple[ArtifactRef, ...] = (),
                           limitations: tuple[str, ...] = (),
                           event_status: ExecutionStatus = ExecutionStatus.OK,
                           ) -> tuple[WorkflowRun, ArtifactRef]:
        """§7.3:append terminal event → 以含該 event 的完整 chain 建/驗 manifest
        → put manifest artifact → run open→terminal 一次性轉換。同 inputs 冪等
        回既有 manifest;不同 completion/hash 為 conflict。"""
        if final_status not in (RunStatus.COMPLETED, RunStatus.FAILED):
            raise RunConflict("finalize requires a terminal status", run_id=run_id)

        current = await self._runs.get(tenant_id=tenant_id, run_id=run_id)
        if current is None:
            raise RunConflict("run does not exist", run_id=run_id)
        if current.status != RunStatus.OPEN:
            if (current.status == final_status
                    and current.completed_at == completed_at
                    and current.manifest_artifact_id == manifest_artifact_id):
                manifest_record = await self._artifacts.get(
                    tenant_id=tenant_id, artifact_id=manifest_artifact_id)
                return current, manifest_record.ref
            raise RunConflict("run already finalized with a different completion",
                              run_id=run_id, status=current.status.value)

        event_type = ("workflow.run.completed"
                      if final_status == RunStatus.COMPLETED
                      else "workflow.run.failed")
        await self.append_event(
            tenant_id=tenant_id, run_id=run_id,
            draft=ExecutionEventDraft(
                event_id=terminal_event_id, occurred_at=completed_at,
                session_id=current.session_id, event_type=event_type,
                stage="workflow.run", status=event_status))

        manifest_ref = await self.build_and_store_manifest(
            tenant_id=tenant_id, run_id=run_id,
            manifest_artifact_id=manifest_artifact_id, completed_at=completed_at,
            root_artifacts=root_artifacts, limitations=limitations)

        after_event = await self._runs.get(tenant_id=tenant_id, run_id=run_id)
        assert after_event is not None
        finalized = after_event.model_copy(update={
            "status": final_status, "completed_at": completed_at,
            "manifest_artifact_id": manifest_artifact_id})
        finalized = WorkflowRun.model_validate(finalized.model_dump())
        await self._runs.finalize(tenant_id=tenant_id, run=finalized)
        return finalized, manifest_ref

    async def build_and_store_manifest(self, *, tenant_id: UUID, run_id: UUID,
                                       manifest_artifact_id: UUID,
                                       completed_at: datetime,
                                       root_artifacts: tuple[ArtifactRef, ...] = (),
                                       limitations: tuple[str, ...] = ()) -> ArtifactRef:
        """讀 transaction 內完整 chain → 建/驗 ``RunManifest`` → 存為 artifact。"""
        run_row = (await self._s.execute(
            sa.select(VNextRunRow).where(
                VNextRunRow.tenant_id == tenant_id,
                VNextRunRow.run_id == run_id))).scalar_one_or_none()
        if run_row is None:
            raise RunConflict("run does not exist", run_id=run_id)
        event_rows = (await self._s.execute(
            sa.select(VNextExecutionEventRow)
            .where(VNextExecutionEventRow.tenant_id == tenant_id,
                   VNextExecutionEventRow.run_id == run_id)
            .order_by(VNextExecutionEventRow.sequence))).scalars().all()
        events = tuple(
            ser.load_event(row.event_json, row.event_hash, event_id=row.event_id,
                           run_id=row.run_id, sequence=row.sequence)
            for row in event_rows)
        if not events:
            raise RunConflict("cannot build a manifest for a run without events",
                              run_id=run_id)
        # Root refs are authoritative terminal pointers.  Reject a missing or
        # hash-mismatched root before the manifest artifact can be persisted.
        await self._artifacts.get_many(tenant_id=tenant_id, refs=root_artifacts)
        taxonomy = resolve_execution_taxonomy(run_row.taxonomy_id,
                                              run_row.taxonomy_version)
        manifest = RunManifest(
            architecture_id=run_row.architecture_id,
            workflow_version=run_row.workflow_version,
            taxonomy_id=run_row.taxonomy_id,
            taxonomy_version=run_row.taxonomy_version,
            taxonomy_hash=run_row.taxonomy_hash,
            run_id=run_id, session_id=run_row.session_id,
            started_at=run_row.started_at, completed_at=completed_at,
            event_count=len(events),
            first_event_hash=events[0].event_hash,
            last_event_hash=events[-1].event_hash,
            root_artifacts=root_artifacts,
            limitations=tuple(sorted(set(limitations))))
        validate_event_chain(events, taxonomy=taxonomy, manifest=manifest)
        stored = await self._artifacts.put(
            tenant_id=tenant_id,
            record=build_inline_artifact(
                artifact_id=manifest_artifact_id, kind="capture.run_manifest",
                media_type="application/json", payload=manifest,
                schema_id=RUN_MANIFEST_SCHEMA_ID, run_id=run_id,
                session_id=run_row.session_id, created_at=completed_at))
        return stored.ref

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
                created_at=sa.func.now(), updated_at=sa.func.now(),
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
