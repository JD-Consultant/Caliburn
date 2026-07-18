"""E8 true-live batch orchestration and offline review finalization.

This module is the executable bridge that E7 intentionally did not contain:
it binds one catalog-derived OpenRouter adapter to the production durable turn
runner, fills every pass^3 slot, exports validated Capture bundles, and then
regrades immutable trial artifacts after blind review decisions are imported.
Gold is loaded only after each provider execution reaches a terminal outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.llm.context import TURN_INTERPRET_CONTEXT_POLICY_V1
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.turn_interpret import (
    TURN_INTERPRET_VERIFIER_POLICY_V1,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)

from .batch_orchestrator import grade_execution
from .capture_export import CaptureBundle, export_run_bundle
from .contracts import (
    BatchPlanCase,
    ExecutionMode,
    ReviewCompleteness,
    ReviewDecisionLabel,
    TrialDisposition,
    TurnEvalBatchPlan,
    TurnEvalGraderResult,
    TurnEvalReviewDecision,
    TurnEvalTrial,
    define_turn_eval_batch_plan,
)
from .live_wiring import (
    LiveBatchProfile,
    openrouter_attempt_records,
    openrouter_observed_cost,
    openrouter_route_is_clean,
)
from .loader import TurnEvalSuite, load_suite
from .review import (
    ImportedReview,
    ReviewItem,
    edge_decision_map,
    import_review_decisions,
    missing_decisions,
    order_review_queue,
)
from .scheduler import (
    Budget,
    BudgetExceeded,
    build_trial_record,
    schedule_slot,
    write_trial_bundle,
)
from .turn_eval_runner import TrialExecution
from .turn_graders import (
    GradingContext,
    build_candidate_edges,
    compute_trial_metrics,
    run_deterministic_graders,
)
from .turn_report import (
    TrialScore,
    build_batch_report,
    render_markdown,
    trial_hard_gate,
)


class LiveBatchError(RuntimeError):
    """The persisted live bundle is incomplete, inconsistent, or tampered."""


@dataclass(frozen=True)
class LiveBatchResult:
    batch_dir: Path
    plan_path: Path
    report_path: Path
    review_queue_path: Path
    decision: str
    trial_ids: tuple


def _atomic_write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(
        (
            json.dumps(payload, ensure_ascii=False, indent=2, default=str)
            + "\n"
        ).encode("utf-8")
    )
    os.replace(tmp, path)


def _atomic_write_jsonl(path: Path, values: Sequence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = "\n".join(canonical_json(value) for value in values)
    tmp.write_bytes(((text + "\n") if text else "").encode("utf-8"))
    os.replace(tmp, path)


def _read_jsonl(path: Path, model_type) -> tuple:
    if not path.is_file():
        raise LiveBatchError(f"required JSONL file is missing: {path}")
    values = []
    for line_number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            values.append(model_type.model_validate_json(line))
        except Exception as exc:  # noqa: BLE001 - bundle integrity boundary
            raise LiveBatchError(
                f"invalid {model_type.__name__} at {path}:{line_number}: {exc}"
            ) from exc
    return tuple(values)


def _build_plan(
    suite: TurnEvalSuite,
    *,
    batch_id: UUID,
    profile: LiveBatchProfile,
    quality_slots: int,
    max_trial_attempts: int,
    max_concurrency: int,
    git_sha: str,
    dirty_worktree: bool,
    account_confirmed_at: datetime,
    account_confirmed_by: str,
    budget: Budget,
    created_at: datetime,
) -> TurnEvalBatchPlan:
    operation = turn_interpret_operation()
    case_entries = sorted(
        (
            BatchPlanCase(
                case_id=inputs.case.case_id,
                split=inputs.case.split,
                runtime_input_hash=inputs.runtime_input_hash,
                evaluation_contract_hash=evaluation.evaluation_contract_hash,
                case_content_hash=evaluation.case_content_hash,
            )
            for inputs, evaluation in zip(
                suite.runtime_inputs, suite.evaluation_contracts, strict=True
            )
        ),
        key=lambda entry: (entry.split.value, entry.case_id),
    )
    config = profile.config
    return define_turn_eval_batch_plan(
        batch_id=batch_id,
        execution_mode=ExecutionMode.LIVE,
        suite_version=suite.suite_version,
        suite_hash=suite.manifest.suite_hash,
        cases=tuple(case_entries),
        quality_slots_per_case=quality_slots,
        max_trial_attempts_per_slot=max_trial_attempts,
        max_concurrency=max_concurrency,
        ordering_seed=f"turn-eval:{batch_id}",
        git_sha=git_sha,
        dirty_worktree=dirty_worktree,
        operation_name=operation.name,
        operation_definition_hash=operation.definition_hash,
        prompt_hash=operation.prompt_template.content_hash,
        output_schema_hash=operation.output_contract.content_hash,
        context_policy_hash=TURN_INTERPRET_CONTEXT_POLICY_V1.policy_hash,
        verifier_policy_hash=TURN_INTERPRET_VERIFIER_POLICY_V1.policy_hash,
        provider=config.provider,
        provider_config_hash=config.config_hash,
        requested_model=config.requested_model,
        catalog_canonical_model=config.catalog_canonical_model,
        upstream_endpoint_slug=config.upstream_endpoint_slug,
        expected_upstream_provider_name=config.expected_upstream_provider_name,
        model_catalog_hash=profile.model_snapshot.snapshot_hash,
        endpoint_catalog_hash=profile.endpoint_snapshot.snapshot_hash,
        reasoning_effort=config.reasoning_effort,
        reasoning_exclude=config.reasoning_exclude,
        data_collection=config.data_collection,
        zdr_required=config.zdr_required,
        account_checklist_confirmed_at=account_confirmed_at,
        account_checklist_confirmed_by=account_confirmed_by,
        max_inference_calls=budget.max_inference_calls,
        max_observed_cost_usd=budget.max_observed_cost_usd,
        max_wall_clock_minutes=budget.max_wall_clock_seconds // 60,
        created_at=created_at,
    )


async def orchestrate_live_batch(
    suite: TurnEvalSuite,
    *,
    session_factory: async_sessionmaker,
    output_dir: Path,
    batch_id: UUID,
    live_profile: LiveBatchProfile,
    llm=None,
    llm_factory=None,
    budget: Budget,
    quality_slots: int,
    max_trial_attempts: int,
    max_concurrency: int,
    git_sha: str,
    dirty_worktree: bool,
    account_confirmed_at: datetime,
    account_confirmed_by: str,
) -> LiveBatchResult:
    """Run a sequential true-live batch and stop on attribution failure."""

    if max_concurrency != 1:
        raise LiveBatchError("the first formal live batch requires max_concurrency=1")
    if quality_slots != 3:
        raise LiveBatchError("the formal pass^3 batch requires exactly 3 quality slots")
    if (llm is None) == (llm_factory is None):
        raise LiveBatchError("provide exactly one of llm or llm_factory")

    started_at = datetime.now(UTC)
    started_mono = time.monotonic()
    plan = _build_plan(
        suite,
        batch_id=batch_id,
        profile=live_profile,
        quality_slots=quality_slots,
        max_trial_attempts=max_trial_attempts,
        max_concurrency=max_concurrency,
        git_sha=git_sha,
        dirty_worktree=dirty_worktree,
        account_confirmed_at=account_confirmed_at,
        account_confirmed_by=account_confirmed_by,
        budget=budget,
        created_at=started_at,
    )

    batch_dir = output_dir / str(batch_id)
    if batch_dir.exists():
        raise LiveBatchError(f"batch directory already exists: {batch_dir}")
    batch_dir.mkdir(parents=True)
    _atomic_write_json(batch_dir / "batch-plan.json", plan.model_dump(mode="json"))
    _atomic_write_json(
        batch_dir / "provider-config.json",
        live_profile.config.model_dump(mode="json"),
    )
    _atomic_write_json(
        batch_dir / "model-catalog-snapshot.json",
        live_profile.model_snapshot.model_dump(mode="json"),
    )
    _atomic_write_json(
        batch_dir / "endpoint-catalog-snapshot.json",
        live_profile.endpoint_snapshot.model_dump(mode="json"),
    )

    captures: dict[UUID, CaptureBundle] = {}
    attempt_ledgers = {}
    trial_ids = []
    all_review_items: list[ReviewItem] = []
    incomplete = False
    harness_invalid = False
    stop_reason: str | None = None

    async def account_execution(execution: TrialExecution):
        bundle = await export_run_bundle(
            session_factory,
            tenant_id=execution.ids.tenant_id,
            run_id=execution.ids.run_id,
        )
        ledger = openrouter_attempt_records(bundle)
        if not ledger:
            raise LiveBatchError("Capture contains no durable model.result attempt")
        captures[execution.ids.trial_id] = bundle
        attempt_ledgers[execution.ids.trial_id] = ledger
        return len(ledger), openrouter_observed_cost(bundle)

    selected_llm_factory = llm_factory
    if selected_llm_factory is None:
        def selected_llm_factory(_inputs, _trial_id):
            return llm

    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        if incomplete or harness_invalid:
            break
        for slot_index in range(1, quality_slots + 1):
            try:
                slot = await schedule_slot(
                    inputs,
                    batch_id=batch_id,
                    case_id=inputs.case.case_id,
                    slot_index=slot_index,
                    session_factory=session_factory,
                    llm_factory=selected_llm_factory,
                    profile=live_profile.provider_profile,
                    trial_started_at_factory=lambda: datetime.now(UTC),
                    max_trial_attempts=max_trial_attempts,
                    budget=budget,
                    elapsed_seconds_factory=lambda: time.monotonic() - started_mono,
                    account_execution=account_execution,
                )
            except BudgetExceeded as exc:
                incomplete = True
                stop_reason = str(exc)
                break

            for trial_attempt, execution, disposition, reason_code in slot.executions:
                if execution is None:
                    harness_invalid = True
                    stop_reason = reason_code or "runner_exception"
                    break
                trial_ids.append(execution.ids)
                capture = captures.get(execution.ids.trial_id)
                attempts = attempt_ledgers.get(execution.ids.trial_id)
                if capture is None or attempts is None:
                    harness_invalid = True
                    stop_reason = "capture_export_missing"
                    break
                trial = build_trial_record(
                    execution,
                    case_id=inputs.case.case_id,
                    slot_index=slot_index,
                    trial_attempt=trial_attempt,
                    runtime_input_hash=inputs.runtime_input_hash,
                    evaluation_contract_hash=evaluation.evaluation_contract_hash,
                    disposition=disposition,
                    reason_code=reason_code,
                    requested_model=live_profile.config.requested_model,
                    capture=capture,
                    attempt_records=attempts,
                    provider_config_hash=live_profile.config.config_hash,
                    model_catalog_hash=live_profile.model_snapshot.snapshot_hash,
                    endpoint_catalog_hash=live_profile.endpoint_snapshot.snapshot_hash,
                )
                graded = grade_execution(
                    inputs,
                    evaluation,
                    execution,
                    slot_index=slot_index,
                    split=inputs.case.split,
                    batch_id=batch_id,
                    decision_labels={},
                    review_complete=False,
                    disposition=disposition,
                    trial_record=trial,
                )
                if disposition == TrialDisposition.QUALITY_SCORED:
                    all_review_items.extend(graded.review_items)
                write_trial_bundle(
                    batch_dir,
                    trial=trial,
                    capture=capture,
                    grader_results_json=[
                        item.model_dump(mode="json") for item in graded.grader_results
                    ],
                    review_items_json=[
                        item.model_dump(mode="json") for item in graded.review_items
                    ],
                    final_state_json=graded.final_state_json,
                    candidate_output_json=graded.candidate_output_json,
                    verification_report_json=graded.verification_report_json,
                )
                if disposition == TrialDisposition.HARNESS_INVALID:
                    harness_invalid = True
                    stop_reason = reason_code or "harness_invalid"
                    break
            if harness_invalid:
                break
            if slot.incomplete:
                incomplete = True
                stop_reason = stop_reason or "quality_slot_not_filled"
                break

    queue = order_review_queue(all_review_items, ordering_seed=plan.ordering_seed)
    queue_path = batch_dir / "review-queue.jsonl"
    _atomic_write_jsonl(queue_path, queue)
    _atomic_write_json(
        batch_dir / "batch-state.json",
        {
            "schema_version": "turn_eval_live_batch_state.v1",
            "batch_id": str(batch_id),
            "status": (
                "harness_invalid"
                if harness_invalid
                else ("batch_incomplete" if incomplete else "awaiting_review")
            ),
            "stop_reason": stop_reason,
            "trial_ids": [str(ids.trial_id) for ids in trial_ids],
            "inference_calls": budget.inference_calls,
            "observed_cost_usd": str(budget.observed_cost_usd),
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )
    report = rebuild_live_report(batch_dir)
    return LiveBatchResult(
        batch_dir=batch_dir,
        plan_path=batch_dir / "batch-plan.json",
        report_path=batch_dir / "batch-report.json",
        review_queue_path=queue_path,
        decision=report.decision.value,
        trial_ids=tuple(trial_ids),
    )


def _verify_trial_integrity(trial_dir: Path) -> bool:
    manifest_path = trial_dir / "integrity-manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text("utf-8"))
        expected = {item["path"]: item for item in manifest["files"]}
    except (KeyError, TypeError, ValueError):
        return False
    actual = {
        path.relative_to(trial_dir).as_posix(): path
        for path in trial_dir.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(actual) != set(expected):
        return False
    for relative, path in actual.items():
        entry = expected[relative]
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if entry.get("byte_size") != path.stat().st_size or entry.get("sha256") != digest:
            return False
    return True


def load_review_queue(batch_dir: Path) -> tuple[ReviewItem, ...]:
    plan = TurnEvalBatchPlan.model_validate_json(
        (batch_dir / "batch-plan.json").read_text("utf-8")
    )
    queue = _read_jsonl(batch_dir / "review-queue.jsonl", ReviewItem)
    ids = [item.review_item_id for item in queue]
    if len(ids) != len(set(ids)):
        raise LiveBatchError("review queue contains duplicate item IDs")
    ordered = order_review_queue(queue, ordering_seed=plan.ordering_seed)
    if tuple(ids) != tuple(item.review_item_id for item in ordered):
        raise LiveBatchError("review queue ordering does not match the batch seed")
    return queue


def apply_review_decisions(
    batch_dir: Path,
    decisions: Sequence[TurnEvalReviewDecision],
    *,
    failure_traces_read: int,
    passing_trace_sample_read: int,
) -> str:
    queue = load_review_queue(batch_dir)
    imported = import_review_decisions(queue, decisions)
    if missing_decisions(queue, imported):
        # Partial imports are durable and intentionally remain REVIEW_INCOMPLETE.
        pass
    ordered = sorted(
        decisions,
        key=lambda item: (str(item.review_item_id), item.revision),
    )
    _atomic_write_jsonl(batch_dir / "review-decisions.jsonl", ordered)
    _atomic_write_json(
        batch_dir / "review-attestation.json",
        {
            "schema_version": "turn_eval_review_attestation.v1",
            "failure_traces_read": failure_traces_read,
            "passing_trace_sample_read": passing_trace_sample_read,
            "reviewers": sorted({item.reviewer for item in decisions}),
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )
    return rebuild_live_report(batch_dir).decision.value


def _load_imported_review(batch_dir: Path, queue: Sequence[ReviewItem]) -> ImportedReview:
    decisions_path = batch_dir / "review-decisions.jsonl"
    decisions = (
        _read_jsonl(decisions_path, TurnEvalReviewDecision)
        if decisions_path.is_file()
        else ()
    )
    return import_review_decisions(queue, decisions)


def _accepted_keys(report: TurnInterpretVerificationReport | None) -> frozenset[str]:
    if report is None:
        return frozenset()
    return frozenset(item.proposal_key for item in report.decisions if item.accepted)


def _score_trial(
    trial_dir: Path,
    *,
    inputs,
    evaluation,
    imported: ImportedReview,
) -> tuple[TrialScore, tuple[ReviewItem, ...]]:
    trial = TurnEvalTrial.model_validate_json(
        (trial_dir / "trial.json").read_text("utf-8")
    )
    candidate_json = json.loads((trial_dir / "candidate-output.json").read_text("utf-8"))
    verification_json = json.loads(
        (trial_dir / "verification-report.json").read_text("utf-8")
    )
    final_state = InterviewState.model_validate_json(
        (trial_dir / "final-state.json").read_text("utf-8")
    )
    output = TurnInterpretOutput.model_validate(candidate_json) if candidate_json else None
    verification = (
        TurnInterpretVerificationReport.model_validate(verification_json)
        if verification_json
        else None
    )
    committed_kind = None
    if trial.terminal_outcome == "committed":
        committed_kind = "evidence" if verification and verification.accepted_count else "noop"
    context = GradingContext(
        inputs=inputs,
        gold=evaluation.gold,
        trial_id=trial.trial_id,
        case_id=trial.case_id,
        output=output,
        report=verification,
        committed_kind=committed_kind,
        state_before_hash=trial.state_before_hash,
        state_after_hash=trial.state_after_hash,
        evidence_status={item.evidence_id: item.status for item in final_state.evidence},
        failure_reason_code=trial.terminal_reason_code,
    )
    graders = run_deterministic_graders(context)
    stored_graders = tuple(
        TurnEvalGraderResult.model_validate(item)
        for item in json.loads((trial_dir / "grader-results.json").read_text("utf-8"))
    )
    if canonical_json(
        [item.model_dump(mode="json") for item in graders]
    ) != canonical_json(
        [item.model_dump(mode="json") for item in stored_graders]
    ):
        raise LiveBatchError(f"deterministic grader drift in {trial_dir}")

    review_items = tuple(
        ReviewItem.model_validate(item)
        for item in json.loads((trial_dir / "review-item.json").read_text("utf-8"))
    )
    decisions = edge_decision_map(imported, review_items)
    edges = (
        build_candidate_edges(
            inputs, evaluation.gold, output, trial_id=trial.trial_id
        )
        if output is not None
        else ()
    )
    metrics = compute_trial_metrics(
        gold=evaluation.gold,
        output=output,
        edges=edges,
        decisions=decisions,
        accepted_proposal_keys=_accepted_keys(verification),
    )
    missing = [
        item.review_item_id
        for item in review_items
        if item.review_item_id not in imported.decisions_by_item
    ]
    score = TrialScore(
        trial_id=trial.trial_id,
        case_id=trial.case_id,
        split=inputs.case.split,
        slot_index=trial.slot_index,
        disposition=trial.disposition,
        grader_results=graders,
        metrics=metrics,
        review_complete=not missing and not metrics.review_incomplete,
        had_infrastructure_retry=trial.had_infrastructure_retry,
        inference_calls=len(trial.attempts),
        observed_cost_usd=trial.observed_cost_total_usd,
        usage_input_tokens=trial.usage_input_tokens,
        usage_output_tokens=trial.usage_output_tokens,
        usage_cache_read_tokens=trial.usage_cache_read_tokens,
        usage_cache_write_tokens=trial.usage_cache_write_tokens,
        usage_reasoning_tokens=trial.usage_reasoning_tokens,
    )
    return score, review_items


def rebuild_live_report(batch_dir: Path):
    plan = TurnEvalBatchPlan.model_validate_json(
        (batch_dir / "batch-plan.json").read_text("utf-8")
    )
    if plan.execution_mode != ExecutionMode.LIVE:
        raise LiveBatchError("offline live report requires a live batch plan")
    suite = load_suite(
        Path(__file__).with_name("cases"), suite_version=plan.suite_version
    )
    if suite.manifest.suite_hash != plan.suite_hash:
        raise LiveBatchError("suite hash no longer matches the frozen batch plan")
    queue = load_review_queue(batch_dir)
    imported = _load_imported_review(batch_dir, queue)
    by_case_inputs = {item.case.case_id: item for item in suite.runtime_inputs}
    by_case_eval = {
        item.case_id: item for item in suite.evaluation_contracts
    }

    scores = []
    seen_review_ids = set()
    capture_verified = True
    route_clean = True
    harness_invalid = False
    for trial_dir in sorted(batch_dir.glob("trials/*/slot-*/trial-attempt-*")):
        capture_verified = capture_verified and _verify_trial_integrity(trial_dir)
        trial = TurnEvalTrial.model_validate_json(
            (trial_dir / "trial.json").read_text("utf-8")
        )
        score, review_items = _score_trial(
            trial_dir,
            inputs=by_case_inputs[trial.case_id],
            evaluation=by_case_eval[trial.case_id],
            imported=imported,
        )
        scores.append(score)
        seen_review_ids.update(item.review_item_id for item in review_items)
        if trial.disposition == TrialDisposition.HARNESS_INVALID:
            harness_invalid = True
        if trial.disposition == TrialDisposition.QUALITY_SCORED:
            routed = [item for item in trial.attempts if item.route is not None]
            route_clean = route_clean and bool(routed) and all(
                openrouter_route_is_clean(item) for item in routed
            )
    if seen_review_ids != {item.review_item_id for item in queue}:
        raise LiveBatchError("review queue does not equal the immutable trial items")

    quality_by_case = {
        case_id: len(
            [
                score
                for score in scores
                if score.case_id == case_id and score.scored
            ]
        )
        for case_id in by_case_inputs
    }
    batch_incomplete = any(
        count != plan.quality_slots_per_case for count in quality_by_case.values()
    )
    state = json.loads((batch_dir / "batch-state.json").read_text("utf-8"))
    harness_invalid = harness_invalid or state.get("status") == "harness_invalid"
    batch_incomplete = batch_incomplete or state.get("status") == "batch_incomplete"

    attestation_path = batch_dir / "review-attestation.json"
    attestation = (
        json.loads(attestation_path.read_text("utf-8"))
        if attestation_path.is_file()
        else {}
    )
    reviewers = tuple(attestation.get("reviewers", ()))
    passing_trace_count = sum(
        1
        for score in scores
        if score.scored and trial_hard_gate(score, by_case_eval[score.case_id].gold)
    )
    required_sample = min(8, passing_trace_count)
    needs_sme = sum(
        1
        for decision in imported.decisions_by_item.values()
        if decision.decision == ReviewDecisionLabel.NEEDS_SME
    )
    review = ReviewCompleteness(
        required_review_items=len(queue),
        completed_review_items=len(imported.decisions_by_item),
        needs_sme_count=needs_sme,
        failure_traces_read=int(attestation.get("failure_traces_read", 0)),
        passing_trace_sample_required=required_sample,
        passing_trace_sample_read=int(
            attestation.get("passing_trace_sample_read", 0)
        ),
    )
    limitations = []
    if any(score.observed_cost_usd is None for score in scores if score.inference_calls):
        limitations.append("one or more provider attempts did not expose observed cost")
    if any("codex" in reviewer.casefold() for reviewer in reviewers):
        limitations.append(
            "semantic review was owner-delegated and AI-assisted; no independent domain reviewer"
        )
    completed_at = datetime.now(UTC)
    started_at = plan.created_at
    report = build_batch_report(
        batch_id=plan.batch_id,
        plan_hash=plan.plan_hash,
        suite_version=plan.suite_version,
        suite_hash=plan.suite_hash,
        execution_mode=ExecutionMode.LIVE,
        git_sha=plan.git_sha,
        dirty_worktree=plan.dirty_worktree,
        gold_by_case={key: value.gold for key, value in by_case_eval.items()},
        split_by_case={key: value.case.split for key, value in by_case_inputs.items()},
        scores=scores,
        review=review,
        route_clean=route_clean,
        capture_verified=capture_verified,
        created_at=completed_at,
        batch_incomplete=batch_incomplete,
        harness_invalid=harness_invalid,
        wall_clock_seconds=max(0, int((completed_at - started_at).total_seconds())),
        limitations=limitations,
    )
    _atomic_write_json(
        batch_dir / "batch-report.json", report.model_dump(mode="json")
    )
    (batch_dir / "batch-report.md").write_bytes(
        render_markdown(report).encode("utf-8")
    )
    return report
