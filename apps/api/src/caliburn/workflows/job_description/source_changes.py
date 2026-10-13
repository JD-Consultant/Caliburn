"""Read-only JD comparisons, using fixed original evidence and the Turn's pinned view."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_description import candidate_service, source_persistence
from caliburn.features.job_description.sources import InterviewSource
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.workflows.job_description.reads import resolve_jd_citation_ref
from caliburn.workflows.job_description.source_queries import JdSourceChanges as JdSourceChanges
from caliburn.workflows.job_description.source_queries import (
    MemorySourceChange as MemorySourceChange,
)
from caliburn.workflows.job_description.source_queries import read_memory_source_changes
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class SourceChangeQuery:
    citation_ref: str


class UnsupportedJdSourceKindError(ValueError):
    """The safe message points back to current input or an authorized formal sequence."""


class JdChangesWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_source(self, binding: PublishedMemoryRead, citation_ref: str) -> JdSourceChanges:
        async with consistent_read_session(self.sessions) as session:
            await _require_read(session, binding)
            file_id = binding.scope.job_file_id
            candidate = await candidate_service.read_position(
                session, file_id, binding.scope.execution_id
            )
            references = await source_persistence.read_source_references(
                session, file_id, candidate.revision_id
            )
            reference = resolve_jd_citation_ref(references, citation_ref)
            source = reference.source
            if isinstance(source, InterviewSource):
                current_id = await interviews.read_execution_input_source_id(
                    session, job_file_id=file_id, execution_id=binding.scope.execution_id
                )
                if source.source_id == current_id:
                    raise UnsupportedJdSourceKindError(
                        f"此引用是本次 input 的訪談序號 {binding.interview_through_sequence + 1}；"
                        "請使用本輪已提供的原話，不需查歷史。"
                    )
                formal = await interviews.read_interview_source_headers(
                    session,
                    InterviewReadScope(file_id, binding.interview_through_sequence),
                    source_ids=(source.source_id,),
                )
                raise UnsupportedJdSourceKindError(
                    "此引用是不可變訪談；請用 read_interview 讀正式序號 "
                    f"{formal[0].interview_sequence}。"
                )
            if binding.snapshot_id is None:
                raise MemoryRevisionNotFoundError("No published comparison endpoint is pinned")
            return await read_memory_source_changes(
                session,
                job_file_id=file_id,
                reference=reference,
                snapshot_id=binding.snapshot_id,
                interview_through_sequence=binding.interview_through_sequence,
            )


async def _require_read(session: AsyncSession, binding: PublishedMemoryRead) -> None:
    if binding.scope.kind != ExecutionKind.CONSULTANT_TURN or (
        await executions.read_execution(session, binding.scope)
    ).status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
        raise ExecutionStateError("This Turn cannot read JD changes")
