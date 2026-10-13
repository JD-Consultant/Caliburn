"""固定非任務項目的建立與來源；命令 ID 及候選由 App 綁定。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.job_description import (
    candidate_service,
)
from caliburn.features.job_description.compound_edits import (
    CreateItemWithSources,
)
from caliburn.features.job_description.compound_edits import ItemCreation as ItemCreation
from caliburn.features.job_description.source_intents import JdSourceSelection
from caliburn.features.job_description.sources import (
    AddJdSource,
    validate_source_changes,
)
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.job_description.sources import resolve_jd_source
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


@dataclass(frozen=True, slots=True)
class CreateItemInput:
    item: ItemCreation
    sources: tuple[JdSourceSelection, ...] = ()


class JdItemCreationWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: CreateItemInput,
    ) -> PreparedJdEdit[CreateItemWithSources]:
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
            return PreparedJdEdit(
                preview.position.scope,
                CreateItemWithSources(
                    command_id,
                    preview.position.revision_id,
                    intent.item,
                    sources,
                ),
            )
