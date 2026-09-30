"""Agent composition for the two public role APIs; no lifecycle or publication logic."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import JsonValue

from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_analysis.results import MemoryAnalysisResult, SituationGap
from caliburn.workflows.memory_analysis.runner import AnalysisRecovery


class SituationAnalysis(Protocol):
    async def run(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        previous: MemoryAnalysisResult | None = None,
        gaps: tuple[SituationGap, ...] = (),
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult: ...


class UnderstandingAnalysis(Protocol):
    async def run(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        previous: MemoryAnalysisResult | None = None,
        situation_changes: list[dict[str, JsonValue]],
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class MemoryRoleDispatch:
    situation: SituationAnalysis
    understanding: UnderstandingAnalysis

    async def __call__(
        self,
        writer: ExecutionWriter,
        stage: MemoryBatchPosition,
        *,
        previous: MemoryAnalysisResult | None = None,
        gaps: tuple[SituationGap, ...] = (),
        situation_changes: list[dict[str, JsonValue]] | None = None,
        recovery: AnalysisRecovery | None = None,
    ) -> MemoryAnalysisResult:
        if stage.phase == MemoryLayer.WORK_SITUATION:
            return await self.situation.run(
                writer, stage, previous=previous, gaps=gaps, recovery=recovery
            )
        if situation_changes is None or gaps:
            raise ValueError("B2 requires actual changes and cannot receive B1-directed gaps")
        return await self.understanding.run(
            writer, stage, previous=previous, situation_changes=situation_changes, recovery=recovery
        )
