"""Pin each read once so title selection, body and source navigation cannot mix positions."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import candidate_queries, position_persistence
from caliburn.features.work_memory.candidates import MemoryBatchPosition, require_layer_read
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.read_models import MemoryObjectReading, MemoryReadView
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError


async def bind_candidate_view(
    session: AsyncSession, stage: MemoryBatchPosition, layer: MemoryLayer
) -> MemoryReadView:
    require_layer_read(stage.phase, layer)
    record = await candidate_queries.require_stage(session, stage)
    return MemoryReadView(
        stage.job_file_id, record.current_position_id, layer, record.through_sequence
    )


async def bind_published_view(
    session: AsyncSession, job_file_id: UUID, snapshot_id: UUID | None, layer: MemoryLayer
) -> MemoryReadView:
    if snapshot_id is None:
        # No snapshot at Turn start stays empty even if a publication happens later.
        return MemoryReadView(job_file_id, None, layer, 0)
    snapshot = await candidate_queries.read_snapshot(session, job_file_id, snapshot_id)
    return MemoryReadView(
        job_file_id, snapshot.position_id, layer, snapshot.covered_through_sequence
    )


async def read_map(session: AsyncSession, view: MemoryReadView) -> tuple[MemoryMapEntry, ...]:
    if view.position_id is None:
        return ()
    return await position_persistence.read_position_map(
        session, view.job_file_id, view.position_id, view.layer
    )


async def read_object(
    session: AsyncSession, view: MemoryReadView, object_id: UUID
) -> MemoryObjectReading:
    if view.position_id is None:
        raise MemoryRevisionNotFoundError("No Memory snapshot was selected for this Turn")
    revision = await candidate_queries.read_position_object(
        session, view.job_file_id, view.position_id, object_id
    )
    if revision.layer != view.layer:
        raise MemoryRevisionNotFoundError("The object is not in the selected layer")
    situation_references: tuple[MemoryMapEntry, ...] = ()
    if revision.work_situation_references:
        # 候選沿物件身分，已發布位置固定版本；導覽只讀來源標頭。
        source_ids = {reference.object_id for reference in revision.work_situation_references}
        sources = await candidate_queries.read_position_selection(
            session, view.job_file_id, view.position_id, tuple(source_ids)
        )
        if len(sources) != len(source_ids) or any(
            item.layer != MemoryLayer.WORK_SITUATION for item in sources.values()
        ):
            raise MemoryRevisionNotFoundError("A source binding is unavailable in the read view")
        situation_references = tuple(
            MemoryMapEntry(item.object_id, item.title, item.description)
            for item in sources.values()
        )
    return MemoryObjectReading(
        revision.content, revision.interview_references, situation_references
    )
