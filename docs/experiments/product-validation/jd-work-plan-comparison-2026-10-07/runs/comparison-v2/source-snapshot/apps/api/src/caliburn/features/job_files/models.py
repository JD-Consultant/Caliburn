"""Job-file values; names are labels, never data-isolation identities."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class JobFileNotFoundError(LookupError):
    """No job file exists in the requested scope."""


class CreationCommandConflictError(ValueError):
    """A creation command has already been used with different input."""


class RenameCommandConflictError(ValueError):
    """A rename command has already been used with different input."""


class StaleJobFileNameError(ValueError):
    """The current label has changed since the client read it."""


def validate_label(value: str, field_name: str) -> None:
    if not value.strip() or len(value) > 200 or "\x00" in value:
        raise ValueError(f"{field_name} must contain 1–200 characters, not be blank or contain NUL")


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
            validate_label(value, name)


@dataclass(frozen=True, slots=True)
class RenameJobFile:
    command_id: UUID
    display_name: str
    expected_name_revision: int

    def __post_init__(self) -> None:
        validate_label(self.display_name, "display_name")
        if type(self.expected_name_revision) is not int or not (
            1 <= self.expected_name_revision <= 9007199254740991
        ):
            raise ValueError("expected_name_revision must be a positive safe integer")


@dataclass(frozen=True, slots=True)
class JobFile:
    job_file_id: UUID
    display_name: str
    name_revision: int
    employee_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobFileCreation:
    job_file: JobFile
    is_new: bool
