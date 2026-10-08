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
from caliburn.features.work_memory import read_queries
from caliburn.features.work_memory.candidates import MemoryPermissionError
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
    members = await memory.read_members(session, job_file_id, snapshot.position_id)
    original = await memory.read_selected(session, job_file_id, members, source.object_id)
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
    """Return current/historical names and changed state by identity, never title lookup."""
    original = await read_fixed_memory_source(
        session,
        job_file_id=job_file_id,
        source=source,
        interview_through_sequence=interview_through_sequence,
    )
    current_view = await read_queries.bind_published_view(
        session, job_file_id, snapshot_id, MemoryLayer(source.layer.value)
    )
    if current_view.through_sequence > interview_through_sequence:
        raise MemoryPermissionError("The pinned Memory exceeds the interview scope")
    current_members = (
        await memory.read_members(session, job_file_id, current_view.position_id)
        if current_view.position_id is not None
        else {}
    )
    if source.object_id not in current_members:
        # Absence is proven against complete fixed membership, not a failed body lookup.
        return None, original.content.title, True
    current = await memory.read_selected(session, job_file_id, current_members, source.object_id)
    if current.layer != original.layer:
        raise MemoryRevisionNotFoundError("The fixed source changed its Memory layer")
    historical_title = (
        original.content.title if original.content.title != current.content.title else None
    )
    return current.content.title, historical_title, current.revision_id != original.revision_id


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
    new_members = await memory.read_members(session, job_file_id, new_snapshot.position_id)
    after = (
        await memory.read_selected(session, job_file_id, new_members, source.object_id)
        if source.object_id in new_members
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
    old_members = {}
    if old_links:
        old_snapshot = await memory.read_snapshot(session, job_file_id, source.snapshot_id)
        old_members = await memory.read_members(session, job_file_id, old_snapshot.position_id)
    for object_id in sorted(old_links.keys() | new_links.keys()):
        old = (
            await memory.read_selected(session, job_file_id, old_members, object_id)
            if object_id in old_links
            else None
        )
        new = (
            await memory.read_selected(session, job_file_id, new_members, object_id)
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
