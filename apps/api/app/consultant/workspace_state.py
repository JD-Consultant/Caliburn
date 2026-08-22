"""Durable identity and validation metadata for one JD workspace."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import Literal, Mapping, cast
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.state import DurableModel


def _sha256_digest(value: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("must be a lowercase sha256 digest")
    return value


Sha256Digest = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(_sha256_digest),
]


class WorkspaceValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"
    CONFLICTED = "conflicted"


class WorkspaceDiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class WorkspaceDiagnostic(DurableModel):
    code: Annotated[str, StringConstraints(min_length=1)]
    message: Annotated[str, StringConstraints(min_length=1)]
    severity: WorkspaceDiagnosticSeverity = WorkspaceDiagnosticSeverity.ERROR


class WorkspaceManifest(DurableModel):
    schema_version: Literal[1] = 1
    generation: int = Field(ge=0)
    resource_digest: Sha256Digest
    approved_baseline_revision: int = Field(ge=0)
    approved_baseline_digest: Sha256Digest
    evidence_basis_digest: Sha256Digest
    validation_status: WorkspaceValidationStatus
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()
    entity_ids_by_handle: dict[str, UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def manifest_is_internally_consistent(self) -> WorkspaceManifest:
        stable_ids = tuple(self.entity_ids_by_handle.values())
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError("duplicate stable ID in workspace handle registry")
        if self.validation_status is WorkspaceValidationStatus.VALID and any(
            diagnostic.severity is WorkspaceDiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        ):
            raise ValueError("valid workspace cannot have error diagnostics")
        return self

    def validate_files(self, files: Mapping[str, str | bytes]) -> None:
        if (
            self.validation_status is WorkspaceValidationStatus.VALID
            and self.resource_digest != workspace_resource_digest(files)
        ):
            raise ValueError("resource digest does not match workspace files")


def workspace_resource_digest(files: Mapping[str, str | bytes]) -> Sha256Digest:
    """Hash exact workspace resource bytes with deterministic path ordering."""

    digest = sha256()
    for path, raw in sorted(files.items(), key=lambda item: str(item[0])):
        path_bytes = str(path).encode("utf-8")
        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
        digest.update(path_bytes)
        digest.update(b"\0")
        digest.update(raw_bytes)
        digest.update(b"\0")
    return cast(Sha256Digest, digest.hexdigest())
