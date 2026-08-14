"""The composition root exposes only the current local job-analysis API."""
from fastapi import FastAPI

from app.app_factory import configure
from app.config import Settings


def _paths(app: FastAPI) -> list[str]:
    # FastAPI 0.141 keeps included routers lazy; OpenAPI is the public flattened
    # route contract and therefore the stable wiring assertion surface.
    return list(app.openapi()["paths"])


def test_configure_mounts_current_job_analysis_api_and_health():
    paths = _paths(configure(FastAPI()))
    assert "/healthz" in paths
    assert all(
        path.startswith("/api/v1/job-analysis/")
        for path in paths
        if path.startswith("/api/v1/")
    )
    assert "/api/v1/job-analysis/consultant-documents" in paths
    assert any(path.endswith("/{document_id}/snapshot") for path in paths)
    assert any(path.endswith("/{document_id}/answers") for path in paths)
    assert any(
        path.endswith("/{document_id}/reviews/{changeset_id}")
        for path in paths
    )
    assert not any("/documents/" in path for path in paths)


def test_configure_does_not_mount_retired_routes():
    paths = set(_paths(configure(FastAPI())))
    assert not any(path.startswith("/api/v1/users") for path in paths)
    assert not any(path.startswith("/api/v1/job-profiles") for path in paths)
    assert not any(path.startswith("/api/v1/occupations") for path in paths)
    assert not any(path.startswith("/api/v1/ai/") for path in paths)
    assert not any("interview" in path for path in paths)


def test_consultant_defaults_pin_one_exact_versioned_model_route():
    fields = Settings.model_fields

    assert fields["consultant_profile_id"].default == "primary-consultant"
    assert fields["consultant_profile_revision"].default == 1
    assert fields["consultant_model"].default == "anthropic/claude-opus-5"
    assert fields["consultant_provider"].default == "Anthropic"
    assert fields["consultant_max_output_tokens"].default == 4096
    assert fields["consultant_timeout_seconds"].default == 90.0
