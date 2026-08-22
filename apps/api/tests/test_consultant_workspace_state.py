from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.consultant.workspace_state import (
    WorkspaceDiagnostic,
    WorkspaceDiagnosticSeverity,
    WorkspaceManifest,
    WorkspaceValidationStatus,
)


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _manifest(**changes: object) -> WorkspaceManifest:
    values: dict[str, object] = {
        "generation": 0,
        "resource_digest": DIGEST_A,
        "approved_baseline_revision": 0,
        "approved_baseline_digest": DIGEST_B,
        "evidence_basis_digest": DIGEST_A,
        "validation_status": WorkspaceValidationStatus.UNVALIDATED,
    }
    values.update(changes)
    return WorkspaceManifest.model_validate(values)


def test_manifest_rejects_negative_generation() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _manifest(generation=-1)


def test_manifest_rejects_non_sha256_digest() -> None:
    with pytest.raises(ValidationError, match="sha256"):
        _manifest(resource_digest="not-a-sha256-digest")


def test_manifest_rejects_duplicate_stable_ids_for_different_handles() -> None:
    stable_id = UUID("00000000-0000-0000-0000-000000000101")

    with pytest.raises(ValidationError, match="duplicate stable ID"):
        _manifest(
            entity_ids_by_handle={
                "duty-001": stable_id,
                "task-001": stable_id,
            }
        )


def test_valid_manifest_rejects_error_diagnostic() -> None:
    with pytest.raises(ValidationError, match="valid workspace cannot have error"):
        _manifest(
            validation_status=WorkspaceValidationStatus.VALID,
            diagnostics=(
                WorkspaceDiagnostic(
                    code="invalid-task-reference",
                    message="Task refers to a missing duty.",
                    severity=WorkspaceDiagnosticSeverity.ERROR,
                ),
            ),
        )


def test_valid_manifest_rejects_a_digest_that_does_not_match_workspace_files() -> None:
    manifest = _manifest(validation_status=WorkspaceValidationStatus.VALID)

    with pytest.raises(ValueError, match="resource digest does not match workspace files"):
        manifest.validate_files({"/workspace/header.json": "{}\n"})
