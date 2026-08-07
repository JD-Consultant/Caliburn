"""ADR 0017: configure() is the single composition root. Assert it mounts every
REST router + /healthz. T12 後測試與 production 同一入口(app.main;
run_live.py 直起 app.main:app,copilotkit_live_app 已退場)。"""
from fastapi import FastAPI

from app.app_factory import configure
from app.config import Settings


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
    assert "/api/v1/occupations" in paths  # root catalog search (ADR 0019)
    assert any(p.startswith("/api/v1/ai/") for p in paths)
    assert "/api/v1/job-analysis/documents" in paths
    assert any(path.endswith("/{document_id}/consultation") for path in paths)
    assert any(path.endswith("/{document_id}/turns") for path in paths)
    assert any(
        path.endswith("/{document_id}/proposals/{proposal_id}/decisions")
        for path in paths
    )


def test_job_analysis_consultant_defaults_pin_one_exact_a6_route():
    fields = Settings.model_fields

    assert fields["job_analysis_model"].default == "anthropic/claude-opus-5"
    assert fields["job_analysis_provider"].default == "anthropic"
    assert fields["job_analysis_timeout_s"].default == 90.0
    # 2026-08-07 真人試跑撞到 `truncated: response hit the output token limit`，
    # 4096 從 4096 提到 16384。**model／provider／timeout 沒有動**——A6 的路由本身不變，
    # 只是給它寫完一次 Task Analysis 輸出的空間（ADR 0042 決定 5 的 A6 性質不受影響）。
    assert fields["job_analysis_max_output_tokens"].default == 16384
