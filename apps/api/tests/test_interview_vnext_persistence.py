"""V2-B-3:repositories + UoW + atomic command commit(reference §12 cases 1–7)。

真 PostgreSQL、真 commit(postgres_session_factory);每 case 唯一 tenant IDs,
cleanup 由 fixture 依 ID 反向刪。守的性質:
- committed state + command/reduction artifacts + command row + event + outbox
  **同生共死**(all-or-nothing);
- 每個 flush point 注入例外 → fresh session 查不到半套資料;
- duplicate 冪等回既有 reduction;same key 不同 payload 穩定 conflict;
- 併發 CAS 恰一個成功;
- artifact immutable(同 ID 同 record 冪等/不同 conflict/UPDATE trigger 拒絕);
- terminal run + null manifest:DB 接受(cleanup 暫態)、application 拒讀
  為 PersistedDataCorruption(§5.2 裁決)。
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from app.interview_vnext.application.durable_commands import (
    INTERVIEW_STATE_SCHEMA_ID,
    DurableCommandOutcome,
    apply_durable_command,
)
from app.interview_vnext.application.persistence import WorkflowRun
from app.interview_vnext.domain.commands import TransitionSessionCommand
from app.interview_vnext.domain.errors import DomainViolation
from app.interview_vnext.domain.session import (
    ARCHITECTURE_ID,
    SessionStatus,
    session_at,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    ArtifactStorage,
    build_inline_artifact,
)
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1
from app.interview_vnext.persistence.errors import (
    ArtifactConflict,
    ExternalArtifactStoreUnavailable,
    IdempotencyConflict,
    PersistedDataCorruption,
    StateVersionConflict,
)
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork


NOW = datetime(2026, 7, 17, 5, 0, tzinfo=UTC)


def initial_state(ids) -> InterviewState:
    return InterviewState(session=session_at(
        session_id=ids.session_id, profile_id=ids.profile_id, tenant_id=ids.tenant_id,
        workflow_version="1.0.0", reference_snapshot_id="ref-snapshot-v1", now=NOW))


def open_run(ids) -> WorkflowRun:
    tax = INTERVIEW_VNEXT_EXECUTION_V1
    return WorkflowRun(
        run_id=ids.run_id, session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID, workflow_version="1.0.0",
        taxonomy_id=tax.taxonomy_id, taxonomy_version=tax.version,
        taxonomy_hash=tax.content_hash, started_at=NOW)


async def bootstrap(factory, ids) -> InterviewState:
    """§7.1/§7.2 前半:session + open run + version-0 snapshot + pointer。"""
    state = initial_state(ids)
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.runs.create(tenant_id=ids.tenant_id, run=open_run(ids))
        snap = await uow.artifacts.put(
            tenant_id=ids.tenant_id,
            record=build_inline_artifact(
                artifact_id=uuid4(), kind="state.snapshot.initial",
                media_type="application/json", payload=state,
                schema_id=INTERVIEW_STATE_SCHEMA_ID, run_id=ids.run_id,
                session_id=ids.session_id, created_at=NOW, contains_test_data=True))
        assert await uow.sessions.set_initial_state_artifact(
            tenant_id=ids.tenant_id, session_id=ids.session_id,
            artifact_id=snap.ref.artifact_id)
        await uow.commit()
    return state


def activate(ids, *, command_id: UUID | None = None,
             target: SessionStatus = SessionStatus.ACTIVE,
             stop_reason: str | None = None) -> TransitionSessionCommand:
    return TransitionSessionCommand(
        command_id=command_id or uuid4(), expected_state_version=0,
        occurred_at=NOW + timedelta(seconds=1), target_status=target,
        stop_reason=stop_reason)


async def apply(factory, ids, command, *, key: str | None = None):
    return await apply_durable_command(
        lambda: SqlAlchemyVNextUnitOfWork(factory),
        tenant_id=ids.tenant_id, session_id=ids.session_id, run_id=ids.run_id,
        command=command, stage="session.plan", event_id=uuid4(),
        command_artifact_id=uuid4(), reduction_artifact_id=uuid4(),
        committed_at=NOW + timedelta(seconds=2), request_idempotency_key=key)


async def _counts(factory, ids) -> dict:
    async with factory() as s:
        params = {"t": str(ids.tenant_id)}
        row = (await s.execute(sa.text(
            "SELECT state_version, status FROM interview_vnext_sessions "
            "WHERE tenant_id = :t"), params)).one()
        return {
            "state_version": row.state_version, "status": row.status,
            "commands": (await s.execute(sa.text(
                "SELECT count(*) FROM interview_vnext_commands "
                "WHERE tenant_id = :t"), params)).scalar_one(),
            "artifacts": (await s.execute(sa.text(
                "SELECT count(*) FROM interview_vnext_artifacts WHERE tenant_id = :t "
                "AND kind <> 'state.snapshot.initial'"), params)).scalar_one(),
            "events": (await s.execute(sa.text(
                "SELECT count(*) FROM interview_vnext_execution_events "
                "WHERE tenant_id = :t"), params)).scalar_one(),
            "outbox": (await s.execute(sa.text(
                "SELECT count(*) FROM interview_vnext_outbox "
                "WHERE tenant_id = :t"), params)).scalar_one(),
            "run_event_count": (await s.execute(sa.text(
                "SELECT event_count FROM interview_vnext_runs "
                "WHERE tenant_id = :t"), params)).scalar_one(),
        }


# ── case 1:round-trip ────────────────────────────────────────────────────────

async def test_initial_state_write_read_round_trip(postgres_session_factory,
                                                   vnext_profile):
    ids = vnext_profile
    state = await bootstrap(postgres_session_factory, ids)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        loaded = await uow.sessions.get(tenant_id=ids.tenant_id,
                                        session_id=ids.session_id)
    assert isinstance(loaded, InterviewState)      # domain model,不是 ORM row
    assert loaded == state


# ── case 2:五件事同 transaction ───────────────────────────────────────────────

async def test_command_commit_is_atomic_across_all_five_tables(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    outcome = await apply(postgres_session_factory, ids, activate(ids))
    assert isinstance(outcome, DurableCommandOutcome) and not outcome.replayed
    assert outcome.result.state.session.status == SessionStatus.ACTIVE

    after = await _counts(postgres_session_factory, ids)
    assert after == {"state_version": 1, "status": "active", "commands": 1,
                     "artifacts": 2, "events": 1, "outbox": 1,
                     "run_event_count": 1}
    async with postgres_session_factory() as s:
        event = (await s.execute(sa.text(
            "SELECT sequence, previous_event_hash, event_type "
            "FROM interview_vnext_execution_events WHERE tenant_id = :t"),
            {"t": str(ids.tenant_id)})).one()
        assert (event.sequence, event.previous_event_hash,
                event.event_type) == (1, None, "state.transition.accepted")
        outbox = (await s.execute(sa.text(
            "SELECT status, delivery_attempts FROM interview_vnext_outbox "
            "WHERE tenant_id = :t"), {"t": str(ids.tenant_id)})).one()
        assert (outbox.status, outbox.delivery_attempts) == ("pending", 0)


# ── case 3:每個 flush point 注入例外 → 半套資料不存在 ───────────────────────────

class _FailingUoW(SqlAlchemyVNextUnitOfWork):
    """在指定 repo 方法**成功執行後**丟例外(失敗點在 flush 之後、commit 之前)。"""

    def __init__(self, factory, fail_on: str, *, on_call: int = 1) -> None:
        super().__init__(factory)
        self._fail_on = fail_on
        self._on_call = on_call

    async def __aenter__(self):
        await super().__aenter__()
        target, method_name = self._fail_on.split(".")
        repo = getattr(self, target)
        original = getattr(repo, method_name)
        calls = {"n": 0}

        async def boom(*args, **kwargs):
            out = await original(*args, **kwargs)
            calls["n"] += 1
            if calls["n"] >= self._on_call:
                raise RuntimeError(f"failpoint:{self._fail_on}")
            return out

        setattr(repo, method_name, boom)
        return self


@pytest.mark.parametrize("fail_on,on_call", [
    ("artifacts.put", 2),        # reduction artifact 後
    ("commands.add", 1),
    ("sessions.save_cas", 1),
    ("capture.append_event", 1),
])
async def test_failpoint_after_each_flush_leaves_no_partial_data(
        postgres_session_factory, vnext_profile, fail_on, on_call):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    with pytest.raises(RuntimeError, match="failpoint"):
        await apply_durable_command(
            lambda: _FailingUoW(postgres_session_factory, fail_on, on_call=on_call),
            tenant_id=ids.tenant_id, session_id=ids.session_id, run_id=ids.run_id,
            command=activate(ids), stage="session.plan", event_id=uuid4(),
            command_artifact_id=uuid4(), reduction_artifact_id=uuid4(),
            committed_at=NOW + timedelta(seconds=2))
    after = await _counts(postgres_session_factory, ids)
    assert after == {"state_version": 0, "status": "planned", "commands": 0,
                     "artifacts": 0, "events": 0, "outbox": 0,
                     "run_event_count": 0}


# ── case 4:duplicate 冪等 ─────────────────────────────────────────────────────

async def test_duplicate_command_replays_existing_result(postgres_session_factory,
                                                         vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    command = activate(ids)
    first = await apply(postgres_session_factory, ids, command)
    second = await apply(postgres_session_factory, ids, command)   # 新 artifact/event id
    assert second.replayed is True
    assert second.result.state_hash == first.result.state_hash
    assert second.record == first.record
    after = await _counts(postgres_session_factory, ids)
    assert (after["commands"], after["events"], after["outbox"],
            after["state_version"]) == (1, 1, 1, 1)


# ── case 5:same key 不同 payload → conflict ──────────────────────────────────

async def test_same_request_key_different_payload_conflicts(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await apply(postgres_session_factory, ids, activate(ids), key="turn-1")
    different = activate(ids, target=SessionStatus.FAILED, stop_reason="不一樣的載荷")
    with pytest.raises(IdempotencyConflict):
        await apply(postgres_session_factory, ids, different, key="turn-1")


# ── case 6:併發 CAS 恰一個成功 ─────────────────────────────────────────────────

async def test_concurrent_commands_exactly_one_wins(postgres_session_factory,
                                                    vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    a = activate(ids)
    b = activate(ids, target=SessionStatus.FAILED, stop_reason="併發輸家")
    results = await asyncio.gather(
        apply(postgres_session_factory, ids, a),
        apply(postgres_session_factory, ids, b),
        return_exceptions=True)
    winners = [r for r in results if isinstance(r, DurableCommandOutcome)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert isinstance(losers[0], (StateVersionConflict, DomainViolation))
    after = await _counts(postgres_session_factory, ids)
    assert (after["state_version"], after["commands"], after["events"]) == (1, 1, 1)


# ── case 7:artifact immutability ─────────────────────────────────────────────

async def test_artifact_idempotent_conflict_and_update_trigger(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    artifact_id = uuid4()

    def record(payload) -> ArtifactRecord:
        return build_inline_artifact(
            artifact_id=artifact_id, kind="context.packet",
            media_type="application/json", payload=payload, run_id=ids.run_id,
            session_id=ids.session_id, created_at=NOW, contains_test_data=True)

    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        stored = await uow.artifacts.put(tenant_id=ids.tenant_id,
                                         record=record({"a": 1}))
        again = await uow.artifacts.put(tenant_id=ids.tenant_id,
                                        record=record({"a": 1}))
        assert again == stored                              # 同 ID 同 record 冪等
        with pytest.raises(ArtifactConflict):               # 同 ID 不同內容
            await uow.artifacts.put(tenant_id=ids.tenant_id,
                                    record=record({"a": 999}))
        await uow.rollback()

    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.artifacts.put(tenant_id=ids.tenant_id, record=record({"a": 1}))
        await uow.commit()
    async with postgres_session_factory() as s:            # UPDATE → trigger 拒絕
        with pytest.raises(DBAPIError, match="immutable"):
            await s.execute(sa.text(
                "UPDATE interview_vnext_artifacts SET kind = 'tampered' "
                "WHERE artifact_id = :a"), {"a": str(artifact_id)})
            await s.commit()


async def test_external_artifact_write_is_rejected(postgres_session_factory,
                                                   vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    external = ArtifactRecord(
        ref=ArtifactRef(artifact_id=uuid4(), kind="model.visible_response",
                        media_type="application/json",
                        content_hash="sha256:" + "a" * 64, byte_size=10),
        run_id=ids.run_id, session_id=ids.session_id, created_at=NOW,
        storage=ArtifactStorage.EXTERNAL, external_uri="s3://bucket/key",
        contains_test_data=True)
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(ExternalArtifactStoreUnavailable):
            await uow.artifacts.put(tenant_id=ids.tenant_id, record=external)
        await uow.rollback()


# ── §5.2 裁決:DB 接受 cleanup 暫態,application 拒讀 ─────────────────────────────

async def test_terminal_run_with_null_manifest_hydrates_as_corruption(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    fake_hash = "sha256:" + "b" * 64
    async with postgres_session_factory() as s:   # DB CHECK 允許(cleanup 暫態)
        await s.execute(sa.text(
            "UPDATE interview_vnext_runs SET status = 'completed', "
            "completed_at = started_at, event_count = 1, "
            "first_event_hash = :h, last_event_hash = :h, "
            "manifest_artifact_id = NULL WHERE tenant_id = :t"),
            {"h": fake_hash, "t": str(ids.tenant_id)})
        await s.commit()
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(PersistedDataCorruption):
            await uow.runs.get(tenant_id=ids.tenant_id, run_id=ids.run_id)
        await uow.rollback()


async def test_tampered_session_row_column_is_corruption(postgres_session_factory,
                                                         vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    async with postgres_session_factory() as s:
        await s.execute(sa.text(
            "UPDATE interview_vnext_sessions SET status = 'paused' "
            "WHERE tenant_id = :t"), {"t": str(ids.tenant_id)})
        await s.commit()
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(PersistedDataCorruption):
            await uow.sessions.get(tenant_id=ids.tenant_id,
                                   session_id=ids.session_id)
        await uow.rollback()
