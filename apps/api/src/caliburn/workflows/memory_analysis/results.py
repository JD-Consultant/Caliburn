"""Memory workflow handoff values, never a publication receipt or private role trace."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from caliburn.features.executions.history_models import ContextPosition
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer


class AnalysisOutcomeError(ValueError):
    """Known invalid/refused model final; only its safe code leaves the role boundary."""

    def __init__(
        self,
        reason_code: Literal[
            "analysis_outcome_malformed",
            "analysis_outcome_refused",
            "analysis_outcome_not_allowed",
        ],
    ) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class SituationGap(BaseModel):
    """Only situation-local questions may cross from B2 to B1."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    target_title: Annotated[str, Field(min_length=1)]
    question: Annotated[str, Field(min_length=1)]
    needed_clarification: Annotated[str, Field(min_length=1)]
    interview_sequences: tuple[Annotated[int, Field(gt=0)], ...]


class AnalysisComplete(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["complete"]


class SituationRework(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["needs_situation"]
    gaps: Annotated[tuple[SituationGap, ...], Field(min_length=1)]


type AnalysisOutcome = AnalysisComplete | SituationRework
_OUTCOME: TypeAdapter[AnalysisOutcome] = TypeAdapter(
    Annotated[AnalysisOutcome, Field(discriminator="status")]
)


def parse_outcome(text: str, layer: MemoryLayer) -> AnalysisOutcome:
    """Validate a saved final result; malformed/refused output is not completion."""
    try:
        outcome = _OUTCOME.validate_json(text, strict=True)
    except ValidationError:
        # ValidationError carries model text. Do not persist or display that payload
        # through ordinary exception tracebacks; native response remains in the saver.
        raise AnalysisOutcomeError("analysis_outcome_malformed") from None
    if layer == MemoryLayer.WORK_SITUATION and not isinstance(outcome, AnalysisComplete):
        raise AnalysisOutcomeError("analysis_outcome_not_allowed")
    return outcome


@dataclass(frozen=True, slots=True)
class MemoryAnalysisResult:
    stage: MemoryBatchPosition
    outcome: AnalysisOutcome
    history_position: ContextPosition
