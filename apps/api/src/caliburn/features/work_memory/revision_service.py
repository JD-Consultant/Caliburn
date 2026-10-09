"""Create fixed Memory aggregates; caller owns transaction and candidate authorization."""

from dataclasses import replace
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
    MemoryRevisionHeader,
    MemoryRevisionNotFoundError,
    MemoryRevisionReference,
)
from caliburn.features.work_memory.sources import read_reference_headers


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
    await _require_valid_sources(session, window, interview_references, work_situation_references)
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
    await persistence.insert_revisions(session, window.job_file_id, (revision.header,))
    return revision


async def read_fixed_revision(
    session: AsyncSession, *, job_file_id: UUID, reference: MemoryRevisionReference
) -> MemoryObjectRevision:
    """Internal fixed-history read; does not expose a model history-selection tool."""
    revisions = await read_fixed_revisions(
        session, job_file_id=job_file_id, references=frozenset({reference})
    )
    return revisions[reference]


async def read_fixed_headers(
    session: AsyncSession, *, job_file_id: UUID, references: frozenset[MemoryRevisionReference]
) -> dict[MemoryRevisionReference, MemoryRevisionHeader]:
    """Require every requested sealed revision in the file; never silently omit corruption."""
    headers = await persistence.read_revision_headers(session, job_file_id, references)
    if headers.keys() != references:
        raise MemoryRevisionNotFoundError("Fixed Memory revision is unavailable in this job file")
    return headers


async def read_fixed_revisions(
    session: AsyncSession, *, job_file_id: UUID, references: frozenset[MemoryRevisionReference]
) -> dict[MemoryRevisionReference, MemoryObjectRevision]:
    """Complete only a caller-selected fixed revision set, with bounded SQL round trips."""
    headers = await read_fixed_headers(session, job_file_id=job_file_id, references=references)
    bodies = await persistence.read_revision_bodies(session, job_file_id, references)
    if bodies.keys() != references:
        raise MemoryRevisionNotFoundError("Fixed Memory body is unavailable in this job file")
    return {ref: header.with_body(bodies[ref]) for ref, header in headers.items()}


async def rebind_understanding_sources(
    session: AsyncSession,
    window: MemorySourceWindow,
    bindings: dict[MemoryRevisionReference, frozenset[MemoryRevisionReference]],
) -> dict[UUID, MemoryRevisionReference]:
    """Change fixed bindings only, preserving immutable content without reading its body.

    The candidate owner decides which sources to retain or advance. This revision owner
    validates the complete set against the same fixed window before writing any revision.
    Caller retains transaction, position authorization and publication responsibility.
    Supply one selected original revision per understanding, as guaranteed by a position.
    """
    if len({reference.object_id for reference in bindings}) != len(bindings):
        raise InvalidMemoryChangeError("Select one revision per understanding for rebinding")
    originals = await read_fixed_headers(
        session, job_file_id=window.job_file_id, references=frozenset(bindings)
    )
    for reference in bindings:
        if originals[reference].layer != MemoryLayer.WORK_UNDERSTANDING:
            raise InvalidMemoryChangeError("Only understanding sources may be rebound")
    await _require_valid_sources(
        session,
        window,
        frozenset(),
        frozenset(source for refs in bindings.values() for source in refs),
    )
    result = {}
    revisions = []
    for reference, sources in bindings.items():
        original = originals[reference]
        if sources == original.work_situation_references:
            result[original.object_id] = reference
            continue
        revised = replace(original, revision_id=uuid4(), work_situation_references=sources)
        revisions.append(revised)
        result[revised.object_id] = MemoryRevisionReference(revised.object_id, revised.revision_id)
    await persistence.insert_revisions(session, window.job_file_id, tuple(revisions))
    return result


async def _require_valid_sources(
    session: AsyncSession,
    window: MemorySourceWindow,
    interview_references: frozenset[UUID],
    work_situation_references: frozenset[MemoryRevisionReference],
) -> None:
    interview_sources = set(interview_references)
    situations = await read_fixed_headers(
        session, job_file_id=window.job_file_id, references=work_situation_references
    )
    for situation in situations.values():
        if situation.layer != MemoryLayer.WORK_SITUATION:
            raise InvalidMemoryChangeError("Understanding sources must be work situations")
        interview_sources.update(situation.interview_references)
    await read_reference_headers(session, window, source_ids=frozenset(interview_sources))
