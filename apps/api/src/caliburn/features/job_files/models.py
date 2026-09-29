"""Job-file values; names are labels, never data-isolation identities."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class JobFileNotFoundError(LookupError):
    """No job file exists in the requested scope."""


class CreationCommandConflictError(ValueError):
    """A creation command has already been used with different input."""


@dataclass(frozen=True, slots=True)
class CreateJobFile:
    command_id: UUID
    display_name: str
    employee_name: str

    def __post_init__(self) -> None:
        for name, value in (
            ("display_name", self.display_name),
            ("employee_name", self.employee_name),
        ):
            if not value.strip() or len(value) > 200 or "\x00" in value:
                raise ValueError(
                    f"{name} must contain 1–200 characters, not be blank or contain NUL"
                )


@dataclass(frozen=True, slots=True)
class JobFile:
    job_file_id: UUID
    display_name: str
    employee_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobFileCreation:
    job_file: JobFile
    is_new: bool
