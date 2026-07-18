"""Turn eval CLI (§17):validate-suite / reference-gate / mocked-batch /
live-batch / export-review / import-review / report.

Exit codes (§17.2):
  0  command completed and its own validation passed
  1  gate fail / review incomplete / batch incomplete
  2  usage / missing key,env,checklist,budget arg (no network, no run)
  3  preflight / catalog / config / harness integrity error
  4  unexpected runner / DB / Capture error

``live-batch`` with no ``OPENROUTER_API_KEY`` exits 2 before creating a batch
dir, querying the catalog, or touching the database.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .live_wiring import API_KEY_ENV, EvalDatabaseError, resolve_eval_database_url


EXIT_OK = 0
EXIT_GATE_FAIL = 1
EXIT_USAGE = 2
EXIT_PREFLIGHT = 3
EXIT_RUNNER = 4

DEFAULT_CASES_ROOT = Path(__file__).with_name("cases")


class UsageError(Exception):
    """A usage/argument error → exit 2, no network, no run."""


@dataclass(frozen=True)
class AccountChecklist:
    confirmed_at: datetime
    confirmed_by: str


def _parse_iso_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UsageError(f"invalid ISO-8601 UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise UsageError("account checklist timestamp must be UTC (offset +00:00)")
    return parsed


def validate_account_checklist(
    *, confirmed_at: str | None, confirmed_by: str | None
) -> AccountChecklist:
    """§10.2:owner 確認欄位缺任一 → exit 2,無 catalog、無 run、無 output dir。"""

    if not confirmed_at or not confirmed_by or not confirmed_by.strip():
        raise UsageError(
            "live batch requires --account-checklist-confirmed-at and "
            "--account-checklist-confirmed-by"
        )
    return AccountChecklist(
        confirmed_at=_parse_iso_utc(confirmed_at),
        confirmed_by=confirmed_by.strip(),
    )


@dataclass(frozen=True)
class Budget:
    max_inference_calls: int
    max_observed_cost_usd: Decimal
    max_wall_clock_minutes: int


def validate_budget(
    *,
    max_inference_calls: int | None,
    max_observed_cost_usd: str | None,
    max_wall_clock_minutes: int | None,
) -> Budget:
    """§10.3:三個上限都必填正值,否則 exit 2。"""

    if max_inference_calls is None or max_inference_calls <= 0:
        raise UsageError("--max-inference-calls must be a positive integer")
    if max_wall_clock_minutes is None or max_wall_clock_minutes <= 0:
        raise UsageError("--max-wall-clock-minutes must be a positive integer")
    if max_observed_cost_usd is None:
        raise UsageError("--max-observed-cost-usd is required")
    try:
        cost = Decimal(max_observed_cost_usd)
    except InvalidOperation as exc:
        raise UsageError("--max-observed-cost-usd must be a decimal") from exc
    if cost <= 0:
        raise UsageError("--max-observed-cost-usd must be positive")
    return Budget(
        max_inference_calls=max_inference_calls,
        max_observed_cost_usd=cost,
        max_wall_clock_minutes=max_wall_clock_minutes,
    )


def require_api_key() -> str:
    """§17.2:no ``OPENROUTER_API_KEY`` → exit 2 before any side effect."""

    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise UsageError(
            f"{API_KEY_ENV} is not set; live batch makes no network/DB call without it"
        )
    return key


# ── subcommands that need no key/DB ──────────────────────────────────────────


def cmd_validate_suite(args) -> int:
    from .loader import CaseLoadError, load_suite

    try:
        suite = load_suite(Path(args.cases_root), suite_version=args.suite_version)
    except CaseLoadError as exc:
        print(f"suite integrity error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    print(f"suite {suite.suite_version} OK: {len(suite.runtime_inputs)} cases")
    print(f"suite_hash={suite.manifest.suite_hash}")
    for entry in suite.manifest.cases:
        print(f"  {entry.split.value:12} {entry.case_id:36} {entry.case_content_hash}")
    return EXIT_OK


def cmd_reference_gate(args) -> int:
    from uuid import NAMESPACE_URL, uuid5

    from .fixture_builder import ReferenceGateError, run_pure_reference_gate
    from .loader import CaseLoadError, load_suite

    try:
        suite = load_suite(Path(args.cases_root), suite_version=args.suite_version)
    except CaseLoadError as exc:
        print(f"suite integrity error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    base = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
    failures = 0
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        trial_id = uuid5(NAMESPACE_URL, f"reference-gate:{inputs.case.case_id}")
        try:
            result = run_pure_reference_gate(
                inputs, evaluation, trial_id=trial_id, base_time=base
            )
        except ReferenceGateError as exc:
            print(f"  FAIL {inputs.case.case_id}: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(
            f"  OK   {inputs.case.case_id}: accepted={result.accepted_count} "
            f"hash_changed={result.state_after_hash != result.state_before_hash}"
        )
    if failures:
        print(f"{failures} reference outputs failed the production gate", file=sys.stderr)
        return EXIT_GATE_FAIL
    print(f"reference gate: {len(suite.runtime_inputs)}/{len(suite.runtime_inputs)} passed")
    return EXIT_OK


def cmd_report(args) -> int:
    batch_dir = Path(args.batch_dir)
    report_path = batch_dir / "batch-report.json"
    if not report_path.is_file():
        print(f"no batch-report.json in {batch_dir}", file=sys.stderr)
        return EXIT_USAGE
    from .contracts import BatchDecision, TurnEvalBatchReport

    report = TurnEvalBatchReport.model_validate_json(report_path.read_text("utf-8"))
    print(f"decision={report.decision.value} promotion_eligible={report.promotion_eligible}")
    passing = {
        BatchDecision.TURN_GATE_PASS_ENGINEERING,
        BatchDecision.TURN_GATE_PASS_DOMAIN_REVIEWED,
    }
    return EXIT_OK if report.decision in passing else EXIT_GATE_FAIL


# ── live-batch argument gate(network/run 之前的驗證)─────────────────────────


@dataclass(frozen=True)
class LiveBatchArgs:
    database_url: str
    model: str
    upstream_endpoint: str
    data_collection: str
    zdr_required: bool
    reasoning_effort: str | None
    checklist: AccountChecklist
    budget: Budget
    api_key: str


def validate_live_batch_args(args) -> LiveBatchArgs:
    """All exit-2 gates before any catalog/DB/inference side effect (§17.2)."""

    api_key = require_api_key()  # exit 2 if missing
    checklist = validate_account_checklist(
        confirmed_at=args.account_checklist_confirmed_at,
        confirmed_by=args.account_checklist_confirmed_by,
    )
    budget = validate_budget(
        max_inference_calls=args.max_inference_calls,
        max_observed_cost_usd=args.max_observed_cost_usd,
        max_wall_clock_minutes=args.max_wall_clock_minutes,
    )
    try:
        database_url = resolve_eval_database_url(args.database_url_env)
    except EvalDatabaseError as exc:
        raise UsageError(str(exc)) from exc
    if args.data_collection not in ("deny", "allow"):
        raise UsageError("--data-collection must be deny or allow")
    return LiveBatchArgs(
        database_url=database_url,
        model=args.model,
        upstream_endpoint=args.upstream_endpoint,
        data_collection=args.data_collection,
        zdr_required=_parse_bool(args.zdr_required),
        reasoning_effort=args.reasoning_effort,
        checklist=checklist,
        budget=budget,
        api_key=api_key,
    )


def _parse_bool(value: str) -> bool:
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise UsageError(f"expected a boolean, got {value!r}")


def cmd_live_batch(args) -> int:
    try:
        validate_live_batch_args(args)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    # 實際 live 執行由 E8 owner 觸發;此處確認參數 gate 通過後,
    # 尚未實作 online orchestration,回報 preflight-pending 而非假裝跑完。
    print(
        "live-batch arguments validated; online orchestration is triggered by the "
        "owner in E8 (see the V3-5 plan §19 E8).",
        file=sys.stderr,
    )
    return EXIT_PREFLIGHT


def cmd_mocked_batch(args) -> int:
    import asyncio
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from .batch_orchestrator import orchestrate_mocked_batch
    from .loader import CaseLoadError, load_suite

    try:
        database_url = resolve_eval_database_url(args.database_url_env)
    except EvalDatabaseError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        suite = load_suite(Path(args.cases_root), suite_version=args.suite_version)
    except CaseLoadError as exc:
        print(f"suite integrity error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    async def run() -> str:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        try:
            result = await orchestrate_mocked_batch(
                suite,
                session_factory=factory,
                output_dir=Path(args.output_dir),
                batch_id=uuid4(),
                trial_started_at=datetime.now(UTC),
                git_sha="0" * 40,
                dirty_worktree=True,  # mocked run never promotion-eligible anyway
            )
        finally:
            await engine.dispose()
        return result.decision

    try:
        decision = asyncio.run(run())
    except Exception as exc:  # noqa: BLE001 — surface as runner error (exit 4)
        print(f"runner error: {exc}", file=sys.stderr)
        return EXIT_RUNNER
    print(f"mocked-batch decision={decision} (harness self-test; not promotion-eligible)")
    passing = decision in ("TURN_GATE_PASS_ENGINEERING", "TURN_GATE_PASS_DOMAIN_REVIEWED")
    return EXIT_OK if passing else EXIT_GATE_FAIL


def cmd_export_review(args) -> int:
    print("export-review requires a completed batch bundle (E8).", file=sys.stderr)
    return EXIT_PREFLIGHT


def cmd_import_review(args) -> int:
    print("import-review requires a completed batch bundle (E8).", file=sys.stderr)
    return EXIT_PREFLIGHT


# ── argument parser ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="turn_eval_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-suite")
    validate.add_argument("--suite-version", required=True)
    validate.add_argument("--cases-root", default=str(DEFAULT_CASES_ROOT))
    validate.set_defaults(func=cmd_validate_suite)

    reference = sub.add_parser("reference-gate")
    reference.add_argument("--suite-version", required=True)
    reference.add_argument("--cases-root", default=str(DEFAULT_CASES_ROOT))
    reference.add_argument("--database-url-env", default=None)
    reference.set_defaults(func=cmd_reference_gate)

    mocked = sub.add_parser("mocked-batch")
    mocked.add_argument("--suite-version", required=True)
    mocked.add_argument("--cases-root", default=str(DEFAULT_CASES_ROOT))
    mocked.add_argument("--database-url-env", required=True)
    mocked.add_argument("--output-dir", required=True)
    mocked.set_defaults(func=cmd_mocked_batch)

    live = sub.add_parser("live-batch")
    live.add_argument("--suite-version", required=True)
    live.add_argument("--cases-root", default=str(DEFAULT_CASES_ROOT))
    live.add_argument("--database-url-env", required=True)
    live.add_argument("--model", required=True)
    live.add_argument("--upstream-endpoint", required=True)
    live.add_argument("--data-collection", required=True)
    live.add_argument("--zdr-required", required=True)
    live.add_argument("--reasoning-effort", default=None)
    live.add_argument("--quality-slots", type=int, default=3)
    live.add_argument("--max-trial-attempts-per-slot", type=int, default=3)
    live.add_argument("--max-concurrency", type=int, default=1)
    live.add_argument("--max-inference-calls", type=int, default=None)
    live.add_argument("--max-observed-cost-usd", default=None)
    live.add_argument("--max-wall-clock-minutes", type=int, default=None)
    live.add_argument("--account-checklist-confirmed-at", default=None)
    live.add_argument("--account-checklist-confirmed-by", default=None)
    live.add_argument("--output-dir", required=True)
    live.set_defaults(func=cmd_live_batch)

    export = sub.add_parser("export-review")
    export.add_argument("--batch-dir", required=True)
    export.set_defaults(func=cmd_export_review)

    imp = sub.add_parser("import-review")
    imp.add_argument("--batch-dir", required=True)
    imp.add_argument("--decisions", required=True)
    imp.set_defaults(func=cmd_import_review)

    report = sub.add_parser("report")
    report.add_argument("--batch-dir", required=True)
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
