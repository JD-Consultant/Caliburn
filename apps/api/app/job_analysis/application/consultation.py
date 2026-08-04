"""One synchronous, durable consultant turn with provider-before-replay."""

from __future__ import annotations

from uuid import UUID

from app.job_analysis.providers import OpenRouterAdapter

from .context import ConversationTurn
from .durable_turn import commit_verified_turn, prepare_turn
from .errors import IdempotencyConflict
from .operation import run_task_analysis_operation
from .persistence import (
    CompletedTurnPayload,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
)
from .verifier import TurnSpeaker


def _employee_turn(operation_id: str, text: str) -> ConversationTurn:
    return ConversationTurn(
        turn_id=f"{operation_id}-employee",
        speaker=TurnSpeaker.EMPLOYEE,
        text=text,
    )


def _require_same_employee_replay(
    entry: JournalEntry,
    *,
    operation_id: str,
    employee_turn: ConversationTurn,
) -> None:
    if entry.kind != "employee_turn" or not isinstance(
        entry.payload, CompletedTurnPayload
    ):
        raise IdempotencyConflict(
            f"entry {operation_id!r} already belongs to another operation"
        )
    if (
        entry.payload.operation_id != operation_id
        or entry.payload.employee_turn != employee_turn
    ):
        raise IdempotencyConflict(
            f"operation {operation_id!r} was replayed with different employee text"
        )


async def _is_committed_replay(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    operation_id: str,
    employee_turn: ConversationTurn,
) -> bool:
    async with uow_factory() as uow:
        existing = await uow.journal.get(document_id, operation_id)
        if existing is None:
            return False
        _require_same_employee_replay(
            existing,
            operation_id=operation_id,
            employee_turn=employee_turn,
        )
        return True


async def submit_employee_turn(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    operation_id: str,
    text: str,
) -> None:
    """Run at most one provider call for a not-yet-committed sequential request.

    This intentionally does not deduplicate two requests that are already in flight.
    The local Web disables duplicate submission while its mutation is pending.
    """

    employee_turn = _employee_turn(operation_id, text)
    if await _is_committed_replay(
        uow_factory,
        document_id=document_id,
        operation_id=operation_id,
        employee_turn=employee_turn,
    ):
        return
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee_turn,
    )
    operation_result = await run_task_analysis_operation(
        packet=snapshot.packet,
        adapter=adapter,
    )
    await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id=operation_id,
        employee_turn=employee_turn,
        operation_result=operation_result,
    )
