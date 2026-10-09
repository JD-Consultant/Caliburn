"""Create one non-task JD item and its evidence in the Turn's private candidate.

The caller checkpoints one prepared intent before execution and reuses it verbatim
on recovery. App command IDs and resolved sources never come from model arguments.
No Turn completion, formal-head write, source store or second receipt lives here.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import (
    candidate_service,
    compound_service,
    revision_editing,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.compound_edits import (
    CreateItemWithSources,
    JdCompoundEditResult,
)
from caliburn.features.job_description.compound_edits import ItemCreation as ItemCreation
from caliburn.features.job_description.sources import (
    AddJdSource,
    JdSource,
    validate_source_changes,
)
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_sources import JdSourceSelection, resolve_jd_source
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class CreateItemInput:
    item: ItemCreation
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedItemCreation:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    item: ItemCreation
    sources: tuple[JdSource, ...]


class JdItemCreationWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: CreateItemInput,
    ) -> PreparedItemCreation:
        if binding.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Only a consultant Turn can create JD items")
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            sources = tuple(
                [await resolve_jd_source(session, binding, source) for source in intent.sources]
            )
            if sources:
                validate_source_changes(tuple(AddJdSource(source) for source in sources))
            return PreparedItemCreation(
                command_id,
                preview.position.scope,
                preview.position.revision_id,
                intent.item,
                sources,
            )

    async def execute(
        self, writer: ExecutionWriter, prepared: PreparedItemCreation
    ) -> JdCompoundEditResult:
        if (
            writer.scope.kind != ExecutionKind.CONSULTANT_TURN
            or writer.scope.execution_id != prepared.candidate.execution_id
        ):
            raise ExecutionStateError("This prepared edit belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            result = await compound_service.apply_compound_edit(
                session,
                file_id,
                CreateItemWithSources(
                    prepared.command_id,
                    prepared.expected_revision_id,
                    prepared.item,
                    prepared.sources,
                ),
                candidate=prepared.candidate,
            )
            return result
