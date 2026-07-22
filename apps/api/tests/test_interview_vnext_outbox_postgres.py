"""V2-B-4:durable capture(create_run/finalize/manifest)與 outbox lease
(reference §12 cases 8–14、plan §7.5、§5.2 裁決的 finalize rollback)。

時間控制:lease 到期/retry 時間無法讓 DB 時鐘倒流,測試以「暫停 outbox guard
trigger → 回填時間欄位 → 恢復」模擬時間流逝;這只繞過第二道防線的**時間**
條件,transition 合法性仍由 adapter SQL WHERE 驗證(並有專屬 conflict 測試)。
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.persistence import (
    ExecutionEventDraft,
    RunStatus,
    WorkflowRun,
)
from app.interview_vnext.domain.commands import TransitionSessionCommand
from app.interview_vnext.domain.session import (
    ARCHITECTURE_ID,
    SessionStatus,
    session_at,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.events import ExecutionStatus, RunManifest
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1
from app.interview_vnext.persistence.errors import (
    OutboxLeaseConflict,
    PersistedDataCorruption,
    PersistenceError,
    RunConflict,
)
from app.interview_vnext.persistence.outbox import PostgresOutbox
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork


NOW = datetime(2026, 7, 17, 6, 0, tzinfo=UTC)


def initial_state(ids) -> InterviewState:
    return InterviewState(session=session_at(
        session_id=ids.session_id, profile_id=ids.profile_id, tenant_id=ids.tenant_id,
        workflow_version="1.0.0", reference_snapshot_id="ref-snapshot-v1", now=NOW))


def open_run(ids, *, run_id: UUID | None = None,
             started_at: datetime = NOW) -> WorkflowRun:
    tax = INTERVIEW_VNEXT_EXECUTION_V1
    return WorkflowRun(
        run_id=run_id or ids.run_id, session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID, workflow_version="1.0.0",
        taxonomy_id=tax.taxonomy_id, taxonomy_version=tax.version,
        taxonomy_hash=tax.content_hash, started_at=started_at)


async def bootstrap_run(factory, ids) -> None:
    """§7.1 + §7.2 完整協定:session → create_run(snapshot + started event)。"""
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=initial_state(ids))
        await uow.capture.create_run(
            tenant_id=ids.tenant_id, run=open_run(ids),
            snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.commit()


async def append(factory, ids, *, run_id: UUID | None = None,
                 event_id: UUID | None = None,
                 occurred_at: datetime | None = None) -> UUID:
    event_id = event_id or uuid4()
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.capture.append_event(
            tenant_id=ids.tenant_id, run_id=run_id or ids.run_id,
            draft=ExecutionEventDraft(
                event_id=event_id, occurred_at=occurred_at or NOW + timedelta(seconds=1),
                session_id=ids.session_id, event_type="workflow.step.started",
                stage="turn.receive", status=ExecutionStatus.OK))
        await uow.commit()
    return event_id


async def _backdate(factory, message_id: UUID, column: str) -> None:
    """模擬時間流逝:trigger 暫停下把 lease/retry 時間改到過去(見模組 docstring)。"""
    assert column in ("lease_expires_at", "next_attempt_at")
    async with factory() as s:
        await s.execute(sa.text(
            "ALTER TABLE interview_vnext_outbox "
            "DISABLE TRIGGER ivn_outbox_guard_update"))
        await s.execute(sa.text(
            f"UPDATE interview_vnext_outbox SET {column} = "  # noqa: S608
            "CURRENT_TIMESTAMP - interval '1 second' WHERE message_id = :m"),
            {"m": str(message_id)})
        await s.execute(sa.text(
            "ALTER TABLE interview_vnext_outbox "
            "ENABLE TRIGGER ivn_outbox_guard_update"))
        await s.commit()


async def _run_state(factory, ids) -> dict:
    async with factory() as s:
        row = (await s.execute(sa.text(
            "SELECT status, event_count, manifest_artifact_id "
            "FROM interview_vnext_runs WHERE run_id = :r"),
            {"r": str(ids.run_id)})).one()
        return {"status": row.status, "event_count": row.event_count,
                "manifest": row.manifest_artifact_id}


# ── §7.2 create_run ───────────────────────────────────────────────────────────

async def test_create_run_snapshots_and_starts_chain(postgres_session_factory,
                                                     vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    assert await _run_state(postgres_session_factory, ids) == {
        "status": "open", "event_count": 1, "manifest": None}
    async with postgres_session_factory() as s:
        pointer = (await s.execute(sa.text(
            "SELECT initial_state_artifact_id FROM interview_vnext_sessions "
            "WHERE session_id = :sid"), {"sid": str(ids.session_id)})).scalar_one()
        assert pointer is not None
        kind = (await s.execute(sa.text(
            "SELECT kind FROM interview_vnext_artifacts WHERE artifact_id = :a"),
            {"a": str(pointer)})).scalar_one()
        assert kind == "state.snapshot.initial"

    # duplicate:identity 完全相同 → 回既有(chain 不前進);不同 → conflict
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        again = await uow.capture.create_run(
            tenant_id=ids.tenant_id, run=open_run(ids),
            snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        assert again.event_count == 1
        with pytest.raises(RunConflict):
            await uow.capture.create_run(
                tenant_id=ids.tenant_id,
                run=open_run(ids, started_at=NOW + timedelta(minutes=5)),
                snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.rollback()


async def test_second_run_after_pointer_lost_is_corruption(postgres_session_factory,
                                                           vnext_profile):
    """§7.2:session 已過 version 0 但 pointer 不存在 → hard fail,
    不可拿當前 state 偽裝 initial state。"""
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    await apply_durable_command(
        lambda: SqlAlchemyVNextUnitOfWork(postgres_session_factory),
        tenant_id=ids.tenant_id, session_id=ids.session_id, run_id=ids.run_id,
        command=TransitionSessionCommand(
            command_id=uuid4(), expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE),
        stage="session.plan", event_id=uuid4(), command_artifact_id=uuid4(),
        reduction_artifact_id=uuid4(), committed_at=NOW + timedelta(seconds=2))
    async with postgres_session_factory() as s:      # cleanup 暫態:pointer 清空
        await s.execute(sa.text(
            "UPDATE interview_vnext_sessions SET initial_state_artifact_id = NULL "
            "WHERE session_id = :sid"), {"sid": str(ids.session_id)})
        await s.commit()
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(PersistedDataCorruption):
            await uow.capture.create_run(
                tenant_id=ids.tenant_id, run=open_run(ids, run_id=uuid4()),
                snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.rollback()


# ── §7.3 finalize ─────────────────────────────────────────────────────────────

async def test_finalize_builds_manifest_and_seals_run(postgres_session_factory,
                                                      vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    manifest_id, terminal_event = uuid4(), uuid4()
    done = NOW + timedelta(seconds=9)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        root = await uow.artifacts.put(
            tenant_id=ids.tenant_id,
            record=build_inline_artifact(
                artifact_id=uuid4(),
                kind="test.terminal_root",
                media_type="application/json",
                payload={"terminal": True},
                run_id=ids.run_id,
                session_id=ids.session_id,
                created_at=done,
                contains_test_data=True,
            ),
        )
        run, manifest_ref = await uow.capture.finalize_run(
            tenant_id=ids.tenant_id, run_id=ids.run_id,
            final_status=RunStatus.COMPLETED, terminal_event_id=terminal_event,
            manifest_artifact_id=manifest_id, completed_at=done,
            root_artifacts=(root.ref,))
        await uow.commit()
    assert run.status == RunStatus.COMPLETED and run.event_count == 2
    state = await _run_state(postgres_session_factory, ids)
    assert state["status"] == "completed" and state["manifest"] == manifest_id

    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        record = await uow.artifacts.get(tenant_id=ids.tenant_id,
                                         artifact_id=manifest_id)
        manifest = RunManifest.model_validate_json(record.inline_content or "")
        assert manifest.event_count == 2
        assert manifest.last_event_hash == run.last_event_hash
        assert manifest.root_artifacts == (root.ref,)

        # terminal run 拒絕後續 event;相同 inputs 冪等;不同 completion conflict
        with pytest.raises(RunConflict):
            await uow.capture.append_event(
                tenant_id=ids.tenant_id, run_id=ids.run_id,
                draft=ExecutionEventDraft(
                    event_id=uuid4(), occurred_at=done + timedelta(seconds=1),
                    session_id=ids.session_id, event_type="workflow.step.started",
                    stage="turn.receive", status=ExecutionStatus.OK))
        again, ref_again = await uow.capture.finalize_run(
            tenant_id=ids.tenant_id, run_id=ids.run_id,
            final_status=RunStatus.COMPLETED, terminal_event_id=terminal_event,
            manifest_artifact_id=manifest_id, completed_at=done)
        assert ref_again == manifest_ref
        with pytest.raises(RunConflict):
            await uow.capture.finalize_run(
                tenant_id=ids.tenant_id, run_id=ids.run_id,
                final_status=RunStatus.COMPLETED, terminal_event_id=terminal_event,
                manifest_artifact_id=manifest_id,
                completed_at=done + timedelta(seconds=5))
        await uow.rollback()

    async with postgres_session_factory() as session:
        event_json = (
            await session.execute(
                sa.text(
                    "SELECT event_json FROM interview_vnext_execution_events "
                    "WHERE tenant_id = :tenant_id AND event_id = :event_id"
                ),
                {
                    "tenant_id": str(ids.tenant_id),
                    "event_id": str(terminal_event),
                },
            )
        ).scalar_one()
    assert json.loads(event_json)["input_artifacts"] == [
        root.ref.model_dump(mode="json")
    ]


async def test_finalize_rollback_leaves_run_open_with_no_partial_rows(
        postgres_session_factory, vnext_profile):
    """§5.2 裁決要求:finalize 未 commit 即中斷 → run 仍 open、無 terminal
    event、無 manifest artifact(all-or-nothing)。"""
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.capture.finalize_run(
            tenant_id=ids.tenant_id, run_id=ids.run_id,
            final_status=RunStatus.COMPLETED, terminal_event_id=uuid4(),
            manifest_artifact_id=uuid4(), completed_at=NOW + timedelta(seconds=9))
        # 不 commit → __aexit__ rollback
    state = await _run_state(postgres_session_factory, ids)
    assert state == {"status": "open", "event_count": 1, "manifest": None}
    async with postgres_session_factory() as s:
        kinds = (await s.execute(sa.text(
            "SELECT kind FROM interview_vnext_artifacts WHERE tenant_id = :t"),
            {"t": str(ids.tenant_id)})).scalars().all()
        assert "capture.run_manifest" not in kinds


# ── case 13/14:append 併發連續 chain;失敗不前進 counter ─────────────────────────

async def test_concurrent_appends_yield_contiguous_chain(postgres_session_factory,
                                                         vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    await asyncio.gather(append(postgres_session_factory, ids),
                         append(postgres_session_factory, ids))
    async with postgres_session_factory() as s:
        rows = (await s.execute(sa.text(
            "SELECT sequence, previous_event_hash, event_hash "
            "FROM interview_vnext_execution_events WHERE run_id = :r "
            "ORDER BY sequence"), {"r": str(ids.run_id)})).all()
    assert [r.sequence for r in rows] == [1, 2, 3]
    assert rows[1].previous_event_hash == rows[0].event_hash
    assert rows[2].previous_event_hash == rows[1].event_hash
    assert (await _run_state(postgres_session_factory, ids))["event_count"] == 3


async def test_failed_append_never_advances_run_counter(postgres_session_factory,
                                                        vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(ValueError, match="stage is not registered"):
            await uow.capture.append_event(
                tenant_id=ids.tenant_id, run_id=ids.run_id,
                draft=ExecutionEventDraft(
                    event_id=uuid4(), occurred_at=NOW + timedelta(seconds=1),
                    session_id=ids.session_id, event_type="workflow.step.started",
                    stage="not.a.stage", status=ExecutionStatus.OK))
        await uow.rollback()
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.capture.append_event(    # 成功寫入但不 commit → 一樣不前進
            tenant_id=ids.tenant_id, run_id=ids.run_id,
            draft=ExecutionEventDraft(
                event_id=uuid4(), occurred_at=NOW + timedelta(seconds=1),
                session_id=ids.session_id, event_type="workflow.step.started",
                stage="turn.receive", status=ExecutionStatus.OK))
    assert (await _run_state(postgres_session_factory, ids))["event_count"] == 1


# ── case 8–11:lease 併發/到期/owner guard/重送 ─────────────────────────────────

async def test_two_workers_never_lease_the_same_message(postgres_session_factory,
                                                        vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        for _ in range(3):                       # 共 4 個 runs → 4 條 pending
            await uow.capture.create_run(
                tenant_id=ids.tenant_id, run=open_run(ids, run_id=uuid4()),
                snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.commit()
    outbox = PostgresOutbox(postgres_session_factory)
    a, b = await asyncio.gather(
        outbox.lease(worker_id="worker-a", limit=3),
        outbox.lease(worker_id="worker-b", limit=3))
    ours = {m.message_id for m in (*a, *b) if m.tenant_id == ids.tenant_id}
    assert len(a) + len(b) >= len(ours) and \
        {m.message_id for m in a} & {m.message_id for m in b} == set()


async def test_expired_lease_is_taken_over_with_attempts_incremented(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    outbox = PostgresOutbox(postgres_session_factory)
    first = await outbox.lease(worker_id="worker-a", limit=50)
    mine = [m for m in first if m.tenant_id == ids.tenant_id]
    assert len(mine) == 1 and mine[0].delivery_attempts == 1
    message_id = mine[0].message_id

    assert [m for m in await outbox.lease(worker_id="worker-b", limit=50)
            if m.tenant_id == ids.tenant_id] == []     # 未到期不可搶
    await _backdate(postgres_session_factory, message_id, "lease_expires_at")
    taken = [m for m in await outbox.lease(worker_id="worker-b", limit=50)
             if m.tenant_id == ids.tenant_id]
    assert len(taken) == 1
    assert taken[0].message_id == message_id            # case 11:同 event ID 重送
    assert taken[0].delivery_attempts == 2
    assert taken[0].lease_owner == "worker-b"


async def test_non_owner_and_expired_owner_cannot_mark(postgres_session_factory,
                                                       vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    outbox = PostgresOutbox(postgres_session_factory)
    mine = [m for m in await outbox.lease(worker_id="worker-a", limit=50)
            if m.tenant_id == ids.tenant_id]
    message_id = mine[0].message_id
    with pytest.raises(OutboxLeaseConflict):
        await outbox.mark_delivered(message_id=message_id, worker_id="worker-b")
    with pytest.raises(OutboxLeaseConflict):
        await outbox.mark_failed(message_id=message_id, worker_id="worker-b",
                                 error_code="exporter_error")
    await _backdate(postgres_session_factory, message_id, "lease_expires_at")
    with pytest.raises(OutboxLeaseConflict):            # 過期 owner 也不行
        await outbox.mark_delivered(message_id=message_id, worker_id="worker-a")


# ── case 12 + §7.5:同 run ordering、terminal 放行、retry/dead_letter ───────────

async def test_same_run_ordering_blocks_later_sequence(postgres_session_factory,
                                                       vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    await append(postgres_session_factory, ids)          # run1 seq2
    run2 = uuid4()
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.capture.create_run(
            tenant_id=ids.tenant_id, run=open_run(ids, run_id=run2),
            snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.commit()

    outbox = PostgresOutbox(postgres_session_factory)
    leased = [m for m in await outbox.lease(worker_id="w", limit=100)
              if m.tenant_id == ids.tenant_id]
    got = {(m.run_id, m.event_sequence) for m in leased}
    assert got == {(ids.run_id, 1), (run2, 1)}          # run1 seq2 被前序擋住

    seq1 = next(m for m in leased if m.run_id == ids.run_id)
    await outbox.mark_delivered(message_id=seq1.message_id, worker_id="w")
    await outbox.mark_delivered(message_id=seq1.message_id, worker_id="w")  # 冪等
    unlocked = [m for m in await outbox.lease(worker_id="w", limit=100)
                if m.tenant_id == ids.tenant_id]
    assert {(m.run_id, m.event_sequence) for m in unlocked} == {(ids.run_id, 2)}


async def test_retry_wait_flow_and_past_retry_rejected(postgres_session_factory,
                                                       vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    outbox = PostgresOutbox(postgres_session_factory)
    mine = [m for m in await outbox.lease(worker_id="w", limit=50)
            if m.tenant_id == ids.tenant_id]
    message_id = mine[0].message_id
    with pytest.raises(PersistenceError):                # retry_at 不可早於 DB now
        await outbox.mark_failed(message_id=message_id, worker_id="w",
                                 error_code="exporter_error",
                                 retry_at=NOW - timedelta(days=1))
    await outbox.mark_failed(message_id=message_id, worker_id="w",
                             error_code="exporter_error",
                             retry_at=datetime.now(UTC) + timedelta(hours=1))
    assert await outbox.status(message_id=message_id) == "retry_wait"
    assert [m for m in await outbox.lease(worker_id="w", limit=50)
            if m.tenant_id == ids.tenant_id] == []       # 未到 retry 時間
    await _backdate(postgres_session_factory, message_id, "next_attempt_at")
    retried = [m for m in await outbox.lease(worker_id="w", limit=50)
               if m.tenant_id == ids.tenant_id]
    assert len(retried) == 1 and retried[0].delivery_attempts == 2


async def test_dead_letter_is_terminal_keeps_payload_and_unblocks_sequence(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)
    await append(postgres_session_factory, ids)          # seq2
    outbox = PostgresOutbox(postgres_session_factory)
    mine = [m for m in await outbox.lease(worker_id="w", limit=50)
            if m.tenant_id == ids.tenant_id]
    seq1 = mine[0]
    await outbox.mark_failed(message_id=seq1.message_id, worker_id="w",
                             error_code="poison_message")
    assert await outbox.status(message_id=seq1.message_id) == "dead_letter"
    async with postgres_session_factory() as s:          # payload/hash 保留供稽核
        row = (await s.execute(sa.text(
            "SELECT event_hash, event_json, last_error_code "
            "FROM interview_vnext_outbox WHERE message_id = :m"),
            {"m": str(seq1.message_id)})).one()
        assert row.event_hash == seq1.event_hash
        assert row.event_json == seq1.event_json
        assert row.last_error_code == "poison_message"
    later = [m for m in await outbox.lease(worker_id="w", limit=50)
             if m.tenant_id == ids.tenant_id]
    assert {m.event_sequence for m in later} == {2}      # 後續 sequence 放行
    await outbox.mark_delivered(message_id=later[0].message_id, worker_id="w")
    assert [m for m in await outbox.lease(worker_id="w", limit=50)
            if m.tenant_id == ids.tenant_id] == []       # terminal 不再被 lease


# ── §7.5:100 runs 分批 lease + partial index 可用性 ───────────────────────────

async def test_hundred_runs_lease_in_batches_and_partial_index_usable(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap_run(postgres_session_factory, ids)   # run 1
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        for _ in range(99):
            await uow.capture.create_run(
                tenant_id=ids.tenant_id, run=open_run(ids, run_id=uuid4()),
                snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.commit()

    # EXPLAIN(enable_seqscan off):證明 pending partial index **可用**,
    # 不寫死 planner 選擇或 cost 數字(§7.5)。
    async with postgres_session_factory() as s:
        await s.execute(sa.text("SET enable_seqscan = off"))
        plan_rows = (await s.execute(sa.text(
            "EXPLAIN SELECT message_id FROM interview_vnext_outbox "
            "WHERE status = 'pending' ORDER BY created_at, message_id"))).scalars().all()
        assert any("ix_ivn_outbox_pending" in line for line in plan_rows)

    outbox = PostgresOutbox(postgres_session_factory)
    seen: set[UUID] = set()
    for _ in range(10):                                   # 分批直到取完本 case 的 100
        batch = [m for m in await outbox.lease(worker_id="w", limit=40)
                 if m.tenant_id == ids.tenant_id]
        assert seen.isdisjoint({m.message_id for m in batch})
        seen |= {m.message_id for m in batch}
        if len(seen) == 100:
            break
    assert len(seen) == 100
