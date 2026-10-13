"""B2 handoff projection from retained candidate positions, never a second diff store."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import candidate_queries as queries
from caliburn.features.work_memory.candidates import MemoryBatchPosition, MemoryPermissionError
from caliburn.features.work_memory.revision_service import read_fixed_headers, read_fixed_revisions
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.features.work_memory.sources import read_reference_headers
from caliburn.features.work_memory.stage_changes import SituationChange, SituationRevision


async def read_situation_handoff_snapshot(
    session: AsyncSession, stage: MemoryBatchPosition
) -> tuple[SituationChange, ...]:
    """Read batch origin and fixed B1 handoff as detached immutable values.

    Only changed situation bodies are loaded. Callers release this session before
    comparison; revision changes remain represented even when net text is unchanged.
    """
    if stage.phase != MemoryLayer.WORK_UNDERSTANDING:
        raise MemoryPermissionError("Only B2 receives situation impact information")
    batch = await queries.require_stage(session, stage)
    before = await queries.read_members(session, stage.job_file_id, batch.base_position_id)
    after = await queries.read_members(session, stage.job_file_id, stage.position_id)
    headers = await read_fixed_headers(
        session,
        job_file_id=stage.job_file_id,
        references=frozenset((*before.values(), *after.values())),
    )
    affected: dict[UUID, list[str]] = {}
    for members in (before, after):
        for reference in members.values():
            revision = headers[reference]
            if revision.layer == MemoryLayer.WORK_UNDERSTANDING:
                for source in revision.work_situation_references:
                    titles = affected.setdefault(source.object_id, [])
                    if revision.title not in titles:
                        titles.append(revision.title)
    changed = [
        identity
        for identity in sorted(before.keys() | after.keys())
        if before.get(identity) != after.get(identity)
        and headers[after[identity] if identity in after else before[identity]].layer
        == MemoryLayer.WORK_SITUATION
    ]
    revisions = await read_fixed_revisions(
        session,
        job_file_id=stage.job_file_id,
        references=frozenset(
            members[identity]
            for identity in changed
            for members in (before, after)
            if identity in members
        ),
    )
    sources = await read_reference_headers(
        session,
        queries.source_window(batch),
        source_ids=frozenset(
            source for revision in revisions.values() for source in revision.interview_references
        ),
    )
    sequences = {source.source_id: source.interview_sequence for source in sources}
    return tuple(
        SituationChange(
            SituationRevision.from_revision(revisions[before[identity]], sequences)
            if identity in before
            else None,
            SituationRevision.from_revision(revisions[after[identity]], sequences)
            if identity in after
            else None,
            tuple(affected.get(identity, [])),
        )
        for identity in changed
    )
