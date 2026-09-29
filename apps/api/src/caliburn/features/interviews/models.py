"""Source identity, true speaker and per-job-file formal ordering."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InterviewSpeaker(StrEnum):
    APP = "app"
    EMPLOYEE = "employee"
    CONSULTANT = "consultant"


@dataclass(frozen=True, slots=True)
class InterviewMessage:
    source_id: UUID
    interview_sequence: int
    speaker: InterviewSpeaker
    interview_text: str


class InputCommandConflictError(RuntimeError):
    """The same submission command cannot be reused for different original text."""


@dataclass(frozen=True, slots=True)
class SubmitInterviewInput:
    job_file_id: UUID
    command_id: UUID
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip() or "\x00" in self.text:
            raise ValueError("Input must contain non-whitespace text without NUL")


@dataclass(frozen=True, slots=True)
class AcceptedInterviewInput:
    job_file_id: UUID
    command_id: UUID
    source_id: UUID
    execution_id: UUID


@dataclass(frozen=True, slots=True)
class InputAcceptance:
    accepted: AcceptedInterviewInput
    is_new: bool
