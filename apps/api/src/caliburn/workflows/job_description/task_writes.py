"""一次固定完整任務、明細、能力關係與直接來源。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.job_description import (
    candidate_service,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
)
from caliburn.features.job_description.compound_edits import (
    BoundTaskCapability,
    CreateTaskWithSources,
)
from caliburn.features.job_description.navigation import resolve_jd_read_ref
from caliburn.features.job_description.source_intents import JdSourceSelection
from caliburn.features.job_description.sources import (
    AddJdSource,
    InvalidJdSourceError,
    JdSource,
    validate_source_changes,
)
from caliburn.features.job_description.tasks import CreateTask
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.job_description.sources import resolve_jd_source
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class TaskDetailInput:
    text: str


@dataclass(frozen=True, slots=True)
class TaskCapabilityInput:
    read_ref: str


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


class JdTaskWriteWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: CreateTaskInput,
    ) -> PreparedJdEdit[CreateTaskWithSources]:
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
                    links.append(BoundTaskCapability(capability.capability_id))
            return PreparedJdEdit(
                preview.position.scope,
                CreateTaskWithSources(
                    command_id,
                    preview.position.revision_id,
                    task,
                    task_sources,
                    tuple(links),
                ),
            )


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
