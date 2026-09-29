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


class InterviewInputNotFoundError(LookupError):
    """No employee input belongs to this job-file execution."""


class InterviewCompletionConflictError(RuntimeError):
    """An already recorded exchange cannot be replayed with another reply."""


class InterviewReadError(ValueError):
    """The entire selection is invalid, unavailable or outside the App-bound scope."""


@dataclass(frozen=True, slots=True)
class StoredInterviewInput:
    source_id: UUID
    interview_text: str


@dataclass(frozen=True, slots=True)
class FormalInterviewExchange:
    employee_input: InterviewMessage
    consultant_reply: InterviewMessage


@dataclass(frozen=True, slots=True)
class InterviewReadScope:
    job_file_id: UUID
    through_sequence: int

    def __post_init__(self) -> None:
        if type(self.through_sequence) is not int or self.through_sequence < 0:
            raise InterviewReadError("The read boundary must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class RecentInterviews:
    messages: tuple[InterviewMessage, ...]
    context_sequences: tuple[int, ...]
