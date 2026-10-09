"""A complete task and its direct evidence are one bounded, recoverable model operation."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import (
    candidate_service,
    compound_service,
    revision_editing,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
)
from caliburn.features.job_description.compound_edits import (
    BoundTaskCapability,
    CreateTaskWithSources,
    JdCompoundEditResult,
)
from caliburn.features.job_description.navigation import resolve_jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    InvalidJdSourceError,
    JdSource,
    validate_source_changes,
)
from caliburn.features.job_description.tasks import CreateTask
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_sources import JdSourceSelection, resolve_jd_source
from caliburn.workflows.memory_reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class TaskDetailInput:
    text: str
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskCapabilityInput:
    read_ref: str
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateTaskInput:
    parent_read_ref: str | None
    title: str | None
    description: str | None
    outcomes: tuple[TaskDetailInput, ...] = ()
    requirements: tuple[TaskDetailInput, ...] = ()
    required_knowledge: tuple[TaskCapabilityInput, ...] = ()
    required_skills: tuple[TaskCapabilityInput, ...] = ()
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedTaskWrite:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    task: CreateTask
    task_sources: tuple[JdSource, ...]
    detail_sources: tuple[tuple[JdSource, ...], ...]
    capabilities: tuple[BoundTaskCapability, ...]


class JdTaskWriteWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: CreateTaskInput,
    ) -> PreparedTaskWrite:
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            area_id = None
            if intent.parent_read_ref is not None:
                area = resolve_jd_read_ref(preview.work, intent.parent_read_ref)
                if not isinstance(area, ResponsibilityArea):
                    raise InvalidJdSourceError("A task parent must select a responsibility area")
                area_id = area.area_id
            task = CreateTask(
                area_id,
                intent.title,
                intent.description,
                tuple(item.text for item in intent.outcomes),
                tuple(item.text for item in intent.requirements),
            )
            task_sources = await _resolve_sources(session, binding, intent.sources)
            detail_sources = tuple(
                [
                    await _resolve_sources(session, binding, detail.sources)
                    for detail in (*intent.outcomes, *intent.requirements)
                ]
            )
            links: list[BoundTaskCapability] = []
            for kind, selected in (
                (CapabilityKind.KNOWLEDGE, intent.required_knowledge),
                (CapabilityKind.SKILL, intent.required_skills),
            ):
                for link in selected:
                    capability = resolve_jd_read_ref(preview.work, link.read_ref)
                    if not isinstance(capability, Capability) or capability.kind != kind:
                        raise InvalidJdSourceError("The capability reference has the wrong kind")
                    if any(item.capability_id == capability.capability_id for item in links):
                        raise InvalidJdSourceError("Link each capability only once")
                    links.append(
                        BoundTaskCapability(
                            capability.capability_id,
                            await _resolve_sources(session, binding, link.sources),
                        )
                    )
            return PreparedTaskWrite(
                command_id,
                preview.position.scope,
                preview.position.revision_id,
                task,
                task_sources,
                detail_sources,
                tuple(links),
            )

    async def execute(
        self, writer: ExecutionWriter, prepared: PreparedTaskWrite
    ) -> JdCompoundEditResult:
        if writer.scope.execution_id != prepared.candidate.execution_id:
            raise ExecutionStateError("This prepared edit belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            result = await compound_service.apply_compound_edit(
                session,
                file_id,
                CreateTaskWithSources(
                    prepared.command_id,
                    prepared.expected_revision_id,
                    prepared.task,
                    prepared.task_sources,
                    prepared.detail_sources,
                    prepared.capabilities,
                ),
                candidate=prepared.candidate,
            )
            return result


async def _resolve_sources(
    session: AsyncSession,
    binding: PublishedMemoryRead,
    selections: tuple[JdSourceSelection, ...],
) -> tuple[JdSource, ...]:
    sources = tuple(
        [await resolve_jd_source(session, binding, selection) for selection in selections]
    )
    if sources:
        validate_source_changes(tuple(AddJdSource(source) for source in sources))
    return sources
