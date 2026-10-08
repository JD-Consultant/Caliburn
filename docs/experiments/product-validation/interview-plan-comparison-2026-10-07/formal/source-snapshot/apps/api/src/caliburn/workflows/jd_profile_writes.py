"""One model profile intent binds evidence once and applies all effects in one transaction."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import (
    candidate_service,
    revision_editing,
    source_persistence,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import ProfileChange, ProfileField, ReviseJdProfile
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InvalidJdSourceError,
    JdSourceChange,
    JdSourceTarget,
    RemoveJdSource,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_candidates import apply_candidate_edit
from caliburn.workflows.jd_sources import (
    JdSourceSelection,
    resolve_aligned_jd_source,
    resolve_jd_source,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class AddProfileSource:
    field: ProfileField
    source: JdSourceSelection


@dataclass(frozen=True, slots=True)
class RemoveProfileSource:
    field: ProfileField
    citation_ref: str


@dataclass(frozen=True, slots=True)
class AlignProfileSource:
    field: ProfileField
    citation_ref: str


type ProfileSourceIntent = AddProfileSource | RemoveProfileSource | AlignProfileSource


@dataclass(frozen=True, slots=True)
class BoundProfileSources:
    field: ProfileField
    changes: tuple[JdSourceChange, ...]


@dataclass(frozen=True, slots=True)
class PreparedProfileWrite:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    changes: tuple[ProfileChange, ...]
    sources: tuple[BoundProfileSources, ...]


class JdProfileWriteWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        changes: tuple[ProfileChange, ...],
        sources: tuple[ProfileSourceIntent, ...],
    ) -> PreparedProfileWrite:
        if not changes and not sources:
            raise InvalidJdSourceError("Choose at least one profile change")
        async with self.sessions() as session:
            execution = await executions.read_execution(session, binding.scope)
            if execution.status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            position = preview.position
            if changes:
                ReviseJdProfile(command_id, position.revision_id, changes)
            references = await source_persistence.read_source_references(
                session, binding.scope.job_file_id, position.revision_id
            )
            grouped: dict[ProfileField, list[JdSourceChange]] = {}
            for intention in sources:
                target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=intention.field)
                if isinstance(intention, AddProfileSource):
                    source = await resolve_jd_source(session, binding, intention.source)
                    change: JdSourceChange = AddJdSource(source)
                else:
                    reference = next(
                        (
                            ref
                            for ref in references
                            if (
                                ref.target == target
                                and f"citation_{ref.citation_id.hex}" == intention.citation_ref
                            )
                        ),
                        None,
                    )
                    if reference is None:
                        raise InvalidJdSourceError(
                            "The citation does not belong to this profile field"
                        )
                    if isinstance(intention, RemoveProfileSource):
                        change = RemoveJdSource(reference.citation_id)
                    else:
                        change = AlignJdSource(
                            reference.citation_id,
                            await resolve_aligned_jd_source(session, binding, reference.source),
                        )
                grouped.setdefault(intention.field, []).append(change)
            bound = tuple(
                BoundProfileSources(field, tuple(values)) for field, values in grouped.items()
            )
            for group in bound:
                ReviseJdSources(
                    command_id,
                    position.revision_id,
                    JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=group.field),
                    group.changes,
                )
            return PreparedProfileWrite(
                command_id, position.scope, position.revision_id, changes, bound
            )

    async def execute(self, writer: ExecutionWriter, prepared: PreparedProfileWrite) -> str:
        if writer.scope.execution_id != prepared.candidate.execution_id:
            raise ExecutionStateError("This prepared edit belongs to a different Turn")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(
                session, writer.scope.job_file_id, prepared.candidate
            )
            revision = prepared.expected_revision_id
            if prepared.changes:
                revision = await apply_candidate_edit(
                    session,
                    writer.scope.job_file_id,
                    prepared.candidate,
                    ReviseJdProfile(
                        uuid5(prepared.command_id, "profile_text"), revision, prepared.changes
                    ),
                )
            for group in prepared.sources:
                revision = await apply_candidate_edit(
                    session,
                    writer.scope.job_file_id,
                    prepared.candidate,
                    ReviseJdSources(
                        uuid5(prepared.command_id, f"profile_source:{group.field}"),
                        revision,
                        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=group.field),
                        group.changes,
                    ),
                )
            if revision == prepared.expected_revision_id:
                return "unchanged"
            if not prepared.changes and all(
                isinstance(change, AlignJdSource)
                for group in prepared.sources
                for change in group.changes
            ):
                return "aligned"
            return "updated"
