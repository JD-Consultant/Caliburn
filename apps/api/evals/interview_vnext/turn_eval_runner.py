"""One-trial durable execution for the V3-5 turn eval harness (§11).

``run_trial`` drives exactly one fresh-session trial through the production
stack:User/JobProfile 行 → InterviewState v0 → durable WorkflowRun +
initial snapshot → 公開 durable commands replay(activate/transcript/episode/
prior evidence)→ production ``execute_turn_interpret`` → 同 UoW finalize。
評分規則不在此模組;``run_trial`` 的 signature 依 §8.2 不接受 gold。

Batch scheduling、Capture export 與 report 屬 E6(另一個 commit 切片)。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.operation_executor import (
    TurnExecutionStatus,
    TurnInterpretProviderProfile,
    TurnInterpretExecutionOutcome,
    execute_turn_interpret,
)
from app.interview_vnext.application.persistence import (
    RunStatus,
    WorkflowRun,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.session import ARCHITECTURE_ID
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.llm.port import LlmPort
from app.interview_vnext.observability.artifacts import ArtifactRef
from app.interview_vnext.observability.events import ExecutionStatus
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.models import JobProfile, User

from .fixture_builder import WORKFLOW_VERSION, setup_commands
from .identities import TrialScopedIds, trial_scoped_ids, turn_uuid
from .loader import TurnEvalCaseInputs

from app.interview_vnext.domain.session import session_at


# fixture domain 時間往前推,確保 target turn 早於 provider call(§11.1)
FIXTURE_WINDOW = timedelta(minutes=10)


@dataclass(frozen=True)
class TrialExecution:
    """Terminal facts of one durable trial, before any grading."""

    ids: TrialScopedIds
    outcome: TurnInterpretExecutionOutcome
    run: WorkflowRun
    manifest_ref: ArtifactRef
    state_before: InterviewState
    state_before_hash: str
    state_after: InterviewState
    state_after_hash: str
    setup_command_count: int


def _uid(trial_id: UUID, label: str) -> UUID:
    return uuid5(trial_id, label)


async def provision_identity(
    session_factory: async_sessionmaker, ids: TrialScopedIds
) -> None:
    """Fresh User/JobProfile rows(vNext sessions.profile_id 的 FK 前提)。"""

    # 冪等:crash/resume(§11.3)重跑同一 trial 時,identity 列可能已存在。
    async with session_factory() as session:
        existing_user = await session.get(User, ids.user_id)
        if existing_user is None:
            session.add(
                User(
                    id=ids.user_id,
                    email=f"turn-eval-{ids.user_id}@eval.local",
                    name="turn eval fixture user",
                )
            )
        existing_profile = await session.get(JobProfile, ids.profile_id)
        if existing_profile is None:
            session.add(
                JobProfile(
                    id=ids.profile_id,
                    user_id=ids.user_id,
                    job_title="turn eval fixture profile",
                )
            )
        await session.commit()


async def run_trial(
    inputs: TurnEvalCaseInputs,
    *,
    session_factory: async_sessionmaker,
    llm: LlmPort,
    profile: TurnInterpretProviderProfile,
    trial_id: UUID,
    trial_started_at: datetime,
) -> TrialExecution:
    """§11 one-trial flow steps 2–10;caller 只提供 runtime inputs 與 LlmPort。"""

    ids = trial_scoped_ids(trial_id)
    base_time = trial_started_at - FIXTURE_WINDOW

    def uow_factory() -> SqlAlchemyVNextUnitOfWork:
        return SqlAlchemyVNextUnitOfWork(session_factory)

    await provision_identity(session_factory, ids)

    taxonomy = INTERVIEW_VNEXT_EXECUTION_V1
    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version=WORKFLOW_VERSION,
            reference_snapshot_id=inputs.reference_snapshot.snapshot_id,
            now=base_time,
        )
    )
    run = WorkflowRun(
        run_id=ids.run_id,
        session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID,
        workflow_version=WORKFLOW_VERSION,
        taxonomy_id=taxonomy.taxonomy_id,
        taxonomy_version=taxonomy.version,
        taxonomy_hash=taxonomy.content_hash,
        started_at=base_time,
    )
    async with uow_factory() as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.capture.create_run(
            tenant_id=ids.tenant_id,
            run=run,
            snapshot_artifact_id=_uid(trial_id, "artifact/initial-state"),
            started_event_id=_uid(trial_id, "event/run-started"),
        )
        await uow.commit()

    steps = setup_commands(inputs, ids=ids, base_time=base_time)
    for step in steps:
        await apply_durable_command(
            uow_factory,
            tenant_id=ids.tenant_id,
            session_id=ids.session_id,
            run_id=ids.run_id,
            command=step.command,
            stage=step.stage,
            event_id=_uid(trial_id, f"event/setup/{step.name}"),
            command_artifact_id=_uid(trial_id, f"artifact/command/{step.name}"),
            reduction_artifact_id=_uid(trial_id, f"artifact/reduction/{step.name}"),
            committed_at=step.command.occurred_at,
            request_idempotency_key=f"turn-eval:{trial_id}:{step.name}",
        )

    async with uow_factory() as uow:
        state_before = await uow.sessions.get(
            tenant_id=ids.tenant_id, session_id=ids.session_id
        )
    state_before_hash = canonical_hash(state_before)

    outcome = await execute_turn_interpret(
        uow_factory,
        tenant_id=ids.tenant_id,
        run_id=ids.run_id,
        session_id=ids.session_id,
        employee_turn_id=turn_uuid(trial_id, inputs.case.target_turn_key),
        operation_id=ids.operation_id,
        idempotency_key=f"turn-eval:{trial_id}:turn-interpret",
        llm=llm,
        profile=profile,
        started_at=trial_started_at,
        now=trial_started_at,
        contains_test_data=True,
    )
    if outcome.status == TurnExecutionStatus.PENDING:
        raise RuntimeError(
            "trial reached a pending checkpoint; deadline recovery belongs to the"
            " batch scheduler"
        )

    checkpoint = outcome.checkpoint
    root_artifacts = tuple(
        ref
        for ref in (
            checkpoint.request_artifact,
            checkpoint.provider_result_artifact,
            checkpoint.verification_artifact,
            checkpoint.domain_result_artifact,
            checkpoint.response_artifact,
            outcome.response_artifact,
        )
        if ref is not None
    )
    # 去重(committed outcome 的 response_artifact 與 checkpoint 相同)
    unique_roots: list[ArtifactRef] = []
    for ref in root_artifacts:
        if ref not in unique_roots:
            unique_roots.append(ref)

    completed_at = checkpoint.updated_at + timedelta(seconds=1)
    final_status = (
        RunStatus.COMPLETED
        if outcome.status == TurnExecutionStatus.COMMITTED
        else RunStatus.FAILED
    )
    event_status = (
        ExecutionStatus.OK
        if final_status == RunStatus.COMPLETED
        else ExecutionStatus.FAILED
    )
    limitations = ()
    if outcome.status == TurnExecutionStatus.FAILED:
        limitations = (f"turn-eval trial failed: {outcome.reason_code}",)
    async with uow_factory() as uow:
        finalized, manifest_ref = await uow.capture.finalize_run(
            tenant_id=ids.tenant_id,
            run_id=ids.run_id,
            final_status=final_status,
            terminal_event_id=_uid(trial_id, "event/run-terminal"),
            manifest_artifact_id=_uid(trial_id, "artifact/run-manifest"),
            completed_at=completed_at,
            root_artifacts=tuple(unique_roots),
            limitations=limitations,
            event_status=event_status,
        )
        await uow.commit()

    async with uow_factory() as uow:
        state_after = await uow.sessions.get(
            tenant_id=ids.tenant_id, session_id=ids.session_id
        )
    return TrialExecution(
        ids=ids,
        outcome=outcome,
        run=finalized,
        manifest_ref=manifest_ref,
        state_before=state_before,
        state_before_hash=state_before_hash,
        state_after=state_after,
        state_after_hash=canonical_hash(state_after),
        setup_command_count=len(steps),
    )


async def cleanup_trial_rows(
    session_factory: async_sessionmaker, ids_list: list[TrialScopedIds]
) -> None:
    """Tenant-scoped cleanup(§17.3):只刪 trial 派生 tenant 的列;
    先斷開 circular FK pointers,再依 FK 反向順序逐表刪除;禁止 TRUNCATE。"""

    reverse_tables = (
        "interview_vnext_operation_attempts",
        "interview_vnext_operation_checkpoints",
        "interview_vnext_outbox",
        "interview_vnext_execution_events",
        "interview_vnext_commands",
        "interview_vnext_artifacts",
        "interview_vnext_runs",
        "interview_vnext_sessions",
    )
    async with session_factory() as session:
        rows = await session.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name LIKE 'interview_vnext_%'"
            )
        )
        existing = {name for (name,) in rows.all()}
        for ids in ids_list:
            params = {"tenant_id": str(ids.tenant_id)}
            if "interview_vnext_runs" in existing:
                await session.execute(
                    sa.text(
                        "UPDATE interview_vnext_runs SET manifest_artifact_id = NULL "
                        "WHERE tenant_id = :tenant_id"
                    ),
                    params,
                )
            if "interview_vnext_sessions" in existing:
                await session.execute(
                    sa.text(
                        "UPDATE interview_vnext_sessions "
                        "SET initial_state_artifact_id = NULL "
                        "WHERE tenant_id = :tenant_id"
                    ),
                    params,
                )
            for table in reverse_tables:
                if table in existing:
                    await session.execute(
                        sa.text(
                            f"DELETE FROM {table} WHERE tenant_id = :tenant_id"  # noqa: S608
                        ),
                        params,
                    )
            await session.execute(
                sa.text("DELETE FROM job_profiles WHERE id = :profile_id"),
                {"profile_id": str(ids.profile_id)},
            )
            await session.execute(
                sa.text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": str(ids.user_id)},
            )
        await session.commit()
