"""Atomic domain-command commit use case (V2-B reference §7.3).

固定順序,同一 transaction:duplicate 檢查 → hydrate committed state → pure
reducer → command/reduction artifacts → command row → session CAS →
``state.transition.accepted`` event + outbox → commit。CAS 0 rows 或 unique
violation 時整筆 rollback,再用**新 transaction**分辨 duplicate(回既有
reduction)或 stale(``StateVersionConflict``)。

Reducer dispatch 是顯式 command type 對照表;未知型別 hard fail,不用反射猜。
Caller 不得自行產生 result state——use case 一律 load current state 再跑
registered pure reducer。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from uuid import UUID

from app.interview_vnext.domain.commands import (
    ApplyCandidateProposalsCommand,
    ApplyGapProposalsCommand,
    ApplyInferenceProposalsCommand,
    ApplyReviewDecisionCommand,
    ApplyTurnInterpretationCommand,
    AppendConsultantQuestionCommand,
    AppendEmployeeTurnCommand,
    CommandBase,
    DecideInferenceCommand,
    InvalidateQuestionFrameCommand,
    OpenEpisodeCommand,
    SupersedeInferenceCommand,
    TransitionCandidateCommand,
    TransitionEpisodeCommand,
    TransitionGapCommand,
    TransitionSessionCommand,
    WithdrawEvidenceCommand,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.reducers import (
    ReductionResult,
    append_consultant_question,
    append_employee_turn,
    apply_candidate_proposals,
    apply_gap_proposals,
    apply_inference_proposals,
    apply_review_decision,
    apply_turn_interpretation,
    decide_inference,
    invalidate_question_frame,
    open_episode,
    supersede_inference,
    transition_candidate,
    transition_episode,
    transition_gap,
    transition_session,
    withdraw_evidence,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.events import ExecutionStatus
from app.interview_vnext.persistence.errors import (
    IdempotencyConflict,
    PersistedDataCorruption,
    StateVersionConflict,
)

from .persistence import (
    CommandRecord,
    ExecutionEventDraft,
    VNextUnitOfWork,
)

_SCHEMA_BASE = "https://caliburn.local/schemas"

# 顯式 command → (committed schema $id, pure reducer)。未知型別 hard fail。
_COMMAND_BINDINGS: dict[type[CommandBase], tuple[str, Callable]] = {
    TransitionSessionCommand:
        (f"{_SCHEMA_BASE}/transition-session-command.v1.schema.json", transition_session),
    AppendConsultantQuestionCommand:
        (f"{_SCHEMA_BASE}/append-consultant-question-command.v1.schema.json",
         append_consultant_question),
    AppendEmployeeTurnCommand:
        (f"{_SCHEMA_BASE}/append-employee-turn-command.v1.schema.json",
         append_employee_turn),
    InvalidateQuestionFrameCommand:
        (f"{_SCHEMA_BASE}/invalidate-question-frame-command.v1.schema.json",
         invalidate_question_frame),
    ApplyTurnInterpretationCommand:
        (f"{_SCHEMA_BASE}/apply-turn-interpretation-command.v1.schema.json",
         apply_turn_interpretation),
    WithdrawEvidenceCommand:
        (f"{_SCHEMA_BASE}/withdraw-evidence-command.v1.schema.json", withdraw_evidence),
    OpenEpisodeCommand:
        (f"{_SCHEMA_BASE}/open-episode-command.v1.schema.json", open_episode),
    TransitionEpisodeCommand:
        (f"{_SCHEMA_BASE}/transition-episode-command.v1.schema.json", transition_episode),
    ApplyGapProposalsCommand:
        (f"{_SCHEMA_BASE}/apply-gap-proposals-command.v1.schema.json",
         apply_gap_proposals),
    TransitionGapCommand:
        (f"{_SCHEMA_BASE}/transition-gap-command.v1.schema.json", transition_gap),
    ApplyInferenceProposalsCommand:
        (f"{_SCHEMA_BASE}/apply-inference-proposals-command.v1.schema.json",
         apply_inference_proposals),
    DecideInferenceCommand:
        (f"{_SCHEMA_BASE}/decide-inference-command.v1.schema.json", decide_inference),
    SupersedeInferenceCommand:
        (f"{_SCHEMA_BASE}/supersede-inference-command.v1.schema.json",
         supersede_inference),
    ApplyCandidateProposalsCommand:
        (f"{_SCHEMA_BASE}/apply-candidate-proposals-command.v1.schema.json",
         apply_candidate_proposals),
    TransitionCandidateCommand:
        (f"{_SCHEMA_BASE}/transition-candidate-command.v1.schema.json",
         transition_candidate),
    ApplyReviewDecisionCommand:
        (f"{_SCHEMA_BASE}/apply-review-decision-command.v1.schema.json",
         apply_review_decision),
}

REDUCTION_RESULT_SCHEMA_ID = f"{_SCHEMA_BASE}/reduction-result.v2.schema.json"
INTERVIEW_STATE_SCHEMA_ID = f"{_SCHEMA_BASE}/interview-state.v3.schema.json"


def _artifact_kinds(command: CommandBase) -> tuple[str, str]:
    """Use the active interpreter closure kinds without changing generic commands."""

    if isinstance(command, ApplyTurnInterpretationCommand):
        return (
            "interview.apply_turn_interpretation_command.v1",
            "interview.reduction_result.v2",
        )
    return "domain.command", "domain.reduction_result"


@dataclass(frozen=True)
class DurableCommandOutcome:
    result: ReductionResult
    record: CommandRecord
    replayed: bool


def _binding(command: CommandBase) -> tuple[str, Callable]:
    try:
        return _COMMAND_BINDINGS[type(command)]
    except KeyError:
        raise TypeError(
            f"no registered reducer/schema for command type {type(command).__name__}"
        ) from None


async def _replay(uow: VNextUnitOfWork, *, tenant_id: UUID,
                  record: CommandRecord, command_hash: str) -> DurableCommandOutcome:
    if record.command_hash != command_hash:
        raise IdempotencyConflict(
            "command id/request key already used with a different payload",
            command_id=record.command_id)
    artifact = await uow.artifacts.get(tenant_id=tenant_id,
                                       artifact_id=record.reduction_artifact_id)
    try:
        result = ReductionResult.model_validate_json(artifact.inline_content or "")
    except Exception as exc:  # noqa: BLE001
        raise PersistedDataCorruption(
            "stored reduction artifact failed validation",
            command_id=record.command_id,
            artifact_id=record.reduction_artifact_id) from exc
    return DurableCommandOutcome(result=result, record=record, replayed=True)


async def _find_existing(uow: VNextUnitOfWork, *, tenant_id: UUID, session_id: UUID,
                         command: CommandBase,
                         request_idempotency_key: str | None) -> CommandRecord | None:
    record = await uow.commands.get_by_command_id(
        tenant_id=tenant_id, session_id=session_id, command_id=command.command_id)
    if record is None and request_idempotency_key is not None:
        record = await uow.commands.get_by_request_key(
            tenant_id=tenant_id, session_id=session_id,
            request_idempotency_key=request_idempotency_key)
    return record


async def _commit_command_core(
    uow: VNextUnitOfWork,
    *,
    tenant_id: UUID,
    session_id: UUID,
    run_id: UUID,
    command: CommandBase,
    stage: str,
    event_id: UUID,
    command_artifact_id: UUID,
    reduction_artifact_id: UUID,
    committed_at: datetime,
    request_idempotency_key: str | None,
    turn_id: UUID | None = None,
    operation_id: UUID | None = None,
    contains_test_data: bool = False,
):
    """§7.3 steps ①½–⑦(caller 已做 dup 快查、之後負責 commit/分類)。
    回傳 (result, record, command_ref, reduction_ref);CAS 0 rows 時已
    rollback 並回 None;reducer 判 idempotent 時回 DurableCommandOutcome(replay)。
    供 apply_durable_command 與 commit_verified_operation(§7.8)共用。"""
    command_schema_id, reducer = _binding(command)
    command_artifact_kind, reduction_artifact_kind = _artifact_kinds(command)
    command_hash = canonical_hash(command)

    # ①½ 先鎖 run row:一致鎖序(run → session/artifacts)。不先鎖的話,
    #    兩個併發 command 的 artifact/command insert 會各持 FK KEY SHARE,
    #    與對方的 session CAS / append 的 FOR UPDATE 互等 → deadlock。
    await uow.runs.lock(tenant_id=tenant_id, run_id=run_id)

    # ②(§5.1)第一個 command 前必須已有 version-0 snapshot pointer
    pointer = await uow.sessions.initial_state_artifact_id(
        tenant_id=tenant_id, session_id=session_id)
    if pointer is None:
        raise PersistedDataCorruption(
            "session has no initial-state snapshot; create_run must precede commands",
            tenant_id=tenant_id, session_id=session_id)

    # ② hydrate committed state(row/nested dual check 在 repository)
    state: InterviewState = await uow.sessions.get(
        tenant_id=tenant_id, session_id=session_id)

    # ③ pure reducer(transaction 內,無 I/O;DomainViolation 原樣往外)
    result: ReductionResult = reducer(state, command)
    if result.idempotent:
        # 等 run 鎖期間同 command 已被別的 transaction commit(合法 race)→
        # 查 record 走 replay;state 說處理過但 record 不存在才是 corruption。
        raced = await uow.commands.get_by_command_id(
            tenant_id=tenant_id, session_id=session_id,
            command_id=command.command_id)
        if raced is not None:
            return await _replay(uow, tenant_id=tenant_id, record=raced,
                                 command_hash=command_hash)
        raise PersistedDataCorruption(
            "state lists command as processed but no command record exists",
            command_id=command.command_id, session_id=session_id)

    # ④ immutable artifacts(command + reduction)
    command_artifact = await uow.artifacts.put(
        tenant_id=tenant_id,
        record=build_inline_artifact(
            artifact_id=command_artifact_id, kind=command_artifact_kind,
            media_type="application/json", payload=command,
            schema_id=command_schema_id, run_id=run_id, session_id=session_id,
            turn_id=turn_id, operation_id=operation_id,
            created_at=committed_at, contains_test_data=contains_test_data))
    reduction_artifact = await uow.artifacts.put(
        tenant_id=tenant_id,
        record=build_inline_artifact(
            artifact_id=reduction_artifact_id, kind=reduction_artifact_kind,
            media_type="application/json", payload=result,
            schema_id=REDUCTION_RESULT_SCHEMA_ID, run_id=run_id,
            session_id=session_id, turn_id=turn_id, operation_id=operation_id,
            created_at=committed_at, contains_test_data=contains_test_data))

    # ⑤ command row
    record = CommandRecord(
        command_id=command.command_id, session_id=session_id, run_id=run_id,
        request_idempotency_key=request_idempotency_key,
        command_schema_id=command_schema_id,
        command_artifact_id=command_artifact.ref.artifact_id,
        command_hash=command_artifact.ref.content_hash,
        reduction_artifact_id=reduction_artifact.ref.artifact_id,
        reduction_hash=reduction_artifact.ref.content_hash,
        expected_state_version=command.expected_state_version,
        result_state_version=result.state.session.state_version,
        result_state_hash=result.state_hash,
        result_reason_code=result.reason_code.value,
        occurred_at=command.occurred_at, committed_at=committed_at)
    await uow.commands.add(tenant_id=tenant_id, record=record)

    # ⑥ session CAS(0 rows → 整筆 rollback,caller 用新 transaction 分類)
    updated = await uow.sessions.save_cas(
        tenant_id=tenant_id, old_version=command.expected_state_version,
        new_state=result.state)
    if not updated:
        await uow.rollback()
        return None

    # ⑦ state.transition.accepted event + outbox(同 transaction)
    await uow.capture.append_event(
        tenant_id=tenant_id, run_id=run_id,
        draft=ExecutionEventDraft(
            event_id=event_id, occurred_at=command.occurred_at,
            session_id=session_id, event_type="state.transition.accepted",
            stage=stage, status=ExecutionStatus.OK,
            input_artifacts=(command_artifact.ref,),
            output_artifacts=(reduction_artifact.ref,),
            state_before_hash=canonical_hash(state),
            state_after_hash=result.state_hash))
    return result, record, command_artifact.ref, reduction_artifact.ref


async def apply_durable_command(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    session_id: UUID,
    run_id: UUID,
    command: CommandBase,
    stage: str,
    event_id: UUID,
    command_artifact_id: UUID,
    reduction_artifact_id: UUID,
    committed_at: datetime,
    request_idempotency_key: str | None = None,
) -> DurableCommandOutcome:
    command_hash = canonical_hash(command)

    async with uow_factory() as uow:
        # ① duplicate(command id / request key)
        existing = await _find_existing(uow, tenant_id=tenant_id, session_id=session_id,
                                        command=command,
                                        request_idempotency_key=request_idempotency_key)
        if existing is not None:
            return await _replay(uow, tenant_id=tenant_id, record=existing,
                                 command_hash=command_hash)

        # unique violation 可能在 flush(core 內)或 commit 才爆;都轉去分類
        try:
            core = await _commit_command_core(
                uow, tenant_id=tenant_id, session_id=session_id, run_id=run_id,
                command=command, stage=stage, event_id=event_id,
                command_artifact_id=command_artifact_id,
                reduction_artifact_id=reduction_artifact_id,
                committed_at=committed_at,
                request_idempotency_key=request_idempotency_key)
            if isinstance(core, DurableCommandOutcome):
                return core                # run-lock 等待期間的 duplicate race
            if core is not None:
                result, record, _command_ref, _reduction_ref = core
                await uow.commit()
                return DurableCommandOutcome(result=result, record=record,
                                             replayed=False)
        except IdempotencyConflict:
            pass                           # concurrent duplicate;新 transaction 分辨

    # CAS 0 rows / duplicate race:**新 transaction** 分辨 duplicate 或 stale(§7.3)
    async with uow_factory() as uow:
        existing = await _find_existing(uow, tenant_id=tenant_id, session_id=session_id,
                                        command=command,
                                        request_idempotency_key=request_idempotency_key)
        if existing is not None:
            return await _replay(uow, tenant_id=tenant_id, record=existing,
                                 command_hash=command_hash)
    raise StateVersionConflict(
        "session state version moved past the command expectation",
        tenant_id=tenant_id, session_id=session_id,
        command_id=command.command_id,
        expected_state_version=command.expected_state_version)
