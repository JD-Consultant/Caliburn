"""Public B1 runner; only the Memory parent advances or publishes the batch."""

from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.settings import ModelSettings
from caliburn.workflows.memory_analysis.results import MemoryAnalysisResult, SituationGap
from caliburn.workflows.memory_analysis.runner import AnalysisRecovery, MemoryAnalysisRunner


@dataclass(frozen=True, slots=True)
class WorkSituationAnalystRunner:
    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings

    async def run(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        previous: MemoryAnalysisResult | None = None,
        gaps: tuple[SituationGap, ...] = (),
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult:
        return await MemoryAnalysisRunner(
            self.sessions, self.checkpointer, self.client, self.settings
        ).run(
            writer,
            stage,
            role=AgentRole.WORK_SITUATION_ANALYST,
            instructions=SITUATION_INSTRUCTIONS,
            previous=previous,
            gaps=gaps,
            recovery=recovery,
        )
