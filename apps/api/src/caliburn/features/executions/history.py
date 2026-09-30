"""Adopt context references under the existing execution owner in the caller transaction."""

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import history_persistence as storage
from caliburn.features.executions import persistence, service
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextBinding,
    ContextPosition,
    HistoryConflictError,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)


async def bind_context_history(
    session: AsyncSession, writer: ExecutionWriter, role: AgentRole
) -> ContextBinding:
    """Pin the role's adopted base once, including an explicitly empty base."""
    await service.lock_active_writer(session, writer)
    _require_role(writer.scope, role)
    record = await storage.read_binding(session, writer.scope, role)
    if record is None:
        head = await storage.lock_head(session, writer.scope.job_file_id, role)
        record = storage.ContextHistoryBindingRecord(
            job_file_id=writer.scope.job_file_id,
            execution_id=writer.scope.execution_id,
            role=role.value,
            base_thread_id=head.thread_id,
            base_checkpoint_id=head.checkpoint_id,
            base_kind=head.kind,
        )
        session.add(record)
        await session.flush()
    return _binding(record)


async def read_context_history(
    session: AsyncSession, scope: ExecutionScope, role: AgentRole
) -> ContextBinding | None:
    """Read a fixed binding without creating rows or refreshing its base."""
    await service.read_execution(session, scope)
    _require_role(scope, role)
    record = await storage.read_binding(session, scope, role)
    return _binding(record) if record is not None else None


async def read_adopted_context(
    session: AsyncSession, job_file_id: UUID, role: AgentRole
) -> ContextPosition | None:
    """Return only the adopted reference, never an arbitrary latest saver checkpoint."""
    if not isinstance(role, AgentRole):
        raise HistoryConflictError("Expected an agent role")
    record = await storage.read_head(session, job_file_id, role)
    return _head_position(record) if record is not None else None


async def read_previous_completed_execution(
    session: AsyncSession, scope: ExecutionScope, role: AgentRole
) -> ExecutionScope | None:
    """Follow this execution's fixed history ancestry through prepared-only windows.

    Reads no native context bodies and does not advance history. An unavailable
    reference is an error, never permission to substitute an empty initial baseline.
    """
    binding = await read_context_history(session, scope, role)
    if binding is None:
        raise HistoryConflictError("The current execution has no fixed context binding")
    position = binding.base
    visited: set[ContextPosition] = set()
    while position is not None:
        if position in visited:
            raise HistoryConflictError("The context ancestry contains a cycle")
        visited.add(position)
        origin = await storage.read_position_origin(session, scope.job_file_id, role, position)
        if origin is None:
            raise HistoryConflictError("A fixed context ancestor is unavailable")
        previous = ExecutionScope(scope.job_file_id, origin.execution_id, scope.kind)
        if position.kind == HistoryWindowKind.COMPLETED_WORK:
            if (
                await service.read_execution(session, previous)
            ).status != ExecutionStatus.COMPLETED:
                raise HistoryConflictError(
                    "A completed history reference lacks completed execution"
                )
            return previous
        position = _binding(origin).base
    return None


async def adopt_prepared_context(
    session: AsyncSession, writer: ExecutionWriter, role: AgentRole, position: ContextPosition
) -> ContextBinding:
    """Adopt an own pre-work window, or reuse the exact prepared base after cancellation.

    A reused prepared base may belong to an earlier execution; a different foreign reference
    is never eligible. The caller must verify the referenced native checkpoint is durable.
    """
    await service.lock_active_writer(session, writer)
    _require_role(writer.scope, role)
    record = await storage.read_binding(session, writer.scope, role)
    if record is None:
        raise HistoryConflictError("Bind the context history before adopting preparation")
    binding = _binding(record)
    if position.kind != HistoryWindowKind.PREPARED_HISTORY or (
        position != binding.base
        and position.thread_id
        != context_thread_id(writer.scope, role, HistoryWindowKind.PREPARED_HISTORY)
    ):
        raise HistoryConflictError("The prepared window does not belong to this role and execution")
    if binding.prepared is not None:
        if binding.prepared != position:
            raise HistoryConflictError("The prepared context has already been fixed")
        return binding
    head = await storage.lock_head(session, writer.scope.job_file_id, role)
    if _head_position(head) != binding.base:
        raise HistoryConflictError("The adopted context no longer matches the pinned base")
    head.thread_id = position.thread_id
    head.checkpoint_id = position.checkpoint_id
    head.kind = position.kind.value
    record.prepared_thread_id = position.thread_id
    record.prepared_checkpoint_id = position.checkpoint_id
    await session.flush()
    return _binding(record)


async def complete_context_histories(
    session: AsyncSession, writer: ExecutionWriter, positions: Mapping[AgentRole, ContextPosition]
) -> None:
    """Atomically adopt all role references and finish eligibility in the caller's transaction.

    The caller coordinates JD/interview/Memory effects in this SAME transaction. Native
    checkpoint existence and product completion are workflow responsibilities, not Graph END.
    """
    execution = await persistence.read_execution(session, writer.scope, lock=True)
    if execution is None:
        raise ExecutionNotFoundError("Execution not found in the requested scope")
    replay = execution.status == ExecutionStatus.COMPLETED
    if replay:
        # The existing owner still fences the writer on an ACK-loss replay.
        await service.finish_execution(session, writer, ExecutionStatus.COMPLETED)
    else:
        await service.lock_active_writer(session, writer)

    roles = _required_roles(writer.scope.kind)
    if set(positions) != set(roles) or any(not isinstance(role, AgentRole) for role in positions):
        raise HistoryConflictError("Completion requires exactly the execution's roles")
    records: dict[AgentRole, storage.ContextHistoryBindingRecord] = {}
    for role in roles:
        position = positions[role]
        if position.kind != HistoryWindowKind.COMPLETED_WORK or not _belongs_to_completed_role(
            writer.scope, role, position.thread_id
        ):
            raise HistoryConflictError(
                "The completed window does not belong to this execution role"
            )
        record = await storage.read_binding(session, writer.scope, role)
        if record is None or record.prepared_thread_id is None:
            raise HistoryConflictError(
                "Every role must have an adopted preparation before completion"
            )
        if replay and _binding(record).completed != position:
            raise HistoryConflictError("Completion replay must use the original context references")
        records[role] = record
    if replay:
        # A later execution may already have advanced the head; never touch it during replay.
        return

    heads: dict[AgentRole, storage.ContextHistoryHeadRecord] = {}
    for role in sorted(roles):
        head = await storage.lock_head(session, writer.scope.job_file_id, role)
        if _head_position(head) != _binding(records[role]).prepared:
            raise HistoryConflictError("The adopted head no longer matches this work's preparation")
        heads[role] = head
    # Check all references before changing anything. The owner rejects pause intent here,
    # under the same execution lock used by pause/cancel and writer replacement.
    await service.finish_execution(session, writer, ExecutionStatus.COMPLETED)
    for role in roles:
        position = positions[role]
        heads[role].thread_id = position.thread_id
        heads[role].checkpoint_id = position.checkpoint_id
        heads[role].kind = position.kind.value
        records[role].completed_thread_id = position.thread_id
        records[role].completed_checkpoint_id = position.checkpoint_id
    await session.flush()


def _belongs_to_completed_role(scope: ExecutionScope, role: AgentRole, thread_id: str) -> bool:
    """A uses its root; Memory may adopt a role's exact native stage window.

    The Memory parent separately proves that this is the completed current candidate
    stage. This owner checks execution/role ownership, not candidate business semantics.
    """
    root = context_thread_id(scope, role, HistoryWindowKind.COMPLETED_WORK)
    if thread_id == root:
        return True
    prefix = f"{root}:stage:"
    if scope.kind != ExecutionKind.MEMORY_BATCH or not thread_id.startswith(prefix):
        return False
    parts = thread_id.removeprefix(prefix).split(":")
    if len(parts) != 2:
        return False
    try:
        return all(str(UUID(value)) == value for value in parts)
    except ValueError:
        return False


def _required_roles(kind: ExecutionKind) -> tuple[AgentRole, ...]:
    if kind == ExecutionKind.CONSULTANT_TURN:
        return (AgentRole.JOB_CONSULTANT,)
    return (AgentRole.WORK_SITUATION_ANALYST, AgentRole.WORK_UNDERSTANDING_ANALYST)


def _require_role(scope: ExecutionScope, role: AgentRole) -> None:
    if not isinstance(role, AgentRole) or role not in _required_roles(scope.kind):
        raise HistoryConflictError("This role does not belong to the execution kind")


def _position(
    thread_id: str | None, checkpoint_id: str | None, kind: str | None
) -> ContextPosition | None:
    if thread_id is None:
        return None
    if checkpoint_id is None or kind is None:
        raise HistoryConflictError("The persisted context position is incomplete")
    return ContextPosition(thread_id, checkpoint_id, HistoryWindowKind(kind))


def _head_position(record: storage.ContextHistoryHeadRecord) -> ContextPosition | None:
    return _position(record.thread_id, record.checkpoint_id, record.kind)


def _binding(record: storage.ContextHistoryBindingRecord) -> ContextBinding:
    return ContextBinding(
        AgentRole(record.role),
        _position(record.base_thread_id, record.base_checkpoint_id, record.base_kind),
        _position(
            record.prepared_thread_id,
            record.prepared_checkpoint_id,
            HistoryWindowKind.PREPARED_HISTORY,
        ),
        _position(
            record.completed_thread_id,
            record.completed_checkpoint_id,
            HistoryWindowKind.COMPLETED_WORK,
        ),
    )
