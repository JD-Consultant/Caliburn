"""Create fixed Memory aggregates; caller owns transaction and candidate authorization."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import revision_persistence as persistence
from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemorySourceWindow,
)
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)
from caliburn.features.work_memory.sources import read_reference_sources


async def write_object_revision(
    session: AsyncSession,
    window: MemorySourceWindow,
    *,
    layer: MemoryLayer,
    content: MemoryContent,
    previous: MemoryRevisionReference | None = None,
    interview_references: frozenset[UUID] = frozenset(),
    work_situation_references: frozenset[MemoryRevisionReference] = frozenset(),
) -> MemoryObjectRevision:
    """Store complete internal edit results, not a model whole-body replacement tool.

    A candidate command must first bind the current position, role and object IDs.
    This primitive creates no current pointer, operation receipt or publication.
    It may reuse an unchanged body, but never merges distinct revision identities.
    """
    prior = (
        await read_fixed_revision(session, job_file_id=window.job_file_id, reference=previous)
        if previous is not None
        else None
    )
    if prior is not None and prior.layer != layer:
        raise InvalidMemoryChangeError("An object cannot change its Memory layer")
    body_unchanged = prior is not None and prior.content.body == content.body
    revision = MemoryObjectRevision(
        object_id=prior.object_id if prior is not None else uuid4(),
        revision_id=uuid4(),
        body_id=prior.body_id if prior is not None and body_unchanged else uuid4(),
        layer=layer,
        content=content,
        interview_references=interview_references,
        work_situation_references=work_situation_references,
    )
    await _require_valid_sources(session, window, revision)
    if (
        prior is not None
        and prior.content == content
        and prior.interview_references == interview_references
        and prior.work_situation_references == work_situation_references
    ):
        return prior
    if prior is None:
        await persistence.insert_object(session, window.job_file_id, revision.object_id, layer)
    if not body_unchanged:
        await persistence.insert_body(
            session, window.job_file_id, revision.object_id, revision.body_id, content.body
        )
    await persistence.insert_revision(session, window.job_file_id, revision)
    return revision


async def read_fixed_revision(
    session: AsyncSession, *, job_file_id: UUID, reference: MemoryRevisionReference
) -> MemoryObjectRevision:
    """Internal fixed-history read; does not expose a model history-selection tool."""
    revision = await persistence.read_revision(
        session, job_file_id, reference.object_id, reference.revision_id
    )
    if revision is None:
        raise MemoryRevisionNotFoundError("Fixed Memory revision is unavailable in this job file")
    return revision


async def _require_valid_sources(
    session: AsyncSession, window: MemorySourceWindow, revision: MemoryObjectRevision
) -> None:
    interview_sources = set(revision.interview_references)
    for reference in revision.work_situation_references:
        situation = await read_fixed_revision(
            session, job_file_id=window.job_file_id, reference=reference
        )
        if situation.layer != MemoryLayer.WORK_SITUATION:
            raise InvalidMemoryChangeError("Understanding sources must be work situations")
        interview_sources.update(situation.interview_references)
    await read_reference_sources(session, window, source_ids=frozenset(interview_sources))
