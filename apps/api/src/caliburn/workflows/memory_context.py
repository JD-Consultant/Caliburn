"""Read fixed Memory stage inputs through product owners, without model or saver formats."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.interviews.models import RecentInterviews
from caliburn.features.work_memory import candidate_queries as candidates
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryMapEntry, MemorySourceWindow
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.features.work_memory.sources import read_required_interviews


@dataclass(frozen=True, slots=True)
class MemoryAnalysisContextData:
    source_window: MemorySourceWindow
    maps: dict[MemoryLayer, tuple[MemoryMapEntry, ...]]
    recent: RecentInterviews | None


class MemoryAnalysisContextWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def read(
        self, writer: ExecutionWriter, stage: MemoryBatchPosition
    ) -> MemoryAnalysisContextData:
        """Use the original batch K/F; B1 receives its full range and lawful guidance."""
        async with self._sessions.begin() as session:
            await executions.lock_active_writer(session, writer)
        async with self._sessions() as session:
            record = await candidates.require_stage(session, stage)
            window = candidates.source_window(record)
            layers = (
                (MemoryLayer.WORK_SITUATION,)
                if stage.phase == MemoryLayer.WORK_SITUATION
                else tuple(MemoryLayer)
            )
            maps = {
                layer: await candidates.read_candidate_map(session, stage, layer)
                for layer in layers
            }
            recent = (
                await read_required_interviews(session, window)
                if stage.phase == MemoryLayer.WORK_SITUATION
                else None
            )
        return MemoryAnalysisContextData(window, maps, recent)
