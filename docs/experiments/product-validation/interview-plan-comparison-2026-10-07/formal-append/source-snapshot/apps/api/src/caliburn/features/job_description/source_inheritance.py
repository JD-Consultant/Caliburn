"""Carry exact citations at the same revision boundary as existing JD content edits."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import persistence, source_persistence, work_queries
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import JdSourceReference, carry_source_references


async def inherited_source_references(
    session: AsyncSession, job_file_id: UUID, before_revision_id: UUID, after_revision_id: UUID
) -> tuple[JdSourceReference, ...]:
    references = await source_persistence.read_source_references(
        session, job_file_id, before_revision_id
    )
    if not references:
        return ()
    before_profile = await persistence.read_revision(session, job_file_id, before_revision_id)
    before_work = await work_queries.read_work_at(session, job_file_id, before_revision_id)
    after_profile = await persistence.read_revision(session, job_file_id, after_revision_id)
    after_work = await work_queries.read_work_at(session, job_file_id, after_revision_id)
    return carry_source_references(
        references,
        source_target_contents(before_profile.profile, before_work),
        source_target_contents(after_profile.profile, after_work),
    )
