"""A1 minimal-bundle baseline behavior tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.professional_consultant.contracts import (
    ConsultantAction,
    NextQuestion,
    TaskDiscoveryOutput,
)
from app.professional_consultant.prompts import PromptProfile
from app.professional_consultant.runner import (
    OperationFailureCode,
    OperationRunError,
    StructuredOperationResponse,
    run_task_discovery_once,
)
from app.professional_consultant.schema_projection import SchemaProfile
from evals.professional_consultant.r1.loader import load_runtime_case
from evals.professional_consultant.r1.minimal_harness import (
    MinimalTaskCandidate,
    MinimalTaskDiscoveryOutput,
    run_minimal_task_discovery_once,
)
from evals.professional_consultant.r1.scripted_provider import ScriptedProvider


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def _question(text: str) -> NextQuestion:
    return NextQuestion(
        action=ConsultantAction.BROADEN,
        text=text,
        target_gap="尚未找到其他穩定且可檢核的本人責任",
        claim_ids=(),
    )


@pytest.mark.asyncio
async def test_a1_minimal_bundle_changes_output_context_and_verifier_policy() -> None:
    source = load_runtime_case(
        CASES_ROOT / "TI-R1-02-tool-work-with-outcome"
    ).runtime_input
    minimal_output = MinimalTaskDiscoveryOutput(
        schema_version="minimal_task_discovery_output.v1",
        task_candidates=(
            MinimalTaskCandidate(
                candidate_id="task-upgrade",
                statement="完成季度 Java 執行環境升級並恢復服務",
            ),
        ),
        next_question=_question("你還固定負責哪些有明確結果的維護工作？"),
    )
    minimal_provider = ScriptedProvider(
        (StructuredOperationResponse(output_text=minimal_output.model_dump_json()),)
    )

    result = await run_minimal_task_discovery_once(
        source, provider=minimal_provider
    )

    assert result == minimal_output
    minimal_request = minimal_provider.requests[0]
    assert minimal_request.prompt.prompt_id == "task-discover.minimal.v1"
    assert minimal_request.output_schema.schema_id == (
        "minimal-task-discover-output.light.v1"
    )
    assert set(json.loads(minimal_request.input_text)) == {
        "schema_version",
        "employee_message",
        "question_context",
        "recent_transcript",
    }

    full_output = TaskDiscoveryOutput(
        schema_version="task_discovery_output.v1",
        claims=(),
        unmapped_signals=(),
        stories=(),
        work_units=(),
        decisions=(),
        task_candidates=(),
        next_question=_question("請再說明一項你目前固定負責的工作結果？"),
    )
    full_provider = ScriptedProvider(
        (StructuredOperationResponse(output_text=full_output.model_dump_json()),)
    )
    await run_task_discovery_once(
        source,
        provider=full_provider,
        prompt_profile=PromptProfile.FULL,
        schema_profile=SchemaProfile.LIGHT,
    )
    full_request = full_provider.requests[0]

    assert minimal_request.output_schema.schema_text != (
        full_request.output_schema.schema_text
    )
    assert "prior_claims" not in minimal_request.input_text
    assert "prior_claims" in full_request.input_text


@pytest.mark.asyncio
async def test_a1_minimal_verifier_rejects_duplicate_tasks_and_repeat_question() -> None:
    source = load_runtime_case(
        CASES_ROOT / "TI-R1-01-tools-not-task"
    ).runtime_input
    duplicate = MinimalTaskCandidate(
        candidate_id="task-duplicate",
        statement="處理工具操作",
    )
    output = MinimalTaskDiscoveryOutput(
        schema_version="minimal_task_discovery_output.v1",
        task_candidates=(duplicate, duplicate),
        next_question=_question(source.recent_questions[-1]),
    )
    provider = ScriptedProvider(
        (StructuredOperationResponse(output_text=output.model_dump_json()),)
    )

    with pytest.raises(OperationRunError) as caught:
        await run_minimal_task_discovery_once(source, provider=provider)

    assert caught.value.failure.code is OperationFailureCode.VERIFICATION_FAILED
    assert caught.value.failure.verification_report is not None
    assert {
        issue.code.value
        for issue in caught.value.failure.verification_report.issues
    } == {"duplicate_id", "duplicate_relation", "repeated_question"}
