"""Behavior tests for the provider-neutral R1 scripted runners."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.professional_consultant.contracts import (
    BoundaryStatus,
    ClaimCertainty,
    ClaimKind,
    ConsultantAction,
    NextQuestion,
    OwnershipScope,
    Polarity,
    ReconciliationDecision,
    ReconciliationKind,
    SourceClaim,
    SourceSpan,
    Story,
    TaskBoundaryAssessment,
    TaskCandidate,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TimeScope,
    TurnUnderstandOutput,
    Typicality,
    WorkReconcileDecideOutput,
    WorkUnit,
)
from app.professional_consultant.prompts import OperationName, PromptProfile
from app.professional_consultant.runner import (
    OperationFailureCode,
    OperationRunError,
    ProviderCallError,
    StructuredOperationResponse,
    run_task_discovery_once,
    run_task_discovery_two_stage,
)
from app.professional_consultant.schema_projection import SchemaProfile
from evals.professional_consultant.r1.loader import load_runtime_case
from evals.professional_consultant.r1.scripted_provider import ScriptedProvider


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def _runtime_input(
    case_id: str = "TI-R1-01-tools-not-task",
) -> TaskDiscoveryInput:
    return load_runtime_case(CASES_ROOT / case_id).runtime_input


def _empty_output_json() -> str:
    return TaskDiscoveryOutput.model_validate_json(
        """{
          "schema_version":"task_discovery_output.v1",
          "claims":[],
          "unmapped_signals":[],
          "stories":[],
          "work_units":[],
          "decisions":[],
          "task_candidates":[],
          "next_question":{
            "action":"broaden",
            "text":"除了這些工具之外，你平常固定負責完成哪些工作結果？",
            "target_gap":"尚未找到穩定的本人工作責任",
            "claim_ids":[]
          }
        }"""
    ).model_dump_json()


def _understanding_output(source: TaskDiscoveryInput) -> TurnUnderstandOutput:
    text = source.employee_message.text
    return TurnUnderstandOutput(
        schema_version="turn_understand_output.v1",
        claims=(
            SourceClaim(
                claim_id="claim-upgrade",
                kind=ClaimKind.WORK_ACTIVITY,
                statement="每季主責 Java 執行環境升級並確認服務恢復",
                ownership=OwnershipScope.EMPLOYEE_RESPONSIBLE,
                time_scope=TimeScope.CURRENT,
                typicality=Typicality.PERIODIC,
                polarity=Polarity.AFFIRMED,
                certainty=ClaimCertainty.EXPLICIT,
                action="升級",
                object="Java 執行環境",
                recipient=None,
                outcome="服務恢復",
                tool_or_method="Java",
                condition="每季",
                correction_target_claim_id=None,
                anchors=(
                    SourceSpan(
                        message_id=source.employee_message.message_id,
                        start=0,
                        end=len(text),
                        quote=text,
                    ),
                ),
            ),
        ),
        unmapped_signals=(),
    )


def _reconcile_output() -> WorkReconcileDecideOutput:
    work = WorkUnit(
        work_unit_id="work-upgrade",
        statement="執行 Java 執行環境升級並恢復服務",
        claim_ids=("claim-upgrade",),
        story_ids=("story-upgrade",),
        outcome="服務於排定停機後恢復",
        support_claim_ids=("claim-upgrade",),
        counter_claim_ids=(),
        unresolved_boundary=(),
    )
    task = TaskCandidate(
        candidate_id="task-upgrade",
        statement="規劃並完成 Java 執行環境升級以恢復服務",
        work_unit_ids=(work.work_unit_id,),
        support_claim_ids=("claim-upgrade",),
        counter_claim_ids=(),
        boundary=TaskBoundaryAssessment(
            meaningful_outcome=BoundaryStatus.MET,
            role_responsibility=BoundaryStatus.MET,
            assignability=BoundaryStatus.MET,
            checkability=BoundaryStatus.MET,
            stability=BoundaryStatus.MET,
            boundary_coherence=BoundaryStatus.MET,
        ),
        limitations=(),
    )
    return WorkReconcileDecideOutput(
        schema_version="work_reconcile_decide_output.v1",
        stories=(
            Story(
                story_id="story-upgrade",
                summary="季度 Java 執行環境升級",
                claim_ids=("claim-upgrade",),
                outcome="服務恢復",
                gaps=(),
            ),
        ),
        work_units=(work,),
        decisions=(
            ReconciliationDecision(
                decision_id="decision-upgrade",
                kind=ReconciliationKind.ADD,
                candidate_id=task.candidate_id,
                existing_candidate_ids=(),
                work_unit_ids=(work.work_unit_id,),
                rationale="有週期、本人責任與可檢核結果",
                missing_information=None,
            ),
        ),
        task_candidates=(task,),
        next_question=NextQuestion(
            action=ConsultantAction.DEEPEN_STORY,
            text="除了季度升級，還有哪些正式低頻但影響較大的維護責任？",
            target_gap="其他低頻高影響維護責任",
            claim_ids=("claim-upgrade",),
        ),
    )


@pytest.mark.asyncio
async def test_once_runner_returns_only_a_verified_domain_output() -> None:
    source = _runtime_input()
    provider = ScriptedProvider(
        (StructuredOperationResponse(output_text=_empty_output_json()),)
    )

    result = await run_task_discovery_once(
        source,
        provider=provider,
        prompt_profile=PromptProfile.FULL,
        schema_profile=SchemaProfile.LIGHT,
    )

    assert isinstance(result, TaskDiscoveryOutput)
    assert result.task_candidates == ()
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.operation is OperationName.TASK_DISCOVERY
    assert request.prompt.prompt_id == "task-discover.full.v1"
    assert request.output_schema.schema_id == "task-discover-output.light.v1"
    assert json.loads(request.input_text)["employee_message"]["message_id"] == (
        source.employee_message.message_id
    )
    assert {
        "messages",
        "response_format",
        "model",
        "endpoint",
        "provider",
        "headers",
    }.isdisjoint(request.model_dump())


@pytest.mark.asyncio
async def test_once_runner_classifies_invalid_json_before_domain_validation() -> None:
    provider = ScriptedProvider(
        (StructuredOperationResponse(output_text='{"claims":[],"claims":[]}'),)
    )

    with pytest.raises(OperationRunError) as caught:
        await run_task_discovery_once(
            _runtime_input(),
            provider=provider,
            prompt_profile=PromptProfile.FULL,
            schema_profile=SchemaProfile.LIGHT,
        )

    assert caught.value.failure.code is OperationFailureCode.OUTPUT_JSON_INVALID
    assert caught.value.failure.operation is OperationName.TASK_DISCOVERY
    assert caught.value.failure.verification_report is None


@pytest.mark.asyncio
async def test_once_runner_normalizes_only_typed_provider_failures() -> None:
    provider = ScriptedProvider((ProviderCallError("provider unavailable"),))

    with pytest.raises(OperationRunError) as caught:
        await run_task_discovery_once(
            _runtime_input(),
            provider=provider,
            prompt_profile=PromptProfile.FULL,
            schema_profile=SchemaProfile.LIGHT,
        )

    assert caught.value.failure.code is OperationFailureCode.PROVIDER_FAILED
    assert caught.value.failure.verification_report is None
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_two_stage_runner_composes_two_verified_operation_results() -> None:
    source = _runtime_input("TI-R1-02-tool-work-with-outcome")
    understanding = _understanding_output(source)
    reconciliation = _reconcile_output()
    provider = ScriptedProvider(
        (
            StructuredOperationResponse(
                output_text=understanding.model_dump_json()
            ),
            StructuredOperationResponse(
                output_text=reconciliation.model_dump_json()
            ),
        )
    )

    result = await run_task_discovery_two_stage(
        source,
        provider=provider,
        schema_profile=SchemaProfile.HEAVY,
    )

    assert result.claims == understanding.claims
    assert result.task_candidates == reconciliation.task_candidates
    assert [request.operation for request in provider.requests] == [
        OperationName.TURN_UNDERSTAND,
        OperationName.WORK_RECONCILE_DECIDE,
    ]
    assert all(
        request.prompt.profile is PromptProfile.FULL
        for request in provider.requests
    )
    stage_two_input = json.loads(provider.requests[1].input_text)
    assert stage_two_input["understanding"]["claims"][0]["claim_id"] == (
        "claim-upgrade"
    )
    assert "prior_claims" in stage_two_input


@pytest.mark.asyncio
async def test_once_runner_separates_schema_and_verification_failures() -> None:
    source = _runtime_input()
    schema_invalid = ScriptedProvider(
        (StructuredOperationResponse(output_text='{"claims":[]}'),)
    )

    with pytest.raises(OperationRunError) as schema_caught:
        await run_task_discovery_once(
            source,
            provider=schema_invalid,
            prompt_profile=PromptProfile.FULL,
            schema_profile=SchemaProfile.LIGHT,
        )

    repeated = TaskDiscoveryOutput.model_validate_json(
        _empty_output_json()
    ).model_copy(
        update={
            "next_question": NextQuestion(
                action=ConsultantAction.BROADEN,
                text=source.recent_questions[-1],
                target_gap="尚未找到穩定工作責任",
                claim_ids=(),
            )
        }
    )
    verifier_invalid = ScriptedProvider(
        (StructuredOperationResponse(output_text=repeated.model_dump_json()),)
    )
    with pytest.raises(OperationRunError) as verifier_caught:
        await run_task_discovery_once(
            source,
            provider=verifier_invalid,
            prompt_profile=PromptProfile.FULL,
            schema_profile=SchemaProfile.LIGHT,
        )

    assert schema_caught.value.failure.code is (
        OperationFailureCode.OUTPUT_SCHEMA_INVALID
    )
    assert schema_caught.value.failure.verification_report is None
    assert verifier_caught.value.failure.code is (
        OperationFailureCode.VERIFICATION_FAILED
    )
    assert verifier_caught.value.failure.verification_report is not None


@pytest.mark.asyncio
async def test_two_stage_runner_stops_after_invalid_understanding() -> None:
    source = _runtime_input("TI-R1-02-tool-work-with-outcome")
    understanding = _understanding_output(source)
    invalid_claim = understanding.claims[0].model_copy(
        update={
            "anchors": (
                SourceSpan(
                    message_id=source.employee_message.message_id,
                    start=0,
                    end=2,
                    quote="錯誤",
                ),
            )
        }
    )
    invalid_understanding = understanding.model_copy(
        update={"claims": (invalid_claim,)}
    )
    provider = ScriptedProvider(
        (
            StructuredOperationResponse(
                output_text=invalid_understanding.model_dump_json()
            ),
            StructuredOperationResponse(
                output_text=_reconcile_output().model_dump_json()
            ),
        )
    )

    with pytest.raises(OperationRunError) as caught:
        await run_task_discovery_two_stage(
            source,
            provider=provider,
            schema_profile=SchemaProfile.LIGHT,
        )

    assert caught.value.failure.code is OperationFailureCode.VERIFICATION_FAILED
    assert caught.value.failure.operation is OperationName.TURN_UNDERSTAND
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_runner_does_not_rewrite_async_cancellation_as_provider_failure() -> None:
    class CancellingProvider:
        async def generate(self, request):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_task_discovery_once(
            _runtime_input(),
            provider=CancellingProvider(),
            prompt_profile=PromptProfile.FULL,
            schema_profile=SchemaProfile.LIGHT,
        )
