"""固定單一項目的文字、關係與來源修改，交共同候選入口執行。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.job_description import (
    candidate_service,
    source_persistence,
)
from caliburn.features.job_description.compound_edits import (
    ReviseItemWithSources,
)
from caliburn.features.job_description.item_revision import (
    AddItemSource,
    AlignItemSource,
    RemoveItemSource,
    ReviseItemInput,
    bind_item_sources,
    prepare_item_revision,
    select_item_citation,
    source_target,
)
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    JdSourceChange,
    JdSourceTarget,
    RemoveJdSource,
)
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.job_description.sources import resolve_aligned_jd_source, resolve_jd_source
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


class JdItemRevisionWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: ReviseItemInput,
    ) -> PreparedJdEdit[ReviseItemWithSources]:
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            work = preview.work
            prepared = prepare_item_revision(work, intent)
            item = prepared.item
            references = await source_persistence.read_source_references(
                session, binding.scope.job_file_id, preview.position.revision_id
            )
            grouped: dict[JdSourceTarget, list[JdSourceChange]] = {}
            for change in intent.changes:
                if isinstance(change, AddItemSource | RemoveItemSource | AlignItemSource):
                    target = source_target(item)
                    if isinstance(change, AddItemSource):
                        bound: JdSourceChange = AddJdSource(
                            await resolve_jd_source(session, binding, change.source)
                        )
                    else:
                        reference = select_item_citation(references, target, change.citation_ref)
                        if isinstance(change, RemoveItemSource):
                            bound = RemoveJdSource(reference.citation_id)
                        else:
                            bound = AlignJdSource(
                                reference.citation_id,
                                await resolve_aligned_jd_source(session, binding, reference.source),
                            )
                    grouped.setdefault(target, []).append(bound)
            return PreparedJdEdit(
                preview.position.scope,
                ReviseItemWithSources(
                    command_id,
                    preview.position.revision_id,
                    prepared.content,
                    prepared.capabilities,
                    bind_item_sources(grouped),
                ),
            )
