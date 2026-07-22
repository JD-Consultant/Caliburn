"""Shared v2 resolved-call fixtures for interview vNext adapter/executor tests.

V3-5A: a provider adapter or scripted port consumes a ``ResolvedModelCall``
(request + resolved ``ProviderBinding`` + schema projection), not a bare
``ModelCallRequest``. Building a valid call by hand is delicate because the
request, binding and projection are cross-hashed (the request carries the
binding/config/projection artifact refs whose content hashes must match the
canonical hash of each object). These helpers centralise the turn output
projection and the three binding-derived artifact refs so every test builds a
consistent call without duplicating that hash wiring.

R3-C2 adds the scripted provider-gate builders: a fully typed, internally
consistent (request, binding, result/evidence/conformance artifact) set the
durable write and every fresh-process recovery path must be able to validate.

Not a test module (no ``test_`` prefix); imported as ``tests.interview_vnext_llm_fixtures``.
"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.interview_vnext.application.provider_gate import (
    CONFORMANCE_ARTIFACT_KIND,
    EVIDENCE_ARTIFACT_KIND,
    RESULT_ARTIFACT_KIND,
)
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.conformance import (
    ATTRIBUTION_STRICT_POLICY_V1,
    ConformanceReport,
    evaluate_conformance,
)
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
    define_provider_execution_evidence,
)
from app.interview_vnext.llm.port import (
    MessageRole,
    ModelCallRequest,
    ModelMessage,
    ResolvedModelCall,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    ProjectedSchema,
    SchemaProjectionReport,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.schema_exports import SCHEMA_EXPORTS
from app.interview_vnext.llm.schema_ids import (
    CONFORMANCE_SCHEMA_ID,
    EXECUTION_EVIDENCE_SCHEMA_ID,
    MODEL_REQUEST_SCHEMA_ID,
    MODEL_RESULT_SCHEMA_ID,
    PROVIDER_BINDING_SCHEMA_ID,
    SCHEMA_PROJECTION_SCHEMA_ID,
)
from app.interview_vnext.llm.testing import (
    scripted_execution_evidence,
    scripted_provider_config,
    scripted_turn_binding,
)
from app.interview_vnext.llm.turn_interpret import TurnInterpretOutput
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    build_inline_artifact,
)


TURN_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json"
)


@lru_cache(maxsize=1)
def turn_output_projection() -> ProjectedSchema:
    """The active turn output projection the executor builds for every request.

    Byte-identical to the published ``turn-interpret-output.v2`` portable schema,
    so a request whose ``output_schema_artifact`` hashes the published schema is
    consistent with this projection's ``projected_schema_hash``.
    """

    schema_id, title, _factory = SCHEMA_EXPORTS["turn-interpret-output.v2.schema.json"]
    source = {**TurnInterpretOutput.model_json_schema(), "$id": schema_id, "title": title}
    return project_portable_strict_output_schema(
        source,
        source_schema_id=schema_id,
        target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
    )


def turn_output_schema() -> dict[str, Any]:
    return deepcopy(turn_output_projection().schema)


def _ref(payload: Any, *, kind: str, schema_id: str | None = None) -> ArtifactRef:
    content = canonical_json(payload)
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="application/json",
        schema_id=schema_id,
        content_hash=canonical_hash(payload),
        byte_size=len(content.encode("utf-8")),
    )


def output_schema_artifact_ref(schema: dict[str, Any] | None = None) -> ArtifactRef:
    return _ref(
        schema if schema is not None else turn_output_schema(),
        kind="model.output_schema",
        schema_id=TURN_OUTPUT_SCHEMA_ID,
    )


def binding_artifact_ref(binding: ProviderBinding) -> ArtifactRef:
    """Ref whose content hash equals ``canonical_hash(binding)`` (ResolvedModelCall gate)."""

    return _ref(binding, kind="model.provider_binding")


def config_artifact_ref(provider_config: Any) -> ArtifactRef:
    """Ref whose content hash equals ``binding.provider_config_hash``.

    Pass the exact config object (dict or Pydantic model) whose canonical hash the
    binding was built from.
    """

    return _ref(provider_config, kind="provider.config")


def projection_artifact_ref(report: SchemaProjectionReport | None = None) -> ArtifactRef:
    return _ref(
        report if report is not None else turn_output_projection().report,
        kind="model.schema_projection",
    )


def unknown_execution_evidence(
    binding: ProviderBinding, *, usage: TokenUsage | None = None
) -> ProviderExecutionEvidence:
    """Minimal, route-less execution evidence bound to ``binding``.

    ``gateway_resolved_model`` and ``raw_routing_artifact`` are null, so an
    envelope can carry it without also carrying a routing artifact. Attribution
    conformance would reject it (transformation/cache ``unknown``), but the
    envelope shape validators only check binding/provider identity.
    """

    return define_provider_execution_evidence(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        gateway_resolved_model=None,
        upstream_provider=None,
        upstream_model=None,
        upstream_endpoint=None,
        route_strategy=None,
        upstream_attempt_count=None,
        transformation_status=TransformationStatus.UNKNOWN,
        pipeline_stages=(),
        cache_status=CacheStatus.UNKNOWN,
        provider_request_id=None,
        generation_id=None,
        usage=usage or TokenUsage(limitations=("scripted evidence has no usage",)),
        cost_decimal=None,
        limitations=("scripted evidence has no route metadata",),
        raw_routing_artifact=None,
    )


def resolved_call(
    request: ModelCallRequest,
    binding: ProviderBinding,
    *,
    projection: SchemaProjectionReport | None = None,
) -> ResolvedModelCall:
    """Wrap a v2 request and its binding into a consistent ``ResolvedModelCall``."""

    return ResolvedModelCall(
        request=request,
        binding=binding,
        schema_projection=projection or turn_output_projection().report,
    )


# ── R3-C2:scripted provider-gate builders(修正計畫 §5.4/§6.4)──────────────

GATE_NOW = datetime(2026, 7, 19, 6, 0, tzinfo=UTC)
SCRIPTED_OPERATION_HASH = canonical_hash({"operation": "turn.interpret", "v": 1})
_UNSET = object()


def _gate_uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-vnext-gate:{name}")


def _det_ref(
    seed: UUID, label: str, payload: Any, *, kind: str, schema_id: str | None = None
) -> ArtifactRef:
    """Deterministic artifact ref:同一 attempt 種子重建必 byte-identical。"""

    content = canonical_json(payload)
    return ArtifactRef(
        artifact_id=uuid5(seed, label),
        kind=kind,
        media_type="application/json",
        schema_id=schema_id,
        content_hash=canonical_hash(payload),
        byte_size=len(content.encode("utf-8")),
    )


def scripted_model_request(
    *,
    attempt: int = 1,
    name: str = "gate",
    binding: ProviderBinding | None = None,
    provider_config: Any = None,
    run_id: UUID | None = None,
    session_id: UUID | None = None,
    turn_id: UUID | None | object = _UNSET,
    operation_id: UUID | None = None,
    attempt_id: UUID | None = None,
    created_at: datetime | None = None,
) -> ModelCallRequest:
    """A fully-refd scripted v2 request consistent with ``scripted_turn_binding``.

    所有 artifact refs 都以 ``attempt_id`` 為種子 deterministic 生成,因此同一
    attempt 重建 request/gate 完全可重放(PG recovery 測試依賴這點)。
    """

    binding = binding or scripted_turn_binding()
    provider_config = (
        provider_config if provider_config is not None else scripted_provider_config()
    )
    created_at = created_at or (GATE_NOW + timedelta(seconds=attempt))
    attempt_id = attempt_id or _gate_uid(f"{name}:attempt:{attempt}")
    projection = turn_output_projection().report
    return ModelCallRequest(
        run_id=run_id or _gate_uid(f"{name}:run"),
        session_id=session_id or _gate_uid(f"{name}:session"),
        turn_id=_gate_uid(f"{name}:turn") if turn_id is _UNSET else turn_id,
        operation_id=operation_id or _gate_uid(f"{name}:operation"),
        attempt_id=attempt_id,
        attempt=attempt,
        operation_name=binding.operation_name,
        operation_definition_hash=SCRIPTED_OPERATION_HASH,
        idempotency_key=f"{name}:turn.interpret:attempt:{attempt}",
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        requested_model=binding.requested_model,
        instructions="Extract only employee-supported work evidence.",
        messages=(ModelMessage(role=MessageRole.USER, text="我每週整理測試結果。"),),
        prompt_artifact=_det_ref(
            attempt_id, "prompt", {"prompt": "v1"}, kind="prompt.template"
        ),
        output_schema_id=TURN_OUTPUT_SCHEMA_ID,
        output_schema_artifact=_det_ref(
            attempt_id,
            "output-schema",
            turn_output_schema(),
            kind="model.output_schema",
            schema_id=TURN_OUTPUT_SCHEMA_ID,
        ),
        context_artifact=_det_ref(
            attempt_id, "context-packet", {"turn": 7}, kind="context.packet"
        ),
        selection_manifest_artifact=_det_ref(
            attempt_id,
            "context-manifest",
            {"selected": [7]},
            kind="context.selection_manifest",
        ),
        binding_artifact=_det_ref(
            attempt_id,
            "provider-binding",
            binding,
            kind="model.provider_binding",
            schema_id=PROVIDER_BINDING_SCHEMA_ID,
        ),
        provider_config_artifact=_det_ref(
            attempt_id, "provider-config", provider_config, kind="provider.config"
        ),
        schema_projection_artifact=_det_ref(
            attempt_id,
            "schema-projection",
            projection,
            kind="model.schema_projection",
            schema_id=SCHEMA_PROJECTION_SCHEMA_ID,
        ),
        created_at=created_at,
        deadline_at=created_at + timedelta(seconds=45),
        max_output_tokens=4_096,
    )


def _scope_record(
    request: ModelCallRequest,
    *,
    label: str,
    kind: str,
    payload: Any,
    schema_id: str | None,
    created_at: datetime,
) -> ArtifactRecord:
    return build_inline_artifact(
        artifact_id=uuid5(request.attempt_id, label),
        kind=kind,
        media_type="application/json",
        payload=payload,
        schema_id=schema_id,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=created_at,
        contains_test_data=True,
    )


def request_input_records(
    request: ModelCallRequest,
    binding: ProviderBinding,
    *,
    provider_config: Any = None,
    projection: SchemaProjectionReport | None = None,
) -> tuple[ArtifactRecord, ArtifactRecord, ArtifactRecord, ArtifactRecord]:
    """(request, binding, provider-config, schema-projection) records whose refs
    are exactly the ones the request carries — what prepare must persist so the
    durable write and recovery can load them back."""

    provider_config = (
        provider_config if provider_config is not None else scripted_provider_config()
    )
    projection = projection or turn_output_projection().report
    request_record = build_inline_artifact(
        artifact_id=uuid5(request.attempt_id, f"request/{request.attempt}"),
        kind="model.request",
        media_type="application/json",
        payload=request,
        schema_id=MODEL_REQUEST_SCHEMA_ID,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        created_at=request.created_at,
        contains_test_data=True,
    )
    binding_record = build_inline_artifact(
        artifact_id=request.binding_artifact.artifact_id,
        kind=request.binding_artifact.kind,
        media_type="application/json",
        payload=binding,
        schema_id=request.binding_artifact.schema_id,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        created_at=request.created_at,
        contains_test_data=True,
    )
    config_record = build_inline_artifact(
        artifact_id=request.provider_config_artifact.artifact_id,
        kind=request.provider_config_artifact.kind,
        media_type="application/json",
        payload=provider_config,
        schema_id=request.provider_config_artifact.schema_id,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        created_at=request.created_at,
        contains_test_data=True,
    )
    projection_record = build_inline_artifact(
        artifact_id=request.schema_projection_artifact.artifact_id,
        kind=request.schema_projection_artifact.kind,
        media_type="application/json",
        payload=projection,
        schema_id=request.schema_projection_artifact.schema_id,
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        created_at=request.created_at,
        contains_test_data=True,
    )
    return request_record, binding_record, config_record, projection_record


@dataclass(frozen=True)
class GateRecords:
    """One internally consistent persisted provider gate."""

    result: ModelCallResult
    evidence: ProviderExecutionEvidence
    conformance: ConformanceReport
    result_record: ArtifactRecord
    evidence_record: ArtifactRecord
    conformance_record: ArtifactRecord


def scripted_gate_records(
    request: ModelCallRequest,
    binding: ProviderBinding | None = None,
    *,
    outcome: ModelOutcome = ModelOutcome.SUCCEEDED,
    result_override: ModelCallResult | None = None,
    evidence_override: ProviderExecutionEvidence | None = None,
    conformance_override: ConformanceReport | None = None,
) -> GateRecords:
    """Build a typed, cross-hashed provider gate for ``request``.

    ``outcome=SUCCEEDED`` 是 clean 直連成功(eligible conformance);
    ``outcome=FAILED`` 是 retryable transport wire failure(unknown route、
    conformance=wire_not_succeeded)。overrides 用於 tamper 向量:替換其中一件
    後,其餘兩件仍照原值建 artifact,交叉驗證應當拒絕。
    """

    binding = binding or scripted_turn_binding()
    completed_at = request.created_at + timedelta(milliseconds=25)
    identity = dict(
        run_id=request.run_id,
        session_id=request.session_id,
        turn_id=request.turn_id,
        operation_id=request.operation_id,
        attempt_id=request.attempt_id,
        attempt=request.attempt,
        operation_name=request.operation_name,
        operation_definition_hash=request.operation_definition_hash,
        binding_id=request.binding_id,
        binding_hash=request.binding_hash,
        gateway_provider=binding.gateway_provider,
        requested_model=request.requested_model,
        prompt_hash=request.prompt_hash,
        output_schema_id=request.output_schema_id,
        output_schema_hash=request.output_schema_hash,
        context_hash=request.context_hash,
        latency_ms=25,
        started_at=request.created_at,
        completed_at=completed_at,
    )
    if outcome == ModelOutcome.SUCCEEDED:
        usage = TokenUsage(
            input_tokens=100, output_tokens=20, cache_read_tokens=0,
            cache_write_tokens=0, reasoning_tokens=0,
        )
        # deterministic refs:同一 request 重建 gate 必須 byte-identical,
        # tamper 測試才能以「單一欄位漂移」精準命中對應檢查。
        visible_payload = {"response": "visible"}
        visible_ref = ArtifactRef(
            artifact_id=uuid5(request.attempt_id, "visible-response"),
            kind="model.visible_response",
            media_type="application/json",
            content_hash=canonical_hash(visible_payload),
            byte_size=len(canonical_json(visible_payload).encode("utf-8")),
        )
        routing_payload = {"schema_version": "scripted_routing.v1", "strategy": "direct"}
        routing_ref = ArtifactRef(
            artifact_id=uuid5(request.attempt_id, "scripted-routing"),
            kind="provider.scripted.routing",
            media_type="application/json",
            content_hash=canonical_hash(routing_payload),
            byte_size=len(canonical_json(routing_payload).encode("utf-8")),
        )
        result = ModelCallResult(
            **identity,
            resolved_model=binding.requested_model,
            outcome=ModelOutcome.SUCCEEDED,
            finish_reason=FinishReason.COMPLETED,
            parsed_output=build_structured_payload(
                schema_id=request.output_schema_id,
                value={"observations": []},
            ),
            visible_response_artifact=visible_ref,
            usage=usage,
        )
        evidence = scripted_execution_evidence(
            binding, usage=usage, raw_routing_artifact=routing_ref
        )
    elif outcome == ModelOutcome.FAILED:
        usage = TokenUsage(limitations=("no provider usage available after timeout",))
        result = ModelCallResult(
            **identity,
            resolved_model=binding.requested_model,
            outcome=ModelOutcome.FAILED,
            finish_reason=FinishReason.PROVIDER_ERROR,
            failure=ModelFailure(
                kind=FailureKind.TRANSPORT_TIMEOUT,
                reason_code="provider.timeout",
                retryable=True,
                safe_message="Provider timed out.",
            ),
            usage=usage,
        )
        evidence = unknown_execution_evidence(binding, usage=usage)
    else:
        raise ValueError(f"unsupported scripted gate outcome: {outcome}")

    result = result_override if result_override is not None else result
    evidence = evidence_override if evidence_override is not None else evidence
    conformance = (
        conformance_override
        if conformance_override is not None
        else evaluate_conformance(
            policy=ATTRIBUTION_STRICT_POLICY_V1,
            binding=binding,
            evidence=evidence,
            wire_outcome=result.outcome,
        )
    )
    return GateRecords(
        result=result,
        evidence=evidence,
        conformance=conformance,
        result_record=_scope_record(
            request,
            label=f"attempt/{request.attempt}/result",
            kind=RESULT_ARTIFACT_KIND,
            payload=result,
            schema_id=MODEL_RESULT_SCHEMA_ID,
            created_at=completed_at,
        ),
        evidence_record=_scope_record(
            request,
            label="provider-execution-evidence",
            kind=EVIDENCE_ARTIFACT_KIND,
            payload=evidence,
            schema_id=EXECUTION_EVIDENCE_SCHEMA_ID,
            created_at=completed_at,
        ),
        conformance_record=_scope_record(
            request,
            label="provider-conformance",
            kind=CONFORMANCE_ARTIFACT_KIND,
            payload=conformance,
            schema_id=CONFORMANCE_SCHEMA_ID,
            created_at=completed_at,
        ),
    )
