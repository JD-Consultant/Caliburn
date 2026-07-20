from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.operation import ContractIdentity, define_operation
from app.interview_vnext.llm.port import (
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
    ModelMessage,
    ResolvedModelCall,
)
from app.interview_vnext.llm.portable_schema import (
    SchemaProjectionReport,
    SchemaProjectionReportDefinition,
)
from app.interview_vnext.llm.registry import (
    OperationNotFound,
    OperationRegistrationConflict,
    OperationRegistry,
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
from app.interview_vnext.llm.testing import (
    ScriptedLlmPort,
    ScriptedStep,
    scripted_provider_config,
    scripted_turn_binding,
)
from app.interview_vnext.observability.artifacts import build_inline_artifact

from tests.interview_vnext_llm_fixtures import (
    TURN_OUTPUT_SCHEMA_ID,
    binding_artifact_ref,
    config_artifact_ref,
    output_schema_artifact_ref,
    projection_artifact_ref,
    resolved_call,
    turn_output_projection,
    unknown_execution_evidence,
)


SCRIPTED_BINDING = scripted_turn_binding()


NOW = datetime(2026, 7, 16, 1, 0, tzinfo=UTC)


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-vnext-llm:{name}")


def identity(name: str) -> ContractIdentity:
    return ContractIdentity(
        name=name,
        version="1.0.0",
        content_hash=canonical_hash({"identity": name, "version": 1}),
    )


def operation(name: str = "turn.interpret"):
    return define_operation(
        name=name,
        version="1.0.0",
        input_contract=identity(f"{name}.input"),
        output_contract=identity(f"{name}.output"),
        prompt_template=identity(f"{name}.prompt"),
        context_policy=identity(f"{name}.context"),
        quality_profile="high.precision",
        timeout_ms=45_000,
        max_attempts=2,
        max_output_tokens=4_096,
        allowed_tools=(),
        safety_policy_flags=("employee.evidence.only",),
    )


def artifact(kind: str, payload) -> object:
    return build_inline_artifact(
        artifact_id=uid(f"artifact:{kind}"),
        kind=kind,
        media_type="application/json",
        payload=payload,
        run_id=uid("run"),
        session_id=uid("session"),
        created_at=NOW,
    ).ref


def attempt_artifact(request: ModelCallRequest, kind: str, payload):
    return build_inline_artifact(
        artifact_id=uid(f"artifact:{kind}:{request.attempt_id}"),
        kind=kind,
        media_type="application/json",
        payload=payload,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=request.created_at,
    )


def test_model_envelope_rejects_dangling_visible_response_ref() -> None:
    model_request = request(attempt=1, attempt_name="dangling-envelope")
    visible = attempt_artifact(
        model_request, "model.visible_response", {"response": "visible"}
    )
    result = ModelCallResult(
        run_id=model_request.run_id,
        session_id=model_request.session_id,
        turn_id=model_request.turn_id,
        operation_id=model_request.operation_id,
        attempt_id=model_request.attempt_id,
        attempt=model_request.attempt,
        operation_name=model_request.operation_name,
        operation_definition_hash=model_request.operation_definition_hash,
        binding_id=model_request.binding_id,
        binding_hash=model_request.binding_hash,
        gateway_provider=SCRIPTED_BINDING.gateway_provider,
        requested_model=model_request.requested_model,
        resolved_model=model_request.requested_model,
        outcome=ModelOutcome.SUCCEEDED,
        finish_reason=FinishReason.COMPLETED,
        parsed_output=build_structured_payload(
            schema_id=model_request.output_schema_id,
            value={"observations": []},
        ),
        visible_response_artifact=visible.ref,
        usage=TokenUsage(
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
            reasoning_tokens=0,
        ),
        latency_ms=1,
        started_at=model_request.created_at,
        completed_at=model_request.created_at + timedelta(milliseconds=1),
        prompt_hash=model_request.prompt_hash,
        output_schema_id=model_request.output_schema_id,
        output_schema_hash=model_request.output_schema_hash,
        context_hash=model_request.context_hash,
    )

    with pytest.raises(ValidationError, match="missing a referenced"):
        ModelCallEnvelope(
            result=result,
            execution_evidence=unknown_execution_evidence(SCRIPTED_BINDING),
            supporting_artifacts=(),
        )


def request(*, attempt: int, attempt_name: str) -> ModelCallRequest:
    spec = operation()
    binding = SCRIPTED_BINDING
    return ModelCallRequest(
        run_id=uid("run"),
        session_id=uid("session"),
        turn_id=uid("turn"),
        operation_id=uid("operation"),
        attempt_id=uid(f"attempt:{attempt_name}"),
        attempt=attempt,
        operation_name=spec.name,
        operation_definition_hash=spec.definition_hash,
        idempotency_key="turn-7:turn.interpret",
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        requested_model=binding.requested_model,
        instructions="Extract only employee-supported work evidence.",
        messages=(ModelMessage(role=MessageRole.USER, text="我每週整理測試結果。"),),
        prompt_artifact=artifact("prompt.template", {"prompt": "v1"}),
        output_schema_id=TURN_OUTPUT_SCHEMA_ID,
        output_schema_artifact=output_schema_artifact_ref(),
        context_artifact=artifact("context.packet", {"turn": 7}),
        selection_manifest_artifact=artifact("context.selection", {"selected": [7]}),
        binding_artifact=binding_artifact_ref(binding),
        provider_config_artifact=config_artifact_ref(scripted_provider_config()),
        schema_projection_artifact=projection_artifact_ref(),
        created_at=NOW + timedelta(seconds=attempt),
        deadline_at=NOW + timedelta(seconds=attempt + 45),
        max_output_tokens=spec.max_output_tokens,
    )


def complete_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=100,
        output_tokens=20,
        cache_read_tokens=0,
        cache_write_tokens=0,
        reasoning_tokens=0,
    )


def test_operation_definition_is_hash_addressed_and_registry_is_deterministic():
    first = operation("episode.code")
    second = operation("turn.interpret")
    registry = OperationRegistry((second, first))

    assert registry.specs == (first, second)
    assert registry.resolve(first.name, definition_hash=first.definition_hash) == first
    assert registry.register(first) == first
    assert registry.manifest_hash == canonical_hash(
        [item.model_dump(mode="json") for item in (first, second)]
    )

    changed = define_operation(
        **first.model_dump(exclude={"definition_hash", "max_output_tokens"}),
        max_output_tokens=8_192,
    )
    with pytest.raises(OperationRegistrationConflict):
        registry.register(changed)
    with pytest.raises(OperationRegistrationConflict):
        registry.resolve(first.name, definition_hash=changed.definition_hash)
    with pytest.raises(OperationNotFound):
        registry.resolve("missing.operation")


def test_operation_hash_and_ordered_policy_fields_cannot_be_forged():
    spec = operation()
    with pytest.raises(ValidationError, match="definition hash mismatch"):
        type(spec).model_validate(
            {
                **spec.model_dump(),
                "definition_hash": canonical_hash({"forged": True}),
            }
        )

    values = spec.model_dump(exclude={"definition_hash"})
    values["safety_policy_flags"] = ("z.last", "a.first")
    with pytest.raises(ValidationError, match="lexicographically sorted"):
        define_operation(**values)


def test_structured_payload_is_canonical_and_returns_fresh_values():
    payload = build_structured_payload(
        schema_id="turn_interpret.v1",
        value={"evidence": [{"claim": "整理測試結果"}]},
    )
    loaded = payload.load()
    loaded["evidence"][0]["claim"] = "mutated"

    assert payload.load()["evidence"][0]["claim"] == "整理測試結果"
    with pytest.raises(ValidationError, match="canonical JSON"):
        type(payload).model_validate(
            {**payload.model_dump(), "canonical_json": '{"z": 1, "a": 2}'}
        )


def test_result_outcomes_are_explicit_and_mutually_exclusive():
    req = request(attempt=1, attempt_name="success")
    parsed = build_structured_payload(schema_id=req.output_schema_id, value={"evidence": []})
    base = dict(
        run_id=req.run_id,
        session_id=req.session_id,
        turn_id=req.turn_id,
        operation_id=req.operation_id,
        attempt_id=req.attempt_id,
        attempt=req.attempt,
        operation_name=req.operation_name,
        operation_definition_hash=req.operation_definition_hash,
        binding_id=req.binding_id,
        binding_hash=req.binding_hash,
        gateway_provider=SCRIPTED_BINDING.gateway_provider,
        requested_model=req.requested_model,
        resolved_model=req.requested_model,
        usage=complete_usage(),
        latency_ms=5,
        started_at=req.created_at,
        completed_at=req.created_at + timedelta(milliseconds=5),
        prompt_hash=req.prompt_hash,
        output_schema_id=req.output_schema_id,
        output_schema_hash=req.output_schema_hash,
        context_hash=req.context_hash,
        visible_response_artifact=artifact("model.visible_response", {"response": "visible"}),
    )

    succeeded = ModelCallResult(
        **base,
        outcome=ModelOutcome.SUCCEEDED,
        finish_reason=FinishReason.COMPLETED,
        parsed_output=parsed,
    )
    refused = ModelCallResult(
        **base,
        outcome=ModelOutcome.REFUSED,
        finish_reason=FinishReason.SAFETY_REFUSAL,
        refusal=ModelRefusal(reason_code="safety.refusal", safe_message="Request declined."),
    )
    incomplete = ModelCallResult(
        **base,
        outcome=ModelOutcome.INCOMPLETE,
        finish_reason=FinishReason.MAX_OUTPUT_TOKENS,
    )
    failed = ModelCallResult(
        **base,
        outcome=ModelOutcome.FAILED,
        finish_reason=FinishReason.PROVIDER_ERROR,
        failure=ModelFailure(
            kind=FailureKind.RATE_LIMITED,
            reason_code="provider.rate_limited",
            retryable=True,
            safe_message="Provider is busy.",
        ),
    )

    assert {succeeded.outcome, refused.outcome, incomplete.outcome, failed.outcome} == set(
        ModelOutcome
    )
    with pytest.raises(ValidationError, match="succeeded result requires only parsed_output"):
        ModelCallResult(
            **base,
            outcome=ModelOutcome.SUCCEEDED,
            finish_reason=FinishReason.COMPLETED,
            parsed_output=parsed,
            refusal=refused.refusal,
        )


def test_unknown_usage_is_null_with_an_explicit_limitation():
    usage = TokenUsage(limitations=("provider did not report token details",))
    assert usage.input_tokens is None
    assert usage.cache_read_tokens is None
    with pytest.raises(ValidationError, match="null token usage"):
        TokenUsage()


def test_portable_message_history_is_cross_provider_alternating():
    valid = request(attempt=1, attempt_name="message-order")
    values = valid.model_dump()
    values["messages"] = (
        ModelMessage(role=MessageRole.USER, text="first"),
        ModelMessage(role=MessageRole.USER, text="second"),
    )
    with pytest.raises(ValidationError, match="must alternate"):
        ModelCallRequest.model_validate(values)


@pytest.mark.asyncio
async def test_scripted_port_exposes_retry_attempts_without_changing_operation_identity():
    failure = ModelFailure(
        kind=FailureKind.TRANSPORT_TIMEOUT,
        reason_code="provider.timeout",
        retryable=True,
        safe_message="Provider timed out.",
    )
    parsed = build_structured_payload(
        schema_id=TURN_OUTPUT_SCHEMA_ID,
        value={"evidence": [{"claim": "整理測試結果"}]},
    )
    first_request = request(attempt=1, attempt_name="retry-1")
    second_request = request(attempt=2, attempt_name="retry-2")
    visible = attempt_artifact(
        second_request, "model.visible_response", {"response": "visible"}
    )
    port = ScriptedLlmPort(
        {
            "turn.interpret": (
                ScriptedStep(
                    expected_attempt=1,
                    outcome=ModelOutcome.FAILED,
                    finish_reason=FinishReason.PROVIDER_ERROR,
                    failure=failure,
                    usage=TokenUsage(limitations=("request failed before usage",)),
                ),
                ScriptedStep(
                    expected_attempt=2,
                    outcome=ModelOutcome.SUCCEEDED,
                    finish_reason=FinishReason.COMPLETED,
                    parsed_output=parsed,
                    visible_response_artifact=visible.ref,
                    supporting_artifacts=(visible,),
                    usage=complete_usage(),
                ),
            )
        }
    )
    first_envelope = await port.generate_structured(
        resolved_call(first_request, SCRIPTED_BINDING)
    )
    second_envelope = await port.generate_structured(
        resolved_call(second_request, SCRIPTED_BINDING)
    )
    first = first_envelope.result
    second = second_envelope.result

    assert first.outcome == ModelOutcome.FAILED
    assert second.outcome == ModelOutcome.SUCCEEDED
    assert first.operation_id == second.operation_id
    assert first.attempt_id != second.attempt_id
    assert first_request.idempotency_key == second_request.idempotency_key
    assert first.context_hash == second.context_hash
    # v2 scripted port also emits a clean-route artifact alongside the visible one.
    assert second_envelope.supporting_artifacts[0] == visible
    assert len(second_envelope.supporting_artifacts) == 2
    assert port.requests == (first_request, second_request)
    port.assert_exhausted()


@pytest.mark.asyncio
async def test_scripted_port_fails_fast_on_unexpected_order_or_exhaustion():
    port = ScriptedLlmPort(
        {
            "turn.interpret": (
                ScriptedStep(
                    expected_attempt=2,
                    outcome=ModelOutcome.INCOMPLETE,
                    finish_reason=FinishReason.CONTEXT_WINDOW_EXCEEDED,
                    usage=TokenUsage(limitations=("cache details unavailable",)),
                ),
            )
        }
    )
    with pytest.raises(AssertionError, match="expected attempt 2"):
        await port.generate_structured(
            resolved_call(request(attempt=1, attempt_name="wrong"), SCRIPTED_BINDING)
        )


# ---- R3-C1 ResolvedModelCall exact projection identity(修正計畫 §5.3)------


def forged_projection_report(**overrides) -> SchemaProjectionReport:
    """Tamper the active turn projection report and recompute its self-hash."""

    report = turn_output_projection().report
    definition = SchemaProjectionReportDefinition.model_validate(
        {**report.model_dump(exclude={"report_hash"}), **overrides}
    )
    return SchemaProjectionReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )


@pytest.mark.parametrize(
    "overrides",
    [
        # code review 回歸向量(§2.2):2.0.0 -> 9.9.9,report/artifact hash 完整重算。
        {"policy_version": "9.9.9", "policy_hash": "sha256:" + "0" * 64},
        {"policy_name": "portable-lenient-output"},
        {"policy_version": "9.9.9"},
        {"policy_hash": "sha256:" + "0" * 64},
        {"target_profile": "portable-lenient"},
    ],
    ids=["review_vector", "name", "version", "hash", "target_profile"],
)
def test_resolved_call_rejects_forged_projection_policy_identity(overrides):
    """§7.2.5/§7.2.6:report 與 artifact hash 皆正確重算,仍須被 exact policy 驗證拒絕。"""

    forged = forged_projection_report(**overrides)
    base = request(attempt=1, attempt_name="forged-projection")
    tampered = base.model_copy(
        update={"schema_projection_artifact": projection_artifact_ref(forged)}
    )
    with pytest.raises(ValidationError, match="projection"):
        ResolvedModelCall(
            request=tampered, binding=SCRIPTED_BINDING, schema_projection=forged
        )


def test_resolved_call_round_trip_uses_the_same_projection_validator():
    """§7.2.9(pure 面):序列化載回的 resolved call 走同一 exact validator。"""

    call = resolved_call(
        request(attempt=1, attempt_name="round-trip"), SCRIPTED_BINDING
    )
    reloaded = ResolvedModelCall.model_validate(call.model_dump(mode="json"))
    assert reloaded.schema_projection.report_hash == call.schema_projection.report_hash
    assert reloaded.binding.binding_hash == SCRIPTED_BINDING.binding_hash
