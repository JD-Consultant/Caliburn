"""Set-based owner metadata reads; admission repeats them under the job-file lock."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import memory_discovery
from caliburn.features.executions import queries as executions
from caliburn.features.executions.models import ExecutionInfo, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.work_memory import consolidation_requests as requests
from caliburn.features.work_memory.consolidation_models import (
    MemoryEvidenceError,
    MemoryEvidenceIssue,
)


@dataclass(frozen=True, slots=True)
class PendingMemorySources:
    source_ids: dict[UUID, UUID]
    issues: tuple[MemoryEvidenceIssue, ...]


@dataclass(frozen=True, slots=True)
class MemoryFailureBlocks:
    reasons: dict[UUID, str]
    issues: tuple[MemoryEvidenceIssue, ...]


@dataclass(frozen=True, slots=True)
class MemoryQualification:
    active: dict[UUID, ExecutionInfo]
    source_ids: dict[UUID, UUID]
    issues: tuple[MemoryEvidenceIssue, ...]


async def read_memory_qualification(
    session: AsyncSession, job_file_id: UUID | None = None
) -> MemoryQualification:
    """One qualification rule for discovery and the claim transaction's locked recheck."""
    blocked = await read_blocks(session, job_file_id)
    excluded = frozenset(blocked.reasons) | {issue.job_file_id for issue in blocked.issues}
    if job_file_id in excluded:
        return MemoryQualification({}, {}, blocked.issues)
    if job_file_id is None:
        active = await memory_discovery.list_active_memory(session)
    else:
        current = await memory_discovery.read_active_memory(session, job_file_id)
        active = (current,) if current is not None else ()
    eligible_active = {
        info.scope.job_file_id: info for info in active if info.scope.job_file_id not in excluded
    }
    # An existing batch owns its fixed source window; later intents do not requalify it.
    if job_file_id in eligible_active:
        return MemoryQualification(eligible_active, {}, blocked.issues)
    pending = await read_pending_sources(
        session,
        job_file_id,
        excluded_file_ids=excluded | eligible_active.keys(),
    )
    return MemoryQualification(eligible_active, pending.source_ids, blocked.issues + pending.issues)


async def read_pending_sources(
    session: AsyncSession,
    job_file_id: UUID | None = None,
    *,
    excluded_file_ids: frozenset[UUID] = frozenset(),
) -> PendingMemorySources:
    intent_statement = requests.intents_projection(job_file_id)
    if excluded_file_ids:
        intent_statement = intent_statement.where(
            intent_statement.selected_columns.job_file_id.not_in(excluded_file_ids)
        )
    intents = intent_statement.subquery("consolidation_intents")
    turns = executions.consolidation_executions_projection(job_file_id).subquery("intent_turns")
    formal = interviews.consolidation_exchange_positions_projection(job_file_id).subquery(
        "intent_formal_exchanges"
    )
    inputs = interviews.accepted_input_positions_projection(job_file_id).subquery("intent_inputs")
    joined = (
        intents.outerjoin(
            turns,
            (turns.c.execution_id == intents.c.execution_id)
            & (turns.c.job_file_id == intents.c.job_file_id),
        )
        .outerjoin(
            inputs,
            (inputs.c.execution_id == intents.c.execution_id)
            & (inputs.c.job_file_id == intents.c.job_file_id),
        )
        .outerjoin(
            formal,
            (formal.c.execution_id == intents.c.execution_id)
            & (formal.c.job_file_id == intents.c.job_file_id),
        )
    )
    # Coverage never participates in integrity validation. Even a covered source must
    # retain its original input and, after successful A completion, its formal exchange.
    reason = case(
        (intents.c.intent_source_id.is_(None), "invalid_intent_payload"),
        (turns.c.status.is_(None), "missing_consultant_turn"),
        (
            or_(inputs.c.source_id.is_(None), inputs.c.source_id != intents.c.intent_source_id),
            "formal_source_mismatch",
        ),
        (
            (turns.c.status == ExecutionStatus.COMPLETED)
            & or_(formal.c.source_id.is_(None), formal.c.source_id != intents.c.intent_source_id),
            "formal_source_mismatch",
        ),
    ).label("reason")
    integrity = (
        select(
            intents.c.job_file_id,
            intents.c.execution_id,
            intents.c.command_id,
            reason,
        )
        .select_from(joined)
        .subquery("intent_integrity")
    )
    issues = tuple(
        MemoryEvidenceIssue(*row)
        for row in await session.execute(
            select(integrity)
            .where(integrity.c.reason.is_not(None))
            .order_by(integrity.c.job_file_id, integrity.c.command_id)
        )
    )
    coverage = requests.published_coverage_projection().subquery("published_coverage")
    # Evaluate uncovered formal exchanges once before joining repeated intent commands.
    # This is statement-local planning, not a persisted queue or another coverage owner.
    eligible = (
        select(
            formal.c.job_file_id,
            formal.c.execution_id,
            formal.c.source_id,
            formal.c.employee_input_sequence,
        )
        .select_from(
            formal.join(
                turns,
                (turns.c.execution_id == formal.c.execution_id)
                & (turns.c.job_file_id == formal.c.job_file_id),
            ).outerjoin(coverage, coverage.c.job_file_id == formal.c.job_file_id)
        )
        .where(
            turns.c.status == ExecutionStatus.COMPLETED,
            formal.c.employee_input_sequence
            > func.coalesce(coverage.c.covered_through_sequence, 0),
        )
        .cte("uncovered_exchanges")
        .prefix_with("MATERIALIZED")
    )
    pending = (
        select(intents.c.job_file_id, intents.c.intent_source_id)
        .select_from(
            intents.join(
                eligible,
                (eligible.c.execution_id == intents.c.execution_id)
                & (eligible.c.job_file_id == intents.c.job_file_id)
                & (eligible.c.source_id == intents.c.intent_source_id),
            )
        )
        .ext(distinct_on(intents.c.job_file_id))
        .order_by(
            intents.c.job_file_id, eligible.c.employee_input_sequence.desc(), intents.c.command_id
        )
    )
    if issues:
        pending = pending.where(
            intents.c.job_file_id.not_in({issue.job_file_id for issue in issues})
        )
    rows = await session.execute(pending)
    return PendingMemorySources({file_id: value for file_id, value in rows}, issues)


async def read_blocks(
    session: AsyncSession, job_file_id: UUID | None = None
) -> MemoryFailureBlocks:
    failures = requests.failures_projection(job_file_id).subquery("memory_failures")
    invalid = or_(
        failures.c.failure_reason.is_(None),
        ~func.length(failures.c.failure_reason).between(1, 100),
        failures.c.failure_frontier.is_(None),
        failures.c.failure_frontier < 0,
    )
    issues = tuple(
        MemoryEvidenceIssue(file_id, execution_id, command_id, "invalid_failure_payload")
        for file_id, execution_id, command_id in await session.execute(
            select(
                failures.c.job_file_id,
                failures.c.execution_id,
                failures.c.command_id,
            )
            .where(invalid)
            .order_by(failures.c.job_file_id, failures.c.command_id)
        )
    )
    # Deterministic first command among all still-blocking failures, not merely the newest.
    statement = select(failures.c.job_file_id, failures.c.failure_reason).where(~invalid)
    frontier: ColumnElement[int]
    if job_file_id is not None:
        frontier = interviews.history_frontier_of(job_file_id)
    else:
        # Evaluate each file's indexed frontier once even with many expired failures.
        files = select(failures.c.job_file_id).distinct().subquery("failed_files")
        frontiers = (
            select(
                files.c.job_file_id,
                interviews.history_frontier_of(files.c.job_file_id).label("frontier"),
            )
            .cte("failure_frontiers")
            .prefix_with("MATERIALIZED")
        )
        statement = statement.join(frontiers, frontiers.c.job_file_id == failures.c.job_file_id)
        frontier = frontiers.c.frontier
    rows = await session.execute(
        statement.where(frontier - failures.c.failure_frontier < requests.RETRY_AFTER_NEW_MESSAGES)
        .ext(distinct_on(failures.c.job_file_id))
        .order_by(failures.c.job_file_id, failures.c.command_id)
    )
    return MemoryFailureBlocks({file_id: value for file_id, value in rows}, issues)


async def read_failure_reason(session: AsyncSession, job_file_id: UUID) -> str | None:
    """Read one file's current block; damaged evidence cannot be presented as no failure."""
    blocked = await read_blocks(session, job_file_id)
    if blocked.issues:
        raise MemoryEvidenceError(blocked.issues[0])
    return blocked.reasons.get(job_file_id)
