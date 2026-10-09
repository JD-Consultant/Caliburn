"""Read-only reference coordinates and a narrowly scoped final revision read."""

from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.occupation_references import persistence
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateError,
)


def candidate_heads_projection(job_file_id: UUID) -> Select[UUID, UUID, UUID]:
    return persistence.candidate_heads_projection(job_file_id)


async def read_head_state(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    generation_id: UUID,
    revision_id: UUID,
) -> OccupationReferenceState:
    operation = await persistence.read_revision(session, job_file_id, execution_id, revision_id)
    if operation is None or operation.result_generation_id != generation_id:
        raise ReferenceStateError("The candidate's saved reference position is unavailable")
    return persistence.state_value(operation.state)
