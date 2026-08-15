from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.consultant.context import ContextSelectionReceipt
from app.consultant.model_output import (
    ConsultantModelOutput,
    OutputAnalysisBasis,
    OutputCandidatePublication,
    OutputQuestion,
    OutputQuestionKind,
    OutputSufficiency,
)
from app.consultant.model_runtime import (
    AttemptKind,
    AttemptReceipt,
    AttemptStatus,
    AttemptUsage,
)
from app.consultant.results import (
    AnalysisBasis,
    ConsultantResult,
    SufficiencyRecommendation,
)
from app.consultant.run_service import (
    build_configured_execution,
    execute_admitted_consultant_turn,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.state import (
    EmployeeSource,
    EmployeeSourceKind,
    RunReceipt,
    RunStatus,
    SourceProcessingStatus,
    initial_thread_state,
)
from app.consultant.views import ConsultantSnapshot, snapshot_from_state


def _source(document_id: UUID, source_id: UUID) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=source_id,
        document_id=document_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="我負責整理採購需求。",
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})


def _snapshot(document_id: UUID, run_id: UUID, source_id: UUID) -> ConsultantSnapshot:
    state = initial_thread_state(document_id)
    state.update(
        {
            "revision": 1,
            "source_count": 1,
            "latest_source_id": str(source_id),
            "latest_run": RunReceipt(
                run_id=run_id,
                status=RunStatus.SOURCE_SAVED,
                source_id=source_id,
                started_at=datetime.now(UTC),
            ).model_dump(mode="json"),
        }
    )
    return snapshot_from_state(state)


def _result(source_id: UUID) -> ConsultantResult:
    basis = AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("task-boundary",),
    )
    return ConsultantResult(
        visible_reply="我已記錄這項工作，接下來可以再釐清它的完成結果。",
        reply_basis=basis,
        used_skill_ids=("task-boundary",),
        sufficiency=SufficiencyRecommendation(
            currently_enough=True,
            reason="目前資訊足以保留這項工作。",
            continuing_benefit="繼續訪談仍可補充細節。",
            basis=basis,
        ),
    )


def _model_output(source_id: UUID) -> ConsultantModelOutput:
    basis = OutputAnalysisBasis(
        source_ids=(source_id,),
        quote_anchors=(),
        skill_ids=("task-boundary",),
    )
    return ConsultantModelOutput(
        visible_reply="我已記錄這項工作，接下來可以再釐清它的完成結果。",
        analysis_bases=(basis,),
        reply_basis_ordinal=1,
        used_skill_ids=("task-boundary",),
        understanding_changes=(),
        attention_changes=(),
        gaps=(),
        candidate_publication=OutputCandidatePublication(
            candidate_revision=0,
            revision_digest="",
            action_ids=(),
        ),
        question=OutputQuestion(
            kind=OutputQuestionKind.NONE,
            text="",
            answer_target="",
            reason="",
            current_understanding="",
            choices=(),
            affected_work_ids=(),
            affected_branch="",
            basis_ordinal=0,
        ),
        sufficiency=OutputSufficiency(
            currently_enough=True,
            reason="目前資訊足以保留這項工作。",
            remaining_gap_reasons=(),
            continuing_benefit="繼續訪談仍可補充細節。",
            basis_ordinal=1,
        ),
    )


class FakeRuntime:
    def __init__(
        self,
        snapshot: ConsultantSnapshot,
        source: EmployeeSource,
    ) -> None:
        self.snapshot = snapshot
        self.source = source
        self.commits = []
        self.failures: list[tuple[UUID, str, object]] = []

    async def reopen_document(self, document_id: UUID) -> ConsultantSnapshot:
        assert document_id == self.snapshot.document_id
        return self.snapshot

    async def list_sources(self, document_id: UUID):
        assert document_id == self.snapshot.document_id
        return (self.source,)

    async def get_source(self, document_id: UUID, source_id: UUID):
        assert document_id == self.snapshot.document_id
        if source_id != self.source.source_id:
            raise KeyError(source_id)
        return self.source

    async def commit_verified_consultant_result(self, **kwargs):
        self.commits.append(kwargs)
        return self.snapshot

    async def mark_consultant_run_failed(
        self,
        *,
        document_id: UUID,
        run_id: UUID,
        error_code: str,
        execution_evidence=None,
    ) -> ConsultantSnapshot:
        assert document_id == self.snapshot.document_id
        self.failures.append((run_id, error_code, execution_evidence))
        return self.snapshot


class FakeAgent:
    def __init__(
        self, *, result: ConsultantModelOutput, execution, fail: bool = False
    ):
        self.result = result
        self.execution = execution
        self.fail = fail
        self.skill_backend = SimpleNamespace(
            loaded_skill_ids=("task-boundary",)
        )

    async def ainvoke(self, payload, *, context, config):
        assert payload["messages"][0].additional_kwargs[
            "employee_source_id"
        ] == str(context.request.current_source_id)
        if self.fail:
            raise TimeoutError("secret employee payload must not be persisted")
        context.context_receipts.append(
            ContextSelectionReceipt(
                run_id=context.request.run_id,
                document_id=context.snapshot.document_id,
                state_revision=context.snapshot.revision,
                profile_id=self.execution.profile_id,
                profile_revision=self.execution.profile_revision,
                policy_id=self.execution.policy_id,
                policy_revision=self.execution.policy_revision,
                selected_skill_ids=context.request.selected_skill_ids,
                loaded_sources=(),
                omitted_sources=(),
                total_input_tokens=100,
                context_token_budget=self.execution.max_context_tokens,
            )
        )
        callback = config["callbacks"][0]
        now = datetime.now(UTC)
        callback.receipts.append(
            AttemptReceipt(
                attempt_id=uuid4(),
                product_run_id=context.request.run_id,
                status=AttemptStatus.SUCCEEDED,
                attempt_kind=AttemptKind.PRIMARY,
                requested_model=self.execution.requested_model,
                provider_allowlist=self.execution.provider_allowlist,
                actual_model=self.execution.requested_model,
                actual_provider=self.execution.provider_allowlist[0],
                profile_id=self.execution.profile_id,
                profile_revision=self.execution.profile_revision,
                policy_id=self.execution.policy_id,
                policy_revision=self.execution.policy_revision,
                effective_parameters=self.execution.effective_parameters,
                started_at=now,
                completed_at=now,
                latency_ms=0,
                usage=AttemptUsage(
                    input_tokens=80,
                    output_tokens=20,
                    total_tokens=100,
                ),
                cost_usd=Decimal("0"),
                finish_reason="stop",
            )
        )
        return {"structured_response": self.result}


def _settings() -> Settings:
    return Settings(_env_file=None, openrouter_api_key="test-key")


def test_configured_execution_has_all_methods_and_only_non_rag_source_tools() -> None:
    execution = build_configured_execution(_settings())

    assert execution.allowed_skill_ids == CONSULTANT_SKILL_IDS
    assert execution.allowed_tool_ids == (
        "read_file",
        "employee_source_get",
        "employee_source_lineage",
        "employee_source_search",
        "job_document_candidate_edit",
    )
    assert "employee_reference_search" not in execution.allowed_tool_ids


@pytest.mark.asyncio
async def test_admitted_turn_is_verified_then_committed_once() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    execution = build_configured_execution(_settings())
    runtime = FakeRuntime(
        _snapshot(document_id, run_id, source_id),
        _source(document_id, source_id),
    )
    agent_factory_kwargs: dict[str, object] = {}

    def agent_factory(**kwargs: object) -> FakeAgent:
        agent_factory_kwargs.update(kwargs)
        return FakeAgent(result=_model_output(source_id), execution=execution)

    await execute_admitted_consultant_turn(
        runtime=runtime,
        document_id=document_id,
        run_id=run_id,
        source_id=source_id,
        execution=execution,
        model=object(),
        agent_factory=agent_factory,
    )

    binding = agent_factory_kwargs["candidate_edit_binding"]
    assert binding.runtime is runtime
    assert binding.document_id == document_id
    assert binding.run_id == run_id
    assert binding.baseline_revision == 1
    assert binding.selected_skill_ids == CONSULTANT_SKILL_IDS
    assert len(runtime.commits) == 1
    commit = runtime.commits[0]["commit"]
    assert commit.run_id == run_id
    assert commit.answer_source_id == source_id
    assert commit.result == _result(source_id)
    assert commit.execution_evidence is not None
    assert commit.execution_evidence.resolved_execution["profile_id"] == (
        execution.profile_id
    )
    assert len(commit.execution_evidence.context_selection_receipts) == 1
    assert len(commit.execution_evidence.attempt_receipts) == 1
    assert runtime.failures == []


@pytest.mark.asyncio
async def test_failed_model_run_is_durably_classified_without_payload() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    execution = build_configured_execution(_settings())
    runtime = FakeRuntime(
        _snapshot(document_id, run_id, source_id),
        _source(document_id, source_id),
    )

    with pytest.raises(TimeoutError):
        await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            execution=execution,
            model=object(),
            agent_factory=lambda **_: FakeAgent(
                result=_model_output(source_id),
                execution=execution,
                fail=True,
            ),
        )

    assert runtime.commits == []
    assert len(runtime.failures) == 1
    failed_run_id, error_code, evidence = runtime.failures[0]
    assert failed_run_id == run_id
    assert error_code == "timeout"
    assert evidence.resolved_execution["profile_id"] == execution.profile_id
    assert evidence.context_selection_receipts == ()
    assert evidence.attempt_receipts == ()


@pytest.mark.asyncio
async def test_elapsed_run_budget_cancels_hung_agent_and_marks_run_failed() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    execution = build_configured_execution(
        Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            consultant_max_elapsed_seconds=0.02,
        )
    )
    runtime = FakeRuntime(
        _snapshot(document_id, run_id, source_id),
        _source(document_id, source_id),
    )

    class HungAgent:
        skill_backend = SimpleNamespace(loaded_skill_ids=())

        async def ainvoke(self, payload, *, context, config):
            del payload, context
            await config["callbacks"][0].on_chat_model_start(
                {},
                [[]],
                run_id=uuid4(),
                metadata={},
            )
            await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            execute_admitted_consultant_turn(
                runtime=runtime,
                document_id=document_id,
                run_id=run_id,
                source_id=source_id,
                execution=execution,
                model=object(),
                agent_factory=lambda **_: HungAgent(),
            ),
            timeout=0.25,
        )

    assert runtime.commits == []
    assert len(runtime.failures) == 1
    assert runtime.failures[0][0] == run_id
    assert runtime.failures[0][1] == "timeout"
    evidence = runtime.failures[0][2]
    assert len(evidence.attempt_receipts) == 1
    assert evidence.attempt_receipts[0]["status"] == "failed"
    assert evidence.attempt_receipts[0]["error_code"] == "timeout"
