"""V3-5 E3:12 pilot cases 的 reference fixture gate(§18.3)。

每個 case 的 known-good reference output 必須通過 production ContextBuilder/
verifier/pure reducer;任何一項不過代表 case/gold/fixture 壞掉,不得發 live
request(計畫 §6.6)。suite hash 凍結:改任何 case 檔必須同 commit 更新此常數
(challenge manifest freeze,§7.1)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid5

import pytest

from app.interview_vnext.domain.evidence import EvidenceStatus
from evals.interview_vnext.contracts import CaseSplit, ExpectedCommit
from evals.interview_vnext.fixture_builder import (
    ReferenceGateError,
    run_pure_reference_gate,
)
from evals.interview_vnext.identities import prior_evidence_uuid
from evals.interview_vnext.loader import load_suite

CASES_ROOT = Path(__file__).resolve().parents[1] / "evals/interview_vnext/cases"
SUITE_VERSION = "turn-interpret-pilot.v1"
# 凍結的 suite hash(§7.1/§8.1):任何 case 檔變動都必須是「有意的 suite 改版」,
# 同 commit 更新此值;challenge 案一旦用於調整系統即失去未見性(§16.7)。
FROZEN_SUITE_HASH = (
    "sha256:ed51167d64a9887f7a119568ad501ea71e1edd63eace6e44ccba222b5d763d5a"
)
BASE_TIME = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
TRIAL_NAMESPACE = uuid5(
    # 測試專用固定 namespace;正式 batch 的 trial ID 由 batch/slot 派生
    __import__("uuid").NAMESPACE_URL,
    "caliburn:turn-eval:fixtures-test",
)


@pytest.fixture(scope="module")
def suite():
    return load_suite(CASES_ROOT, suite_version=SUITE_VERSION)


@pytest.fixture(scope="module")
def gate_results(suite):
    results = {}
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        trial_id = uuid5(TRIAL_NAMESPACE, inputs.case.case_id)
        results[inputs.case.case_id] = (
            inputs,
            evaluation,
            run_pure_reference_gate(
                inputs, evaluation, trial_id=trial_id, base_time=BASE_TIME
            ),
        )
    return results


def test_suite_shape_and_frozen_hash(suite):
    assert len(suite.runtime_inputs) == 12
    dev = [c for c in suite.runtime_inputs if c.case.split == CaseSplit.DEVELOPMENT]
    challenge = [
        c for c in suite.runtime_inputs if c.case.split == CaseSplit.CHALLENGE
    ]
    assert len(dev) == 8 and len(challenge) == 4
    purposes = [c.case.failure_purpose for c in suite.runtime_inputs]
    assert len(purposes) == len(set(purposes)), "failure purposes must differ"
    assert all(c.case.pilot_only for c in suite.runtime_inputs)
    assert all(c.case.locale == "zh-TW" for c in suite.runtime_inputs)
    assert suite.manifest.suite_hash == FROZEN_SUITE_HASH, (
        "suite content changed; publish a new suite version and update the frozen"
        " hash in the same commit"
    )


def test_all_reference_outputs_pass_the_production_gate(gate_results):
    assert len(gate_results) == 12
    for case_id, (inputs, evaluation, result) in gate_results.items():
        assert result.report.dropped_count == 0, case_id
        if evaluation.gold.expected_commit == ExpectedCommit.EVIDENCE:
            assert result.accepted_count >= 1, case_id
            assert result.state_after_hash != result.state_before_hash, case_id
        else:
            assert result.accepted_count == 0, case_id
            assert result.state_after_hash == result.state_before_hash, case_id


def test_known_correction_supersedes_prior_evidence(gate_results):
    inputs, evaluation, result = gate_results["TI-09-known-correction"]
    prior_id = prior_evidence_uuid(
        result.ids.trial_id, "prior-inventory-report-frequency"
    )
    status = {e.evidence_id: e.status for e in result.state_after.evidence}
    assert status[prior_id] == EvidenceStatus.SUPERSEDED
    accepted = result.report.decisions[0].evidence
    assert accepted is not None and accepted.supersedes == (prior_id,)


def test_unknown_correction_does_not_supersede(gate_results):
    _, evaluation, result = gate_results["TI-10-unknown-correction-target"]
    for key in (
        "prior-inventory-report-frequency",
        "prior-complaint-report-frequency",
    ):
        prior_id = prior_evidence_uuid(result.ids.trial_id, key)
        status = {e.evidence_id: e.status for e in result.state_after.evidence}
        assert status[prior_id] == EvidenceStatus.ACTIVE, key
    accepted = result.report.decisions[0].evidence
    assert accepted is not None
    assert accepted.correction_target_unknown is True
    assert accepted.supersedes == ()


def test_zero_evidence_case_is_a_typed_noop(gate_results):
    inputs, evaluation, result = gate_results["TI-11-zero-evidence"]
    assert result.output.observations == ()
    assert result.state_after_hash == result.state_before_hash
    reasons = {item.reason_code.value for item in result.output.insufficiencies}
    assert "no_work_fact" in reasons


def test_injection_case_anchors_the_actual_occurrence(gate_results):
    inputs, evaluation, result = gate_results["TI-12-injection-unicode-repeat"]
    target_text = inputs.transcript[-1].text
    first_example = target_text.find("檢查報表")
    accepted = result.report.decisions[0]
    assert accepted.computed_span is not None
    # 接受的 span 必須落在第二個 occurrence(實際工作),不是範例文字
    assert accepted.computed_span.start > first_example
    claims = " ".join(o.claim for o in result.output.observations)
    assert "主管權限" not in claims


def test_prior_evidence_becomes_correction_candidates_in_context(gate_results):
    _, _, result = gate_results["TI-09-known-correction"]
    candidate_ids = {
        item.evidence.evidence_id for item in result.context.packet.correction_candidates
    }
    assert prior_evidence_uuid(
        result.ids.trial_id, "prior-inventory-report-frequency"
    ) in candidate_ids


def test_reference_snapshots_are_empty_for_all_cases(suite):
    for inputs in suite.runtime_inputs:
        assert inputs.reference_snapshot.snippets == ()


def test_broken_reference_output_fails_the_gate(suite):
    inputs = suite.runtime_inputs[0]
    evaluation = suite.evaluation_contracts[0]
    reference = evaluation.reference_output
    broken_output = reference.output.model_copy(update={"observations": ()})
    broken = evaluation.model_copy(
        update={"reference_output": reference.model_copy(update={"output": broken_output})}
    )
    with pytest.raises(ReferenceGateError):
        run_pure_reference_gate(
            inputs,
            broken,
            trial_id=uuid5(TRIAL_NAMESPACE, "broken"),
            base_time=BASE_TIME,
        )
