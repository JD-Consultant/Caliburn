"""Public B2 runner; private history is never passed to B1 as gap context."""

from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.agents.memory_analysis.runner import MemoryAnalysisRunner
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.settings import ModelSettings
from caliburn.workflows.memory_analysis.results import AnalysisRecovery, MemoryAnalysisResult


@dataclass(frozen=True, slots=True)
class WorkUnderstandingAnalystRunner:
    sessions: async_sessionmaker[AsyncSession]
    checkpointer: BaseCheckpointSaver[str]
    client: AsyncOpenAI
    settings: ModelSettings

    async def run(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        situation_changes: list[dict[str, JsonValue]],
        previous: MemoryAnalysisResult | None = None,
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult:
        return await MemoryAnalysisRunner(
            self.sessions, self.checkpointer, self.client, self.settings
        ).run(
            writer,
            stage,
            role=AgentRole.WORK_UNDERSTANDING_ANALYST,
            instructions=UNDERSTANDING_INSTRUCTIONS,
            previous=previous,
            situation_changes=situation_changes,
            recovery=recovery,
        )
