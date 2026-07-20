"""V3-4R/V3-5A R4 OpenRouter Chat eval adapter — mocked-HTTP wire/evidence tests.

不打 live API;所有 provider 行為經 `httpx.MockTransport` + adapter 的真 JSON
decoder。覆蓋 request projection、single-call/deadline、error matrix、raw/error
artifacts、success/usage/redaction,以及 R4 的 wire/evidence 分離:route/model/
pipeline/cache 污染是 wire success + 誠實 evidence,eligibility 由 application
`attribution-strict/1.0.0` conformance 判定(§12.2)。

規格:docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4, uuid5

import httpx
import pytest

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.binding import ProviderBinding, define_provider_binding
from app.interview_vnext.llm.conformance import (
    ConformanceReasonCode,
    ConformanceReport,
    evaluate_conformance,
    resolve_conformance_policy,
)
from app.interview_vnext.llm.execution import CacheStatus, TransformationStatus
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.port import (
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
    ModelMessage,
    ResolvedModelCall,
)
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.result import FailureKind, FinishReason, ModelOutcome
from app.interview_vnext.llm.schema_exports import published_schema
from app.interview_vnext.observability.artifacts import ArtifactRef

from evals.interview_vnext.openrouter_model_catalog import (
    OpenRouterEndpointSnapshot,
    OpenRouterModelSnapshot,
)
from evals.interview_vnext.openrouter_provider_config import (
    OPENROUTER_ADAPTER_ID,
    OPENROUTER_ADAPTER_VERSION,
    OpenRouterProbeInputs,
    build_openrouter_eval_binding,
    build_openrouter_eval_config,
)
from evals.interview_vnext.providers.openrouter_chat import (
    ERROR_ARTIFACT_KIND,
    ERROR_ARTIFACT_LABEL,
    RAW_ARTIFACT_KIND,
    RAW_ARTIFACT_LABEL,
    ROUTING_ARTIFACT_LABEL,
    VISIBLE_ARTIFACT_LABEL,
    OpenRouterChatEvalAdapter,
)

from tests.interview_vnext_llm_fixtures import (
    TURN_OUTPUT_SCHEMA_ID,
    binding_artifact_ref,
    config_artifact_ref,
    projection_artifact_ref,
    resolved_call,
    turn_output_projection,
)


FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openrouter_chat"
CATALOG_FIXTURES = FIXTURES
API_KEY = "sk-or-eval-test-not-a-real-key"
RUN_ID = uuid5(uuid4(), "run")
CREATED_AT = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)
REQUESTED_MODEL = "testlab/analyst-large"
CANONICAL_MODEL = "testlab/analyst-large-20260717"
ENDPOINT_SLUG = "testhost"


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def build_config(**overrides: Any):
    values: dict[str, Any] = {
        "requested_model": REQUESTED_MODEL,
        "upstream_endpoint_slug": ENDPOINT_SLUG,
        "data_collection": "deny",
        "zdr_required": False,
        "reasoning_effort": "medium",
    }
    values.update(overrides)
    probe_inputs = OpenRouterProbeInputs(**values)
    model_snapshot = OpenRouterModelSnapshot(
        requested_model=REQUESTED_MODEL,
        fetched_at=CREATED_AT,
        url_path=f"/model/{REQUESTED_MODEL}",
        raw=fixture_json("catalog-model.json"),
    )
    endpoint_snapshot = OpenRouterEndpointSnapshot(
        requested_model=REQUESTED_MODEL,
        fetched_at=CREATED_AT,
        url_path=f"/models/{REQUESTED_MODEL}/endpoints",
        raw=fixture_json("catalog-endpoints.json"),
    )
    return build_openrouter_eval_config(probe_inputs, model_snapshot, endpoint_snapshot)


def _text_ref(text: str, *, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="text/markdown",
        content_hash=f"sha256:{digest}",
        byte_size=len(text.encode("utf-8")),
    )


def _json_ref(payload: Any, *, kind: str, schema_id: str | None = None) -> ArtifactRef:
    content = canonical_json(payload)
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="application/json",
        schema_id=schema_id,
        content_hash=canonical_hash(payload),
        byte_size=len(content.encode("utf-8")),
    )


STANDARD_CONFIG = build_config()
STANDARD_BINDING = build_openrouter_eval_binding(STANDARD_CONFIG)


def make_binding(**overrides: Any) -> ProviderBinding:
    """A binding variant for pre-HTTP mismatch tests (V3-5A §6.1).

    Rebuilds the standard OpenRouter binding with field overrides so a request can
    carry a consistent binding whose identity nonetheless disagrees with the
    adapter's config (e.g. a foreign gateway provider or requested model).
    """

    fields = STANDARD_BINDING.model_dump(exclude={"schema_version", "binding_hash"})
    fields.update(overrides)
    return define_provider_binding(**fields)


def make_request(
    *, binding: ProviderBinding | None = None, config: Any = None, **overrides: Any
) -> ModelCallRequest:
    binding = binding or STANDARD_BINDING
    config = config if config is not None else STANDARD_CONFIG
    operation = turn_interpret_operation()
    schema = published_schema("turn-interpret-output.v1.schema.json")
    attempt_id = overrides.pop("attempt_id", uuid4())
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "session_id": uuid4(),
        "turn_id": uuid4(),
        "operation_id": uuid4(),
        "attempt_id": attempt_id,
        "attempt": 1,
        "operation_name": binding.operation_name,
        "operation_definition_hash": operation.definition_hash,
        "idempotency_key": f"turn-interpret/{attempt_id}/1",
        "binding_id": binding.binding_id,
        "binding_hash": binding.binding_hash,
        "requested_model": binding.requested_model,
        "instructions": "You are the Caliburn turn interpreter. Test-only instructions.",
        "messages": (
            ModelMessage(role=MessageRole.USER, text="synthetic employee turn (test)"),
        ),
        "prompt_artifact": _text_ref("test-only prompt", kind="model.prompt"),
        "output_schema_id": TURN_OUTPUT_SCHEMA_ID,
        "output_schema_artifact": _json_ref(
            schema,
            kind="model.output_schema",
            schema_id=TURN_OUTPUT_SCHEMA_ID,
        ),
        "context_artifact": _json_ref({"context": "synthetic"}, kind="model.context"),
        "selection_manifest_artifact": _json_ref(
            {"selection": "synthetic"}, kind="model.selection_manifest"
        ),
        "binding_artifact": binding_artifact_ref(binding),
        "provider_config_artifact": config_artifact_ref(config),
        "schema_projection_artifact": projection_artifact_ref(),
        "deadline_at": CREATED_AT + timedelta(seconds=60),
        "created_at": CREATED_AT,
        "max_output_tokens": operation.max_output_tokens,
    }
    values.update(overrides)
    return ModelCallRequest(**values)


def make_call(
    *,
    binding: ProviderBinding | None = None,
    config: Any = None,
    request: ModelCallRequest | None = None,
    projection: Any = None,
    **overrides: Any,
) -> ResolvedModelCall:
    """A resolved call the adapter executes: request + binding + schema projection.

    The binding and config default to the standard OpenRouter pair (the resolved
    call always models the binding's own config, independent of the adapter the
    call is later handed to). ``projection`` defaults to the active turn output
    projection.
    """

    binding = binding or STANDARD_BINDING
    config = config if config is not None else STANDARD_CONFIG
    request = request or make_request(binding=binding, config=config, **overrides)
    return resolved_call(
        request,
        binding,
        projection=projection or turn_output_projection().report,
    )


class FakeClock:
    def __init__(self, start: datetime = CREATED_AT) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current


def make_adapter(
    handler, **kwargs: Any
) -> tuple[OpenRouterChatEvalAdapter, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        outcome = handler(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    clock = kwargs.pop("clock", None) or FakeClock()
    config = kwargs.pop("config", None) or build_config()
    adapter = OpenRouterChatEvalAdapter(
        api_key=API_KEY,
        config=config,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)),
        now=clock.now,
        **kwargs,
    )
    return adapter, calls


def fixture_response(name: str) -> httpx.Response:
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    meta = manifest["fixtures"][name]
    return httpx.Response(
        meta.get("status", 200),
        json=fixture_json(name),
        headers=meta.get("headers", {}),
    )


def error_body(error_type: str, *, code: int | str | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code if code is not None else error_type,
            "message": f"synthetic {error_type}",
            "metadata": {"error_type": error_type},
        }
    }


def assert_no_secret_anywhere(envelope: ModelCallEnvelope) -> None:
    blobs = [canonical_json(envelope.result)]
    blobs.extend(canonical_json(record) for record in envelope.supporting_artifacts)
    for blob in blobs:
        assert API_KEY not in blob
        assert "Authorization" not in blob
        assert "sk-or-eval" not in blob


def artifact_by_label(envelope: ModelCallEnvelope, label: str) -> dict[str, Any]:
    attempt_id = envelope.result.attempt_id
    stored = {record.ref.artifact_id: record for record in envelope.supporting_artifacts}
    record = stored[uuid5(attempt_id, label)]
    return json.loads(record.inline_content)


def conformance_report(
    envelope: ModelCallEnvelope, binding: ProviderBinding | None = None
) -> ConformanceReport:
    """§5.3:executor/probe 用同一純函式評 eligibility;測試亦然。"""

    binding = binding or STANDARD_BINDING
    policy = resolve_conformance_policy(binding.conformance_policy)
    return evaluate_conformance(
        policy=policy,
        binding=binding,
        evidence=envelope.execution_evidence,
        wire_outcome=envelope.result.outcome,
    )


def assert_wire_success_with_reasons(
    envelope: ModelCallEnvelope,
    expected_reasons: tuple[ConformanceReasonCode, ...],
) -> None:
    """§12.2 三段式:wire success、payload 保留、ineligible + exact reasons。"""

    result = envelope.result
    assert result.outcome is ModelOutcome.SUCCEEDED
    assert result.parsed_output is not None
    assert result.failure is None
    report = conformance_report(envelope)
    assert report.eligible is False
    assert report.reason_codes == expected_reasons
    # conformance-only failure 不建立 ModelFailure/error artifact(§7.4)。
    kinds = {record.ref.kind for record in envelope.supporting_artifacts}
    assert ERROR_ARTIFACT_KIND not in kinds
    assert RAW_ARTIFACT_KIND in kinds
    assert "provider.openrouter.routing" in kinds
    assert "provider.response.visible" in kinds
    assert_no_secret_anywhere(envelope)


def assert_failure(
    envelope: ModelCallEnvelope,
    *,
    kind: FailureKind,
    reason_code: str,
    retryable: bool,
    finish_reason: FinishReason = FinishReason.PROVIDER_ERROR,
) -> None:
    result = envelope.result
    assert result.outcome == ModelOutcome.FAILED, result.outcome
    assert result.finish_reason == finish_reason
    failure = result.failure
    assert failure is not None
    assert failure.kind == kind, failure.kind
    assert failure.reason_code == reason_code, failure.reason_code
    assert failure.retryable is retryable
    error_ref = failure.error_artifact
    assert error_ref is not None
    assert error_ref.artifact_id == uuid5(result.attempt_id, ERROR_ARTIFACT_LABEL)
    stored = {record.ref.artifact_id: record for record in envelope.supporting_artifacts}
    assert stored[error_ref.artifact_id].ref.kind == ERROR_ARTIFACT_KIND
    assert_no_secret_anywhere(envelope)


# ---- config-secret hygiene at adapter boundary ------------------------------


class TestAdapterConfig:
    def test_config_and_body_never_carry_key(self):
        config = build_config()
        assert API_KEY not in canonical_json(config)
        assert config.expected_upstream_provider_name == "TestHost"


# ---- pre-HTTP binding + deadline (§7.1) -------------------------------------


class TestAdapterFailsBeforeHttp:
    async def test_expired_deadline_fails_before_http(self):
        clock = FakeClock(CREATED_AT + timedelta(seconds=120))
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), clock=clock
        )
        envelope = await adapter.generate_structured(make_call())
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.TRANSPORT_TIMEOUT,
            reason_code="openrouter.timeout",
            retryable=True,
        )
        assert envelope.result.usage.input_tokens is None
        assert envelope.result.usage.limitations

    @pytest.mark.parametrize(
        "call_factory",
        [
            # requested model the adapter config does not accept
            lambda: make_call(
                binding=make_binding(
                    requested_model="testlab/analyst-mini",
                    accepted_gateway_models=("testlab/analyst-mini",),
                    accepted_upstream_models=("testlab/analyst-mini",),
                )
            ),
            # operation the eval schema catalog does not publish
            lambda: make_call(binding=make_binding(operation_name="turn.receive")),
            lambda: make_call(operation_definition_hash=f"sha256:{'0' * 64}"),
            lambda: make_call(
                output_schema_id="https://caliburn.local/schemas/unknown.v1.schema.json"
            ),
        ],
        ids=["model", "operation_name", "operation_hash", "output_schema"],
    )
    async def test_binding_mismatches_fail_before_http(self, call_factory):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        envelope = await adapter.generate_structured(call_factory())
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )

    # ---- R3-C1 runtime adapter/binding preflight(修正計畫 §5.1/§7.1)-------

    @pytest.mark.parametrize(
        "overrides",
        [
            {"adapter_id": "openai.responses"},
            {"adapter_version": "1.0.0"},
        ],
        ids=["adapter_id", "adapter_version"],
    )
    async def test_adapter_identity_mismatch_fails_before_http(self, overrides):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        envelope = await adapter.generate_structured(
            make_call(binding=make_binding(**overrides))
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )
        evidence = envelope.execution_evidence
        # evidence 描述實際 runtime adapter,不從不相符的 binding 複製(§5.1.1)。
        assert evidence.adapter_id == OPENROUTER_ADAPTER_ID
        assert evidence.adapter_version == OPENROUTER_ADAPTER_VERSION
        assert any("binding preflight" in item for item in evidence.limitations)

    async def test_gateway_mismatch_records_runtime_adapter_facts(self):
        """§7.1 gateway 向量:result/evidence 都記 runtime gateway,identity 保留 attempted。"""

        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        attempted = make_binding(gateway_provider="openai")
        envelope = await adapter.generate_structured(make_call(binding=attempted))
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )
        result = envelope.result
        assert result.gateway_provider == "openrouter"  # actual runtime gateway
        assert result.binding_id == attempted.binding_id  # attempted identity
        assert result.binding_hash == attempted.binding_hash
        assert result.requested_model == attempted.requested_model
        evidence = envelope.execution_evidence
        assert evidence.gateway_provider == "openrouter"
        assert evidence.adapter_id == OPENROUTER_ADAPTER_ID
        assert evidence.adapter_version == OPENROUTER_ADAPTER_VERSION
        assert evidence.binding_id == attempted.binding_id
        assert evidence.binding_hash == attempted.binding_hash

    @pytest.mark.parametrize(
        "drift_overrides",
        [
            # §7.1.5:只有 reasoning field 不同。
            {"reasoning_effort": "high"},
            # §7.1.6:只有 data-collection routing/privacy field 不同。
            {"data_collection": "allow"},
        ],
        ids=["reasoning", "data_collection"],
    )
    async def test_runtime_config_drift_fails_before_http(self, drift_overrides):
        """§7.1.7:requested model 相同、只有 config hash 不同仍拒絕。"""

        drifted = build_config(**drift_overrides)
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), config=drifted
        )
        call = make_call()  # standard binding + standard config
        assert drifted.requested_model == call.binding.requested_model
        assert drifted.config_hash != call.binding.provider_config_hash
        envelope = await adapter.generate_structured(call)
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )
        # §7.1.8:error artifact 只能含 hash,不得洩漏 config 欄位或值。
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        blob = canonical_json(error)
        assert "reasoning_effort" not in blob
        assert "data_collection" not in blob
        assert drifted.config_hash in blob or call.binding.provider_config_hash in blob

    async def test_schema_hash_mismatch_fails_before_http(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        # A portable-but-different output schema: the catalog compares the request's
        # output-schema hash against the published schema and fails closed. In v2 the
        # request and projection must stay internally consistent, so the tampered
        # schema is projected and referenced by both.
        tampered = published_schema("turn-interpret-output.v1.schema.json")
        tampered["properties"]["tampered"] = {"type": "string"}
        tampered["required"] = [*tampered["required"], "tampered"]
        projected = project_portable_strict_output_schema(
            tampered,
            source_schema_id=TURN_OUTPUT_SCHEMA_ID,
            target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
        )
        request = make_request(
            output_schema_artifact=_json_ref(
                projected.schema,
                kind="model.output_schema",
                schema_id=TURN_OUTPUT_SCHEMA_ID,
            ),
            schema_projection_artifact=projection_artifact_ref(projected.report),
        )
        envelope = await adapter.generate_structured(
            make_call(request=request, projection=projected.report)
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )

    async def test_reasoning_budget_exceeding_output_fails_before_http(self):
        # R3-C1:變體 config 帶自己的 binding,讓 runtime preflight 通過後
        # 仍能命中既有的 reasoning-budget 檢查(INVALID_REQUEST,而非 preflight)。
        variant = build_config(reasoning_effort=None, reasoning_max_tokens=8192)
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), config=variant
        )
        # operation.max_output_tokens is 4096 < 8192 reasoning budget.
        envelope = await adapter.generate_structured(
            make_call(binding=build_openrouter_eval_binding(variant), config=variant)
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )


# ---- outbound request projection (§7.2/§7.3/§7.5) ---------------------------


class TestAdapterRequestProjection:
    async def test_exact_url_headers_body_and_forbidden_keys(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        call = make_call()
        request = call.request
        envelope = await adapter.generate_structured(call)
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert len(calls) == 1
        call = calls[0]
        assert str(call.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert call.method == "POST"
        assert call.headers["authorization"] == f"Bearer {API_KEY}"
        assert call.headers["content-type"] == "application/json"
        assert call.headers["accept"] == "application/json"
        assert call.headers["x-openrouter-metadata"] == "enabled"
        for forbidden_header in ("x-openrouter-cache", "http-referer", "x-openrouter-title"):
            assert forbidden_header not in {name.lower() for name in call.headers}

        body = json.loads(call.content)
        assert body["model"] == REQUESTED_MODEL
        assert body["stream"] is False
        assert body["max_tokens"] == request.max_output_tokens
        assert body["messages"] == [
            {"role": "system", "content": request.instructions},
            {"role": "user", "content": "synthetic employee turn (test)"},
        ]
        text_format = body["response_format"]
        assert text_format["type"] == "json_schema"
        assert text_format["json_schema"]["name"] == "turn_interpret_output_v1"
        assert text_format["json_schema"]["strict"] is True
        assert canonical_hash(text_format["json_schema"]["schema"]) == (
            request.output_schema_hash
        )
        assert text_format["json_schema"]["schema"] == published_schema(
            "turn-interpret-output.v1.schema.json"
        )
        assert body["provider"] == {
            "order": [ENDPOINT_SLUG],
            "only": [ENDPOINT_SLUG],
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        }
        assert body["plugins"] == [
            {"id": "context-compression", "enabled": False},
            {"id": "response-healing", "enabled": False},
            {"id": "web", "enabled": False},
            {"id": "file-parser", "enabled": False},
        ]
        assert body["reasoning"] == {"effort": "medium", "exclude": True}

        for forbidden in (
            "models", "route", "preset", "session_id", "user", "trace",
            "tools", "tool_choice", "parallel_tool_calls",
            "transforms", "web_search_options",
            "temperature", "top_p", "top_k", "seed",
            "n", "stop", "logprobs", "stream_options", "metadata",
        ):
            assert forbidden not in body, forbidden

    async def test_zdr_only_sent_when_required(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        await adapter.generate_structured(make_call())
        assert "zdr" not in json.loads(calls[0].content)["provider"]

        # R3-C1:exact runtime preflight 下,變體 config 必須帶自己的 binding。
        variant = build_config(zdr_required=True)
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), config=variant
        )
        await adapter.generate_structured(
            make_call(binding=build_openrouter_eval_binding(variant), config=variant)
        )
        assert json.loads(calls[0].content)["provider"]["zdr"] is True

    async def test_reasoning_max_tokens_variant_is_exclusive_form(self):
        variant = build_config(reasoning_effort=None, reasoning_max_tokens=2048)
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), config=variant
        )
        await adapter.generate_structured(
            make_call(binding=build_openrouter_eval_binding(variant), config=variant)
        )
        assert json.loads(calls[0].content)["reasoning"] == {
            "max_tokens": 2048,
            "exclude": True,
        }

    async def test_no_reasoning_when_disabled(self):
        variant = build_config(reasoning_effort=None)
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"), config=variant
        )
        await adapter.generate_structured(
            make_call(binding=build_openrouter_eval_binding(variant), config=variant)
        )
        assert "reasoning" not in json.loads(calls[0].content)

    async def test_messages_are_mapped_verbatim_including_unicode(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        await adapter.generate_structured(
            make_call(
                instructions="系統指示:嚴格輸出 JSON。\n第二行。",
                messages=(
                    ModelMessage(role=MessageRole.USER, text="第一題:員工說了什麼?"),
                    ModelMessage(role=MessageRole.ASSISTANT, text="請描述你的日常。"),
                    ModelMessage(
                        role=MessageRole.USER, text="我負責 API 設計與 code review。"
                    ),
                ),
            )
        )
        body = json.loads(calls[0].content)
        assert body["messages"] == [
            {"role": "system", "content": "系統指示:嚴格輸出 JSON。\n第二行。"},
            {"role": "user", "content": "第一題:員工說了什麼?"},
            {"role": "assistant", "content": "請描述你的日常。"},
            {"role": "user", "content": "我負責 API 設計與 code review。"},
        ]


# ---- single-call / deadline / cancellation (§8) -----------------------------


class TestSingleCallSemantics:
    @pytest.mark.parametrize(
        "handler",
        [
            lambda request: httpx.Response(429, json=error_body("rate_limit_exceeded", code=429)),
            lambda request: httpx.Response(500, json=error_body("server", code=500)),
            lambda request: httpx.ReadTimeout("provider stalled"),
            lambda request: httpx.ConnectError("refused"),
        ],
    )
    async def test_adapter_never_retries(self, handler):
        adapter, calls = make_adapter(handler)
        await adapter.generate_structured(make_call())
        assert len(calls) == 1

    async def test_transport_timeout_is_typed(self):
        adapter, calls = make_adapter(
            lambda request: httpx.ReadTimeout("provider stalled")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.TRANSPORT_TIMEOUT,
            reason_code="openrouter.timeout",
            retryable=True,
        )

    async def test_transport_error_is_typed(self):
        adapter, calls = make_adapter(
            lambda request: httpx.ConnectError("refused")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.TRANSPORT_ERROR,
            reason_code="openrouter.transport_error",
            retryable=True,
        )

    async def test_cancelled_error_propagates(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise asyncio.CancelledError()

        adapter, calls = make_adapter(handler)
        with pytest.raises(asyncio.CancelledError):
            await adapter.generate_structured(make_call())
        assert len(calls) == 1

    async def test_external_client_is_not_closed_by_adapter(self):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: fixture_response("success.json")
            )
        )
        adapter = OpenRouterChatEvalAdapter(
            api_key=API_KEY, config=build_config(), http_client=client,
            now=FakeClock().now,
        )
        await adapter.generate_structured(make_call())
        await adapter.aclose()
        assert not client.is_closed
        await client.aclose()


# ---- HTTP / embedded error matrix (§10) -------------------------------------


class TestErrorMatrix:
    @pytest.mark.parametrize(
        ("error_type", "status", "kind", "reason_code", "retryable", "finish"),
        [
            ("context_length_exceeded", 400, FailureKind.INVALID_REQUEST,
             "openrouter.context_window_exceeded", False,
             FinishReason.CONTEXT_WINDOW_EXCEEDED),
            ("max_tokens_exceeded", 400, FailureKind.INVALID_REQUEST,
             "openrouter.max_tokens_exceeded", False, FinishReason.MAX_OUTPUT_TOKENS),
            ("token_limit_exceeded", 400, FailureKind.INVALID_REQUEST,
             "openrouter.token_limit_exceeded", False, FinishReason.MAX_OUTPUT_TOKENS),
            ("string_too_long", 400, FailureKind.INVALID_REQUEST,
             "openrouter.string_too_long", False, FinishReason.CONTEXT_WINDOW_EXCEEDED),
            ("authentication", 401, FailureKind.AUTHENTICATION_FAILED,
             "openrouter.authentication_failed", False, FinishReason.PROVIDER_ERROR),
            ("permission_denied", 403, FailureKind.AUTHENTICATION_FAILED,
             "openrouter.permission_denied", False, FinishReason.PROVIDER_ERROR),
            ("payment_required", 402, FailureKind.RATE_LIMITED,
             "openrouter.credits_unavailable", False, FinishReason.PROVIDER_ERROR),
            ("rate_limit_exceeded", 429, FailureKind.RATE_LIMITED,
             "openrouter.rate_limited", True, FinishReason.PROVIDER_ERROR),
            ("provider_overloaded", 503, FailureKind.PROVIDER_UNAVAILABLE,
             "openrouter.provider_overloaded", True, FinishReason.PROVIDER_ERROR),
            ("provider_unavailable", 502, FailureKind.PROVIDER_UNAVAILABLE,
             "openrouter.provider_unavailable", True, FinishReason.PROVIDER_ERROR),
            ("timeout", 504, FailureKind.TRANSPORT_TIMEOUT,
             "openrouter.provider_timeout", True, FinishReason.PROVIDER_ERROR),
            ("server", 500, FailureKind.PROVIDER_UNAVAILABLE,
             "openrouter.server_error", True, FinishReason.PROVIDER_ERROR),
            ("invalid_request", 400, FailureKind.INVALID_REQUEST,
             "openrouter.invalid_request", False, FinishReason.PROVIDER_ERROR),
            ("invalid_prompt", 400, FailureKind.INVALID_REQUEST,
             "openrouter.invalid_prompt", False, FinishReason.PROVIDER_ERROR),
            ("not_found", 404, FailureKind.INVALID_REQUEST,
             "openrouter.not_found", False, FinishReason.PROVIDER_ERROR),
            ("precondition_failed", 412, FailureKind.INVALID_REQUEST,
             "openrouter.precondition_failed", False, FinishReason.PROVIDER_ERROR),
            ("payload_too_large", 413, FailureKind.INVALID_REQUEST,
             "openrouter.payload_too_large", False, FinishReason.PROVIDER_ERROR),
            ("unprocessable", 422, FailureKind.INVALID_REQUEST,
             "openrouter.unprocessable", False, FinishReason.PROVIDER_ERROR),
        ],
    )
    async def test_stable_error_type_matrix(
        self, error_type, status, kind, reason_code, retryable, finish
    ):
        adapter, calls = make_adapter(
            lambda request: httpx.Response(
                status,
                json=error_body(error_type, code=status),
                headers={"x-request-id": f"req_{error_type}"},
            )
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope, kind=kind, reason_code=reason_code,
            retryable=retryable, finish_reason=finish,
        )
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        assert error["error_type"] == error_type
        assert error["http_status"] == status

    async def test_refusal_error_types_map_to_refused(self):
        for error_type in ("content_policy_violation", "refusal"):
            adapter, _ = make_adapter(
                lambda request, et=error_type: httpx.Response(
                    403, json=error_body(et, code=403)
                )
            )
            envelope = await adapter.generate_structured(make_call())
            result = envelope.result
            assert result.outcome == ModelOutcome.REFUSED
            assert result.finish_reason == FinishReason.SAFETY_REFUSAL
            assert result.refusal is not None
            assert result.refusal.safe_message == "The model declined this request."
            assert error_type not in result.refusal.safe_message
            assert_no_secret_anywhere(envelope)

    async def test_http_200_top_level_error_wins_over_status(self):
        adapter, _ = make_adapter(lambda request: fixture_response("top-error-200.json"))
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.RATE_LIMITED,
            reason_code="openrouter.rate_limited",
            retryable=True,
        )
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        assert error["status_mismatch"] is True
        assert error["retry_after_seconds"] == 7

    async def test_choice_embedded_error_precedes_partial_content(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("choice-embedded-error.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            reason_code="openrouter.provider_unavailable",
            retryable=True,
        )
        assert envelope.result.parsed_output is None
        assert envelope.result.provider_finish_reason.startswith("embedded_error:")
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"][0]["text"] == "partial output before the upstream failure"

    async def test_non_2xx_without_error_object_uses_status_fallback(self):
        adapter, _ = make_adapter(
            lambda request: httpx.Response(500, json={"foo": "bar"})
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            reason_code="openrouter.server_error",
            retryable=True,
        )

    async def test_non_json_error_body_is_captured(self):
        adapter, _ = make_adapter(
            lambda request: httpx.Response(503, text="<html>gateway</html>")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            reason_code="openrouter.provider_overloaded",
            retryable=True,
        )
        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["http"]["status_code"] == 503

    async def test_2xx_non_json_body_is_output_parse_failure(self):
        adapter, _ = make_adapter(
            lambda request: httpx.Response(200, text="not json at all")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.output_parse_failed",
            retryable=False,
        )

    @pytest.mark.parametrize(
        ("status", "retryable"),
        [(451, False), (599, True)],
    )
    async def test_completely_unknown_status_codes(self, status, retryable):
        adapter, _ = make_adapter(
            lambda request: httpx.Response(status, json={"unknown": True})
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.FAILED
        assert result.failure.kind == FailureKind.UNKNOWN_PROVIDER_FAILURE
        assert result.failure.retryable is retryable

    async def test_error_type_status_mismatch_records_both(self):
        # error_type says auth (non-retryable) but HTTP status is 500.
        adapter, _ = make_adapter(
            lambda request: httpx.Response(500, json=error_body("authentication"))
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.AUTHENTICATION_FAILED,
            reason_code="openrouter.authentication_failed",
            retryable=False,
        )
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        assert error["error_type"] == "authentication"
        assert error["http_status"] == 500

    async def test_error_artifact_has_no_key_and_deterministic_scope(self):
        adapter, _ = make_adapter(
            lambda request: httpx.Response(401, json=error_body("authentication"))
        )
        call = make_call()
        request = call.request
        envelope = await adapter.generate_structured(call)
        error_ref = envelope.result.failure.error_artifact
        assert error_ref.artifact_id == uuid5(request.attempt_id, ERROR_ARTIFACT_LABEL)
        record = {r.ref.artifact_id: r for r in envelope.supporting_artifacts}[
            error_ref.artifact_id
        ]
        assert record.run_id == request.run_id
        assert record.attempt_id == request.attempt_id
        assert record.retention_class == "eval"
        assert "sk-or" not in record.inline_content


# ============================ R4: success / routing / usage ==================

EXPECTED_SUCCESS_OUTPUT = {
    "schema_version": "turn_interpret_output.v1",
    "observations": [],
    "user_signal": "answer",
    "episode_signal": "continue",
    "emergent_topics": [],
    "insufficiencies": [],
}


def clean_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "requested": REQUESTED_MODEL,
        "strategy": "direct",
        "attempt": 1,
        "endpoints": [
            {"provider": "TestHost", "model": REQUESTED_MODEL, "selected": True}
        ],
        "attempts": [{"provider": "TestHost", "model": REQUESTED_MODEL, "status": 200}],
        "pipeline": [],
    }
    metadata.update(overrides)
    return metadata


def success_body(**overrides: Any) -> dict[str, Any]:
    body = fixture_json("success.json")
    metadata_overrides = overrides.pop("metadata", None)
    body.update(overrides)
    if metadata_overrides is not None:
        body["openrouter_metadata"] = metadata_overrides
    return body


def respond(body: dict[str, Any], *, status: int = 200, headers: dict | None = None):
    return httpx.Response(
        status, json=body, headers=headers or {"x-request-id": "req_fx_success"}
    )


class TestSuccessPath:
    async def test_success_parses_single_object_with_full_capture(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert len(calls) == 1
        assert result.outcome == ModelOutcome.SUCCEEDED
        assert result.finish_reason == FinishReason.COMPLETED
        assert result.provider_finish_reason == "chat:stop|native:end_turn"
        assert result.resolved_model == REQUESTED_MODEL
        assert result.provider_request_id == "req_fx_success"
        assert result.provider_conversation_id is None
        assert result.parsed_output is not None
        assert result.parsed_output.load() == EXPECTED_SUCCESS_OUTPUT

        usage = result.usage
        assert usage.input_tokens == 1200
        assert usage.output_tokens == 350
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 256
        assert usage.reasoning_tokens == 128
        assert usage.limitations == ()

        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["schema_version"] == "openrouter_chat_raw.v1"
        assert raw["gateway"] == "openrouter"
        assert raw["http"]["status_code"] == 200
        assert raw["redactions"] == []

        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["schema_version"] == "openrouter_routing.v2"
        assert routing["resolved_model"] == REQUESTED_MODEL
        assert routing["metadata_requested_model"] == REQUESTED_MODEL
        assert routing["catalog_canonical_model"] == CANONICAL_MODEL
        assert routing["configured_endpoint_slug"] == ENDPOINT_SLUG
        assert routing["expected_provider_name"] == "TestHost"
        assert routing["selected_provider_name"] == "TestHost"
        assert routing["selected_model"] == REQUESTED_MODEL
        assert routing["selected_count"] == 1
        assert routing["strategy"] == "direct"
        assert routing["router_attempt"] == 1
        assert routing["generation_id"] == "gen-fx-success"
        assert isinstance(routing["cost"], str)
        assert float(routing["cost"]) == pytest.approx(0.00123)
        assert routing["usage_total_mismatch"] is False
        assert routing["pipeline_stage_summaries"] == []
        assert routing["transformation_status"] == "clean"
        assert routing["cache_status"] == "absent"
        assert routing["cache_header_value"] is None
        assert routing["normalization_limitations"] == []
        # §7.4:artifact 是 observation,不含任何 eligibility verdict。
        for forbidden in ("conformance", "eligible", "pipeline_clean"):
            assert forbidden not in routing

        # §7.5:evidence 只記 actual facts;endpoint 由 outbound + response 共同 attest。
        evidence = envelope.execution_evidence
        assert evidence.gateway_resolved_model == REQUESTED_MODEL
        assert evidence.upstream_provider == "TestHost"
        assert evidence.upstream_model == REQUESTED_MODEL
        assert evidence.upstream_endpoint == ENDPOINT_SLUG
        assert evidence.route_strategy == "direct"
        assert evidence.upstream_attempt_count == 1
        assert evidence.transformation_status == TransformationStatus.CLEAN
        assert evidence.pipeline_stages == ()
        assert evidence.cache_status == CacheStatus.ABSENT
        assert evidence.limitations == ()
        assert evidence.raw_routing_artifact is not None
        assert evidence.raw_routing_artifact.kind == "provider.openrouter.routing"

        report = conformance_report(envelope)
        assert report.eligible is True
        assert report.reason_codes == ()

        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["schema_version"] == "provider_visible_response.v1"
        assert visible["items"][0]["type"] == "output_text"
        assert visible["items"][0]["choice_index"] == 0
        assert_no_secret_anywhere(envelope)

    async def test_unknown_additive_fields_still_succeed(self):
        body = success_body(
            system_fingerprint="fp_fx",
            some_future_field={"new": True},
            metadata=clean_metadata(future_router_field="ignored"),
        )
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["body"]["system_fingerprint"] == "fp_fx"

    async def test_length_is_incomplete_and_partial_preserved(self):
        adapter, _ = make_adapter(lambda request: fixture_response("length.json"))
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.INCOMPLETE
        assert result.finish_reason == FinishReason.MAX_OUTPUT_TOKENS
        assert result.provider_finish_reason == "chat:length|native:max_tokens"
        assert result.parsed_output is None
        assert result.failure is None
        assert result.refusal is None
        assert result.usage.reasoning_tokens == 2048
        assert result.visible_response_artifact is not None

    async def test_content_filter_is_refusal(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("content-filter.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.REFUSED
        assert result.finish_reason == FinishReason.SAFETY_REFUSAL
        assert result.parsed_output is None
        assert result.refusal is not None
        assert result.refusal.safe_message == "The model declined this request."
        assert result.refusal.provider_category == "content_filter"
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"][0]["text"] == "I cannot continue with this request."

    async def test_tool_calls_are_not_executed(self):
        adapter, calls = make_adapter(lambda request: fixture_response("tool-calls.json"))
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.unexpected_tool_calls",
            retryable=False,
            finish_reason=FinishReason.TOOL_USE,
        )

    async def test_empty_content_is_retryable_provider_error(self):
        adapter, _ = make_adapter(lambda request: fixture_response("empty-content.json"))
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.empty_content",
            retryable=True,
        )

    async def test_invalid_json_is_not_repaired(self):
        adapter, _ = make_adapter(lambda request: fixture_response("invalid-json.json"))
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.output_parse_failed",
            retryable=False,
        )
        assert envelope.result.parsed_output is None
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"][0]["text"].startswith("```json")

    async def test_non_object_root_is_schema_invalid(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("non-object-root.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_SCHEMA_INVALID,
            reason_code="openrouter.output_schema_invalid",
            retryable=False,
        )

    async def test_resolved_model_mismatch_is_wire_success_but_ineligible(self):
        """R4 §8:top-level model 不在 binding allowlist 不再是 ModelFailure。"""

        adapter, _ = make_adapter(
            lambda request: fixture_response("resolved-model-mismatch.json")
        )
        envelope = await adapter.generate_structured(make_call())
        # fixture 的 metadata selected model 也是未綁定的 mini,endpoint 無法 attest。
        assert_wire_success_with_reasons(
            envelope,
            (
                ConformanceReasonCode.GATEWAY_MODEL_MISMATCH,
                ConformanceReasonCode.ROUTE_METADATA_MISSING,
                ConformanceReasonCode.UPSTREAM_MODEL_MISMATCH,
            ),
        )
        assert envelope.result.resolved_model == "testlab/analyst-mini"
        assert envelope.execution_evidence.gateway_resolved_model == (
            "testlab/analyst-mini"
        )

    async def test_prefix_model_is_wire_success_but_ineligible(self):
        body = success_body(model="testlab/analyst-large-2026")
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.GATEWAY_MODEL_MISMATCH,)
        )
        assert envelope.execution_evidence.gateway_resolved_model == (
            "testlab/analyst-large-2026"
        )

    async def test_multiple_choices_is_cardinality_failure(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("multiple-choices.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.choice_cardinality_invalid",
            retryable=False,
        )
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert len(visible["items"]) == 2

    async def test_native_finish_reason_is_preserved_losslessly(self):
        body = success_body()
        body["choices"][0]["native_finish_reason"] = "stop_sequence_x"
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.provider_finish_reason == "chat:stop|native:stop_sequence_x"


class TestReasoningRedaction:
    async def test_reasoning_text_is_redacted_and_never_visible(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("success-with-reasoning.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.SUCCEEDED
        assert result.usage.reasoning_tokens == 256

        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["redaction_status"] == "redacted"
        assert "reasoning" in raw["redactions"]
        message = raw["body"]["choices"][0]["message"]
        assert message["reasoning"]["redacted"] is True
        assert message["reasoning"]["present"] is True
        assert "sha256:" in message["reasoning"]["sha256"]

        blob = canonical_json(envelope.result) + "".join(
            record.inline_content for record in envelope.supporting_artifacts
        )
        assert "SECRET CHAIN OF THOUGHT" not in blob
        assert "step one secret" not in blob

        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        for item in visible["items"]:
            assert "SECRET" not in item["text"]


class TestUsageMapping:
    async def test_usage_missing_is_all_null_with_limitation(self):
        adapter, _ = make_adapter(lambda request: fixture_response("usage-missing.json"))
        envelope = await adapter.generate_structured(make_call())
        usage = envelope.result.usage
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert usage.input_tokens is None
        assert usage.output_tokens is None
        assert usage.reasoning_tokens is None
        assert usage.limitations == ("openrouter response did not include usage",)

    async def test_usage_zeros_are_preserved(self):
        adapter, _ = make_adapter(lambda request: fixture_response("usage-zeros.json"))
        envelope = await adapter.generate_structured(make_call())
        usage = envelope.result.usage
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0
        assert usage.reasoning_tokens == 0
        assert usage.limitations == ()
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["cost"] == "0"

    async def test_nested_usage_details_missing_adds_sorted_limitations(self):
        body = success_body()
        body["usage"] = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        usage = envelope.result.usage
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens is None
        assert usage.reasoning_tokens is None
        assert list(usage.limitations) == sorted(usage.limitations)
        assert len(set(usage.limitations)) == len(usage.limitations)

    async def test_usage_total_mismatch_is_flagged_without_changing_values(self):
        body = success_body()
        body["usage"] = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 999,
        }
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.usage.input_tokens == 100
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["usage_total_mismatch"] is True

    async def test_decimal_cost_is_not_recomputed_as_float(self):
        body = success_body()
        body["usage"]["cost"] = "0.0001234567890123"
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["cost"] == "0.0001234567890123"

    async def test_scientific_notation_cost_becomes_canonical_decimal(self):
        """R4-C2:合法但科學記號的 cost 必須 canonical 化,不得讓 typed evidence
        的 canonical-decimal 驗證拋例外。"""

        body = success_body()
        body["usage"]["cost"] = 1e-7
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome is ModelOutcome.SUCCEEDED
        assert envelope.execution_evidence.cost_decimal == "0.0000001"
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["cost"] == "0.0000001"
        assert conformance_report(envelope).eligible is True

    @pytest.mark.parametrize(
        "cost", ["not-a-decimal", -0.5, "-1", "NaN", "Infinity", True]
    )
    async def test_unusable_cost_is_null_with_limitation_not_exception(self, cost):
        body = success_body()
        body["usage"]["cost"] = cost
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome is ModelOutcome.SUCCEEDED
        evidence = envelope.execution_evidence
        assert evidence.cost_decimal is None
        assert any("cost" in item for item in evidence.limitations)
        # cost 不是 attribution 判準;facts 誠實記 null 後仍 eligible。
        assert conformance_report(envelope).eligible is True

    @pytest.mark.parametrize(
        "field", ["prompt_tokens", "completion_tokens"]
    )
    async def test_negative_token_counts_are_null_with_limitation(self, field):
        """R4-C2:負數 token 不是可用 fact(TokenUsage ge=0),必須 null 化,
        不得讓 ValidationError 外洩。"""

        body = success_body()
        body["usage"][field] = -1
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome is ModelOutcome.SUCCEEDED
        usage = envelope.result.usage
        mapped = {
            "prompt_tokens": usage.input_tokens,
            "completion_tokens": usage.output_tokens,
        }[field]
        assert mapped is None
        assert any(field in item for item in usage.limitations)
        assert conformance_report(envelope).eligible is True


METADATA_MISSING_REASONS = (
    ConformanceReasonCode.CACHE_INELIGIBLE,
    ConformanceReasonCode.ROUTE_METADATA_MISSING,
    ConformanceReasonCode.TRANSFORMATION_INELIGIBLE,
)
PIPELINE_REASONS = (
    ConformanceReasonCode.PIPELINE_NOT_EMPTY,
    ConformanceReasonCode.TRANSFORMATION_INELIGIBLE,
)


class TestRoutingContamination:
    """R4 §8/§12.2:每個污染向量都是 wire success + 誠實 evidence + exact reasons。"""

    async def _run(self, metadata, *, headers: dict | None = None):
        body = success_body(metadata=metadata)
        adapter, _ = make_adapter(lambda request: respond(body, headers=headers))
        return await adapter.generate_structured(make_call())

    async def test_metadata_missing_is_ineligible_route_unknown(self):
        body = success_body()
        del body["openrouter_metadata"]
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert_wire_success_with_reasons(envelope, METADATA_MISSING_REASONS)
        evidence = envelope.execution_evidence
        assert evidence.upstream_provider is None
        assert evidence.upstream_endpoint is None
        assert evidence.route_strategy is None
        assert evidence.transformation_status == TransformationStatus.UNKNOWN
        assert evidence.cache_status == CacheStatus.UNKNOWN
        assert evidence.limitations  # explicit, sorted, non-empty

    async def test_requested_model_mismatch_blocks_endpoint_attestation(self):
        envelope = await self._run(clean_metadata(requested="testlab/other"))
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        evidence = envelope.execution_evidence
        # actual metadata 保存;endpoint 不可 attest(§6.4)。
        assert evidence.upstream_provider == "TestHost"
        assert evidence.upstream_endpoint is None
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["metadata_requested_model"] == "testlab/other"

    @pytest.mark.parametrize("strategy", ["auto", "latest", "fallback", "pareto", "fusion"])
    async def test_non_direct_strategy_is_ineligible(self, strategy):
        envelope = await self._run(clean_metadata(strategy=strategy))
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_STRATEGY_MISMATCH,)
        )
        assert envelope.execution_evidence.route_strategy == strategy

    async def test_router_attempt_gt_one_is_ineligible(self):
        # attempts 與 attempt=2 一致(真實 fallback retry 的誠實 metadata)。
        envelope = await self._run(
            clean_metadata(
                attempt=2,
                attempts=[
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 503},
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 200},
                ],
            )
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.UPSTREAM_ATTEMPT_MISMATCH,)
        )
        assert envelope.execution_evidence.upstream_attempt_count == 2

    async def test_two_attempts_with_lying_attempt_field_is_ineligible(self):
        """R4-C blocker 2:attempt=1 但 attempts 有兩筆(同 provider)——
        單次 direct execution 無法證立,不得 eligible。"""

        envelope = await self._run(
            clean_metadata(
                attempt=1,
                attempts=[
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 503},
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 200},
                ],
            )
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        assert envelope.execution_evidence.upstream_attempt_count is None

    async def test_explicit_null_pipeline_is_ineligible(self):
        """R4-C blocker 1:`"pipeline": null` 不是官方省略語意,必須 unknown。"""

        envelope = await self._run(clean_metadata(pipeline=None))
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.TRANSFORMATION_INELIGIBLE,)
        )
        evidence = envelope.execution_evidence
        assert evidence.transformation_status == TransformationStatus.UNKNOWN
        assert evidence.pipeline_stages == ()

    async def test_blank_strategy_is_typed_envelope_not_exception(self):
        """R4-C blocker 3:blank metadata 值必須回受控 envelope,不得讓
        evidence ValidationError 外洩。"""

        envelope = await self._run(clean_metadata(strategy=" "))
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        assert envelope.execution_evidence.route_strategy is None

    async def test_blank_selected_provider_is_typed_envelope_not_exception(self):
        envelope = await self._run(
            clean_metadata(
                endpoints=[{"provider": " ", "model": "\t", "selected": True}]
            )
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        evidence = envelope.execution_evidence
        assert evidence.upstream_provider is None
        assert evidence.upstream_model is None

    async def test_blank_body_model_is_typed_protocol_failure(self):
        body = success_body(model="   ")
        adapter, calls = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.UNKNOWN_PROVIDER_FAILURE,
            reason_code="openrouter.protocol_invalid",
            retryable=False,
        )
        assert envelope.execution_evidence.gateway_resolved_model is None

    async def test_selected_provider_mismatch_keeps_actual_provider(self):
        envelope = await self._run(
            clean_metadata(
                endpoints=[
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": True}
                ]
            )
        )
        assert_wire_success_with_reasons(
            envelope,
            (
                ConformanceReasonCode.ROUTE_METADATA_MISSING,
                ConformanceReasonCode.UPSTREAM_PROVIDER_MISMATCH,
            ),
        )
        evidence = envelope.execution_evidence
        assert evidence.upstream_provider == "OtherHost"
        assert evidence.upstream_endpoint is None

    async def test_multiple_selected_endpoints_null_route_facts(self):
        envelope = await self._run(
            clean_metadata(
                endpoints=[
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "selected": True},
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": True},
                ]
            )
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        evidence = envelope.execution_evidence
        assert evidence.upstream_provider is None
        assert evidence.upstream_model is None
        assert evidence.upstream_endpoint is None
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["selected_count"] == 2

    async def test_attempts_conflict_blocks_endpoint_attestation(self):
        envelope = await self._run(
            clean_metadata(
                attempts=[
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "status": 503},
                    {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 200},
                ]
            )
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.ROUTE_METADATA_MISSING,)
        )
        assert envelope.execution_evidence.upstream_endpoint is None

    @pytest.mark.parametrize(
        ("stage", "expected_status"),
        [
            ({"type": "guardrail", "name": "moderation"}, "inspected"),
            ({"type": "guardrail", "name": "moderation", "flagged": False}, "inspected"),
            ({"type": "context_compression", "name": "middle-out"}, "mutated"),
            ({"type": "response_healing", "name": "json-heal"}, "mutated"),
            ({"type": "server_tools", "name": "web"}, "mutated"),
            ({"type": "plugin", "name": "file-parser"}, "mutated"),
            ({"type": "unknown_future_stage", "name": "x"}, "unknown"),
        ],
    )
    async def test_any_pipeline_stage_is_ineligible(self, stage, expected_status):
        envelope = await self._run(clean_metadata(pipeline=[stage]))
        assert_wire_success_with_reasons(envelope, PIPELINE_REASONS)
        evidence = envelope.execution_evidence
        assert len(evidence.pipeline_stages) == 1
        assert evidence.pipeline_stages[0].transformation_status.value == expected_status
        assert evidence.transformation_status.value == expected_status
        report = conformance_report(envelope)
        assert report.transformation_status.value == expected_status
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        summary = routing["pipeline_stage_summaries"][0]
        assert summary["index"] == 1
        assert summary["transformation"] == expected_status
        assert summary["details_hash"].startswith("sha256:")

    async def test_general_unknown_metadata_field_is_ignored(self):
        envelope = await self._run(
            clean_metadata(unexpected_router_field={"anything": True})
        )
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert conformance_report(envelope).eligible is True

    async def test_snapshot_canonical_model_in_selected_route_is_accepted(self):
        envelope = await self._run(
            clean_metadata(
                endpoints=[
                    {
                        "provider": "TestHost",
                        "model": CANONICAL_MODEL,
                        "selected": True,
                    }
                ],
                attempts=[
                    {"provider": "TestHost", "model": CANONICAL_MODEL, "status": 200}
                ],
            )
        )
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert conformance_report(envelope).eligible is True
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["selected_model"] == CANONICAL_MODEL
        assert envelope.execution_evidence.upstream_endpoint == ENDPOINT_SLUG

    async def test_unbound_selected_model_is_ineligible(self):
        envelope = await self._run(
            clean_metadata(
                endpoints=[
                    {
                        "provider": "TestHost",
                        "model": "testlab/unbound-model",
                        "selected": True,
                    }
                ]
            )
        )
        assert_wire_success_with_reasons(
            envelope,
            (
                ConformanceReasonCode.ROUTE_METADATA_MISSING,
                ConformanceReasonCode.UPSTREAM_MODEL_MISMATCH,
            ),
        )
        assert envelope.execution_evidence.upstream_model == "testlab/unbound-model"

    async def test_cache_hit_header_is_ineligible_cache(self):
        # 官方語意:cache hit 通常同時移除 metadata → cache + route 雙重 ineligible。
        body = success_body()
        del body["openrouter_metadata"]
        adapter, _ = make_adapter(
            lambda request: respond(
                body,
                headers={
                    "x-request-id": "req_fx_cache",
                    "x-openrouter-cache-status": "HIT",
                },
            )
        )
        envelope = await adapter.generate_structured(make_call())
        # metadata 同時缺失 → cache + route + transformation 全 fail closed。
        assert_wire_success_with_reasons(envelope, METADATA_MISSING_REASONS)
        assert envelope.execution_evidence.cache_status == CacheStatus.HIT
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["cache_status"] == "hit"
        assert routing["cache_header_value"] == "HIT"

    async def test_cache_hit_with_metadata_is_cache_only_reason(self):
        envelope = await self._run(
            clean_metadata(),
            headers={
                "x-request-id": "req_fx_cache2",
                "x-openrouter-cache-status": "HIT",
            },
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.CACHE_INELIGIBLE,)
        )
        assert envelope.execution_evidence.cache_status == CacheStatus.HIT

    async def test_unrecognized_cache_header_is_unknown_and_ineligible(self):
        envelope = await self._run(
            clean_metadata(),
            headers={
                "x-request-id": "req_fx_cache3",
                "x-openrouter-cache-status": "STALE",
            },
        )
        assert_wire_success_with_reasons(
            envelope, (ConformanceReasonCode.CACHE_INELIGIBLE,)
        )
        assert envelope.execution_evidence.cache_status == CacheStatus.UNKNOWN

    async def test_cache_miss_header_stays_eligible(self):
        envelope = await self._run(
            clean_metadata(),
            headers={
                "x-request-id": "req_fx_cache4",
                "x-openrouter-cache-status": "MISS",
            },
        )
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert envelope.execution_evidence.cache_status == CacheStatus.MISS
        assert conformance_report(envelope).eligible is True

    async def test_zero_usage_without_cache_header_is_not_cache_hit(self):
        # 禁止 heuristic:token 0/cost 0 不是 cache hit 證據(§6.6)。
        body = success_body()
        body["usage"] = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
            "cost": 0,
        }
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert envelope.execution_evidence.cache_status == CacheStatus.ABSENT
        assert conformance_report(envelope).eligible is True

    async def test_contaminated_route_still_captures_routing_artifact(self):
        envelope = await self._run(clean_metadata(strategy="auto"))
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["strategy"] == "auto"
        assert routing["schema_version"] == "openrouter_routing.v2"
        assert "conformance" not in routing


class TestWireFailureKeepsRouteFacts:
    """§7.5/§8:wire failure 的 route facts 不再被丟掉;authority 仍是 wire failure。"""

    async def test_invalid_json_with_contaminated_route_is_wire_failure(self):
        body = fixture_json("invalid-json.json")
        body["openrouter_metadata"] = clean_metadata(strategy="auto")
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openrouter.output_parse_failed",
            retryable=False,
        )
        # evidence 仍保存 actual route facts。
        assert envelope.execution_evidence.route_strategy == "auto"
        # conformance 只回 wire_not_succeeded,不改 retryability。
        report = conformance_report(envelope)
        assert report.eligible is False
        assert report.reason_codes == (ConformanceReasonCode.WIRE_NOT_SUCCEEDED,)

    async def test_error_response_metadata_still_enters_evidence(self):
        body = {
            **error_body("rate_limit_exceeded", code=429),
            "openrouter_metadata": clean_metadata(strategy="fallback"),
        }
        adapter, calls = make_adapter(lambda request: httpx.Response(429, json=body))
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.RATE_LIMITED,
            reason_code="openrouter.rate_limited",
            retryable=True,
        )
        evidence = envelope.execution_evidence
        assert evidence.route_strategy == "fallback"
        assert evidence.upstream_provider == "TestHost"
        assert evidence.raw_routing_artifact is not None
        routing = artifact_by_label(envelope, ROUTING_ARTIFACT_LABEL)
        assert routing["strategy"] == "fallback"

    async def test_refusal_with_contaminated_route_keeps_facts(self):
        body = fixture_json("content-filter.json")
        body["openrouter_metadata"] = clean_metadata(
            attempt=2,
            attempts=[
                {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 503},
                {"provider": "TestHost", "model": REQUESTED_MODEL, "status": 200},
            ],
        )
        adapter, _ = make_adapter(lambda request: respond(body))
        envelope = await adapter.generate_structured(make_call())
        assert envelope.result.outcome == ModelOutcome.REFUSED
        assert envelope.execution_evidence.upstream_attempt_count == 2
        report = conformance_report(envelope)
        assert report.reason_codes == (ConformanceReasonCode.WIRE_NOT_SUCCEEDED,)
