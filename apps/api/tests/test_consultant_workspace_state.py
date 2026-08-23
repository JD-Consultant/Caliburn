from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.consultant.workspace_state import (
    WorkspaceDiagnostic,
    WorkspaceDiagnosticSeverity,
    WorkspaceManifest,
    WorkspaceValidationStatus,
    workspace_resource_digest,
)


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
WORKSPACE_RESOURCE_DIGEST_VECTOR = "8d3c7ab80efc84e4d337b3dae067639e97fee83768fb9c9b4c3277cf1639a32d"


def _digest_vector_files() -> dict[str, str | bytes]:
    return {
        "/workspace/z.json": "台北\n",
        "/workspace/a.json": b"{}\n",
    }


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


def test_workspace_resource_digest_has_a_stable_utf8_sorted_fixed_vector() -> None:
    assert workspace_resource_digest(_digest_vector_files()) == (
        WORKSPACE_RESOURCE_DIGEST_VECTOR
    )
    assert workspace_resource_digest(
        {
            "/workspace/a.json": "{}\n",
            "/workspace/z.json": "台北\n",
        }
    ) == WORKSPACE_RESOURCE_DIGEST_VECTOR


def test_valid_manifest_accepts_files_matching_the_resource_digest() -> None:
    manifest = _manifest(
        resource_digest=WORKSPACE_RESOURCE_DIGEST_VECTOR,
        validation_status=WorkspaceValidationStatus.VALID,
    )

    manifest.validate_files(_digest_vector_files())
