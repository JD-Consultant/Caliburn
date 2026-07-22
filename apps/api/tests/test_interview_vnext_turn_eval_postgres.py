"""V3-5 E4:12 reference cases 走 real PostgreSQL production stack(§18.6)。

每 trial 全新 user/profile/session/run/tenant;setup 只經公開 durable
commands;ScriptedLlmPort 回放 materialized reference output;production
executor/verifier/reducer/Capture/finalize 全程真跑。CI 缺
``TEST_DATABASE_URL`` 會 fail(見 conftest ``require_postgres``),不允許 skip。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
import pytest_asyncio
import sqlalchemy as sa

from app.interview_vnext.application.operation_executor import (
    TurnExecutionStatus,
)
from app.interview_vnext.application.persistence import RunStatus
from app.interview_vnext.domain.evidence import EvidenceStatus
from app.interview_vnext.llm.result import (
    FinishReason,
    ModelOutcome,
    ModelRefusal,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.testing import (
    ScriptedLlmPort,
    ScriptedStep,
    scripted_provider_config,
    scripted_turn_binding,
)
from app.interview_vnext.observability.artifacts import build_inline_artifact
from evals.interview_vnext.capture_export import export_run_bundle
from evals.interview_vnext.contracts import ExpectedCommit
from evals.interview_vnext.fixture_builder import (
    prior_evidence_id_map,
    run_pure_reference_gate,
)
from evals.interview_vnext.identities import (
    trial_scoped_ids,
    turn_uuid,
)
from evals.interview_vnext.loader import load_suite
from evals.interview_vnext.turn_eval_runner import (
    cleanup_trial_rows,
    run_trial,
)

CASES_ROOT = Path(__file__).resolve().parents[1] / "evals/interview_vnext/cases"
TRIAL_STARTED_AT = datetime(2026, 7, 18, 9, 0, tzinfo=UTC)
OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json"
)
BINDING = scripted_turn_binding()


def trial_uuid_for(case_id: str, salt: str = "pg") -> object:
    return uuid5(NAMESPACE_URL, f"caliburn:turn-eval:pg-test:{salt}:{case_id}")


@pytest.fixture(scope="module")
def suite():
    return load_suite(CASES_ROOT, suite_version="turn-interpret-c1-v2-pilot.v1")


@pytest_asyncio.fixture
async def tracked_cleanup(postgres_session_factory):
    created = []
    yield created
    await cleanup_trial_rows(postgres_session_factory, created)


def usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=800,
        output_tokens=120,
        cache_read_tokens=0,
        cache_write_tokens=0,
        reasoning_tokens=0,
    )


def scripted_reference_llm(inputs, evaluation, trial_id) -> ScriptedLlmPort:
    output = run_pure_reference_gate(
        inputs,
        evaluation,
        trial_id=trial_id,
        base_time=TRIAL_STARTED_AT,
    ).output
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
        created_at=TRIAL_STARTED_AT,
        contains_test_data=True,
    )
    return ScriptedLlmPort(
        {
            "turn.interpret": [
                ScriptedStep(
                    expected_attempt=1,
                    outcome=ModelOutcome.SUCCEEDED,
                    finish_reason=FinishReason.COMPLETED,
                    parsed_output=build_structured_payload(
                        schema_id=OUTPUT_SCHEMA_ID, value=output
                    ),
                    visible_response_artifact=visible.ref,
                    supporting_artifacts=(visible,),
                    usage=usage(),
                )
            ]
        }
    )


async def execute_reference_trial(
    postgres_session_factory, suite, case_id: str, *, salt: str = "pg", cleanup=None
):
    index = [c.case.case_id for c in suite.runtime_inputs].index(case_id)
    inputs = suite.runtime_inputs[index]
    evaluation = suite.evaluation_contracts[index]
    trial_id = trial_uuid_for(case_id, salt)
    if cleanup is not None:
        # 失敗的 trial 也要清:deterministic ID 會讓殘留列撞下一次執行
        cleanup.append(trial_scoped_ids(trial_id))
    llm = scripted_reference_llm(inputs, evaluation, trial_id)
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    llm.assert_exhausted()
    return inputs, evaluation, execution


async def test_all_reference_cases_commit_on_real_postgres(
    postgres_session_factory, suite, tracked_cleanup
):
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        case_id = inputs.case.case_id
        _, _, execution = await execute_reference_trial(
            postgres_session_factory, suite, case_id, cleanup=tracked_cleanup
        )

        assert execution.outcome.status == TurnExecutionStatus.COMMITTED, case_id
        assert execution.run.status == RunStatus.COMPLETED, case_id
        assert execution.run.manifest_artifact_id is not None, case_id
        report = execution.outcome.verification_report
        assert report is not None and report.dropped_count == 0, case_id

        if evaluation.gold.expected_commit == ExpectedCommit.EVIDENCE_AND_RECEIPT:
            assert execution.outcome.reduction_result is not None, case_id
            assert execution.state_after_hash != execution.state_before_hash, case_id
        else:
            assert execution.outcome.reduction_result is not None, case_id
            assert execution.outcome.interpretation_record_ref is not None, case_id
            assert report.accepted_evidence_ids == (), case_id
            assert execution.state_after_hash != execution.state_before_hash, case_id

        expectation = evaluation.gold.state_expectation
        status_by_id = {
            e.evidence_id: e.status for e in execution.state_after.evidence
        }
        prior_ids = prior_evidence_id_map(inputs, trial_id=execution.ids.trial_id)
        for key in expectation.prior_evidence_superseded_keys:
            assert (
                status_by_id[prior_ids[key]]
                == EvidenceStatus.SUPERSEDED
            ), (case_id, key)
        for key in expectation.forbidden_superseded_keys:
            assert (
                status_by_id[prior_ids[key]]
                == EvidenceStatus.ACTIVE
            ), (case_id, key)


async def test_terminal_run_manifest_matches_event_chain(
    postgres_session_factory, suite, tracked_cleanup
):
    _, _, execution = await execute_reference_trial(
        postgres_session_factory, suite, "TI-01-single-action", salt="manifest",
        cleanup=tracked_cleanup,
    )
    ids = execution.ids
    bundle = await export_run_bundle(
        postgres_session_factory, tenant_id=ids.tenant_id, run_id=ids.run_id
    )
    manifest = bundle.manifest
    assert manifest.event_count == len(bundle.events) == execution.run.event_count
    assert manifest.first_event_hash == bundle.events[0].event_hash
    assert manifest.last_event_hash == bundle.events[-1].event_hash
    assert manifest.root_artifacts, "terminal run must carry root artifacts"
    root_kinds = [ref.kind for ref in manifest.root_artifacts]
    assert len({ref.artifact_id for ref in manifest.root_artifacts}) == len(
        manifest.root_artifacts
    )
    assert root_kinds[:4] == [
        "model.request",
        "model.provider_binding",
        "provider.config",
        "model.schema_projection",
    ]
    assert {
            "model.result",
            "model.provider_execution_evidence",
            "model.provider_conformance",
            "interview.turn_interpret_verification_report.v2",
            "interview.turn_interpretation_record.v1",
            "interview.apply_turn_interpretation_command.v1",
            "interview.reduction_result.v2",
            "interview.turn_interpret_output.v2",
            "interview.turn_interpret_execution_outcome.v2",
        }.issubset(root_kinds)

    started = next(
        event for event in bundle.events if event.event_type == "model.call.started"
    )
    result = next(
        event
        for event in bundle.events
        if event.event_type in {"model.call.completed", "model.call.failed"}
    )
    conformance = next(
        event
        for event in bundle.events
        if event.event_type == "provider.conformance.completed"
    )
    assert [ref.kind for ref in started.input_artifacts] == root_kinds[:4]
    assert result.input_artifacts == started.input_artifacts
    assert [ref.kind for ref in result.output_artifacts[-2:]] == [
        "model.result",
        "model.provider_execution_evidence",
    ]
    assert conformance.input_artifacts == (
        started.input_artifacts[1],
        result.output_artifacts[-1],
    )
    assert [ref.kind for ref in conformance.output_artifacts] == [
        "model.provider_conformance"
    ]
    assert result.status.value == conformance.status.value == "ok"


async def test_two_trials_share_no_state(
    postgres_session_factory, suite, tracked_cleanup
):
    _, _, first = await execute_reference_trial(
        postgres_session_factory, suite, "TI-09-known-correction", salt="a",
        cleanup=tracked_cleanup,
    )
    _, _, second = await execute_reference_trial(
        postgres_session_factory, suite, "TI-09-known-correction", salt="b",
        cleanup=tracked_cleanup,
    )
    first_ids = set(first.ids.model_dump(mode="json").values())
    second_ids = set(second.ids.model_dump(mode="json").values())
    assert not (first_ids & second_ids)
    assert first.state_after_hash != second.state_after_hash  # 不同 session/turn UUIDs
    assert first.outcome.status == second.outcome.status == TurnExecutionStatus.COMMITTED


async def test_refusal_finalizes_a_failed_run_without_state_change(
    postgres_session_factory, suite, tracked_cleanup
):
    index = [c.case.case_id for c in suite.runtime_inputs].index(
        "TI-01-single-action"
    )
    inputs = suite.runtime_inputs[index]
    trial_id = trial_uuid_for("TI-01-single-action", "refusal")
    ids = trial_scoped_ids(trial_id)
    tracked_cleanup.append(ids)
    attempt_id = uuid5(ids.operation_id, "attempt/1")
    visible = build_inline_artifact(
        artifact_id=uuid5(attempt_id, "visible-refusal"),
        kind="model.visible_response",
        media_type="application/json",
        payload={"refusal": "The model declined this request."},
        run_id=ids.run_id,
        session_id=ids.session_id,
        turn_id=turn_uuid(trial_id, inputs.case.target_turn_key),
        operation_id=ids.operation_id,
        attempt_id=attempt_id,
        created_at=TRIAL_STARTED_AT,
        contains_test_data=True,
    )
    llm = ScriptedLlmPort(
        {
            "turn.interpret": [
                ScriptedStep(
                    expected_attempt=1,
                    outcome=ModelOutcome.REFUSED,
                    finish_reason=FinishReason.SAFETY_REFUSAL,
                    refusal=ModelRefusal(
                        reason_code="provider_refused",
                        safe_message="The model declined this request.",
                    ),
                    visible_response_artifact=visible.ref,
                    supporting_artifacts=(visible,),
                    usage=usage(),
                )
            ]
        }
    )
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    assert execution.outcome.status == TurnExecutionStatus.FAILED
    assert execution.run.status == RunStatus.FAILED
    assert execution.run.manifest_artifact_id is not None
    assert execution.state_after_hash == execution.state_before_hash


async def test_cleanup_removes_only_the_given_tenant(
    postgres_session_factory, suite, tracked_cleanup
):
    _, _, keep = await execute_reference_trial(
        postgres_session_factory, suite, "TI-11-zero-evidence", salt="keep",
        cleanup=tracked_cleanup,
    )
    _, _, drop = await execute_reference_trial(
        postgres_session_factory, suite, "TI-11-zero-evidence", salt="drop",
        cleanup=tracked_cleanup,
    )
    await cleanup_trial_rows(postgres_session_factory, [drop.ids])
    async with postgres_session_factory() as session:
        kept = (
            await session.execute(
                sa.text(
                    "SELECT count(*) FROM interview_vnext_sessions "
                    "WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": str(keep.ids.tenant_id)},
            )
        ).scalar_one()
        dropped = (
            await session.execute(
                sa.text(
                    "SELECT count(*) FROM interview_vnext_sessions "
                    "WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": str(drop.ids.tenant_id)},
            )
        ).scalar_one()
    assert kept == 1 and dropped == 0
