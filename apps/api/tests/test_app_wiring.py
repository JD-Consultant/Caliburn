"""ADR 0017: configure() is the single composition root. Assert it mounts every
REST router + /healthz, so the route set can't silently drift between the app
tests hit (main) and the app production runs (copilotkit_live_app)."""
from fastapi import FastAPI

from app.app_factory import configure


def _paths(app: FastAPI) -> list[str]:
    return [getattr(r, "path", "") for r in app.routes]


def test_configure_mounts_all_rest_routers_and_health():
    paths = _paths(configure(FastAPI()))
    assert "/healthz" in paths
    # one representative endpoint per router group (users / job_profiles /
    # documents / ai), all under the shared /api/v1 prefix
    assert "/api/v1/users/" in paths
    assert "/api/v1/job-profiles/" in paths
    assert any(p == "/api/v1/job-profiles/{profile_id}/document" for p in paths)
    assert any(p.startswith("/api/v1/ai/") for p in paths)
