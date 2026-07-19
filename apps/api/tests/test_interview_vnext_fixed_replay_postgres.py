"""V3-3 fixed-replay executor integration tests against real PostgreSQL."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
import sqlalchemy as sa

import app.interview_vnext.application.operation_executor as executor_module
from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.operation_executor import (
    TurnExecutionStatus,
    execute_turn_interpret,
)
from app.interview_vnext.domain.commands import (
    AppendTranscriptTurnCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.evidence import (
    EvidenceKind,
    EvidenceSubject,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.session import (
    ARCHITECTURE_ID,
    SessionStatus,
    session_at,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.llm.port import (
    LlmPort,
    ModelCallEnvelope,
    ModelCallRequest,
    ResolvedModelCall,
)
from app.interview_vnext.llm.testing import (
    scripted_execution_evidence,
    scripted_provider_config,
    scripted_turn_binding,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    ModelRefusal,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.turn_interpret import (
    EpisodeSignal,
    EvidenceQualifiersProposal,
    FrequencyQualifierProposal,
    ObservationProposal,
    TurnInterpretOutput,
    UserSignal,
)
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.checkpoint import CheckpointStatus
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V2
from app.interview_vnext.persistence.errors import CheckpointConflict
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.interview_vnext.application.persistence import WorkflowRun


NOW = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)
EXECUTE_AT = NOW + timedelta(seconds=10)
EMPLOYEE_TEXT = "我每天核對訂單並產出報表。"


def uid(ids, name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-v3-executor:{ids.session_id}:{name}")


def uow_factory(factory):
    return lambda: SqlAlchemyVNextUnitOfWork(factory)


def open_run(ids) -> WorkflowRun:
    taxonomy = INTERVIEW_VNEXT_EXECUTION_V2
    return WorkflowRun(
        run_id=ids.run_id,
        session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID,
        workflow_version="1.0.0",
        taxonomy_id=taxonomy.taxonomy_id,
        taxonomy_version=taxonomy.version,
        taxonomy_hash=taxonomy.content_hash,
        started_at=NOW,
    )


async def commit_bootstrap_command(factory, ids, command, *, name: str, at: datetime):
    return await apply_durable_command(
        uow_factory(factory),
        tenant_id=ids.tenant_id,
        session_id=ids.session_id,
        run_id=ids.run_id,
        command=command,
        stage="turn.receive",
        event_id=uid(ids, f"event/{name}"),
        command_artifact_id=uid(ids, f"command/{name}"),
        reduction_artifact_id=uid(ids, f"reduction/{name}"),
        committed_at=at,
        request_idempotency_key=f"test-bootstrap:{name}",
    )


async def bootstrap(factory, ids) -> TranscriptTurn:
    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version="1.0.0",
            reference_snapshot_id="reference-fixture-v1",
            now=NOW,
        )
    )
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.capture.create_run(
            tenant_id=ids.tenant_id,
            run=open_run(ids),
            snapshot_artifact_id=uid(ids, "initial-state"),
            started_event_id=uid(ids, "event/run-started"),
        )
        await uow.commit()

    await commit_bootstrap_command(
        factory,
        ids,
        TransitionSessionCommand(
            command_id=uid(ids, "activate"),
            expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE,
        ),
        name="activate",
        at=NOW + timedelta(seconds=1),
    )
    consultant = TranscriptTurn(
        turn_id=uid(ids, "turn/consultant"),
        session_id=ids.session_id,
        client_turn_id="test-consultant-1",
        sequence=1,
        role=TranscriptRole.CONSULTANT,
        text="請描述你固定負責的工作與產出。",
        occurred_at=NOW + timedelta(seconds=2),
        received_at=NOW + timedelta(seconds=2),
    )
    await commit_bootstrap_command(
        factory,
        ids,
        AppendTranscriptTurnCommand(
            command_id=uid(ids, "append/consultant"),
            expected_state_version=1,
            occurred_at=NOW + timedelta(seconds=2),
            turn=consultant,
        ),
        name="append-consultant",
        at=NOW + timedelta(seconds=2),
    )
    employee = TranscriptTurn(
        turn_id=uid(ids, "turn/employee"),
        session_id=ids.session_id,
        client_turn_id="test-employee-1",
        sequence=2,
        role=TranscriptRole.EMPLOYEE,
        text=EMPLOYEE_TEXT,
        previous_turn_id=consultant.turn_id,
        occurred_at=NOW + timedelta(seconds=3),
        received_at=NOW + timedelta(seconds=3),
    )
    await commit_bootstrap_command(
        factory,
        ids,
        AppendTranscriptTurnCommand(
            command_id=uid(ids, "append/employee"),
            expected_state_version=2,
            occurred_at=NOW + timedelta(seconds=3),
            turn=employee,
        ),
        name="append-employee",
        at=NOW + timedelta(seconds=3),
    )
    return employee


def qualifiers() -> EvidenceQualifiersProposal:
    return EvidenceQualifiersProposal(
        time_scope=TimeScope.CURRENT,
        typicality=Typicality.TYPICAL,
        polarity=Polarity.AFFIRMED,
        frequency=FrequencyQualifierProposal(
            value=None,
            unit=FrequencyUnit.PER_DAY,
            verbatim="每天",
        ),
        importance=Importance.NOT_STATED,
        ownership=Ownership.OWNER,
    )


def proposal(*, key: str = "obs-01", quote: str = "我每天核對訂單"):
    return ObservationProposal(
        proposal_key=key,
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim="每天核對訂單",
        quote=quote,
        quote_occurrence=1,
        qualifiers=qualifiers(),
        correction_target_evidence_ids=(),
        correction_target_unknown=False,
    )


def output(*observations: ObservationProposal) -> TurnInterpretOutput:
    return TurnInterpretOutput(
        schema_version="turn_interpret_output.v1",
        observations=observations,
        user_signal=UserSignal.ANSWER,
        episode_signal=EpisodeSignal.CONTINUE,
        emergent_topics=(),
        insufficiencies=(),
    )


def usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=100,
        output_tokens=40,
        cache_read_tokens=0,
        cache_write_tokens=0,
        reasoning_tokens=0,
    )


# V3-5A: the executor resolves this binding into a ResolvedModelCall; the scripted
# providers below produce v2 envelopes (wire result + attribution-strict-eligible
# execution evidence) bound to it.
BINDING = scripted_turn_binding()


def _scripted_routing_artifact(request: ModelCallRequest, *, created_at):
    return build_inline_artifact(
        artifact_id=uuid5(request.attempt_id, "scripted-routing"),
        kind="provider.scripted.routing",
        media_type="application/json",
        payload={
            "schema_version": "scripted_routing.v1",
            "strategy": "direct",
            "upstream_attempt_count": 1,
        },
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=created_at,
        contains_test_data=True,
    )


class ResultProvider(LlmPort):
    def __init__(
        self,
        scripts: tuple[str, ...],
        *,
        lock_factory=None,
        lock_tenant_id: UUID | None = None,
        before_return: Callable[[ModelCallRequest], Awaitable[None]] | None = None,
    ) -> None:
        self.scripts = list(scripts)
        self.lock_factory = lock_factory
        self.lock_tenant_id = lock_tenant_id
        self.before_return = before_return
        self.requests: list[ModelCallRequest] = []

    async def generate_structured(
        self, call: ResolvedModelCall
    ) -> ModelCallEnvelope:
        request = call.request
        binding = call.binding
        self.requests.append(request)
        if self.lock_factory is not None:
            assert self.lock_tenant_id is not None
            async with self.lock_factory() as session:
                await session.execute(
                    sa.text(
                        "SELECT run_id FROM interview_vnext_runs "
                        "WHERE run_id = :run_id AND tenant_id = :tenant_id FOR UPDATE"
                    ),
                    {
                        "run_id": str(request.run_id),
                        "tenant_id": str(self.lock_tenant_id),
                    },
                )
                await session.commit()
        if self.before_return is not None:
            await self.before_return(request)
        script = self.scripts.pop(0)
        completed_at = request.created_at + timedelta(seconds=1)
        common = dict(
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            attempt=request.attempt,
            operation_name=request.operation_name,
            operation_definition_hash=request.operation_definition_hash,
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            gateway_provider=binding.gateway_provider,
            requested_model=request.requested_model,
            resolved_model=request.requested_model,
            usage=usage(),
            latency_ms=1000,
            started_at=request.created_at,
            completed_at=completed_at,
            prompt_hash=request.prompt_hash,
            output_schema_id=request.output_schema_id,
            output_schema_hash=request.output_schema_hash,
            context_hash=request.context_hash,
        )
        if script == "timeout":
            return executor_module._timeout_envelope(
                request, binding=binding, now=completed_at
            )
        routing = _scripted_routing_artifact(request, created_at=completed_at)
        evidence = scripted_execution_evidence(
            binding, usage=usage(), raw_routing_artifact=routing.ref
        )

        raw = {
            "success": output(proposal()),
            "partial": output(
                proposal(), proposal(key="obs-02", quote="不存在的逐字引文")
            ),
            "noop": output(),
            "invalid": {"not": "the committed output contract"},
        }.get(script)
        structured_value = (
            raw.model_dump(mode="json")
            if isinstance(raw, TurnInterpretOutput)
            else raw
        )
        visible = build_inline_artifact(
            artifact_id=uuid5(request.attempt_id, "visible-response"),
            kind="model.visible_response",
            media_type="application/json",
            payload={
                "script": script,
                "value": structured_value if structured_value is not None else "refused",
            },
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            created_at=completed_at,
            contains_test_data=True,
        )
        if script == "refusal":
            result = ModelCallResult(
                **common,
                outcome=ModelOutcome.REFUSED,
                finish_reason=FinishReason.SAFETY_REFUSAL,
                refusal=ModelRefusal(
                    reason_code="provider.refused",
                    safe_message="scripted refusal",
                ),
                visible_response_artifact=visible.ref,
            )
        else:
            result = ModelCallResult(
                **common,
                outcome=ModelOutcome.SUCCEEDED,
                finish_reason=FinishReason.COMPLETED,
                parsed_output=build_structured_payload(
                    schema_id=request.output_schema_id,
                    value=structured_value,
                ),
                visible_response_artifact=visible.ref,
            )
        return ModelCallEnvelope(
            result=result,
            execution_evidence=evidence,
            supporting_artifacts=(visible, routing),
        )


class CrashingProvider(LlmPort):
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, call: ResolvedModelCall):
        self.calls += 1
        raise RuntimeError("simulated process loss after durable attempt start")


class BlockingProvider(ResultProvider):
    def __init__(self) -> None:
        super().__init__(("success",))
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.entered_count = 0

    async def generate_structured(
        self, call: ResolvedModelCall
    ) -> ModelCallEnvelope:
        self.entered_count += 1
        self.entered.set()
        await self.release.wait()
        return await super().generate_structured(call)


def execute_kwargs(ids, employee: TranscriptTurn, provider: LlmPort):
    return dict(
        tenant_id=ids.tenant_id,
        run_id=ids.run_id,
        session_id=ids.session_id,
        employee_turn_id=employee.turn_id,
        operation_id=uid(ids, "operation/turn-interpret"),
        idempotency_key="turn-2:interpret",
        llm=provider,
        binding=BINDING,
        provider_config=scripted_provider_config(),
        started_at=EXECUTE_AT,
        now=EXECUTE_AT,
        contains_test_data=True,
    )


async def load_state(factory, ids):
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        return await uow.sessions.get(
            tenant_id=ids.tenant_id, session_id=ids.session_id
        )


async def attempt_rows(factory, ids):
    async with factory() as session:
        return (
            await session.execute(
                sa.text(
                    "SELECT attempt, status, request_artifact_id, result_artifact_id "
                    "FROM interview_vnext_operation_attempts "
                    "WHERE tenant_id = :tenant_id ORDER BY attempt"
                ),
                {"tenant_id": str(ids.tenant_id)},
            )
        ).all()


async def test_executor_commits_verified_evidence_replays_without_provider_and_releases_db(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    provider = ResultProvider(
        ("success",),
        lock_factory=postgres_session_factory,
        lock_tenant_id=ids.tenant_id,
    )
    kwargs = execute_kwargs(ids, employee, provider)

    first = await asyncio.wait_for(
        execute_turn_interpret(uow_factory(postgres_session_factory), **kwargs),
        timeout=5,
    )
    replay = await execute_turn_interpret(
        uow_factory(postgres_session_factory), **kwargs
    )

    assert first.status == TurnExecutionStatus.COMMITTED
    assert first.checkpoint.status == CheckpointStatus.COMMITTED
    assert len(first.accepted_evidence) == 1
    assert first.reduction_result is not None
    assert replay.status == TurnExecutionStatus.COMMITTED
    assert replay.checkpoint == first.checkpoint
    assert len(provider.requests) == 1
    state = await load_state(postgres_session_factory, ids)
    assert [item.claim for item in state.evidence] == ["每天核對訂單"]
    rows = await attempt_rows(postgres_session_factory, ids)
    assert len(rows) == 1 and rows[0].result_artifact_id is not None
    # R3-C1(§7.6):executor 的 provider.config artifact 不宣告不存在的 generic
    # schema ID,content hash 仍等於 binding 引用的 config hash。
    async with postgres_session_factory() as session:
        config_rows = (
            await session.execute(
                sa.text(
                    "SELECT schema_id, content_hash "
                    "FROM interview_vnext_artifacts "
                    "WHERE tenant_id = :tenant_id AND kind = 'provider.config'"
                ),
                {"tenant_id": str(ids.tenant_id)},
            )
        ).all()
    assert len(config_rows) == 1
    assert config_rows[0].schema_id is None
    assert config_rows[0].content_hash == BINDING.provider_config_hash


async def test_two_workers_only_claim_one_provider_call(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    provider = BlockingProvider()
    kwargs = execute_kwargs(ids, employee, provider)
    first_task = asyncio.create_task(
        execute_turn_interpret(uow_factory(postgres_session_factory), **kwargs)
    )
    await asyncio.wait_for(provider.entered.wait(), timeout=2)

    try:
        second = await asyncio.wait_for(
            execute_turn_interpret(uow_factory(postgres_session_factory), **kwargs),
            timeout=2,
        )
        assert second.status == TurnExecutionStatus.PENDING
        assert provider.entered_count == 1
    finally:
        provider.release.set()
    first = await asyncio.wait_for(first_task, timeout=3)

    assert first.status == TurnExecutionStatus.COMMITTED
    assert provider.entered_count == 1
    assert len(provider.requests) == 1


async def test_executor_commits_typed_noop_without_state_mutation(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    before = await load_state(postgres_session_factory, ids)
    provider = ResultProvider(("noop",))

    result = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **execute_kwargs(ids, employee, provider),
    )

    after = await load_state(postgres_session_factory, ids)
    assert result.status == TurnExecutionStatus.COMMITTED
    assert result.noop_result is not None
    assert result.reduction_result is None
    assert result.verification_report.accepted_count == 0
    assert before == after


async def test_executor_commits_only_locally_verified_observations(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    provider = ResultProvider(("partial",))

    result = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **execute_kwargs(ids, employee, provider),
    )

    assert result.verification_report.accepted_count == 1
    assert result.verification_report.dropped_count == 1
    assert len(result.accepted_evidence) == 1
    assert len((await load_state(postgres_session_factory, ids)).evidence) == 1


async def test_existing_calling_attempt_is_not_called_twice_and_timeout_retries(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    crashed = CrashingProvider()
    kwargs = execute_kwargs(ids, employee, crashed)
    with pytest.raises(RuntimeError, match="simulated process loss"):
        await execute_turn_interpret(
            uow_factory(postgres_session_factory), **kwargs
        )

    recovery = ResultProvider(("success",))
    pending_kwargs = execute_kwargs(ids, employee, recovery)
    pending = await execute_turn_interpret(
        uow_factory(postgres_session_factory), **pending_kwargs
    )
    assert pending.status == TurnExecutionStatus.PENDING
    assert recovery.requests == []

    after_deadline = EXECUTE_AT + timedelta(seconds=121)
    recovered = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **{**pending_kwargs, "now": after_deadline},
    )
    assert recovered.status == TurnExecutionStatus.COMMITTED
    assert [request.attempt for request in recovery.requests] == [2]
    rows = await attempt_rows(postgres_session_factory, ids)
    assert [row.attempt for row in rows] == [1, 2]
    assert all(row.result_artifact_id is not None for row in rows)


async def test_recorded_retryable_result_recovers_after_crash_before_next_attempt(
    postgres_session_factory, vnext_profile, monkeypatch
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    real_claim_attempt = executor_module.claim_attempt_for_provider
    starts = 0

    async def crash_before_second_start(*args, **kwargs):
        nonlocal starts
        starts += 1
        if starts == 2:
            raise RuntimeError("simulated crash before retry attempt start")
        return await real_claim_attempt(*args, **kwargs)

    monkeypatch.setattr(
        executor_module, "claim_attempt_for_provider", crash_before_second_start
    )
    first_provider = ResultProvider(("timeout",))
    with pytest.raises(RuntimeError, match="before retry attempt"):
        await execute_turn_interpret(
            uow_factory(postgres_session_factory),
            **execute_kwargs(ids, employee, first_provider),
        )
    rows = await attempt_rows(postgres_session_factory, ids)
    assert [row.attempt for row in rows] == [1]
    assert rows[0].status == "result_recorded"

    monkeypatch.setattr(
        executor_module, "claim_attempt_for_provider", real_claim_attempt
    )
    recovery_provider = ResultProvider(("success",))
    recovered = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **execute_kwargs(ids, employee, recovery_provider),
    )
    assert recovered.status == TurnExecutionStatus.COMMITTED
    assert [request.attempt for request in recovery_provider.requests] == [2]
    assert [row.attempt for row in await attempt_rows(postgres_session_factory, ids)] == [
        1,
        2,
    ]


async def test_schema_repair_is_bounded_and_carries_machine_validation_errors(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    provider = ResultProvider(("invalid", "success"))

    result = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **execute_kwargs(ids, employee, provider),
    )

    assert result.status == TurnExecutionStatus.COMMITTED
    assert [request.attempt for request in provider.requests] == [1, 2]
    repair_message = provider.requests[1].messages[-1].text
    assert "SCHEMA_REPAIR:" in repair_message
    assert '"errors"' in repair_message
    assert "missing" in repair_message


async def test_refusal_is_terminal_and_never_reaches_reducer(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)
    before = await load_state(postgres_session_factory, ids)
    provider = ResultProvider(("refusal",))

    result = await execute_turn_interpret(
        uow_factory(postgres_session_factory),
        **execute_kwargs(ids, employee, provider),
    )

    assert result.status == TurnExecutionStatus.FAILED
    assert result.checkpoint.status == CheckpointStatus.FAILED
    assert result.reason_code == "provider_refused"
    assert await load_state(postgres_session_factory, ids) == before


async def test_state_change_during_provider_call_rejects_stale_verified_commit(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = await bootstrap(postgres_session_factory, ids)

    async def append_concurrent_turn(_request: ModelCallRequest) -> None:
        turn = TranscriptTurn(
            turn_id=uid(ids, "turn/concurrent"),
            session_id=ids.session_id,
            client_turn_id="test-concurrent-1",
            sequence=3,
            role=TranscriptRole.CONSULTANT,
            text="這是 provider 執行期間進來的新訊息。",
            previous_turn_id=employee.turn_id,
            occurred_at=EXECUTE_AT + timedelta(milliseconds=500),
            received_at=EXECUTE_AT + timedelta(milliseconds=500),
        )
        await commit_bootstrap_command(
            postgres_session_factory,
            ids,
            AppendTranscriptTurnCommand(
                command_id=uid(ids, "append/concurrent"),
                expected_state_version=3,
                occurred_at=EXECUTE_AT + timedelta(milliseconds=500),
                turn=turn,
            ),
            name="append-concurrent",
            at=EXECUTE_AT + timedelta(milliseconds=500),
        )

    provider = ResultProvider(("success",), before_return=append_concurrent_turn)
    with pytest.raises(CheckpointConflict, match="state moved"):
        await execute_turn_interpret(
            uow_factory(postgres_session_factory),
            **execute_kwargs(ids, employee, provider),
        )

    state = await load_state(postgres_session_factory, ids)
    assert state.session.state_version == 4
    assert state.evidence == ()
    async with uow_factory(postgres_session_factory)() as uow:
        checkpoint = await uow.checkpoints.get_by_operation(
            tenant_id=ids.tenant_id,
            operation_id=uid(ids, "operation/turn-interpret"),
        )
    assert checkpoint.status == CheckpointStatus.VERIFIED
