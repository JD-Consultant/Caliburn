"""Read fixed JD Memory evidence through its owners, within caller-qualified scope.

Callers select eligible JD references and pin the comparison snapshot/interview bound.
These queries do not grant execution access, search history by title, or align citations.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_description.sources import (
    InvalidJdSourceError,
    JdSourceReference,
    MemorySource,
)
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory.candidates import MemoryPermissionError
from caliburn.features.work_memory.read_models import MemoryObjectMetadata
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
)


@dataclass(frozen=True, slots=True)
class MemorySourceChange:
    before: MemoryObjectRevision | None
    after: MemoryObjectRevision | None
    before_interviews: tuple[int, ...]
    after_interviews: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class JdSourceChanges:
    reference: JdSourceReference
    changes: tuple[MemorySourceChange, ...]


async def read_fixed_memory_source(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    source: MemorySource,
    interview_through_sequence: int,
) -> MemoryObjectRevision:
    """Read the cited revision only if its original snapshot selects that identity/layer."""
    snapshot = await memory.read_snapshot(session, job_file_id, source.snapshot_id)
    if snapshot.covered_through_sequence > interview_through_sequence:
        raise MemoryPermissionError("The original source exceeds the interview scope")
    original = await memory.read_position_object(
        session, job_file_id, snapshot.position_id, source.object_id
    )
    if original.revision_id != source.revision_id or original.layer.value != source.layer.value:
        raise MemoryRevisionNotFoundError("The citation does not match its original fixed snapshot")
    return original


async def read_memory_source_titles(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    source: MemorySource,
    snapshot_id: UUID | None,
    interview_through_sequence: int,
) -> tuple[str | None, str | None, bool]:
    """單條來源沿批次標頭查詢，依身分比較名稱與版本。"""
    titles = await read_memory_source_title_batch(
        session,
        job_file_id=job_file_id,
        sources=(source,),
        snapshot_id=snapshot_id,
        interview_through_sequence=interview_through_sequence,
    )
    return titles[source]


async def read_memory_source_title_batch(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    sources: tuple[MemorySource, ...],
    snapshot_id: UUID | None,
    interview_through_sequence: int,
) -> dict[MemorySource, tuple[str | None, str | None, bool]]:
    """本次概覽按固定快照分組，只讀引用物件的標頭，不保存跨請求快取。"""
    if not sources:
        return {}
    by_snapshot: dict[UUID, list[MemorySource]] = {}
    for source in dict.fromkeys(sources):
        by_snapshot.setdefault(source.snapshot_id, []).append(source)
    originals: dict[MemorySource, MemoryObjectMetadata] = {}
    for original_snapshot_id, group in by_snapshot.items():
        original_snapshot = await memory.read_snapshot(session, job_file_id, original_snapshot_id)
        if original_snapshot.covered_through_sequence > interview_through_sequence:
            raise MemoryPermissionError("The original source exceeds the interview scope")
        members = await memory.read_position_selection(
            session,
            job_file_id,
            original_snapshot.position_id,
            tuple({source.object_id for source in group}),
        )
        for source in group:
            original = members.get(source.object_id)
            if original is None or (
                original.revision_id != source.revision_id
                or original.layer.value != source.layer.value
            ):
                raise MemoryRevisionNotFoundError(
                    "The citation does not match its original fixed snapshot"
                )
            originals[source] = original
    current_members: dict[UUID, MemoryObjectMetadata] = {}
    if snapshot_id is not None:
        current_snapshot = await memory.read_snapshot(session, job_file_id, snapshot_id)
        if current_snapshot.covered_through_sequence > interview_through_sequence:
            raise MemoryPermissionError("The pinned Memory exceeds the interview scope")
        current_members = await memory.read_position_selection(
            session,
            job_file_id,
            current_snapshot.position_id,
            tuple({source.object_id for source in sources}),
        )
    titles: dict[MemorySource, tuple[str | None, str | None, bool]] = {}
    for source, original in originals.items():
        current = current_members.get(source.object_id)
        if current is None:
            # 有效封存位置內查無指定身分才算刪除；標頭不完整仍由 owner 拒絕。
            titles[source] = (None, original.title, True)
            continue
        if current.layer != original.layer:
            raise MemoryRevisionNotFoundError("The fixed source changed its Memory layer")
        historical_title = original.title if original.title != current.title else None
        titles[source] = (
            current.title,
            historical_title,
            current.revision_id != original.revision_id,
        )
    return titles


async def read_memory_source_changes(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    reference: JdSourceReference,
    snapshot_id: UUID,
    interview_through_sequence: int,
) -> JdSourceChanges:
    """Compare fixed Memory identities and their situation chains without changing review state."""
    source = reference.source
    if not isinstance(source, MemorySource):
        raise InvalidJdSourceError("Memory source changes require a fixed Memory reference")
    before = await read_fixed_memory_source(
        session,
        job_file_id=job_file_id,
        source=source,
        interview_through_sequence=interview_through_sequence,
    )
    new_snapshot = await memory.read_snapshot(session, job_file_id, snapshot_id)
    if new_snapshot.covered_through_sequence > interview_through_sequence:
        raise MemoryPermissionError("The source exceeds the interview boundary")
    current_members = await memory.read_position_selection(
        session, job_file_id, new_snapshot.position_id, (source.object_id,)
    )
    after = (
        await memory.read_position_object(
            session, job_file_id, new_snapshot.position_id, source.object_id
        )
        if source.object_id in current_members
        else None
    )
    if after is not None and after.layer != before.layer:
        raise MemoryRevisionNotFoundError("The same source identity changed layer")
    changes = [
        await _source_change(session, job_file_id, interview_through_sequence, before, after)
    ]
    # A changed understanding may retain the same text but depend on changed situations.
    old_links = {ref.object_id: ref for ref in before.work_situation_references}
    new_links = {ref.object_id: ref for ref in after.work_situation_references} if after else {}
    old_snapshot = await memory.read_snapshot(session, job_file_id, source.snapshot_id)
    for object_id in sorted(old_links.keys() | new_links.keys()):
        old = (
            await memory.read_position_object(
                session, job_file_id, old_snapshot.position_id, object_id
            )
            if object_id in old_links
            else None
        )
        new = (
            await memory.read_position_object(
                session, job_file_id, new_snapshot.position_id, object_id
            )
            if object_id in new_links
            else None
        )
        for selected, links in ((old, old_links), (new, new_links)):
            if selected is not None and (
                selected.layer != MemoryLayer.WORK_SITUATION
                or selected.revision_id != links[object_id].revision_id
            ):
                raise MemoryRevisionNotFoundError("The published source chain is incomplete")
        changes.append(
            await _source_change(session, job_file_id, interview_through_sequence, old, new)
        )
    return JdSourceChanges(reference, tuple(changes))


async def _source_change(
    session: AsyncSession,
    job_file_id: UUID,
    interview_through_sequence: int,
    before: MemoryObjectRevision | None,
    after: MemoryObjectRevision | None,
) -> MemorySourceChange:
    async def sequences(value: MemoryObjectRevision | None) -> tuple[int, ...]:
        if value is None or not value.interview_references:
            return ()
        selected = await interviews.read_interview_sources(
            session,
            InterviewReadScope(job_file_id, interview_through_sequence),
            source_ids=tuple(value.interview_references),
        )
        return tuple(sorted(message.interview_sequence for message in selected))

    return MemorySourceChange(before, after, await sequences(before), await sequences(after))
