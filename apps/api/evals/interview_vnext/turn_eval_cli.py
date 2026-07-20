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
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

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

    if (batch_dir / "batch-plan.json").is_file():
        from .live_batch import rebuild_live_report

        try:
            rebuild_live_report(batch_dir)
        except Exception as exc:  # noqa: BLE001 - CLI integrity boundary
            print(f"report rebuild error: {exc}", file=sys.stderr)
            return EXIT_PREFLIGHT

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
        live_args = validate_live_batch_args(args)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.quality_slots != 3:
        print("usage error: formal live batch requires --quality-slots 3", file=sys.stderr)
        return EXIT_USAGE
    if args.max_trial_attempts_per_slot not in (1, 2, 3):
        print(
            "usage error: --max-trial-attempts-per-slot must be 1..3",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.max_concurrency != 1:
        print(
            "usage error: first formal live batch requires --max-concurrency 1",
            file=sys.stderr,
        )
        return EXIT_USAGE

    from .loader import CaseLoadError, load_suite

    try:
        suite = load_suite(Path(args.cases_root), suite_version=args.suite_version)
    except CaseLoadError as exc:
        print(f"suite integrity error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT

    try:
        git_sha, dirty = _git_snapshot()
    except RuntimeError as exc:
        print(f"git preflight error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    if dirty:
        print("git preflight error: formal live batch requires a clean worktree", file=sys.stderr)
        return EXIT_PREFLIGHT

    import asyncio
    import httpx
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from .live_batch import orchestrate_live_batch
    from .live_wiring import (
        LivePreflightError,
        build_live_adapter,
        build_live_batch_profile,
    )
    from .openrouter_model_catalog import CatalogProbeError
    from .openrouter_provider_config import OpenRouterProbeInputs
    from .scheduler import Budget as SchedulerBudget
    from .turn_eval_runner import cleanup_trial_rows

    async def run():
        client = httpx.AsyncClient(follow_redirects=False)
        engine = None
        adapter = None
        try:
            probe_inputs = OpenRouterProbeInputs(
                requested_model=live_args.model,
                upstream_endpoint_slug=live_args.upstream_endpoint,
                data_collection=live_args.data_collection,
                zdr_required=live_args.zdr_required,
                reasoning_effort=live_args.reasoning_effort,
            )
            profile = await build_live_batch_profile(
                api_key=live_args.api_key,
                probe_inputs=probe_inputs,
                reasoning_effort=live_args.reasoning_effort,
                http_client=client,
            )
            adapter = build_live_adapter(
                profile, api_key=live_args.api_key, http_client=client
            )
            engine = create_async_engine(live_args.database_url)
            factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            result = await orchestrate_live_batch(
                suite,
                session_factory=factory,
                output_dir=Path(args.output_dir),
                batch_id=uuid4(),
                live_profile=profile,
                llm=adapter,
                budget=SchedulerBudget(
                    max_inference_calls=live_args.budget.max_inference_calls,
                    max_observed_cost_usd=live_args.budget.max_observed_cost_usd,
                    max_wall_clock_seconds=(
                        live_args.budget.max_wall_clock_minutes * 60
                    ),
                ),
                quality_slots=args.quality_slots,
                max_trial_attempts=args.max_trial_attempts_per_slot,
                max_concurrency=args.max_concurrency,
                git_sha=git_sha,
                dirty_worktree=dirty,
                account_confirmed_at=live_args.checklist.confirmed_at,
                account_confirmed_by=live_args.checklist.confirmed_by,
            )
            await cleanup_trial_rows(factory, list(result.trial_ids))
            return result
        finally:
            if adapter is not None:
                await adapter.aclose()
            await client.aclose()
            if engine is not None:
                await engine.dispose()

    try:
        result = asyncio.run(run())
    except (CatalogProbeError, LivePreflightError, ValueError) as exc:
        print(f"live preflight error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    except Exception as exc:  # noqa: BLE001 - preserve bundle, surface runner error
        print(f"live runner error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUNNER

    print(f"live batch={result.batch_dir.name} decision={result.decision}")
    print(f"bundle={result.batch_dir}")
    print(f"review_queue={result.review_queue_path}")
    return EXIT_GATE_FAIL


def _git_snapshot() -> tuple[str, bool]:
    def run(*argv: str) -> str:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "git command failed")
        return completed.stdout.strip()

    sha = run("git", "rev-parse", "HEAD")
    if len(sha) != 40:
        raise RuntimeError("git HEAD is not a 40-character SHA")
    dirty = bool(run("git", "status", "--porcelain"))
    return sha, dirty


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
    from .live_batch import LiveBatchError, load_review_queue

    batch_dir = Path(args.batch_dir)
    try:
        queue = load_review_queue(batch_dir)
    except (LiveBatchError, OSError, ValueError) as exc:
        print(f"review export error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    print(f"review_queue={batch_dir / 'review-queue.jsonl'} items={len(queue)}")
    return EXIT_OK


def cmd_import_review(args) -> int:
    from .contracts import BatchDecision, TurnEvalReviewDecision
    from .live_batch import LiveBatchError, _read_jsonl, apply_review_decisions
    from .review import ReviewImportError

    try:
        decisions = _read_jsonl(Path(args.decisions), TurnEvalReviewDecision)
        decision = apply_review_decisions(
            Path(args.batch_dir),
            decisions,
            failure_traces_read=args.failure_traces_read,
            passing_trace_sample_read=args.passing_trace_sample_read,
        )
    except (LiveBatchError, ReviewImportError, OSError, ValueError) as exc:
        print(f"review import error: {exc}", file=sys.stderr)
        return EXIT_PREFLIGHT
    print(f"decision={decision}")
    passing = {
        BatchDecision.TURN_GATE_PASS_ENGINEERING.value,
        BatchDecision.TURN_GATE_PASS_DOMAIN_REVIEWED.value,
    }
    return EXIT_OK if decision in passing else EXIT_GATE_FAIL


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
    imp.add_argument("--failure-traces-read", type=int, default=0)
    imp.add_argument("--passing-trace-sample-read", type=int, default=0)
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
