"""Crash recovery — pure decision over committed checkpoints (V2-B reference §9).

Recovery 掃描的是 committed checkpoint/attempt rows,不是記憶體 agent state,
更不是「最後一則聊天文字」。``decide_recovery`` 是純函式;coordinator 每次
`step()` 只執行**一個** decision/transaction,執行後重讀重判,絕不在一個超長
transaction 跑完整 workflow。需要 network 的 executor(reconcile/新 attempt 的
provider call)必須先讓 DB transaction 結束,network 後另開 transaction 記結果。

Durable 事實與 retryable:``record_attempt_result`` 在同一 transaction 寫
attempt row 與 checkpoint 轉換,因此 crash 後「calling + result_recorded」的
組合**只可能**來自 retryable 結果(succeeded/non-retryable 會在同 transaction
轉走)。呼叫端仍可用 ``last_result_retryable=False`` 顯式覆寫(防禦 §9 表列的
non-retryable row)。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.interview_vnext.observability.checkpoint import (
    CheckpointStatus,
    OperationCheckpoint,
)
from app.interview_vnext.persistence.errors import (
    CheckpointConflict,
    PersistedDataCorruption,
)

from .persistence import AttemptStatus, OperationAttempt, VNextUnitOfWork


class RecoveryAction(StrEnum):
    START_ATTEMPT = "start_attempt"
    WAIT_FOR_DEADLINE = "wait_for_deadline"
    RECONCILE_PROVIDER = "reconcile_provider"
    RECORD_LOST_AND_RETRY = "record_lost_and_retry"
    MARK_FAILED = "mark_failed"
    VERIFY_EXISTING_RESULT = "verify_existing_result"
    COMMIT_VERIFIED_RESULT = "commit_verified_result"
    RETURN_COMMITTED = "return_committed"
    RETURN_FAILED = "return_failed"


# 這些 action 在 §9 保證**不得**再打 provider generate
NO_PROVIDER_CALL_ACTIONS = frozenset({
    RecoveryAction.WAIT_FOR_DEADLINE,
    RecoveryAction.VERIFY_EXISTING_RESULT,
    RecoveryAction.COMMIT_VERIFIED_RESULT,
    RecoveryAction.RETURN_COMMITTED,
    RecoveryAction.RETURN_FAILED,
    RecoveryAction.MARK_FAILED,
})


@dataclass(frozen=True)
class RecoveryContext:
    checkpoint: OperationCheckpoint
    active_attempt: OperationAttempt | None


async def load_recovery_context(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    operation_id: UUID,
) -> RecoveryContext:
    """讀 committed rows(fresh session;讀完即釋放 transaction)。"""
    async with uow_factory() as uow:
        checkpoint = await uow.checkpoints.get_by_operation(
            tenant_id=tenant_id, operation_id=operation_id)
        if checkpoint is None:
            raise CheckpointConflict("operation checkpoint does not exist",
                                     tenant_id=tenant_id, operation_id=operation_id)
        attempt = None
        if checkpoint.active_attempt_id is not None:
            attempt = await uow.attempts.get(
                tenant_id=tenant_id, attempt_id=checkpoint.active_attempt_id)
            if attempt is None:
                raise PersistedDataCorruption(
                    "checkpoint references a missing attempt row",
                    operation_id=operation_id,
                    attempt_id=checkpoint.active_attempt_id)
        await uow.rollback()
    return RecoveryContext(checkpoint=checkpoint, active_attempt=attempt)


def decide_recovery(
    context: RecoveryContext,
    *,
    now: datetime,
    max_attempts: int,
    provider_supports_reconcile: bool = False,
    last_result_retryable: bool | None = None,
) -> RecoveryAction:
    """§9 decision table 的純函式版;不做 I/O、不猜記憶體狀態。"""
    checkpoint, attempt = context.checkpoint, context.active_attempt

    if checkpoint.status == CheckpointStatus.PREPARED:
        return RecoveryAction.START_ATTEMPT
    if checkpoint.status == CheckpointStatus.PROVIDER_COMPLETED:
        return RecoveryAction.VERIFY_EXISTING_RESULT
    if checkpoint.status == CheckpointStatus.VERIFIED:
        return RecoveryAction.COMMIT_VERIFIED_RESULT
    if checkpoint.status == CheckpointStatus.COMMITTED:
        return RecoveryAction.RETURN_COMMITTED
    if checkpoint.status == CheckpointStatus.FAILED:
        return RecoveryAction.RETURN_FAILED

    assert checkpoint.status == CheckpointStatus.CALLING
    if attempt is None:
        raise PersistedDataCorruption(
            "calling checkpoint requires an active attempt row",
            operation_id=checkpoint.operation_id)

    if attempt.status == AttemptStatus.RESULT_RECORDED:
        retryable = True if last_result_retryable is None else last_result_retryable
        if not retryable:
            return RecoveryAction.MARK_FAILED
        return (RecoveryAction.START_ATTEMPT
                if attempt.attempt < max_attempts
                else RecoveryAction.MARK_FAILED)

    # attempt 仍 in flight:結果未知
    if attempt.provider_execution_ref is not None and provider_supports_reconcile:
        return RecoveryAction.RECONCILE_PROVIDER
    if now < attempt.deadline_at:
        return RecoveryAction.WAIT_FOR_DEADLINE
    return (RecoveryAction.RECORD_LOST_AND_RETRY
            if attempt.attempt < max_attempts
            else RecoveryAction.MARK_FAILED)


RecoveryExecutor = Callable[[RecoveryContext], Awaitable[None]]


class RecoveryCoordinator:
    """一次執行一個 decision/transaction 後返回;呼叫端迴圈驅動直到 terminal。
    executors 由組裝端注入(START_ATTEMPT 之後的 provider call、verification
    的 semantic verifier 都住在 executor 內、且必在 DB transaction 之外)。
    未註冊 executor 的 action 只回報不執行(WAIT/RETURN_* 天然如此)。"""

    def __init__(
        self,
        uow_factory: Callable[[], VNextUnitOfWork],
        *,
        tenant_id: UUID,
        max_attempts: int,
        executors: Mapping[RecoveryAction, RecoveryExecutor],
        provider_supports_reconcile: bool = False,
    ) -> None:
        self._uow_factory = uow_factory
        self._tenant_id = tenant_id
        self._max_attempts = max_attempts
        self._executors = dict(executors)
        self._reconcile = provider_supports_reconcile

    async def step(self, *, operation_id: UUID, now: datetime,
                   last_result_retryable: bool | None = None) -> RecoveryAction:
        context = await load_recovery_context(
            self._uow_factory, tenant_id=self._tenant_id, operation_id=operation_id)
        action = decide_recovery(
            context, now=now, max_attempts=self._max_attempts,
            provider_supports_reconcile=self._reconcile,
            last_result_retryable=last_result_retryable)
        executor = self._executors.get(action)
        if executor is not None:
            await executor(context)
        return action
