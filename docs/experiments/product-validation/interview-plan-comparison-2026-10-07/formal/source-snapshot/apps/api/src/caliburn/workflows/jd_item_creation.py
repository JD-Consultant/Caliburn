"""Create one non-task JD item and its evidence in the Turn's private candidate.

The caller checkpoints one prepared intent before execution and reuses it verbatim
on recovery. App command IDs and resolved sources never come from model arguments.
No Turn completion, formal-head write, source store or second receipt lives here.
"""

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service, revision_editing, work_queries
from caliburn.features.job_description.areas import CreateArea, EditJdAreas, ResponsibilityArea
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    Capability,
    CreateCapability,
    EditJdCapabilities,
)
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CreateCollaborator,
    EditJdCollaborators,
)
from caliburn.features.job_description.conditions import (
    CreateCondition,
    EditJdConditions,
    JobCondition,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    JdSource,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
    validate_source_changes,
)
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_candidates import apply_candidate_edit
from caliburn.workflows.jd_sources import JdSourceSelection, resolve_jd_source
from caliburn.workflows.memory_reads import PublishedMemoryRead

type ItemCreation = CreateArea | CreateCapability | CreateCollaborator | CreateCondition
type CreatedItem = ResponsibilityArea | Capability | Collaborator | JobCondition
type ItemCreationCommand = EditJdAreas | EditJdCapabilities | EditJdCollaborators | EditJdConditions


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

    async def execute(self, writer: ExecutionWriter, prepared: PreparedItemCreation) -> str:
        if (
            writer.scope.kind != ExecutionKind.CONSULTANT_TURN
            or writer.scope.execution_id != prepared.candidate.execution_id
        ):
            raise ExecutionStateError("This prepared creation belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            previous = await work_queries.read_work_at(
                session, file_id, prepared.expected_revision_id
            )
            revision = await apply_candidate_edit(
                session, file_id, prepared.candidate, _creation_command(prepared)
            )
            # Recovery uses the original operation's revision, never the latest candidate.
            result = await work_queries.read_work_at(session, file_id, revision)
            previous_refs = {jd_read_ref(item) for item in _items(previous)}
            created = [item for item in _items(result) if jd_read_ref(item) not in previous_refs]
            if len(created) != 1:
                raise RuntimeError("The original item operation must identify one new item")
            item = created[0]
            if prepared.sources:
                await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    ReviseJdSources(
                        uuid5(prepared.command_id, "sources"),
                        revision,
                        _source_target(item),
                        tuple(AddJdSource(source) for source in prepared.sources),
                    ),
                )
            return f"created · read_ref: {jd_read_ref(item)}"


def _creation_command(prepared: PreparedItemCreation) -> ItemCreationCommand:
    command_id = uuid5(prepared.command_id, "item")
    revision = prepared.expected_revision_id
    match prepared.item:
        case CreateArea():
            return EditJdAreas(command_id, revision, prepared.item)
        case CreateCapability():
            return EditJdCapabilities(command_id, revision, prepared.item)
        case CreateCollaborator():
            return EditJdCollaborators(command_id, revision, prepared.item)
        case CreateCondition():
            return EditJdConditions(command_id, revision, prepared.item)
    raise TypeError("Unsupported JD item creation")


def _items(work: JdWorkRevision) -> tuple[CreatedItem, ...]:
    return (*work.areas, *work.capabilities, *work.collaborators, *work.conditions)


def _source_target(item: CreatedItem) -> JdSourceTarget:
    match item:
        case ResponsibilityArea():
            return JdSourceTarget(SourceTargetKind.AREA, item_id=item.area_id)
        case Capability():
            return JdSourceTarget(SourceTargetKind.CAPABILITY, item_id=item.capability_id)
        case Collaborator():
            return JdSourceTarget(SourceTargetKind.COLLABORATOR, item_id=item.collaborator_id)
        case JobCondition():
            return JdSourceTarget(SourceTargetKind.CONDITION, item_id=item.condition_id)
