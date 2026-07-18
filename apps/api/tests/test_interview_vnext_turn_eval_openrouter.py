"""V3-5 E7:OpenRouter live wiring 與 CLI 的無 key / DB safety / contamination gate。

Live batch 不進一般 CI;此檔只驗「不需 key 的路徑」:CLI 參數 gate、無
OPENROUTER_API_KEY 立即 exit 2 且零 network/DB/output、eval DB 名稱安全、
以及 route contamination 由既有 adapter 判定的 disposition 分類。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from evals.interview_vnext import turn_eval_cli as cli
from evals.interview_vnext.live_wiring import (
    EvalDatabaseError,
    resolve_eval_database_url,
)


CASES_ROOT = Path(__file__).resolve().parents[1] / "evals/interview_vnext/cases"


def base_live_argv(tmp_path, *, with_budget=True, with_checklist=True):
    argv = [
        "live-batch",
        "--suite-version", "turn-interpret-pilot.v1",
        "--cases-root", str(CASES_ROOT),
        "--database-url-env", "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "--model", "anthropic/claude-sonnet-5",
        "--upstream-endpoint", "anthropic",
        "--data-collection", "deny",
        "--zdr-required", "false",
        "--reasoning-effort", "medium",
        "--output-dir", str(tmp_path / "out"),
    ]
    if with_budget:
        argv += [
            "--max-inference-calls", "120",
            "--max-observed-cost-usd", "10.00",
            "--max-wall-clock-minutes", "180",
        ]
    if with_checklist:
        argv += [
            "--account-checklist-confirmed-at", "2026-07-18T00:00:00+00:00",
            "--account-checklist-confirmed-by", "owner",
        ]
    return argv


# ── no key ───────────────────────────────────────────────────────────────────


def test_live_batch_without_key_exits_2_and_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/caliburn_test",
    )
    out_dir = tmp_path / "out"
    rc = cli.main(base_live_argv(tmp_path))
    assert rc == cli.EXIT_USAGE
    assert not out_dir.exists()  # 無 output dir


def test_require_api_key_raises_without_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(cli.UsageError):
        cli.require_api_key()


# ── budget / checklist gates ─────────────────────────────────────────────────


def test_missing_budget_exits_2(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/caliburn_test",
    )
    rc = cli.main(base_live_argv(tmp_path, with_budget=False))
    assert rc == cli.EXIT_USAGE


def test_missing_checklist_exits_2(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/caliburn_test",
    )
    rc = cli.main(base_live_argv(tmp_path, with_checklist=False))
    assert rc == cli.EXIT_USAGE


def test_budget_must_be_positive(monkeypatch):
    with pytest.raises(cli.UsageError):
        cli.validate_budget(
            max_inference_calls=0,
            max_observed_cost_usd="10",
            max_wall_clock_minutes=180,
        )
    with pytest.raises(cli.UsageError):
        cli.validate_budget(
            max_inference_calls=10,
            max_observed_cost_usd="-1",
            max_wall_clock_minutes=180,
        )
    budget = cli.validate_budget(
        max_inference_calls=120,
        max_observed_cost_usd="10.00",
        max_wall_clock_minutes=180,
    )
    assert budget.max_observed_cost_usd == Decimal("10.00")


def test_checklist_requires_utc(monkeypatch):
    with pytest.raises(cli.UsageError):
        cli.validate_account_checklist(
            confirmed_at="2026-07-18T00:00:00", confirmed_by="owner"
        )
    with pytest.raises(cli.UsageError):
        cli.validate_account_checklist(
            confirmed_at="2026-07-18T00:00:00+08:00", confirmed_by="owner"
        )
    checklist = cli.validate_account_checklist(
        confirmed_at="2026-07-18T00:00:00+00:00", confirmed_by="owner"
    )
    assert checklist.confirmed_by == "owner"


# ── eval DB safety(§17.3)────────────────────────────────────────────────────


def test_eval_db_only_from_env_and_rejects_production(monkeypatch):
    monkeypatch.delenv("INTERVIEW_VNEXT_EVAL_DATABASE_URL", raising=False)
    with pytest.raises(EvalDatabaseError, match="not set"):
        resolve_eval_database_url("INTERVIEW_VNEXT_EVAL_DATABASE_URL")

    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/caliburn",
    )
    with pytest.raises(EvalDatabaseError, match="_test"):
        resolve_eval_database_url("INTERVIEW_VNEXT_EVAL_DATABASE_URL")

    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/caliburn_test",
    )
    url = resolve_eval_database_url("INTERVIEW_VNEXT_EVAL_DATABASE_URL")
    assert url.endswith("caliburn_test")

    monkeypatch.setenv(
        "INTERVIEW_VNEXT_EVAL_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/turn_eval?sslmode=disable",
    )
    assert resolve_eval_database_url("INTERVIEW_VNEXT_EVAL_DATABASE_URL")


# ── contamination → harness_invalid disposition ──────────────────────────────


def test_route_contamination_is_harness_invalid():
    """A DB/runner exception during a trial classifies as harness_invalid (§9.4)."""

    from evals.interview_vnext.scheduler import classify_disposition
    from evals.interview_vnext.contracts import TrialDisposition

    disposition, reason = classify_disposition(
        None, error=RuntimeError("route contaminated: resolved model mismatch")
    )
    assert disposition == TrialDisposition.HARNESS_INVALID
    assert reason == "RuntimeError"


def test_timeout_reason_is_infrastructure_invalid():
    from evals.interview_vnext.scheduler import _INFRASTRUCTURE_MARKERS

    assert any(m in "provider.timeout" for m in _INFRASTRUCTURE_MARKERS)


# ── validate-suite / reference-gate / report CLI(無 key/DB)──────────────────


def test_validate_suite_cli(capsys):
    rc = cli.main(
        [
            "validate-suite",
            "--suite-version", "turn-interpret-pilot.v1",
            "--cases-root", str(CASES_ROOT),
        ]
    )
    assert rc == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "12 cases" in out
    assert "suite_hash=" in out


def test_reference_gate_cli(capsys):
    rc = cli.main(
        [
            "reference-gate",
            "--suite-version", "turn-interpret-pilot.v1",
            "--cases-root", str(CASES_ROOT),
        ]
    )
    assert rc == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "12/12 passed" in out


def test_validate_suite_reports_integrity_error(tmp_path, capsys):
    # 空目錄 → 缺 split → EXIT_PREFLIGHT(harness integrity)
    rc = cli.main(
        [
            "validate-suite",
            "--suite-version", "turn-interpret-pilot.v1",
            "--cases-root", str(tmp_path),
        ]
    )
    assert rc == cli.EXIT_PREFLIGHT


def test_no_key_makes_no_catalog_or_db_call(tmp_path, monkeypatch):
    """live-batch 無 key 時,validate_live_batch_args 在任何 network 前就 raise。"""

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class Args:
        account_checklist_confirmed_at = "2026-07-18T00:00:00+00:00"
        account_checklist_confirmed_by = "owner"
        max_inference_calls = 120
        max_observed_cost_usd = "10.00"
        max_wall_clock_minutes = 180
        database_url_env = "INTERVIEW_VNEXT_EVAL_DATABASE_URL"
        model = "anthropic/claude-sonnet-5"
        upstream_endpoint = "anthropic"
        data_collection = "deny"
        zdr_required = "false"
        reasoning_effort = "medium"

    with pytest.raises(cli.UsageError, match="OPENROUTER_API_KEY"):
        cli.validate_live_batch_args(Args())


# ── end-to-end mocked orchestration on real PostgreSQL ───────────────────────


async def test_mocked_batch_orchestrator_writes_bundle_and_report(
    postgres_session_factory, tmp_path
):
    from uuid import uuid4

    from evals.interview_vnext.batch_orchestrator import orchestrate_mocked_batch
    from evals.interview_vnext.contracts import TurnEvalBatchReport
    from evals.interview_vnext.loader import load_suite
    from evals.interview_vnext.turn_eval_runner import cleanup_trial_rows

    suite = load_suite(CASES_ROOT, suite_version="turn-interpret-pilot.v1")
    batch_id = uuid4()
    result = await orchestrate_mocked_batch(
        suite,
        session_factory=postgres_session_factory,
        output_dir=tmp_path,
        batch_id=batch_id,
        trial_started_at=datetime(2026, 7, 18, 9, 0, tzinfo=UTC),
        git_sha="0" * 40,
        dirty_worktree=True,
    )
    try:
        assert result.decision == "TURN_GATE_PASS_ENGINEERING"
        report = TurnEvalBatchReport.model_validate_json(
            result.report_path.read_text("utf-8")
        )
        assert report.promotion_eligible is False  # mocked never promotion-eligible
        assert len(report.case_matrix) == 12
        assert all(entry.pass_pow_3 for entry in report.case_matrix)
        # 36 trial 目錄 + batch-report.md 都在
        assert (result.batch_dir / "batch-report.md").is_file()
        trial_dirs = list(result.batch_dir.glob("trials/*/slot-*/trial-attempt-*"))
        assert len(trial_dirs) == 36
    finally:
        await cleanup_trial_rows(postgres_session_factory, list(result.trial_ids))
