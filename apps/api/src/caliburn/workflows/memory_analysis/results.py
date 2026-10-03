"""Memory workflow handoff values, never a publication receipt or private role trace."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from caliburn.agent_execution.context_compaction import HeldCompaction, HeldPreparationCount
from caliburn.agent_execution.tool_steps import HeldInputCount, HeldModelResponse
from caliburn.features.executions.history_models import ContextPosition
from caliburn.features.work_memory.candidates import MemoryBatchPosition

type AnalysisRecovery = HeldModelResponse | HeldInputCount | HeldCompaction | HeldPreparationCount


class AnalysisOutcomeError(ValueError):
    """Known invalid/refused model final; only its safe code leaves the role boundary."""

    def __init__(
        self,
        reason_code: Literal[
            "analysis_outcome_malformed",
            "analysis_outcome_refused",
        ],
    ) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class AnalysisComplete(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["complete"]


def parse_outcome(text: str) -> AnalysisComplete:
    """Validate a saved final result; malformed/refused output is not completion."""
    try:
        outcome = AnalysisComplete.model_validate_json(text, strict=True)
    except ValidationError:
        # ValidationError carries model text. Do not persist or display that payload
        # through ordinary exception tracebacks; native response remains in the saver.
        raise AnalysisOutcomeError("analysis_outcome_malformed") from None
    return outcome


@dataclass(frozen=True, slots=True)
class MemoryAnalysisResult:
    stage: MemoryBatchPosition
    outcome: AnalysisComplete
    history_position: ContextPosition
