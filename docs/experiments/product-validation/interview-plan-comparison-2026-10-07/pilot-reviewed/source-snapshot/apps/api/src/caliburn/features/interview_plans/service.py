"""Plan operations join the caller's qualified short transaction."""

import hashlib
import json
from uuid import UUID, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interview_plans import persistence
from caliburn.features.interview_plans.models import (
    PlanConflictError,
    PlanEdit,
    PlanEditResult,
    PlanPosition,
    PlanSnapshot,
    PlanStateError,
    QualifiedPlanTurn,
    StalePlanPositionError,
)


async def start_candidate(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, base: str | None
) -> PlanSnapshot:
    """Capture a full nullable baseline once; reentry always returns its start operation."""
    existing = await read_base(session, job_file_id, execution_id)
    if existing is not None:
        return existing
    operation = persistence.PlanOperationRecord(
        job_file_id=job_file_id,
        execution_id=execution_id,
        operation_id=uuid5(execution_id, "interview_plan.start"),
        kind="start",
        expected_revision_id=None,
        revision_id=uuid4(),
        body=base,
        intent_digest=None,
        result_text=None,
    )
    session.add(operation)
    await session.flush()
    session.add(
        persistence.PlanCandidateRecord(
            job_file_id=job_file_id,
            execution_id=execution_id,
            base_revision_id=operation.revision_id,
            current_revision_id=operation.revision_id,
        )
    )
    await session.flush()
    return _snapshot(operation)


async def read_base(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> PlanSnapshot | None:
    """Read the fixed initial body, independently of the current candidate head."""
    candidate = await persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None:
        return None
    operation = await _require_revision(
        session, job_file_id, execution_id, candidate.base_revision_id
    )
    if operation.kind != "start":
        raise PlanStateError("The plan base does not address its original start")
    return _snapshot(operation)


async def read_current(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> PlanSnapshot | None:
    candidate = await persistence.read_candidate(session, job_file_id, execution_id)
    if candidate is None:
        return None
    operation = await _require_revision(
        session, job_file_id, execution_id, candidate.current_revision_id
    )
    return _snapshot(operation)


async def read_qualified_plan(
    session: AsyncSession, job_file_id: UUID, qualified_turns: tuple[QualifiedPlanTurn, ...]
) -> PlanSnapshot | None:
    operation = await persistence.read_qualified_operation(session, job_file_id, qualified_turns)
    return _snapshot(operation) if operation is not None else None


async def apply_prepared(session: AsyncSession, edit: PlanEdit) -> PlanEditResult:
    """Commit a prepared full effect or recover its exact original result without rewinding head.

    The workflow holds the file and active writer locks. This owner never reapplies the patch,
    regenerates its observation, uses new limits, or commits the caller's transaction.
    """
    position = edit.position
    recovered = await recover_prepared(session, edit)
    if recovered is not None:
        return recovered
    candidate = await persistence.read_candidate(
        session, position.job_file_id, position.execution_id
    )
    if candidate is None:
        raise PlanStateError("No plan candidate belongs to this Turn")
    digest = _intent_digest(edit)
    if candidate.current_revision_id != position.revision_id:
        raise StalePlanPositionError("The plan candidate has advanced past the expected revision")
    await _require_revision(
        session, position.job_file_id, position.execution_id, position.revision_id
    )
    operation = persistence.PlanOperationRecord(
        job_file_id=position.job_file_id,
        execution_id=position.execution_id,
        operation_id=edit.operation_id,
        kind="apply",
        expected_revision_id=position.revision_id,
        revision_id=uuid4(),
        body=edit.next_plan,
        intent_digest=digest,
        result_text=edit.result_text,
    )
    session.add(operation)
    await session.flush()
    candidate.current_revision_id = operation.revision_id
    await session.flush()
    return PlanEditResult(_snapshot(operation), edit.result_text)


async def recover_prepared(session: AsyncSession, edit: PlanEdit) -> PlanEditResult | None:
    """Recover only a retained exact original operation; this narrow path never creates effects."""
    position = edit.position
    original = await persistence.read_operation(session, position.job_file_id, edit.operation_id)
    if original is None:
        return None
    if (
        original.kind != "apply"
        or original.execution_id != position.execution_id
        or original.expected_revision_id != position.revision_id
        or original.intent_digest != _intent_digest(edit)
        or original.body != edit.next_plan
        or original.result_text != edit.result_text
    ):
        raise PlanConflictError("The operation identity already belongs to another plan intent")
    if (
        await persistence.read_candidate(session, position.job_file_id, position.execution_id)
        is None
    ):
        raise PlanStateError("The original plan candidate is unavailable")
    await _require_revision(
        session, position.job_file_id, position.execution_id, position.revision_id
    )
    if original.result_text is None:
        raise PlanStateError("The original plan result is unavailable")
    return PlanEditResult(_snapshot(original), original.result_text)


async def validate_final(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    position: PlanPosition | None,
) -> None:
    """Check the supplied final head in the settlement transaction, including completed replay.

    Old capability has no candidate and passes None; new capability's caller must separately
    require its saved root. Existing candidates can never be skipped by passing None.
    """
    current = await read_current(session, job_file_id, execution_id)
    if current is None and position is None:
        return
    if current is None or position is None:
        raise PlanStateError("Completion requires this Turn's saved final plan position")
    if (position.job_file_id, position.execution_id) != (job_file_id, execution_id):
        raise PlanStateError("The final plan belongs to another Turn")
    if current.position != position:
        raise StalePlanPositionError("The supplied final plan is not this Turn's saved head")


def _intent_digest(edit: PlanEdit) -> str:
    # Version 1 is a retained command contract, independent of later result serializers.
    payload = {
        "version": 1,
        "kind": "apply",
        "job_file_id": str(edit.position.job_file_id),
        "execution_id": str(edit.position.execution_id),
        "expected_revision_id": str(edit.position.revision_id),
        "diff": edit.diff,
        "next_plan": edit.next_plan,
        "result_text": edit.result_text,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


async def _require_revision(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID, revision_id: UUID
) -> persistence.PlanOperationRecord:
    operation = await persistence.read_revision(session, job_file_id, execution_id, revision_id)
    if operation is None:
        raise PlanStateError("The saved plan position is unavailable")
    return operation


def _snapshot(operation: persistence.PlanOperationRecord) -> PlanSnapshot:
    return PlanSnapshot(
        PlanPosition(operation.job_file_id, operation.execution_id, operation.revision_id),
        operation.body,
    )
