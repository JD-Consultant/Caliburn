"""Human Memory browsing pins a publication, independently of active model bindings."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.job_files.queries import read_job_file
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision


@dataclass(frozen=True, slots=True)
class PublishedMemoryMap:
    snapshot_id: UUID | None
    covered_through_sequence: int
    work_situations: tuple[MemoryMapEntry, ...]
    work_understandings: tuple[MemoryMapEntry, ...]


class PublishedMemoryWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_latest(self, job_file_id: UUID) -> PublishedMemoryMap:
        async with consistent_read_session(self.sessions) as session:
            await read_job_file(session, job_file_id)
            snapshot = await candidate_queries.read_latest_snapshot(session, job_file_id)
            if snapshot is None:
                return PublishedMemoryMap(None, 0, (), ())
            situations = await candidate_queries.read_snapshot_map(
                session, job_file_id, snapshot.snapshot_id, MemoryLayer.WORK_SITUATION
            )
            understandings = await candidate_queries.read_snapshot_map(
                session, job_file_id, snapshot.snapshot_id, MemoryLayer.WORK_UNDERSTANDING
            )
            return PublishedMemoryMap(
                snapshot.snapshot_id, snapshot.covered_through_sequence, situations, understandings
            )

    async def read_object(
        self, job_file_id: UUID, snapshot_id: UUID, object_id: UUID
    ) -> MemoryObjectRevision:
        async with consistent_read_session(self.sessions) as session:
            await read_job_file(session, job_file_id)
            return await candidate_queries.read_snapshot_object(
                session, job_file_id, snapshot_id, object_id
            )
