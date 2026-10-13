"""JD evidence selection intents; source qualification belongs to workflows."""

from dataclasses import dataclass

from caliburn.features.job_description.sources import MemorySourceLayer


@dataclass(frozen=True, slots=True)
class InterviewSourceSelection:
    interview_sequence: int


@dataclass(frozen=True, slots=True)
class MemorySourceSelection:
    layer: MemorySourceLayer
    target_title: str


type JdSourceSelection = InterviewSourceSelection | MemorySourceSelection
