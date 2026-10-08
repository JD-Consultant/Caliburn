"""Pure JD profile values and explicit partial-edit intent; no storage or transport."""

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID


class JdCommandConflictError(ValueError):
    """A JD command identity was reused with different intent."""


class StaleJdRevisionError(ValueError):
    """A new edit no longer targets the current formal JD revision."""


class InvalidProfileChangeError(ValueError):
    """The requested profile changes cannot be applied as one unambiguous operation."""


class ProfileField(StrEnum):
    JOB_TITLE = "job_title"
    ORGANIZATION_UNIT = "organization_unit"
    REPORTS_TO = "reports_to"
    PURPOSE = "purpose"


@dataclass(frozen=True, slots=True)
class JdProfile:
    job_title: str | None = None
    organization_unit: str | None = None
    reports_to: str | None = None
    purpose: str | None = None


@dataclass(frozen=True, slots=True)
class SetProfileField:
    field: ProfileField
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip() or "\x00" in self.value:
            raise InvalidProfileChangeError("A set value must contain nonblank text without NUL")


@dataclass(frozen=True, slots=True)
class ClearProfileField:
    field: ProfileField


type ProfileChange = SetProfileField | ClearProfileField


@dataclass(frozen=True, slots=True)
class ReviseJdProfile:
    command_id: UUID
    expected_revision_id: UUID
    changes: tuple[ProfileChange, ...]

    def __post_init__(self) -> None:
        fields = [change.field for change in self.changes]
        if not fields or len(fields) != len(set(fields)):
            raise InvalidProfileChangeError("Choose at least one field, and change each field once")


@dataclass(frozen=True, slots=True)
class JdProfileRevision:
    revision_id: UUID
    profile: JdProfile


def apply_profile_changes(profile: JdProfile, changes: tuple[ProfileChange, ...]) -> JdProfile:
    """Unmentioned fields remain untouched; clearing is distinct from empty text."""
    values = {
        change.field.value: change.value if isinstance(change, SetProfileField) else None
        for change in changes
    }
    return replace(profile, **values)


def profile_change_payload(changes: tuple[ProfileChange, ...]) -> list[dict[str, str]]:
    """Original typed intent for replay comparison, not a second editable profile."""
    return [
        {"action": "set_field", "field": change.field.value, "value": change.value}
        if isinstance(change, SetProfileField)
        else {"action": "clear_field", "field": change.field.value}
        for change in changes
    ]
