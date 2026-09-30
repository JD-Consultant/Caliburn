"""Atomically settle A's interview, JD and history eligibility through their existing owners.

Before complete(), the caller must have verified and durably saved the complete native
final reply and its completed context position, including the Step/control boundary.
Graph END alone is not that proof. This module does no model or saver I/O.

The Memory owner records intents before completion and derives dispatch eligibility from
this transaction's completed execution AND matching formal employee input. Thus a crash
after commit cannot lose a notification and cancellation cannot qualify it. No second
outbox flag or in-memory wakeup is authoritative. Memory source membership is verified
when tools resolve sources; this module only checks formal interview eligibility.
"""

from uuid import uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole, ContextPosition
from caliburn.features.executions.models import (
    ExecutionInfo,
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import FormalInterviewExchange, InterviewReadScope
from caliburn.features.job_description import candidate_service, source_persistence
from caliburn.features.job_description.candidates import CandidateStateError, JdCandidatePosition
from caliburn.features.job_description.sources import InterviewSource
from caliburn.features.job_files import service as job_files
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.jd_candidates import adopt_candidate_jd


class ConsultantCompletionWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def complete(
        self,
        writer: ExecutionWriter,
        position: JdCandidatePosition,
        reply_text: str,
        context_position: ContextPosition,
    ) -> FormalInterviewExchange:
        """Commit once or recover the exact original reply/JD/context; mismatched replays fail.

        Retain the original position, reply and context_position after an unknown COMMIT.
        Exceptions roll back all participants, including formal sequence allocation.
        """
        _require_consultant(writer)
        if position.scope.execution_id != writer.scope.execution_id:
            raise CandidateStateError("The candidate belongs to another consultant Turn")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            exchange = await record_formal_interview(session, writer, reply_text=reply_text)
            references = await source_persistence.read_source_references(
                session, writer.scope.job_file_id, position.revision_id
            )
            source_ids = tuple(
                reference.source.source_id
                for reference in references
                if isinstance(reference.source, InterviewSource)
            )
            if source_ids:
                # The owner result is this completion's new formal frontier, also on replay.
                # Query only selected identities; never rewrite current_input or scan history.
                await interviews.read_interview_sources(
                    session,
                    InterviewReadScope(
                        writer.scope.job_file_id, exchange.consultant_reply.interview_sequence
                    ),
                    source_ids=source_ids,
                )
            await adopt_candidate_jd(
                session,
                writer,
                position,
                uuid5(writer.scope.execution_id, "consultant_completion.adopt_candidate"),
            )
            # This owner finishes execution eligibility too. Its final pause/writer check
            # must be in this transaction so a competing control cannot leave half a result.
            await history.complete_context_histories(
                session, writer, {AgentRole.JOB_CONSULTANT: context_position}
            )
            return exchange

    async def stop(self, writer: ExecutionWriter, status: ExecutionStatus) -> ExecutionInfo:
        """Discard only this Turn and return the actual terminal outcome, including a prior win.

        Cancellation and final failure preserve adopted pre-work history. A terminal replay
        is fenced by the original writer and never rewinds completed work or another outcome.
        """
        _require_consultant(writer)
        if status not in (ExecutionStatus.CANCELLED, ExecutionStatus.FAILED):
            raise ValueError("Stopping a Turn requires cancelled or failed")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            original = await executions.read_execution(session, writer.scope)
            if original.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.FAILED,
            ):
                # Idempotent owner call also rejects a superseded writer, without changing
                # the original outcome to the newly requested status.
                await executions.finish_execution(session, writer, original.status)
                return original
            await executions.lock_unfinished_writer(session, writer)
            try:
                position = await candidate_service.read_position(
                    session, writer.scope.job_file_id, writer.scope.execution_id
                )
            except CandidateStateError:
                # No open draft: stopping is legal before its creation. This narrow query
                # also excludes already closed drafts; never create/reopen one just to stop.
                position = None
            if position is not None:
                await candidate_service.discard_candidate(
                    session,
                    writer.scope.job_file_id,
                    position,
                    uuid5(writer.scope.execution_id, "consultant_completion.discard_candidate"),
                )
            await executions.finish_execution(session, writer, status)
            return await executions.read_execution(session, writer.scope)


def _require_consultant(writer: ExecutionWriter) -> None:
    if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only consultant Turns use this completion workflow")
