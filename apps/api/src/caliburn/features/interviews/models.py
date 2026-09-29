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
