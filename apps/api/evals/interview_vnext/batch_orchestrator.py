"""Top-level batch composition: run → export → grade → review → report (§11/§15).

Ties the trial runner, Capture exporter, deterministic graders, blind review
and report together into one batch. The mocked path is a harness self-test: the
scripted provider replays each case's reference output, so every candidate edge
is auto-labelled ``equivalent`` — this proves the pipeline end to end, it is not
a real model adjudication and never yields a promotion-eligible live decision.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.application.operation_executor import (
    TurnInterpretProviderProfile,
)
from app.interview_vnext.domain.hashing import canonical_hash

from .capture_export import export_run_bundle
from .contracts import (
    CaseSplit,
    ExecutionMode,
    ReviewCompleteness,
    ReviewDecisionLabel,
    TrialDisposition,
)
from .fixture_builder import materialize_reference_output
from .identities import trial_scoped_ids, turn_uuid
from .loader import TurnEvalSuite
from .review import build_review_items, edge_decision_map, import_review_decisions
from .scheduler import (
    accepted_proposal_keys,
    build_trial_record,
    committed_kind,
    evidence_status_map,
    trial_output,
    verifier_reason_codes,
    write_trial_bundle,
)
from .turn_eval_runner import TrialExecution, run_trial
from .turn_graders import (
    GradingContext,
    build_candidate_edges,
    compute_trial_metrics,
    run_deterministic_graders,
)
from .turn_report import TrialScore, build_batch_report, render_markdown


@dataclass(frozen=True)
class GradedTrial:
    score: TrialScore
    grader_results: tuple
    review_items: tuple
    candidate_output_json: dict | None
    verification_report_json: dict | None
    final_state_json: dict


def grade_execution(
    inputs,
    evaluation,
    execution: TrialExecution,
    *,
    slot_index: int,
    split: CaseSplit,
    batch_id: UUID,
    decision_labels: dict[tuple[str, str], ReviewDecisionLabel] | None = None,
    review_complete: bool = True,
) -> GradedTrial:
    """Grade one execution;mocked 自測時 ``decision_labels`` 省略 → 全 equivalent。"""

    output = trial_output(execution)
    ctx = GradingContext(
        inputs=inputs,
        gold=evaluation.gold,
        trial_id=execution.ids.trial_id,
        case_id=inputs.case.case_id,
        output=output,
        report=execution.outcome.verification_report,
        committed_kind=committed_kind(execution),
        state_before_hash=execution.state_before_hash,
        state_after_hash=execution.state_after_hash,
        evidence_status=evidence_status_map(execution),
    )
    grader_results = run_deterministic_graders(ctx)

    edges = ()
    review_items = ()
    if output is not None:
        edges = build_candidate_edges(
            inputs, evaluation.gold, output, trial_id=execution.ids.trial_id
        )
        matched = {e.proposal_key for e in edges}
        unmatched = [
            p.proposal_key
            for p in output.observations
            if p.proposal_key not in matched
        ]
        review_items = build_review_items(
            batch_id=batch_id,
            inputs=inputs,
            gold=evaluation.gold,
            output=output,
            accepted_proposal_keys=accepted_proposal_keys(execution),
            verifier_reason_codes=verifier_reason_codes(execution),
            edges=edges,
            unmatched_proposal_keys=unmatched,
        )
        if decision_labels is None:
            decision_labels = {}
            for edge in edges:
                decision_labels[edge.edge_key] = ReviewDecisionLabel.EQUIVALENT
            for key in unmatched:
                decision_labels[("__unmatched__", key)] = (
                    ReviewDecisionLabel.DIFFERENT
                )
        metrics = compute_trial_metrics(
            gold=evaluation.gold,
            output=output,
            edges=edges,
            decisions=decision_labels,
            accepted_proposal_keys=accepted_proposal_keys(execution),
        )
    else:
        metrics = compute_trial_metrics(
            gold=evaluation.gold,
            output=None,
            edges=(),
            decisions={},
            accepted_proposal_keys=frozenset(),
        )

    result = execution.outcome.provider_result
    score = TrialScore(
        trial_id=execution.ids.trial_id,
        case_id=inputs.case.case_id,
        split=split,
        slot_index=slot_index,
        disposition=TrialDisposition.QUALITY_SCORED,
        grader_results=grader_results,
        metrics=metrics,
        review_complete=review_complete,
        inference_calls=1,
        usage_input_tokens=result.usage.input_tokens if result else None,
        usage_output_tokens=result.usage.output_tokens if result else None,
    )
    verification = execution.outcome.verification_report
    return GradedTrial(
        score=score,
        grader_results=grader_results,
        review_items=review_items,
        candidate_output_json=output.model_dump(mode="json") if output else None,
        verification_report_json=(
            verification.model_dump(mode="json") if verification else None
        ),
        final_state_json=execution.state_after.model_dump(mode="json"),
    )


def _reference_llm_factory(suite: TurnEvalSuite):
    from app.interview_vnext.llm.result import (
        FinishReason,
        ModelOutcome,
        build_structured_payload,
    )
    from app.interview_vnext.llm.testing import ScriptedLlmPort, ScriptedStep
    from app.interview_vnext.observability.artifacts import build_inline_artifact
    from datetime import UTC, datetime

    output_schema_id = (
        "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json"
    )
    index_by_id = {c.case.case_id: i for i, c in enumerate(suite.runtime_inputs)}

    def factory(inputs, trial_id, started_at):
        evaluation = suite.evaluation_contracts[index_by_id[inputs.case.case_id]]
        output = materialize_reference_output(
            inputs, evaluation.reference_output, trial_id=trial_id
        )
        ids = trial_scoped_ids(trial_id)
        attempt_id = uuid5(ids.operation_id, "attempt/1")
        visible = build_inline_artifact(
            artifact_id=uuid5(attempt_id, "visible-response"),
            kind="model.visible_response",
            media_type="application/json",
            payload=output.model_dump(mode="json"),
            run_id=ids.run_id,
            session_id=ids.session_id,
            turn_id=turn_uuid(trial_id, inputs.case.target_turn_key),
            operation_id=ids.operation_id,
            attempt_id=attempt_id,
            created_at=started_at,
            contains_test_data=True,
        )
        from app.interview_vnext.llm.result import TokenUsage

        return ScriptedLlmPort(
            {
                "turn.interpret": [
                    ScriptedStep(
                        expected_attempt=1,
                        outcome=ModelOutcome.SUCCEEDED,
                        finish_reason=FinishReason.COMPLETED,
                        parsed_output=build_structured_payload(
                            schema_id=output_schema_id, value=output
                        ),
                        visible_response_artifact=visible.ref,
                        supporting_artifacts=(visible,),
                        usage=TokenUsage(
                            input_tokens=800, output_tokens=120,
                            cache_read_tokens=0, cache_write_tokens=0,
                            reasoning_tokens=0,
                        ),
                    )
                ]
            }
        )

    return factory


@dataclass(frozen=True)
class MockedBatchResult:
    batch_dir: Path
    report_path: Path
    decision: str
    trial_ids: tuple


async def orchestrate_mocked_batch(
    suite: TurnEvalSuite,
    *,
    session_factory: async_sessionmaker,
    output_dir: Path,
    batch_id: UUID,
    trial_started_at,
    git_sha: str,
    dirty_worktree: bool,
) -> MockedBatchResult:
    """Run the full mocked pipeline for 12×3 trials and write a batch bundle.

    Harness self-test:promotion is never eligible (mocked mode + auto-review).
    """

    profile = TurnInterpretProviderProfile(
        provider="scripted", requested_model="scripted-reference"
    )
    factory = _reference_llm_factory(suite)
    batch_dir = output_dir / str(batch_id)
    batch_dir.mkdir(parents=True, exist_ok=True)

    scores = []
    trial_ids = []
    gold_by_case = {}
    split_by_case = {}
    all_review_items = []
    all_decisions = []
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        gold_by_case[inputs.case.case_id] = evaluation.gold
        split_by_case[inputs.case.case_id] = inputs.case.split
        for slot in (1, 2, 3):
            trial_id = uuid5(batch_id, f"{inputs.case.case_id}/slot/{slot}")
            llm = factory(inputs, trial_id, trial_started_at)
            execution = await run_trial(
                inputs,
                session_factory=session_factory,
                llm=llm,
                profile=profile,
                trial_id=trial_id,
                trial_started_at=trial_started_at,
            )
            trial_ids.append(execution.ids)
            bundle = await export_run_bundle(
                session_factory,
                tenant_id=execution.ids.tenant_id,
                run_id=execution.ids.run_id,
            )
            graded = grade_execution(
                inputs, evaluation, execution,
                slot_index=slot, split=inputs.case.split, batch_id=batch_id,
            )
            scores.append(graded.score)
            all_review_items.extend(graded.review_items)
            # 自動裁決:mocked 自測用 equivalent(harness 自證,非真人 adjudication)
            trial = build_trial_record(
                execution,
                case_id=inputs.case.case_id,
                slot_index=slot,
                trial_attempt=1,
                runtime_input_hash=inputs.runtime_input_hash,
                evaluation_contract_hash=evaluation.evaluation_contract_hash,
                disposition=TrialDisposition.QUALITY_SCORED,
                reason_code=None,
                requested_model="scripted-reference",
                capture=bundle,
            )
            write_trial_bundle(
                batch_dir,
                trial=trial,
                capture=bundle,
                grader_results_json=[g.model_dump(mode="json") for g in graded.grader_results],
                review_items_json=[r.model_dump(mode="json") for r in graded.review_items],
                final_state_json=graded.final_state_json,
                candidate_output_json=graded.candidate_output_json,
                verification_report_json=graded.verification_report_json,
            )

    review = ReviewCompleteness(
        required_review_items=len(all_review_items),
        completed_review_items=len(all_review_items),
        needs_sme_count=0,
        failure_traces_read=0,
        passing_trace_sample_required=8,
        passing_trace_sample_read=8,
    )
    report = build_batch_report(
        batch_id=batch_id,
        plan_hash="sha256:" + "0" * 64,
        suite_version=suite.suite_version,
        suite_hash=suite.manifest.suite_hash,
        execution_mode=ExecutionMode.MOCKED,
        git_sha=git_sha,
        dirty_worktree=dirty_worktree,
        gold_by_case=gold_by_case,
        split_by_case=split_by_case,
        scores=scores,
        review=review,
        route_clean=True,
        capture_verified=True,
        created_at=trial_started_at,
        limitations=(
            "mocked provider replays reference output; harness self-test, not a "
            "model quality result",
        ),
    )
    report_path = batch_dir / "batch-report.json"
    report_path.write_bytes(
        (json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    (batch_dir / "batch-report.md").write_bytes(render_markdown(report).encode("utf-8"))
    return MockedBatchResult(
        batch_dir=batch_dir,
        report_path=report_path,
        decision=report.decision.value,
        trial_ids=tuple(trial_ids),
    )
