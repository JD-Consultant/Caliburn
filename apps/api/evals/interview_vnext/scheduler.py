"""Batch scheduler: disposition, infrastructure replacement, budget, bundle (§9/§12).

The scheduler drives quality slots per case and, when a trial is only
infrastructure-invalid, opens a fresh replacement trial (new session/run) up to
the per-slot cap while keeping the original trial in the report. It never
retries a single HTTP call itself — provider calls stay inside the production
executor/adapter. Budget caps are checked before each new trial. Each trial is
written to an immutable, atomically-renamed directory with a root integrity
manifest; raw live bundles and reports are gitignored.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Awaitable, Callable, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.application.operation_executor import (
    TurnExecutionStatus,
)
from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.port import LlmPort
from app.interview_vnext.llm.turn_interpret import TurnInterpretOutput

from .capture_export import CaptureBundle, export_run_bundle
from .contracts import (
    TrialAttemptRecord,
    TrialDisposition,
    TurnEvalTrial,
)
from .identities import slot_uuid, trial_uuid
from .loader import TurnEvalCaseInputs
from .turn_eval_runner import TrialExecution, run_trial


# 純 infrastructure 失敗的 reason 前綴/關鍵字(§9.4);其餘 provider 失敗算 quality。
_INFRASTRUCTURE_MARKERS = (
    "timeout",
    "429",
    "rate_limit",
    "unavailable",
    "transport",
    "provider.5",
    "connect",
    "provider_overloaded",
    "server_error",
)

# These failures invalidate attribution/configuration rather than measuring
# turn-interpret quality.  They must stop the batch instead of entering the
# quality denominator (§9.4).  `provider.conformance_failed` is the R4+ neutral
# terminal reason for a wire-succeeded but attribution-ineligible attempt
# (R4 §10.4 stop-gap until R6 carries full conformance refs in the trial
# contract); the older markers stay readable for historical v1 bundles.
_HARNESS_FAILURE_MARKERS = (
    "provider.conformance_failed",
    "route_contaminated",
    "resolved_model_mismatch",
    "binding_invalid",
    "authentication_failed",
    "permission_denied",
    "credits_unavailable",
)


class BudgetExceeded(RuntimeError):
    """A batch budget cap was reached before a new trial could start."""


@dataclass
class Budget:
    max_inference_calls: int
    max_observed_cost_usd: Decimal
    max_wall_clock_seconds: int
    inference_calls: int = 0
    observed_cost_usd: Decimal = Decimal(0)

    def can_start_new_trial(self, *, elapsed_seconds: float) -> bool:
        if self.inference_calls >= self.max_inference_calls:
            return False
        if self.observed_cost_usd >= self.max_observed_cost_usd:
            return False
        if elapsed_seconds >= self.max_wall_clock_seconds:
            return False
        return True

    def charge(self, *, calls: int, cost: Decimal | None) -> None:
        self.inference_calls += calls
        if cost is not None:
            self.observed_cost_usd += cost


def classify_disposition(
    execution: TrialExecution | None, *, error: Exception | None = None
) -> tuple[TrialDisposition, str | None]:
    """§9.4 disposition matrix (mocked/live share the same terminal classifier)."""

    if error is not None:
        return TrialDisposition.HARNESS_INVALID, type(error).__name__
    assert execution is not None
    outcome = execution.outcome
    if outcome.status == TurnExecutionStatus.COMMITTED:
        return TrialDisposition.QUALITY_SCORED, None
    if outcome.status == TurnExecutionStatus.PENDING:
        return TrialDisposition.HARNESS_INVALID, "pending_checkpoint"
    reason = (outcome.reason_code or "").lower()
    if any(marker in reason for marker in _HARNESS_FAILURE_MARKERS):
        return TrialDisposition.HARNESS_INVALID, outcome.reason_code
    if any(marker in reason for marker in _INFRASTRUCTURE_MARKERS):
        return TrialDisposition.INFRASTRUCTURE_INVALID, outcome.reason_code
    # refusal / max tokens / content filter / parse/schema fail on normal input
    return TrialDisposition.QUALITY_SCORED, outcome.reason_code


def _attempt_records(execution: TrialExecution) -> tuple[TrialAttemptRecord, ...]:
    result = execution.outcome.provider_result
    if result is None:
        return ()
    return (
        TrialAttemptRecord(
            attempt=result.attempt,
            outcome=result.outcome,
            finish_reason=result.finish_reason,
            failure_kind=result.failure.kind if result.failure else None,
            reason_code=(result.failure.reason_code if result.failure else None),
            retryable=(result.failure.retryable if result.failure else None),
            resolved_model=result.resolved_model,
            provider_request_id=result.provider_request_id,
            usage=result.usage,
            latency_ms=result.latency_ms,
        ),
    )


def build_trial_record(
    execution: TrialExecution,
    *,
    case_id: str,
    slot_index: int,
    trial_attempt: int,
    runtime_input_hash: str,
    evaluation_contract_hash: str,
    disposition: TrialDisposition,
    reason_code: str | None,
    requested_model: str,
    capture: CaptureBundle,
    attempt_records: tuple[TrialAttemptRecord, ...] | None = None,
    provider_config_hash: str | None = None,
    model_catalog_hash: str | None = None,
    endpoint_catalog_hash: str | None = None,
) -> TurnEvalTrial:
    ids = execution.ids
    outcome = execution.outcome
    terminal_outcome = {
        TurnExecutionStatus.COMMITTED: "committed",
        TurnExecutionStatus.FAILED: "failed",
        TurnExecutionStatus.PENDING: "pending",
    }[outcome.status]
    report = outcome.verification_report
    accepted_ids = tuple(report.accepted_evidence_ids) if report else ()
    result = outcome.provider_result
    attempts = attempt_records if attempt_records is not None else _attempt_records(execution)

    def sum_usage(field_name: str) -> int | None:
        values = [
            getattr(item.usage, field_name)
            for item in attempts
            if getattr(item.usage, field_name) is not None
        ]
        return sum(values) if values else None

    costs = [
        item.observed_cost_usd
        for item in attempts
        if item.observed_cost_usd is not None
    ]
    observed_cost = sum(costs, Decimal(0)) if costs else None
    return TurnEvalTrial(
        schema_version="turn_eval_trial.v2",
        trial_id=ids.trial_id,
        case_id=case_id,
        slot_index=slot_index,
        trial_attempt=trial_attempt,
        runtime_input_hash=runtime_input_hash,
        evaluation_contract_hash=evaluation_contract_hash,
        tenant_id=ids.tenant_id,
        user_id=ids.user_id,
        profile_id=ids.profile_id,
        session_id=ids.session_id,
        run_id=ids.run_id,
        operation_id=ids.operation_id,
        started_at=execution.run.started_at,
        completed_at=execution.run.completed_at or execution.run.started_at,
        disposition=disposition,
        included_in_quality_denominator=(
            disposition == TrialDisposition.QUALITY_SCORED
        ),
        had_infrastructure_retry=any(
            item.retryable is True for item in attempts[:-1]
        ),
        terminal_run_status=execution.run.status.value,
        terminal_checkpoint_status=outcome.checkpoint.status.value,
        terminal_outcome=terminal_outcome,
        terminal_reason_code=reason_code,
        attempts=attempts,
        requested_model=requested_model,
        context_hash=result.context_hash if result else None,
        prompt_hash=result.prompt_hash if result else None,
        output_schema_hash=result.output_schema_hash if result else None,
        operation_definition_hash=(
            result.operation_definition_hash if result else None
        ),
        provider_config_hash=provider_config_hash,
        model_catalog_hash=model_catalog_hash,
        endpoint_catalog_hash=endpoint_catalog_hash,
        state_before_hash=execution.state_before_hash,
        state_after_hash=execution.state_after_hash,
        accepted_evidence_ids=accepted_ids,
        verifier_accepted_count=report.accepted_count if report else None,
        verifier_dropped_count=report.dropped_count if report else None,
        verifier_reason_codes=tuple(
            sorted(
                {
                    code.value
                    for decision in (report.decisions if report else ())
                    for code in decision.reason_codes
                }
            )
        ),
        usage_input_tokens=sum_usage("input_tokens"),
        usage_output_tokens=sum_usage("output_tokens"),
        usage_cache_read_tokens=sum_usage("cache_read_tokens"),
        usage_cache_write_tokens=sum_usage("cache_write_tokens"),
        usage_reasoning_tokens=sum_usage("reasoning_tokens"),
        observed_cost_total_usd=observed_cost,
        latency_total_ms=(sum(item.latency_ms for item in attempts) if attempts else None),
        capture_manifest_artifact_id=execution.run.manifest_artifact_id,
        capture_event_count=capture.event_count,
        capture_last_event_hash=capture.last_event_hash,
    )


def trial_output(execution: TrialExecution) -> TurnInterpretOutput | None:
    """The model output as a TurnInterpretOutput, or None for a failed trial."""

    result = execution.outcome.provider_result
    if result is not None and result.parsed_output is not None:
        try:
            return TurnInterpretOutput.model_validate(result.parsed_output.load())
        except Exception:  # noqa: BLE001 — a failed parse is a quality failure
            return None
    report = execution.outcome.verification_report
    if report is None:
        return None
    return None


# ── Bundle writer(§12.2 atomic dir + integrity manifest)─────────────────────


def _atomic_write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n").encode(
            "utf-8"
        )
    )
    os.replace(tmp, path)


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_trial_bundle(
    batch_dir: Path,
    *,
    trial: TurnEvalTrial,
    capture: CaptureBundle,
    grader_results_json: list,
    review_items_json: list,
    final_state_json: dict,
    candidate_output_json: dict | None,
    verification_report_json: dict | None,
) -> Path:
    """Write one trial directory atomically with a root integrity manifest."""

    trial_dir = (
        batch_dir
        / "trials"
        / trial.case_id
        / f"slot-{trial.slot_index:02d}"
        / f"trial-attempt-{trial.trial_attempt:02d}"
    )
    tmp_dir = trial_dir.with_name(trial_dir.name + f".tmp-{trial.trial_id}")
    if tmp_dir.exists():
        for child in sorted(tmp_dir.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        tmp_dir.rmdir()
    (tmp_dir / "capture").mkdir(parents=True)

    _atomic_write_json(tmp_dir / "trial.json", trial.model_dump(mode="json"))
    _atomic_write_json(
        tmp_dir / "capture" / "run.json", capture.manifest.model_dump(mode="json")
    )
    (tmp_dir / "capture" / "events.jsonl").write_bytes(
        (
            "\n".join(
                canonical_json(e.model_dump(mode="json")) for e in capture.events
            )
            + "\n"
        ).encode("utf-8")
    )
    (tmp_dir / "capture" / "artifacts.jsonl").write_bytes(
        (
            "\n".join(
                canonical_json(a.model_dump(mode="json")) for a in capture.artifacts
            )
            + "\n"
        ).encode("utf-8")
    )
    _atomic_write_json(
        tmp_dir / "capture" / "manifest.json", capture.manifest.model_dump(mode="json")
    )
    _atomic_write_json(tmp_dir / "final-state.json", final_state_json)
    _atomic_write_json(tmp_dir / "candidate-output.json", candidate_output_json)
    _atomic_write_json(tmp_dir / "verification-report.json", verification_report_json)
    _atomic_write_json(tmp_dir / "grader-results.json", grader_results_json)
    _atomic_write_json(tmp_dir / "review-item.json", review_items_json)

    # root integrity manifest:除自己以外每個檔案的 relative path/size/sha256
    entries = []
    for path in sorted(tmp_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(tmp_dir).as_posix()
            entries.append(
                {
                    "path": rel,
                    "byte_size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    _atomic_write_json(
        tmp_dir / "integrity-manifest.json",
        {"trial_id": str(trial.trial_id), "files": entries},
    )

    if trial_dir.exists():
        raise FileExistsError(f"trial bundle already exists: {trial_dir}")
    trial_dir.parent.mkdir(parents=True, exist_ok=True)
    os.replace(tmp_dir, trial_dir)
    return trial_dir


# ── Slot scheduling(§9.5)────────────────────────────────────────────────────


@dataclass
class SlotResult:
    case_id: str
    slot_index: int
    executions: list[tuple[int, TrialExecution, TrialDisposition, str | None]] = field(
        default_factory=list
    )
    quality_execution: TrialExecution | None = None
    incomplete: bool = False


LlmFactory = Callable[[TurnEvalCaseInputs, UUID], LlmPort]


async def schedule_slot(
    inputs: TurnEvalCaseInputs,
    *,
    batch_id: UUID,
    case_id: str,
    slot_index: int,
    session_factory: async_sessionmaker,
    llm_factory: LlmFactory,
    binding: ProviderBinding,
    provider_config: object,
    trial_started_at_factory: Callable[[], object],
    max_trial_attempts: int,
    budget: Budget,
    elapsed_seconds_factory: Callable[[], float],
    account_execution: Callable[
        [TrialExecution], Awaitable[tuple[int, Decimal | None]]
    ]
    | None = None,
    on_harness_invalid: Callable[[TrialExecution | None, Exception | None], None]
    | None = None,
) -> SlotResult:
    """Fill one quality slot, replacing infrastructure-only trials (§9.5)."""

    slot_id = slot_uuid(batch_id, case_id, slot_index)
    result = SlotResult(case_id=case_id, slot_index=slot_index)
    for attempt in range(1, max_trial_attempts + 1):
        if not budget.can_start_new_trial(
            elapsed_seconds=elapsed_seconds_factory()
        ):
            raise BudgetExceeded(
                f"budget exhausted before {case_id} slot {slot_index} attempt {attempt}"
            )
        trial_id = trial_uuid(slot_id, attempt)
        error: Exception | None = None
        execution: TrialExecution | None = None
        accounted_calls = 1
        accounted_cost: Decimal | None = None
        try:
            execution = await run_trial(
                inputs,
                session_factory=session_factory,
                llm=llm_factory(inputs, trial_id),
                binding=binding,
                provider_config=provider_config,
                trial_id=trial_id,
                trial_started_at=trial_started_at_factory(),
            )
            if account_execution is not None:
                accounted_calls, accounted_cost = await account_execution(execution)
            else:
                accounted_calls = len(_attempt_records(execution)) or 1
        except Exception as exc:  # noqa: BLE001 — classify below as harness_invalid
            error = exc
        disposition, reason = classify_disposition(execution, error=error)
        budget.charge(
            calls=accounted_calls, cost=accounted_cost
        )
        result.executions.append((attempt, execution, disposition, reason))
        if disposition == TrialDisposition.HARNESS_INVALID:
            if on_harness_invalid is not None:
                on_harness_invalid(execution, error)
            result.incomplete = True
            return result
        if disposition == TrialDisposition.QUALITY_SCORED:
            result.quality_execution = execution
            return result
        # infrastructure_invalid → 保留原 trial,開新 replacement(下一 attempt)
    result.incomplete = True
    return result
