"""Immutable R1 trial-capture publication and integrity tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.professional_consultant.contracts import (
    ConsultantAction,
    NextQuestion,
    TaskDiscoveryOutput,
)
from app.professional_consultant.prompts import OperationName, PromptProfile, prompt_for
from app.professional_consultant.runner import (
    OperationFailure,
    OperationFailureCode,
    StructuredOperationRequest,
    StructuredOperationResponse,
)
from app.professional_consultant.schema_projection import (
    SchemaProfile,
    provider_schema_for,
)
from evals.professional_consultant.r1.ablation import ABLATION_ARMS
from evals.professional_consultant.r1.capture import (
    CapturedOperationInput,
    CaptureIntegrityError,
    ContextOperationInputCapture,
    ProviderAttemptEvidence,
    ResolvedResponseFacts,
    SourceStateSnapshot,
    TrialCaptureBundle,
    TrialEvidence,
    TrialStatus,
    read_trial_capture,
    write_trial_capture,
)
from evals.professional_consultant.r1.loader import load_runtime_case


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def _empty_result() -> TaskDiscoveryOutput:
    return TaskDiscoveryOutput(
        schema_version="task_discovery_output.v1",
        claims=(),
        unmapped_signals=(),
        stories=(),
        work_units=(),
        decisions=(),
        task_candidates=(),
        next_question=NextQuestion(
            action=ConsultantAction.BROADEN,
            text="除了目前提到的內容，你固定負責完成哪些明確工作結果？",
            target_gap="尚未找到穩定且可檢核的本人責任",
            claim_ids=(),
        ),
    )


def _request(source_json: str) -> StructuredOperationRequest:
    return StructuredOperationRequest(
        operation=OperationName.TASK_DISCOVERY,
        operation_version="1.0.0",
        prompt=prompt_for(OperationName.TASK_DISCOVERY, PromptProfile.MINIMAL),
        output_schema=provider_schema_for(
            OperationName.TASK_DISCOVERY, SchemaProfile.LIGHT
        ),
        input_text=source_json,
    )


def _successful_bundle() -> TrialCaptureBundle:
    runtime_case = load_runtime_case(CASES_ROOT / "TI-R1-01-tools-not-task")
    arm = ABLATION_ARMS[0]
    trial_id = f"fast-{runtime_case.metadata.case_id}-{arm.arm_id.value}"
    result = _empty_result()
    response = StructuredOperationResponse(output_text=result.model_dump_json())
    request = _request(runtime_case.runtime_input.model_dump_json())
    source = SourceStateSnapshot(
        schema_version="r1_source_state_snapshot.v1",
        trial_id=trial_id,
        case_id=runtime_case.metadata.case_id,
        arm_id=arm.arm_id,
        runtime_case=runtime_case,
    )
    context = ContextOperationInputCapture(
        schema_version="r1_context_operation_input.v1",
        trial_id=trial_id,
        case_id=runtime_case.metadata.case_id,
        arm_id=arm.arm_id,
        calls=(
            CapturedOperationInput(
                call_index=1,
                requested_model="requested/strongest-alias",
                request=request,
            ),
        ),
    )
    evidence = TrialEvidence(
        schema_version="r1_trial_evidence.v1",
        trial_id=trial_id,
        case_id=runtime_case.metadata.case_id,
        arm_id=arm.arm_id,
        status=TrialStatus.SUCCEEDED,
        attempts=(
            ProviderAttemptEvidence(
                call_index=1,
                status="succeeded",
                response=response,
                resolved=ResolvedResponseFacts(
                    evidence_source="response",
                    generation_id="gen-scripted-001",
                    resolved_model="resolved/permanent-model",
                    resolved_provider="Provider Actual",
                    resolved_endpoint="provider-actual/model-endpoint-1",
                ),
            ),
        ),
        result=result,
        failure=None,
    )
    return TrialCaptureBundle(
        arm=arm,
        source_state=source,
        context_operation_input=context,
        trial_evidence=evidence,
    )


def test_capture_publishes_three_layers_then_a_frozen_create_only_manifest(
    tmp_path: Path,
) -> None:
    bundle = _successful_bundle()

    manifest = write_trial_capture(tmp_path, bundle)
    trial_dir = tmp_path / bundle.source_state.trial_id
    loaded = read_trial_capture(tmp_path, bundle.source_state.trial_id)

    assert sorted(path.name for path in trial_dir.iterdir()) == [
        "context-operation-input.json",
        "manifest.json",
        "source-state.json",
        "trial-evidence.json",
    ]
    assert loaded.manifest == manifest
    assert loaded.source_state == bundle.source_state
    assert loaded.context_operation_input == bundle.context_operation_input
    assert loaded.trial_evidence == bundle.trial_evidence
    assert manifest.arm == bundle.arm
    assert manifest.expected_generator_calls == 1
    source_text = (trial_dir / "source-state.json").read_text(encoding="utf-8")
    assert "expectations" not in source_text
    assert "adjudication" not in source_text
    assert loaded.context_operation_input.calls[0].requested_model == (
        "requested/strongest-alias"
    )
    assert loaded.trial_evidence.attempts[0].resolved is not None
    assert loaded.trial_evidence.attempts[0].resolved.resolved_model == (
        "resolved/permanent-model"
    )
    with pytest.raises(ValidationError, match="frozen"):
        manifest.case_id = "changed"  # type: ignore[misc]
    with pytest.raises(FileExistsError):
        write_trial_capture(tmp_path, bundle)


def test_capture_reader_fails_closed_when_referenced_bytes_are_tampered(
    tmp_path: Path,
) -> None:
    bundle = _successful_bundle()
    write_trial_capture(tmp_path, bundle)
    source_path = tmp_path / bundle.source_state.trial_id / "source-state.json"
    source_path.write_bytes(source_path.read_bytes() + b" ")

    with pytest.raises(CaptureIntegrityError, match="digest"):
        read_trial_capture(tmp_path, bundle.source_state.trial_id)


def test_typed_provider_failure_is_terminal_evidence_without_resolved_inference(
    tmp_path: Path,
) -> None:
    success = _successful_bundle()
    failure = OperationFailure(
        code=OperationFailureCode.PROVIDER_FAILED,
        operation=OperationName.TASK_DISCOVERY,
        detail="provider boundary reported a call failure",
        verification_report=None,
    )
    failed_evidence = success.trial_evidence.model_copy(
        update={
            "status": TrialStatus.FAILED,
            "attempts": (
                ProviderAttemptEvidence(
                    call_index=1,
                    status="provider_failed",
                    response=None,
                    resolved=None,
                ),
            ),
            "result": None,
            "failure": failure,
        }
    )
    bundle = success.model_copy(update={"trial_evidence": failed_evidence})

    write_trial_capture(tmp_path, bundle)
    loaded = read_trial_capture(tmp_path, bundle.source_state.trial_id)

    assert loaded.trial_evidence.status is TrialStatus.FAILED
    assert loaded.trial_evidence.failure == failure
    assert loaded.trial_evidence.attempts[0].resolved is None
