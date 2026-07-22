"""V2-B-5:checkpoint attempts 與 crash recovery(reference §9/§12 cases 15–19)。

「process crash」測法(§12.1):每個 phase 的 transaction commit 後,所有
Python 物件/AsyncSession 都被丟棄——每個 durable operation 函式本來就自開
自關 UoW,decision 一律由 fresh session 重讀 committed rows,絕不信記憶體。
Scripted provider 只是計數器:`provider_completed|verified|committed|failed`
之後的 recovery,generate 呼叫數必須維持 0(§8.5)。
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import pytest
import sqlalchemy as sa

from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.durable_operations import (
    AttemptOutcome,
    claim_attempt_for_provider,
    commit_verified_noop_operation,
    commit_verified_operation,
    fail_operation,
    prepare_operation,
    record_attempt_result,
    record_verification,
    start_attempt,
)
from app.interview_vnext.application.persistence import RunStatus, WorkflowRun
from app.interview_vnext.application.recovery import (
    RecoveryAction,
    RecoveryCoordinator,
    decide_recovery,
    load_recovery_context,
)
from app.interview_vnext.domain.commands import TransitionSessionCommand
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.session import (
    ARCHITECTURE_ID,
    SessionStatus,
    session_at,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.llm.conformance import (
    ConformanceReport,
    ConformanceReportDefinition,
)
from app.interview_vnext.llm.result import ModelOutcome, TokenUsage
from app.interview_vnext.llm.testing import scripted_turn_binding
from app.interview_vnext.persistence.errors import PersistedDataCorruption
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.checkpoint import CheckpointStatus
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V2
from app.interview_vnext.persistence.errors import (
    CheckpointConflict,
    ExecutionEventConflict,
    StateContextStale,
)
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.interview_vnext.persistence.repositories import SqlAlchemySessionRepository

from tests.interview_vnext_llm_fixtures import (
    GateRecords,
    request_input_records,
    scripted_gate_records,
    scripted_model_request,
    unknown_execution_evidence,
)


NOW = datetime(2026, 7, 17, 7, 0, tzinfo=UTC)
MAX_ATTEMPTS = 3
DEADLINE = NOW + timedelta(seconds=30)
OP_NAME = "turn.interpret"
DEFINITION_HASH = canonical_hash({"operation": OP_NAME, "v": 1})


def initial_state(ids) -> InterviewState:
    return InterviewState(session=session_at(
        session_id=ids.session_id, profile_id=ids.profile_id, tenant_id=ids.tenant_id,
        workflow_version="1.0.0", reference_snapshot_id="ref-snapshot-v1", now=NOW))


def open_run(ids) -> WorkflowRun:
    tax = INTERVIEW_VNEXT_EXECUTION_V2
    return WorkflowRun(
        run_id=ids.run_id, session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID, workflow_version="1.0.0",
        taxonomy_id=tax.taxonomy_id, taxonomy_version=tax.version,
        taxonomy_hash=tax.content_hash, started_at=NOW)


def op_id(ids) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-recovery-op:{ids.session_id}")


def artifact(ids, name: str, payload, *, attempt_id: UUID | None = None) -> object:
    return build_inline_artifact(
        artifact_id=uuid5(NAMESPACE_URL, f"caliburn-recovery-art:{ids.session_id}:{name}"),
        kind="model.call_result" if "result" in name else "model.request",
        media_type="application/json", payload=payload, run_id=ids.run_id,
        session_id=ids.session_id, operation_id=op_id(ids),
        attempt_id=attempt_id,
        created_at=NOW, contains_test_data=True)


class CountingProvider:
    """Scripted provider:只計 generate 呼叫數(outcome 由測試指定)。"""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> dict:
        self.calls += 1
        return {"proposal": f"第 {self.calls} 次呼叫的產出"}


async def bootstrap(factory, ids) -> None:
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=initial_state(ids))
        await uow.capture.create_run(
            tenant_id=ids.tenant_id, run=open_run(ids),
            snapshot_artifact_id=uuid4(), started_event_id=uuid4())
        await uow.commit()


def uow_factory(factory):
    return lambda: SqlAlchemyVNextUnitOfWork(factory)


# R3-C2(修正計畫 §6.5):record_attempt_result 從 attempt 的 request artifact
# 載回 typed request 並交叉驗證 typed result/evidence/conformance,plain JSON
# 替身不再合法;helpers 以 attempt_id 為種子建 deterministic scripted gate。
BINDING = scripted_turn_binding()


def request_for(ids, attempt_id: UUID, *, attempt: int = 1):
    return scripted_model_request(
        attempt=attempt,
        name=f"recovery:{ids.session_id}:{attempt_id}",
        run_id=ids.run_id,
        session_id=ids.session_id,
        turn_id=None,
        operation_id=op_id(ids),
        attempt_id=attempt_id,
        created_at=NOW + timedelta(seconds=1),
    )


def prepare_request_uid(ids) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-recovery-prepare:{ids.session_id}")


async def prepare(factory, ids):
    request = request_for(ids, prepare_request_uid(ids))
    request_record, binding_record, config_record, projection_record = (
        request_input_records(request, BINDING)
    )
    return await prepare_operation(
        uow_factory(factory), tenant_id=ids.tenant_id, run_id=ids.run_id,
        session_id=ids.session_id, checkpoint_id=uuid4(), operation_id=op_id(ids),
        operation_name=OP_NAME, operation_definition_hash=DEFINITION_HASH,
        idempotency_key="turn-1:interpret",
        request_artifact=request_record,
        extra_request_artifacts=(binding_record, config_record, projection_record),
        step_event_id=uuid4(), occurred_at=NOW + timedelta(seconds=1))


async def start(
    factory, ids, *, attempt_id: UUID, attempt: int = 1, at=None, deadline=None
):
    # 每個 attempt 綁自己的 typed request artifact(binding/config/projection 的
    # persisted refs 由該 request 的 deterministic ids 引用)。
    request = request_for(ids, attempt_id, attempt=attempt)
    request_record, binding_record, config_record, projection_record = (
        request_input_records(request, BINDING)
    )
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        for record_item in (binding_record, config_record, projection_record):
            await uow.artifacts.put(tenant_id=ids.tenant_id, record=record_item)
        await uow.commit()
    return await start_attempt(
        uow_factory(factory), tenant_id=ids.tenant_id, operation_id=op_id(ids),
        attempt_id=attempt_id, provider="scripted",
        requested_model=BINDING.requested_model,
        deadline_at=deadline or DEADLINE, max_attempts=MAX_ATTEMPTS,
        request_artifact=request_record,
        call_event_id=uuid4(), occurred_at=at or NOW + timedelta(seconds=2))


async def record(factory, ids, *, attempt_id: UUID, name: str, outcome: AttemptOutcome,
                 attempt: int = 1, at=None):
    # SUCCEEDED 是 clean wire success + eligible conformance;失敗 outcome 是
    # wire failure(unknown route、conformance=wire_not_succeeded)。三件 typed
    # artifact 與 request/binding 交叉一致,record_attempt_result 內的 provider
    # gate 全驗後才落盤。
    request = request_for(ids, attempt_id, attempt=attempt)
    wire = (
        ModelOutcome.SUCCEEDED
        if outcome == AttemptOutcome.SUCCEEDED
        else ModelOutcome.FAILED
    )
    gate = scripted_gate_records(request, BINDING, outcome=wire)
    return await record_attempt_result(
        uow_factory(factory), tenant_id=ids.tenant_id, operation_id=op_id(ids),
        attempt_id=attempt_id,
        result_artifact=gate.result_record,
        execution_evidence_artifact=gate.evidence_record,
        conformance_artifact=gate.conformance_record,
        outcome=outcome,
        max_attempts=MAX_ATTEMPTS,
        result_event_id=uuid4(), conformance_event_id=uuid4(),
        occurred_at=at or NOW + timedelta(seconds=3))


async def decide(factory, ids, *, now=None, **kwargs) -> RecoveryAction:
    context = await load_recovery_context(
        uow_factory(factory), tenant_id=ids.tenant_id, operation_id=op_id(ids))
    return decide_recovery(context, now=now or NOW + timedelta(seconds=5),
                           max_attempts=MAX_ATTEMPTS, **kwargs)


async def _attempt_rows(factory, ids) -> list:
    async with factory() as s:
        return (await s.execute(sa.text(
            "SELECT attempt, status FROM interview_vnext_operation_attempts "
            "WHERE tenant_id = :t ORDER BY attempt"),
            {"t": str(ids.tenant_id)})).all()


async def _provider_event_payloads(factory, ids) -> list[dict]:
    async with factory() as session:
        rows = (
            await session.execute(
                sa.text(
                    "SELECT event_json FROM interview_vnext_execution_events "
                    "WHERE tenant_id = :tenant_id AND run_id = :run_id "
                    "AND event_type IN ('model.call.started', 'model.call.completed', "
                    "'model.call.failed', 'provider.conformance.completed') "
                    "ORDER BY sequence"
                ),
                {
                    "tenant_id": str(ids.tenant_id),
                    "run_id": str(ids.run_id),
                },
            )
        ).scalars().all()
    return [json.loads(row) for row in rows]


async def verify_noop_operation(factory, ids):
    await prepare(factory, ids)
    attempt_id = uuid4()
    await start(factory, ids, attempt_id=attempt_id)
    await record(
        factory,
        ids,
        attempt_id=attempt_id,
        name="result-noop",
        outcome=AttemptOutcome.SUCCEEDED,
    )
    verification = artifact(
        ids,
        "verification-noop",
        {"accepted": [], "dropped": [{"reason": "off_topic"}]},
    )
    await record_verification(
        uow_factory(factory),
        tenant_id=ids.tenant_id,
        operation_id=op_id(ids),
        verification_artifact=verification,
        accepted=True,
        event_id=uuid4(),
        occurred_at=NOW + timedelta(seconds=6),
    )
    return verification


def noop_response(ids, *, payload=None, artifact_id=None, at=None):
    return build_inline_artifact(
        artifact_id=artifact_id
        or uuid5(NAMESPACE_URL, f"noop-response:{ids.session_id}"),
        kind="operation.response",
        media_type="application/json",
        payload=(
            payload
            if payload is not None
            else {"say": "這一回合沒有可寫入的工作事實。"}
        ),
        run_id=ids.run_id,
        session_id=ids.session_id,
        operation_id=op_id(ids),
        created_at=at or NOW + timedelta(seconds=8),
        contains_test_data=True,
    )


def noop_commit_kwargs(ids, verification, *, response=None, step_event_id=None):
    return {
        "tenant_id": ids.tenant_id,
        "operation_id": op_id(ids),
        "response_artifact": response or noop_response(ids),
        "verification_artifact": verification,
        "noop_result_artifact_id": uuid5(
            NAMESPACE_URL, f"noop-result:{ids.session_id}"
        ),
        "step_event_id": step_event_id
        or uuid5(NAMESPACE_URL, f"noop-step:{ids.session_id}"),
        "committed_at": NOW + timedelta(seconds=8),
        "dropped_count": 1,
    }


# ── case 15/17:prepared recovery 只建一次 attempt 1;兩 workers 一個 CAS 贏 ──────

async def test_prepared_recovery_creates_attempt_one_exactly_once(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    assert await decide(postgres_session_factory, ids) == RecoveryAction.START_ATTEMPT

    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    again_cp, again_attempt = await start(postgres_session_factory, ids,
                                          attempt_id=a1)      # 冪等重入
    assert again_attempt.attempt_id == a1
    with pytest.raises(CheckpointConflict):                   # 不同 attempt_id → 拒
        await start(postgres_session_factory, ids, attempt_id=uuid4())
    assert [r.attempt for r in await _attempt_rows(postgres_session_factory, ids)] == [1]


async def test_two_recovery_workers_only_one_wins_cas(postgres_session_factory,
                                                      vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    results = await asyncio.gather(
        start(postgres_session_factory, ids, attempt_id=uuid4()),
        start(postgres_session_factory, ids, attempt_id=uuid4()),
        return_exceptions=True)
    winners = [r for r in results if isinstance(r, tuple)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert isinstance(losers[0], CheckpointConflict)
    assert len(await _attempt_rows(postgres_session_factory, ids)) == 1


async def test_same_attempt_claim_race_grants_exactly_one_provider_owner(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    attempt_id = uuid4()
    request = request_for(ids, attempt_id)
    request_record, binding_record, config_record, projection_record = (
        request_input_records(request, BINDING)
    )
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        for record_item in (binding_record, config_record, projection_record):
            await uow.artifacts.put(tenant_id=ids.tenant_id, record=record_item)
        await uow.commit()

    async def claim():
        return await claim_attempt_for_provider(
            uow_factory(postgres_session_factory),
            tenant_id=ids.tenant_id,
            operation_id=op_id(ids),
            attempt_id=attempt_id,
            provider="scripted",
            requested_model=BINDING.requested_model,
            deadline_at=DEADLINE,
            max_attempts=MAX_ATTEMPTS,
            request_artifact=request_record,
            call_event_id=uuid5(attempt_id, "call-started"),
            occurred_at=NOW + timedelta(seconds=2),
        )

    first, second = await asyncio.gather(claim(), claim())
    assert sorted((first[2], second[2])) == [False, True]
    assert first[1] == second[1]
    assert len(await _attempt_rows(postgres_session_factory, ids)) == 1


# ── case 16:deadline 前等待、deadline 後 lost+retry 恰一次 ──────────────────────

async def test_calling_waits_before_deadline_and_retries_once_after(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    provider = CountingProvider()
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    provider.generate()                                       # in-flight 的那次呼叫

    # deadline 未到:等,不重打
    assert await decide(postgres_session_factory, ids,
                        now=NOW + timedelta(seconds=5)) == \
        RecoveryAction.WAIT_FOR_DEADLINE
    assert provider.calls == 1

    # deadline 已到:先保存 lost result 完成舊 attempt,再開新 attempt(恰 +1)
    after = NOW + timedelta(seconds=60)
    assert await decide(postgres_session_factory, ids, now=after) == \
        RecoveryAction.RECORD_LOST_AND_RETRY
    await record(postgres_session_factory, ids, attempt_id=a1, name="result-lost-1",
                 outcome=AttemptOutcome.RETRYABLE_FAILURE, at=after)
    a2 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a2,
                attempt=2,
                at=after + timedelta(seconds=1),
                deadline=after + timedelta(seconds=300))
    provider.generate()
    rows = await _attempt_rows(postgres_session_factory, ids)
    assert [(r.attempt, r.status) for r in rows] == [
        (1, "result_recorded"), (2, "calling")]
    # 新 attempt in-flight、deadline 未到 → 只會等,不會再長出第三個 attempt
    assert await decide(postgres_session_factory, ids,
                        now=after + timedelta(seconds=2)) == \
        RecoveryAction.WAIT_FOR_DEADLINE
    assert provider.calls == 2
    events = await _provider_event_payloads(postgres_session_factory, ids)
    assert [event["event_type"] for event in events] == [
        "model.call.started",
        "model.call.failed",
        "provider.conformance.completed",
        "model.call.started",
    ]
    assert [event["status"] for event in events] == [
        "ok", "failed", "skipped", "ok"
    ]
    assert events[1]["input_artifacts"] == events[0]["input_artifacts"]
    assert [ref["kind"] for ref in events[2]["input_artifacts"]] == [
        "model.provider_binding",
        "model.provider_execution_evidence",
    ]


async def test_attempt_budget_exhaustion_marks_failed(postgres_session_factory,
                                                      vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    at = NOW + timedelta(seconds=2)
    for n in range(1, MAX_ATTEMPTS + 1):                      # 3 次全 retryable 失敗
        attempt_id = uuid4()
        await start(
            postgres_session_factory, ids, attempt_id=attempt_id, attempt=n, at=at
        )
        at += timedelta(seconds=1)
        checkpoint = await record(postgres_session_factory, ids,
                                  attempt_id=attempt_id, name=f"result-{n}",
                                  outcome=AttemptOutcome.RETRYABLE_FAILURE,
                                  attempt=n, at=at)
        at += timedelta(seconds=1)
    # 第 3 次 retryable + 額度耗盡 → record 內轉 failed
    assert checkpoint.status == CheckpointStatus.FAILED
    assert await decide(postgres_session_factory, ids) == RecoveryAction.RETURN_FAILED
    with pytest.raises(CheckpointConflict):                   # 不可再開 attempt
        await start(postgres_session_factory, ids, attempt_id=uuid4(), at=at)
    events = await _provider_event_payloads(postgres_session_factory, ids)
    assert [event["status"] for event in events] == [
        "ok", "failed", "skipped",
        "ok", "failed", "skipped",
        "ok", "failed", "skipped",
    ]


# ── case 18/19:provider_completed 之後零 provider call;committed 回同一結果 ─────

async def test_late_phases_never_call_provider_and_committed_replays(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    provider = CountingProvider()
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    provider.generate()
    await record(postgres_session_factory, ids, attempt_id=a1, name="result-ok",
                 outcome=AttemptOutcome.SUCCEEDED)

    # provider_completed:只允許 verify
    assert await decide(postgres_session_factory, ids) == \
        RecoveryAction.VERIFY_EXISTING_RESULT
    await record_verification(
        uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
        operation_id=op_id(ids),
        verification_artifact=artifact(ids, "verification", {"accepted": True}),
        accepted=True, event_id=uuid4(), occurred_at=NOW + timedelta(seconds=6))

    # verified:只允許 commit
    assert await decide(postgres_session_factory, ids) == \
        RecoveryAction.COMMIT_VERIFIED_RESULT
    command = TransitionSessionCommand(
        command_id=uuid5(NAMESPACE_URL, f"caliburn-recovery-cmd:{ids.session_id}"),
        expected_state_version=0, occurred_at=NOW + timedelta(seconds=7),
        target_status=SessionStatus.ACTIVE)
    commit_kwargs = dict(
        tenant_id=ids.tenant_id, operation_id=op_id(ids), run_id=ids.run_id,
        command=command, response_payload={"say": "已記下,我們繼續。"},
        response_artifact_id=uuid5(NAMESPACE_URL, f"resp:{ids.session_id}"),
        command_artifact_id=uuid5(NAMESPACE_URL, f"cmd-art:{ids.session_id}"),
        reduction_artifact_id=uuid5(NAMESPACE_URL, f"red-art:{ids.session_id}"),
        transition_event_id=uuid5(NAMESPACE_URL, f"ev-t:{ids.session_id}"),
        step_event_id=uuid5(NAMESPACE_URL, f"ev-s:{ids.session_id}"),
        committed_at=NOW + timedelta(seconds=8))
    first_cp, first_result, first_closure = await commit_verified_operation(
        uow_factory(postgres_session_factory), **commit_kwargs)
    assert first_cp.status == CheckpointStatus.COMMITTED
    assert first_result.state.session.status == SessionStatus.ACTIVE

    # committed:回既有 response/domain result,不重跑 reducer、不打 provider
    assert await decide(postgres_session_factory, ids) == \
        RecoveryAction.RETURN_COMMITTED
    replay_cp, replay_result, replay_closure = await commit_verified_operation(
        uow_factory(postgres_session_factory), **commit_kwargs)
    assert replay_cp.response_artifact == first_cp.response_artifact
    assert replay_cp.domain_result_artifact == first_cp.domain_result_artifact
    assert replay_result.state_hash == first_result.state_hash
    assert replay_closure == first_closure
    assert provider.calls == 1                               # 全程恰一次 generate
    provider_events = await _provider_event_payloads(postgres_session_factory, ids)
    assert [event["event_type"] for event in provider_events] == [
        "model.call.started",
        "model.call.completed",
        "provider.conformance.completed",
    ]
    assert [event["status"] for event in provider_events] == ["ok", "ok", "ok"]
    assert provider_events[1]["input_artifacts"] == provider_events[0]["input_artifacts"]
    assert [ref["kind"] for ref in provider_events[1]["output_artifacts"][-2:]] == [
        "model.result",
        "model.provider_execution_evidence",
    ]


async def test_verified_noop_is_atomic_idempotent_and_has_no_command(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    verification = await verify_noop_operation(postgres_session_factory, ids)
    kwargs = noop_commit_kwargs(ids, verification)

    first_checkpoint, first_result = await commit_verified_noop_operation(
        uow_factory(postgres_session_factory), **kwargs
    )
    replay_checkpoint, replay_result = await commit_verified_noop_operation(
        uow_factory(postgres_session_factory), **kwargs
    )

    assert first_checkpoint.status == CheckpointStatus.COMMITTED
    assert first_checkpoint.state_after_hash == first_checkpoint.state_before_hash
    assert replay_checkpoint == first_checkpoint
    assert replay_result == first_result
    assert first_result.accepted_count == 0
    assert first_result.dropped_count == 1

    async with postgres_session_factory() as session:
        state_version = (await session.execute(sa.text(
            "SELECT state_version FROM interview_vnext_sessions "
            "WHERE tenant_id = :tenant_id AND session_id = :session_id"
        ), {"tenant_id": str(ids.tenant_id),
            "session_id": str(ids.session_id)})).scalar_one()
        command_count = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_commands "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()
        artifact_row = (await session.execute(sa.text(
            "SELECT kind, schema_id FROM interview_vnext_artifacts "
            "WHERE tenant_id = :tenant_id AND artifact_id = :artifact_id"
        ), {"tenant_id": str(ids.tenant_id),
            "artifact_id": str(kwargs["noop_result_artifact_id"])})).one()
        event_json = (await session.execute(sa.text(
            "SELECT event_json FROM interview_vnext_execution_events "
            "WHERE tenant_id = :tenant_id AND event_id = :event_id"
        ), {"tenant_id": str(ids.tenant_id),
            "event_id": str(kwargs["step_event_id"])})).scalar_one()
        outbox_count = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_outbox "
            "WHERE tenant_id = :tenant_id AND message_id = :message_id"
        ), {"tenant_id": str(ids.tenant_id),
            "message_id": str(kwargs["step_event_id"])})).scalar_one()

    event = json.loads(event_json)
    assert state_version == 0
    assert command_count == 0
    assert tuple(artifact_row) == (
        "operation.noop_result",
        "https://caliburn.local/schemas/operation-noop-result.v1.schema.json",
    )
    assert json.loads(event["metadata_json"]) == {
        "accepted_count": 0,
        "dropped_count": 1,
        "reason": "no_domain_mutation",
    }
    assert event["state_before_hash"] == event["state_after_hash"]
    assert outbox_count == 1

    changed_response = noop_response(
        ids,
        artifact_id=kwargs["response_artifact"].ref.artifact_id,
        payload={"say": "這是不同內容，不得冒充冪等重送。"},
    )
    with pytest.raises(CheckpointConflict, match="different no-op outcome"):
        await commit_verified_noop_operation(
            uow_factory(postgres_session_factory),
            **{**kwargs, "response_artifact": changed_response},
        )

    changed_verification = artifact(
        ids,
        "verification-noop-changed",
        {"accepted": [], "dropped": [{"reason": "declined"}]},
    )
    with pytest.raises(CheckpointConflict, match="different no-op outcome"):
        await commit_verified_noop_operation(
            uow_factory(postgres_session_factory),
            **{**kwargs, "verification_artifact": changed_verification},
        )

    with pytest.raises(CheckpointConflict, match="different no-op outcome"):
        await commit_verified_noop_operation(
            uow_factory(postgres_session_factory),
            **{**kwargs, "step_event_id": uuid4()},
        )


async def test_verified_noop_rolls_back_everything_when_event_conflicts(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    verification = await verify_noop_operation(postgres_session_factory, ids)
    response = noop_response(ids)
    noop_id = uuid5(NAMESPACE_URL, f"noop-result:{ids.session_id}")
    async with postgres_session_factory() as session:
        conflicting_event_id = (await session.execute(sa.text(
            "SELECT event_id FROM interview_vnext_execution_events "
            "WHERE tenant_id = :tenant_id ORDER BY sequence LIMIT 1"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()
        event_count_before = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_execution_events "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()
        outbox_count_before = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_outbox "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()

    with pytest.raises(ExecutionEventConflict):
        await commit_verified_noop_operation(
            uow_factory(postgres_session_factory),
            **noop_commit_kwargs(
                ids,
                verification,
                response=response,
                step_event_id=conflicting_event_id,
            ),
        )

    async with postgres_session_factory() as session:
        checkpoint_status = (await session.execute(sa.text(
            "SELECT status FROM interview_vnext_operation_checkpoints "
            "WHERE tenant_id = :tenant_id AND operation_id = :operation_id"
        ), {"tenant_id": str(ids.tenant_id),
            "operation_id": str(op_id(ids))})).scalar_one()
        new_artifact_count = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_artifacts "
            "WHERE tenant_id = :tenant_id AND artifact_id IN (:response_id, :noop_id)"
        ), {"tenant_id": str(ids.tenant_id),
            "response_id": str(response.ref.artifact_id),
            "noop_id": str(noop_id)})).scalar_one()
        event_count_after = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_execution_events "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()
        outbox_count_after = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_outbox "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()

    assert checkpoint_status == "verified"
    assert new_artifact_count == 0
    assert event_count_after == event_count_before
    assert outbox_count_after == outbox_count_before


async def test_two_identical_noop_committers_create_one_completion(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    verification = await verify_noop_operation(postgres_session_factory, ids)
    kwargs = noop_commit_kwargs(ids, verification)

    outcomes = await asyncio.gather(
        commit_verified_noop_operation(
            uow_factory(postgres_session_factory), **kwargs
        ),
        commit_verified_noop_operation(
            uow_factory(postgres_session_factory), **kwargs
        ),
        return_exceptions=True,
    )
    successes = [item for item in outcomes if isinstance(item, tuple)]
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert len(successes) >= 1
    assert all(isinstance(item, CheckpointConflict) for item in failures)

    async with postgres_session_factory() as session:
        completions = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_execution_events "
            "WHERE tenant_id = :tenant_id AND event_id = :event_id"
        ), {"tenant_id": str(ids.tenant_id),
            "event_id": str(kwargs["step_event_id"])})).scalar_one()
        commands = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_commands "
            "WHERE tenant_id = :tenant_id"
        ), {"tenant_id": str(ids.tenant_id)})).scalar_one()
    assert completions == 1
    assert commands == 0


async def test_stale_state_blocks_verified_noop_without_new_artifacts(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    verification = await verify_noop_operation(postgres_session_factory, ids)
    response = noop_response(ids)
    noop_id = uuid5(NAMESPACE_URL, f"noop-result:{ids.session_id}")

    await apply_durable_command(
        uow_factory(postgres_session_factory),
        tenant_id=ids.tenant_id,
        session_id=ids.session_id,
        run_id=ids.run_id,
        command=TransitionSessionCommand(
            command_id=uuid4(),
            expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=7),
            target_status=SessionStatus.ACTIVE,
        ),
        stage="session.plan",
        event_id=uuid4(),
        command_artifact_id=uuid4(),
        reduction_artifact_id=uuid4(),
        committed_at=NOW + timedelta(seconds=8),
    )

    with pytest.raises(CheckpointConflict, match="re-prepare"):
        await commit_verified_noop_operation(
            uow_factory(postgres_session_factory),
            **noop_commit_kwargs(ids, verification, response=response),
        )

    async with postgres_session_factory() as session:
        checkpoint_status = (await session.execute(sa.text(
            "SELECT status FROM interview_vnext_operation_checkpoints "
            "WHERE tenant_id = :tenant_id AND operation_id = :operation_id"
        ), {"tenant_id": str(ids.tenant_id),
            "operation_id": str(op_id(ids))})).scalar_one()
        new_artifact_count = (await session.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_artifacts "
            "WHERE tenant_id = :tenant_id AND artifact_id IN (:response_id, :noop_id)"
        ), {"tenant_id": str(ids.tenant_id),
            "response_id": str(response.ref.artifact_id),
            "noop_id": str(noop_id)})).scalar_one()
    assert checkpoint_status == "verified"
    assert new_artifact_count == 0


async def test_verification_rejection_fails_without_touching_state(
        postgres_session_factory, vnext_profile):
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    await record(postgres_session_factory, ids, attempt_id=a1, name="result-ok",
                 outcome=AttemptOutcome.SUCCEEDED)
    checkpoint = await record_verification(
        uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
        operation_id=op_id(ids),
        verification_artifact=artifact(ids, "verification",
                                       {"accepted": False, "why": "語意不符"}),
        accepted=False, event_id=uuid4(), occurred_at=NOW + timedelta(seconds=6))
    assert checkpoint.status == CheckpointStatus.FAILED
    assert await decide(postgres_session_factory, ids) == RecoveryAction.RETURN_FAILED
    async with postgres_session_factory() as s:              # reducer 從未跑
        version = (await s.execute(sa.text(
            "SELECT state_version FROM interview_vnext_sessions "
            "WHERE tenant_id = :t"), {"t": str(ids.tenant_id)})).scalar_one()
        assert version == 0


async def test_stale_state_blocks_verified_commit(postgres_session_factory,
                                                  vnext_profile):
    """§7.8(2):prepare 之後 state 已前進 → 不把舊 proposal 硬套新 state。"""
    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    await record(postgres_session_factory, ids, attempt_id=a1, name="result-ok",
                 outcome=AttemptOutcome.SUCCEEDED)
    await record_verification(
        uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
        operation_id=op_id(ids),
        verification_artifact=artifact(ids, "verification", {"accepted": True}),
        accepted=True, event_id=uuid4(), occurred_at=NOW + timedelta(seconds=6))
    # 另一條路徑先推進 state(version 0 → 1)
    await apply_durable_command(
        uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
        session_id=ids.session_id, run_id=ids.run_id,
        command=TransitionSessionCommand(
            command_id=uuid4(), expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=7),
            target_status=SessionStatus.ACTIVE),
        stage="session.plan", event_id=uuid4(), command_artifact_id=uuid4(),
        reduction_artifact_id=uuid4(), committed_at=NOW + timedelta(seconds=8))
    with pytest.raises(StateContextStale) as captured:
        await commit_verified_operation(
            uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
            operation_id=op_id(ids), run_id=ids.run_id,
            command=TransitionSessionCommand(
                command_id=uuid4(), expected_state_version=0,
                occurred_at=NOW + timedelta(seconds=9),
                target_status=SessionStatus.ACTIVE),
            response_payload={}, response_artifact_id=uuid4(),
            command_artifact_id=uuid4(), reduction_artifact_id=uuid4(),
            transition_event_id=uuid4(), step_event_id=uuid4(),
            committed_at=NOW + timedelta(seconds=9))
    assert captured.value.expected_state_version == 0
    assert captured.value.actual_state_version == 1


async def test_verified_commit_cas_loser_is_typed_stale_and_rolls_back(
    postgres_session_factory, vnext_profile, monkeypatch
):
    """C4 race window 3: state CAS loses after reduction; no domain rows survive."""

    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    attempt_id = uuid4()
    await start(postgres_session_factory, ids, attempt_id=attempt_id)
    await record(
        postgres_session_factory,
        ids,
        attempt_id=attempt_id,
        name="result-cas-loser",
        outcome=AttemptOutcome.SUCCEEDED,
    )
    await record_verification(
        uow_factory(postgres_session_factory),
        tenant_id=ids.tenant_id,
        operation_id=op_id(ids),
        verification_artifact=artifact(ids, "verification-cas-loser", {"accepted": True}),
        accepted=True,
        event_id=uuid4(),
        occurred_at=NOW + timedelta(seconds=6),
    )

    command_id = uuid4()

    async def lose_cas(self, *, tenant_id, old_version, new_state):
        return False

    monkeypatch.setattr(SqlAlchemySessionRepository, "save_cas", lose_cas)
    with pytest.raises(StateContextStale) as captured:
        await commit_verified_operation(
            uow_factory(postgres_session_factory),
            tenant_id=ids.tenant_id,
            operation_id=op_id(ids),
            run_id=ids.run_id,
            command=TransitionSessionCommand(
                command_id=command_id,
                expected_state_version=0,
                occurred_at=NOW + timedelta(seconds=9),
                target_status=SessionStatus.ACTIVE,
            ),
            response_payload={},
            response_artifact_id=uuid4(),
            command_artifact_id=uuid4(),
            reduction_artifact_id=uuid4(),
            transition_event_id=uuid4(),
            step_event_id=uuid4(),
            committed_at=NOW + timedelta(seconds=9),
        )
    assert captured.value.actual_state_version is None

    async with postgres_session_factory() as session:
        command_count = (
            await session.execute(
                sa.text(
                    "SELECT count(*) FROM interview_vnext_commands "
                    "WHERE tenant_id = :tenant_id AND command_id = :command_id"
                ),
                {"tenant_id": str(ids.tenant_id), "command_id": str(command_id)},
            )
        ).scalar_one()
    assert command_count == 0


async def test_coordinator_executes_one_decision_per_step(postgres_session_factory,
                                                          vnext_profile):
    """§8.4:coordinator 一次一個 decision/transaction;fail_operation 走
    workflow.step.failed。"""
    ids = vnext_profile
    provider = CountingProvider()
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)

    started: list[UUID] = []

    async def do_start(context) -> None:
        attempt_id = uuid4()
        await start(postgres_session_factory, ids, attempt_id=attempt_id)
        provider.generate()               # provider call 在 transaction 之外
        started.append(attempt_id)

    coordinator = RecoveryCoordinator(
        uow_factory(postgres_session_factory), tenant_id=ids.tenant_id,
        max_attempts=MAX_ATTEMPTS,
        executors={RecoveryAction.START_ATTEMPT: do_start})
    assert await coordinator.step(operation_id=op_id(ids),
                                  now=NOW + timedelta(seconds=3)) == \
        RecoveryAction.START_ATTEMPT
    # in-flight + 未到 deadline → 等(沒 executor,不動作)
    assert await coordinator.step(operation_id=op_id(ids),
                                  now=NOW + timedelta(seconds=4)) == \
        RecoveryAction.WAIT_FOR_DEADLINE
    # driver 收到 provider 的 non-retryable 失敗 → 同 transaction 轉 failed
    await record(postgres_session_factory, ids, attempt_id=started[0],
                 name="result-nonretryable",
                 outcome=AttemptOutcome.NON_RETRYABLE_FAILURE,
                 at=NOW + timedelta(seconds=20))
    assert await coordinator.step(operation_id=op_id(ids),
                                  now=NOW + timedelta(seconds=61)) == \
        RecoveryAction.RETURN_FAILED
    assert provider.calls == 1


# ── R3-C2 §7.3:durable write truth table 與 rollback ────────────────────────


def ineligible_success_gate(ids, attempt_id) -> GateRecords:
    """wire succeeded 但 attribution ineligible(route facts unknown)的 gate。"""

    request = request_for(ids, attempt_id)
    evidence = unknown_execution_evidence(
        BINDING,
        usage=TokenUsage(
            input_tokens=100, output_tokens=20, cache_read_tokens=0,
            cache_write_tokens=0, reasoning_tokens=0,
        ),
    )
    return scripted_gate_records(
        request, BINDING, outcome=ModelOutcome.SUCCEEDED,
        evidence_override=evidence,
    )


def forged_conformance(report: ConformanceReport, **overrides) -> ConformanceReport:
    definition = ConformanceReportDefinition.model_validate(
        {**report.model_dump(exclude={"report_hash"}), **overrides}
    )
    return ConformanceReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )


async def gate_side_effect_counts(factory, ids) -> tuple[int, int, list]:
    async with factory() as s:
        artifacts = (await s.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_artifacts WHERE tenant_id = :t"),
            {"t": str(ids.tenant_id)})).scalar_one()
        events = (await s.execute(sa.text(
            "SELECT count(*) FROM interview_vnext_execution_events WHERE tenant_id = :t"),
            {"t": str(ids.tenant_id)})).scalar_one()
    return artifacts, events, await _attempt_rows(factory, ids)


async def record_gate(factory, ids, *, attempt_id, gate: GateRecords,
                      outcome: AttemptOutcome, at=None):
    return await record_attempt_result(
        uow_factory(factory), tenant_id=ids.tenant_id, operation_id=op_id(ids),
        attempt_id=attempt_id,
        result_artifact=gate.result_record,
        execution_evidence_artifact=gate.evidence_record,
        conformance_artifact=gate.conformance_record,
        outcome=outcome, max_attempts=MAX_ATTEMPTS,
        result_event_id=uuid4(), conformance_event_id=uuid4(),
        occurred_at=at or NOW + timedelta(seconds=3))


async def test_wire_succeeded_but_ineligible_fails_with_conformance_authority(
        postgres_session_factory, vnext_profile):
    """§7.3.2:succeeded+ineligible → failed,failure authority=conformance report。"""

    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    gate = ineligible_success_gate(ids, a1)
    checkpoint = await record_gate(
        postgres_session_factory, ids, attempt_id=a1, gate=gate,
        outcome=AttemptOutcome.NON_RETRYABLE_FAILURE)
    assert checkpoint.status == CheckpointStatus.FAILED
    assert checkpoint.failure_artifact == gate.conformance_record.ref
    assert (
        checkpoint.provider_execution_evidence_artifact == gate.evidence_record.ref
    )
    assert checkpoint.provider_conformance_artifact == gate.conformance_record.ref
    provider_events = await _provider_event_payloads(postgres_session_factory, ids)
    assert [event["status"] for event in provider_events] == [
        "ok", "failed", "failed"
    ]
    assert provider_events[1]["input_artifacts"] == provider_events[0]["input_artifacts"]
    assert [ref["kind"] for ref in provider_events[2]["input_artifacts"]] == [
        "model.provider_binding",
        "model.provider_execution_evidence",
    ]


@pytest.mark.parametrize(
    "case", ["succeeded_on_wire_failure", "succeeded_on_ineligible",
             "retryable_on_ineligible"],
)
async def test_impossible_classifications_roll_back_before_any_write(
        postgres_session_factory, vnext_profile, case):
    """§7.3.4-6:§5.5 truth table 的矛盾組合在任何 write 前 raise 且零殘留。"""

    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    if case == "succeeded_on_wire_failure":
        gate = scripted_gate_records(
            request_for(ids, a1), BINDING, outcome=ModelOutcome.FAILED
        )
        outcome = AttemptOutcome.SUCCEEDED
    elif case == "succeeded_on_ineligible":
        gate = ineligible_success_gate(ids, a1)
        outcome = AttemptOutcome.SUCCEEDED
    else:
        gate = ineligible_success_gate(ids, a1)
        outcome = AttemptOutcome.RETRYABLE_FAILURE
    before = await gate_side_effect_counts(postgres_session_factory, ids)
    with pytest.raises(CheckpointConflict):
        await record_gate(
            postgres_session_factory, ids, attempt_id=a1, gate=gate, outcome=outcome
        )
    # §7.3.12:rollback 後沒有新增 artifacts/events,attempt 也未轉 result_recorded。
    assert await gate_side_effect_counts(postgres_session_factory, ids) == before
    rows = await _attempt_rows(postgres_session_factory, ids)
    assert [(r.attempt, r.status) for r in rows] == [(1, "calling")]


@pytest.mark.parametrize(
    "tamper", ["foreign_binding_evidence", "evidence_hash_drift", "wrong_kind"],
)
async def test_tampered_gate_artifacts_roll_back_before_any_write(
        postgres_session_factory, vnext_profile, tamper):
    """§7.3.7/8/11(PG 面):typed 交叉驗證失敗 → 整個 UoW rollback、零殘留。"""

    ids = vnext_profile
    await bootstrap(postgres_session_factory, ids)
    await prepare(postgres_session_factory, ids)
    a1 = uuid4()
    await start(postgres_session_factory, ids, attempt_id=a1)
    request = request_for(ids, a1)
    if tamper == "foreign_binding_evidence":
        foreign = scripted_turn_binding(binding_id="turn-interpret-foreign")
        gate = scripted_gate_records(
            request, BINDING, outcome=ModelOutcome.FAILED,
            evidence_override=unknown_execution_evidence(foreign),
        )
    elif tamper == "evidence_hash_drift":
        base = scripted_gate_records(request, BINDING)
        gate = scripted_gate_records(
            request, BINDING,
            conformance_override=forged_conformance(
                base.conformance, execution_evidence_hash="sha256:" + "9" * 64
            ),
        )
    else:
        base = scripted_gate_records(request, BINDING)
        payload = base.result_record.model_dump()
        payload["ref"] = {**payload["ref"], "kind": "model.request"}
        from app.interview_vnext.observability.artifacts import ArtifactRecord

        gate = GateRecords(
            result=base.result, evidence=base.evidence,
            conformance=base.conformance,
            result_record=ArtifactRecord.model_validate(payload),
            evidence_record=base.evidence_record,
            conformance_record=base.conformance_record,
        )
    before = await gate_side_effect_counts(postgres_session_factory, ids)
    with pytest.raises(PersistedDataCorruption):
        await record_gate(
            postgres_session_factory, ids, attempt_id=a1, gate=gate,
            outcome=AttemptOutcome.RETRYABLE_FAILURE
            if tamper != "wrong_kind"
            else AttemptOutcome.SUCCEEDED,
        )
    assert await gate_side_effect_counts(postgres_session_factory, ids) == before
    rows = await _attempt_rows(postgres_session_factory, ids)
    assert [(r.attempt, r.status) for r in rows] == [(1, "calling")]
