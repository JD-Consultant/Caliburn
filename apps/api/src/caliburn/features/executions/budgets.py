"""Reserve outbound work in a short transaction, independently of model result adoption."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import budget_persistence as storage
from caliburn.features.executions import persistence, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
    BudgetUsage,
    ExecutionBudget,
    OutboundAdmission,
    OutboundAttempt,
    OutboundFailure,
    OutboundKind,
    OutboundRequest,
    validate_cost,
)
from caliburn.features.executions.models import (
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionWriter,
)


async def fix_execution_budget(
    session: AsyncSession, writer: ExecutionWriter, policy: ExecutionBudget
) -> ExecutionBudget:
    await service.lock_active_writer(session, writer)
    existing = await storage.read_budget(session, writer.scope.execution_id)
    if existing is not None:
        if _policy(existing) != policy:
            raise BudgetConflictError("The execution budget has already been fixed")
        return policy
    session.add(
        storage.ExecutionBudgetRecord(
            execution_id=writer.scope.execution_id,
            max_model_steps=policy.max_model_steps,
            max_compactions=policy.max_compactions,
            max_outbound_attempts=policy.max_outbound_attempts,
            max_attempts_per_request=policy.max_attempts_per_request,
            deadline_at=policy.deadline_at,
            max_cost_usd=policy.max_cost_usd,
            cost_basis=policy.cost_basis,
        )
    )
    await session.flush()
    return policy


async def reserve_outbound_attempt(
    session: AsyncSession,
    writer: ExecutionWriter,
    *,
    request: OutboundRequest,
    attempt_id: UUID,
    reserved_cost_usd: Decimal,
) -> OutboundAdmission:
    """Only a NEW, confirmed-committed admission permits one send.

    Re-entering this operation returns created=False, never permission to resend. On an
    uncertain commit the caller reconciles this identity. HTTP must be outside the transaction.
    """
    validate_cost(reserved_cost_usd, positive=True)
    await service.read_execution(session, writer.scope)
    existing = await storage.read_attempt(session, writer.scope.execution_id, attempt_id)
    if existing is not None:
        return _existing_admission(existing, request, reserved_cost_usd)
    await service.lock_active_writer(session, writer)
    existing = await storage.read_attempt(session, writer.scope.execution_id, attempt_id)
    if existing is not None:
        return _existing_admission(existing, request, reserved_cost_usd)
    await check_outbound_capacity(
        session, writer, request=request, reserved_cost_usd=reserved_cost_usd
    )
    record = storage.OutboundAttemptRecord(
        execution_id=writer.scope.execution_id,
        attempt_id=attempt_id,
        request_id=request.request_id,
        kind=request.kind.value,
        fingerprint=request.fingerprint,
        writer_id=writer.writer_id,
        reserved_cost_usd=reserved_cost_usd,
    )
    session.add(record)
    await session.flush()
    return OutboundAdmission(_attempt(record), created=True)


async def check_outbound_capacity(
    session: AsyncSession,
    writer: ExecutionWriter,
    *,
    request: OutboundRequest,
    reserved_cost_usd: Decimal,
) -> None:
    """Fail exhausted work before backoff; checking is NOT permission to send.

    Admission uses this same rule under the same execution lock. The workflow must still
    obtain a newly committed admission after any waiting; no separate budget validator.
    """
    validate_cost(reserved_cost_usd, positive=True)
    await service.lock_active_writer(session, writer)
    policy = await storage.read_budget(session, writer.scope.execution_id)
    if policy is None:
        raise BudgetConflictError("Fix the execution budget before outbound work")
    previous = await storage.read_request_attempts(
        session, writer.scope.execution_id, request.request_id
    )
    if any(
        record.kind != request.kind.value or record.fingerprint != request.fingerprint
        for record in previous
    ):
        raise BudgetConflictError("A logical request cannot change its payload or kind")
    usage = await storage.read_usage(session, writer.scope.execution_id)
    if await storage.current_time(session) >= policy.deadline_at:
        raise BudgetExceededError(BudgetLimit.DEADLINE)
    if usage.outbound_attempts >= policy.max_outbound_attempts:
        raise BudgetExceededError(BudgetLimit.OUTBOUND_ATTEMPTS)
    if len(previous) >= policy.max_attempts_per_request:
        raise BudgetExceededError(BudgetLimit.REQUEST_ATTEMPTS)
    if not previous:
        if request.kind == OutboundKind.MODEL and usage.model_steps >= policy.max_model_steps:
            raise BudgetExceededError(BudgetLimit.MODEL_STEPS)
        if request.kind == OutboundKind.COMPACTION and usage.compactions >= policy.max_compactions:
            raise BudgetExceededError(BudgetLimit.COMPACTIONS)
    if usage.accounted_cost_usd + reserved_cost_usd > policy.max_cost_usd:
        raise BudgetExceededError(BudgetLimit.COST)


async def read_budget_usage(session: AsyncSession, scope: ExecutionScope) -> BudgetUsage:
    await service.read_execution(session, scope)
    return await storage.read_usage(session, scope.execution_id)


async def read_execution_time(session: AsyncSession, scope: ExecutionScope) -> datetime:
    """Read the DB clock after scope validation; callers hold the lock for retry decisions."""
    await service.read_execution(session, scope)
    return await storage.current_time(session)


async def read_execution_budget(
    session: AsyncSession, scope: ExecutionScope
) -> ExecutionBudget | None:
    await service.read_execution(session, scope)
    record = await storage.read_budget(session, scope.execution_id)
    return _policy(record) if record is not None else None


async def read_outbound_attempt(
    session: AsyncSession, scope: ExecutionScope, attempt_id: UUID
) -> OutboundAttempt | None:
    await service.read_execution(session, scope)
    record = await storage.read_attempt(session, scope.execution_id, attempt_id)
    return _attempt(record) if record is not None else None


async def read_request_attempts(
    session: AsyncSession, scope: ExecutionScope, request_id: UUID
) -> tuple[OutboundAttempt, ...]:
    """Reconcile existing sends without granting a new outbound allowance."""
    await service.read_execution(session, scope)
    records = await storage.read_request_attempts(session, scope.execution_id, request_id)
    return tuple(_attempt(record) for record in records)


async def record_attempt_cost(
    session: AsyncSession, scope: ExecutionScope, attempt_id: UUID, *, cost_usd: Decimal
) -> OutboundAttempt:
    """Record known usage cost even after cancellation/replacement; this does not adopt R/C.

    No usage means keep the reservation. Only a verified cost (possibly above its estimate)
    may settle it. A reported zero is an explicit observation, never a default for errors.
    """
    validate_cost(cost_usd)
    if await persistence.read_execution(session, scope, lock=True) is None:
        raise ExecutionNotFoundError("Execution not found in the requested scope")
    record = await storage.read_attempt(session, scope.execution_id, attempt_id)
    if record is None:
        raise BudgetConflictError("Cannot account for an unknown outbound attempt")
    if record.reported_cost_usd is not None and record.reported_cost_usd != cost_usd:
        raise BudgetConflictError("An observed cost cannot be replaced")
    record.reported_cost_usd = cost_usd
    await session.flush()
    return _attempt(record)


async def record_attempt_failure(
    session: AsyncSession,
    scope: ExecutionScope,
    attempt_id: UUID,
    *,
    failure: OutboundFailure,
) -> OutboundAttempt:
    """Preserve an observed failure even after cancellation; never authorize another send.

    The caller supplies a classified code and any aware retry deadline. Failure alone does
    not release the cost reservation, and replay cannot replace or clear the original.
    """
    if await persistence.read_execution(session, scope, lock=True) is None:
        raise ExecutionNotFoundError("Execution not found in the requested scope")
    record = await storage.read_attempt(session, scope.execution_id, attempt_id)
    if record is None:
        raise BudgetConflictError("Cannot record failure for an unknown outbound attempt")
    original = _attempt(record)
    if original.failure is not None:
        if original.failure != failure:
            raise BudgetConflictError("An observed failure cannot be replaced")
        return original
    if record.reported_cost_usd is not None:
        raise BudgetConflictError("An accounted successful attempt cannot become a failure")
    record.failure_code = failure.failure_code
    record.retry_not_before = failure.retry_not_before
    await session.flush()
    return _attempt(record)


def _attempt(record: storage.OutboundAttemptRecord) -> OutboundAttempt:
    return OutboundAttempt(
        record.attempt_id,
        OutboundRequest(record.request_id, OutboundKind(record.kind), record.fingerprint),
        record.writer_id,
        record.reserved_cost_usd,
        record.reported_cost_usd,
        OutboundFailure(record.failure_code, record.retry_not_before)
        if record.failure_code is not None
        else None,
    )


def _existing_admission(
    record: storage.OutboundAttemptRecord, request: OutboundRequest, reserved_cost_usd: Decimal
) -> OutboundAdmission:
    if _attempt(record).request != request or record.reserved_cost_usd != reserved_cost_usd:
        raise BudgetConflictError(
            "Attempt identity cannot change its original request or reservation"
        )
    return OutboundAdmission(_attempt(record), created=False)


def _policy(record: storage.ExecutionBudgetRecord) -> ExecutionBudget:
    return ExecutionBudget(
        record.max_model_steps,
        record.max_compactions,
        record.max_outbound_attempts,
        record.max_attempts_per_request,
        record.deadline_at,
        record.max_cost_usd,
        record.cost_basis,
    )
