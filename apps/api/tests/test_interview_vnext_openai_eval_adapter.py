"""V3-4 OpenAI Responses eval adapter — mocked-HTTP conformance tests.

規格:docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md
不打 live API;所有 provider 行為經 httpx mock + 官方 SDK deserialization。
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
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.binding import ProviderBinding, define_provider_binding
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

from evals.interview_vnext.provider_config import (
    OPENAI_ADAPTER_ID,
    OPENAI_ADAPTER_VERSION,
    OpenAIResponsesEvalConfig,
    build_openai_reference_binding,
)
from evals.interview_vnext.providers.openai_responses import (
    ERROR_ARTIFACT_KIND,
    ERROR_ARTIFACT_LABEL,
    RAW_ARTIFACT_LABEL,
    VISIBLE_ARTIFACT_LABEL,
    OpenAIResponsesEvalAdapter,
)
from evals.interview_vnext.schema_catalog import (
    TURN_INTERPRET_OUTPUT_SCHEMA_ID,
    CatalogEntry,
    PublishedOutputSchemaCatalog,
    SchemaCatalogError,
)

from tests.interview_vnext_llm_fixtures import (
    binding_artifact_ref,
    config_artifact_ref,
    projection_artifact_ref,
    resolved_call,
    turn_output_projection,
)


RUN_ID = uuid5(uuid4(), "run")  # fresh per test session, stable within it
CREATED_AT = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)


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


STANDARD_CONFIG = OpenAIResponsesEvalConfig()
STANDARD_BINDING = build_openai_reference_binding(STANDARD_CONFIG)


def make_binding(**overrides: Any) -> ProviderBinding:
    """An OpenAI binding variant for pre-HTTP mismatch tests (V3-5A §6.1)."""

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
        "output_schema_id": TURN_INTERPRET_OUTPUT_SCHEMA_ID,
        "output_schema_artifact": _json_ref(
            schema, kind="model.output_schema", schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID
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
    binding = binding or STANDARD_BINDING
    config = config if config is not None else STANDARD_CONFIG
    request = request or make_request(binding=binding, config=config, **overrides)
    return resolved_call(
        request, binding, projection=projection or turn_output_projection().report
    )


class TestOpenAIResponsesEvalConfig:
    def test_default_dump_and_hash_cover_hard_invariants(self):
        config = OpenAIResponsesEvalConfig()
        assert config.config_hash == OpenAIResponsesEvalConfig().config_hash
        dump = config.model_dump(mode="json")
        assert dump["schema_version"] == "openai_responses_eval_config.v1"
        assert dump["provider"] == "openai"
        assert dump["requested_model"] == "gpt-5.6"
        assert dump["accepted_resolved_models"] == ["gpt-5.6", "gpt-5.6-sol"]
        assert dump["reasoning_mode"] == "standard"
        assert dump["reasoning_effort"] == "medium"
        assert dump["service_tier"] == "default"
        assert dump["store"] is False
        assert dump["background"] is False
        assert dump["stream"] is False
        assert dump["truncation"] == "disabled"
        assert dump["sdk_max_retries"] == 0
        assert dump["contains_test_data"] is True

    def test_config_hash_tracks_versionable_eval_knobs(self):
        default = OpenAIResponsesEvalConfig()
        assert default.config_hash != OpenAIResponsesEvalConfig(
            reasoning_effort="high"
        ).config_hash
        assert default.config_hash != OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6-sol"
        ).config_hash

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("provider", "anthropic"),
            ("reasoning_mode", "pro"),
            ("service_tier", "auto"),
            ("store", True),
            ("background", True),
            ("stream", True),
            ("truncation", "auto"),
            ("sdk_max_retries", 2),
            ("contains_test_data", False),
        ],
    )
    def test_hard_invariants_cannot_be_overridden(self, field, value):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(**{field: value})

    def test_config_is_frozen(self):
        config = OpenAIResponsesEvalConfig()
        with pytest.raises(ValidationError):
            config.requested_model = "gpt-5.6-sol"

    def test_secret_fields_are_rejected_and_absent(self):
        for secret_field in ("api_key", "organization", "project"):
            assert secret_field not in OpenAIResponsesEvalConfig.model_fields
            with pytest.raises(ValidationError):
                OpenAIResponsesEvalConfig(**{secret_field: "sk-eval-secret"})
        assert "sk-" not in canonical_json(OpenAIResponsesEvalConfig())

    @pytest.mark.parametrize(
        "models",
        [
            (),
            ("gpt-5.6", "gpt-5.6"),
            ("gpt-5.6-sol", "gpt-5.6"),
        ],
    )
    def test_accepted_resolved_models_must_be_nonempty_unique_sorted(self, models):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(accepted_resolved_models=models)

    def test_requested_model_need_not_be_in_allowlist(self):
        config = OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6",
            accepted_resolved_models=("gpt-5.6-sol",),
        )
        assert config.requested_model not in config.accepted_resolved_models

    @pytest.mark.parametrize("seconds", [0.0, -1.0, 120.0])
    def test_connect_timeout_bounds(self, seconds):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(connect_timeout_seconds=seconds)


class TestPublishedOutputSchemaCatalog:
    def test_resolve_returns_exact_published_schema_and_hash(self):
        request = make_request()
        binding = PublishedOutputSchemaCatalog().resolve(request)
        assert binding.schema_id == TURN_INTERPRET_OUTPUT_SCHEMA_ID
        assert binding.format_name == "turn_interpret_output_v1"
        assert binding.schema == published_schema("turn-interpret-output.v1.schema.json")
        assert binding.schema_hash == request.output_schema_hash
        assert canonical_hash(binding.schema) == request.output_schema_hash
        operation = turn_interpret_operation()
        assert binding.schema_hash == operation.output_contract.content_hash

    def test_resolve_returns_a_fresh_deep_copy(self):
        catalog = PublishedOutputSchemaCatalog()
        first = catalog.resolve(make_request())
        first.schema["properties"].clear()
        second = catalog.resolve(make_request())
        assert second.schema == published_schema("turn-interpret-output.v1.schema.json")

    def test_unknown_schema_id_fails_closed(self):
        request = make_request(
            output_schema_id="https://caliburn.local/schemas/unknown.v1.schema.json"
        )
        with pytest.raises(SchemaCatalogError, match="unknown output schema id"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_schema_hash_mismatch_fails_closed(self):
        tampered = published_schema("turn-interpret-output.v1.schema.json")
        tampered["properties"]["tampered"] = {"type": "string"}
        request = make_request(
            output_schema_artifact=_json_ref(
                tampered,
                kind="model.output_schema",
                schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
            )
        )
        with pytest.raises(SchemaCatalogError, match="hash does not match"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_catalog_entry_with_foreign_id_fails_on_schema_id(self):
        catalog = PublishedOutputSchemaCatalog(
            {
                TURN_INTERPRET_OUTPUT_SCHEMA_ID: CatalogEntry(
                    filename="turn-interpret-input.v1.schema.json",
                    format_name="turn_interpret_output_v1",
                )
            }
        )
        with pytest.raises(SchemaCatalogError, match=r"\$id does not match"):
            catalog.resolve(make_request())

    def test_non_portable_published_schema_fails_lint(self):
        input_schema_id = (
            "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json"
        )
        input_schema = published_schema("turn-interpret-input.v1.schema.json")
        catalog = PublishedOutputSchemaCatalog(
            {
                input_schema_id: CatalogEntry(
                    filename="turn-interpret-input.v1.schema.json",
                    format_name="turn_interpret_input_v1",
                )
            }
        )
        request = make_request(
            output_schema_id=input_schema_id,
            output_schema_artifact=_json_ref(
                input_schema, kind="model.output_schema", schema_id=input_schema_id
            ),
        )
        with pytest.raises(SchemaCatalogError, match="not portable"):
            catalog.resolve(request)

    def test_operation_name_mismatch_fails_closed(self):
        request = make_request(operation_name="turn.receive")
        with pytest.raises(SchemaCatalogError, match="operation name"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_operation_definition_hash_mismatch_fails_closed(self):
        request = make_request(
            operation_definition_hash=f"sha256:{'0' * 64}",
        )
        with pytest.raises(SchemaCatalogError, match="definition hash"):
            PublishedOutputSchemaCatalog().resolve(request)


# ---- mocked-HTTP adapter harness --------------------------------------------

API_KEY = "sk-eval-test-not-a-real-key"
FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openai_responses"


class FakeClock:
    def __init__(self, start: datetime = CREATED_AT) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def fixture_response(name: str) -> httpx.Response:
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    meta = manifest["fixtures"][name]
    body = json.loads((FIXTURES / name).read_text("utf-8"))
    return httpx.Response(
        meta.get("status", 200), json=body, headers=meta.get("headers", {})
    )


def make_adapter(
    handler,
    **kwargs: Any,
) -> tuple[OpenAIResponsesEvalAdapter, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        outcome = handler(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    clock = kwargs.pop("clock", None) or FakeClock()
    adapter = OpenAIResponsesEvalAdapter(
        api_key=API_KEY,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)),
        now=clock.now,
        **kwargs,
    )
    return adapter, calls


def assert_no_secret_anywhere(envelope: ModelCallEnvelope) -> None:
    blobs = [canonical_json(envelope.result)]
    blobs.extend(canonical_json(record) for record in envelope.supporting_artifacts)
    for blob in blobs:
        assert API_KEY not in blob
        assert "Authorization" not in blob


def assert_failure(
    envelope: ModelCallEnvelope,
    *,
    kind: FailureKind,
    reason_code: str,
    retryable: bool,
    finish_reason: FinishReason = FinishReason.PROVIDER_ERROR,
) -> None:
    result = envelope.result
    assert result.outcome == ModelOutcome.FAILED
    assert result.finish_reason == finish_reason
    failure = result.failure
    assert failure is not None
    assert failure.kind == kind
    assert failure.reason_code == reason_code
    assert failure.retryable is retryable
    error_ref = failure.error_artifact
    assert error_ref is not None
    assert error_ref.artifact_id == uuid5(result.attempt_id, ERROR_ARTIFACT_LABEL)
    stored = {record.ref.artifact_id: record for record in envelope.supporting_artifacts}
    assert stored[error_ref.artifact_id].ref.kind == ERROR_ARTIFACT_KIND
    assert_no_secret_anywhere(envelope)


class TestAdapterFailsBeforeHttp:
    async def test_expired_deadline_fails_before_http(self):
        clock = FakeClock(CREATED_AT + timedelta(seconds=120))
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json"), clock=clock
        )
        envelope = await adapter.generate_structured(make_call())
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.TRANSPORT_TIMEOUT,
            reason_code="openai.timeout",
            retryable=True,
        )
        assert envelope.result.resolved_model == "gpt-5.6"
        assert envelope.result.usage.input_tokens is None
        assert envelope.result.usage.limitations

    async def test_unknown_schema_id_fails_before_http(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        envelope = await adapter.generate_structured(
            make_call(
                output_schema_id="https://caliburn.local/schemas/unknown.v1.schema.json"
            )
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )

    async def test_schema_hash_mismatch_fails_before_http(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        # Portable-but-different output schema: the catalog compares the request's
        # output-schema hash to the published schema and fails closed. In v2 the
        # request/projection stay consistent, so the tampered schema is projected.
        tampered = published_schema("turn-interpret-output.v1.schema.json")
        tampered["properties"]["tampered"] = {"type": "string"}
        tampered["required"] = [*tampered["required"], "tampered"]
        projected = project_portable_strict_output_schema(
            tampered,
            source_schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
            target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
        )
        request = make_request(
            output_schema_artifact=_json_ref(
                projected.schema,
                kind="model.output_schema",
                schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
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
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )

    async def test_operation_definition_mismatch_fails_before_http(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        envelope = await adapter.generate_structured(
            make_call(operation_definition_hash=f"sha256:{'0' * 64}")
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )

    async def test_wrong_requested_model_fails_before_http(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        envelope = await adapter.generate_structured(
            make_call(
                binding=make_binding(
                    requested_model="gpt-5.5",
                    accepted_gateway_models=("gpt-5.5",),
                    accepted_upstream_models=("gpt-5.5",),
                )
            )
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )

    # ---- R3-C1 runtime adapter/binding preflight(修正計畫 §5.1/§7.1)-------

    @pytest.mark.parametrize(
        "overrides",
        [
            {"adapter_id": "openrouter.chat-completions"},
            {"adapter_version": "1.0.0"},
        ],
        ids=["adapter_id", "adapter_version"],
    )
    async def test_adapter_identity_mismatch_fails_before_http(self, overrides):
        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        envelope = await adapter.generate_structured(
            make_call(binding=make_binding(**overrides))
        )
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )
        evidence = envelope.execution_evidence
        # evidence 描述實際 runtime adapter,不從不相符的 binding 複製(§5.1.1)。
        assert evidence.adapter_id == OPENAI_ADAPTER_ID
        assert evidence.adapter_version == OPENAI_ADAPTER_VERSION
        assert any("binding preflight" in item for item in evidence.limitations)

    async def test_gateway_mismatch_records_runtime_adapter_facts(self):
        """§7.1 gateway 向量:result/evidence 都記 runtime gateway,identity 保留 attempted。"""

        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json")
        )
        attempted = make_binding(gateway_provider="openrouter")
        envelope = await adapter.generate_structured(make_call(binding=attempted))
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )
        result = envelope.result
        assert result.gateway_provider == "openai"  # actual runtime gateway
        assert result.binding_id == attempted.binding_id  # attempted identity
        assert result.binding_hash == attempted.binding_hash
        assert result.requested_model == attempted.requested_model
        evidence = envelope.execution_evidence
        assert evidence.gateway_provider == "openai"
        assert evidence.adapter_id == OPENAI_ADAPTER_ID
        assert evidence.adapter_version == OPENAI_ADAPTER_VERSION
        assert evidence.binding_id == attempted.binding_id
        assert evidence.binding_hash == attempted.binding_hash
        # §5.1:preflight 失敗不建立假 routing metadata。
        assert evidence.upstream_provider is None
        assert evidence.route_strategy is None

    @pytest.mark.parametrize(
        "drift_config",
        [
            # §7.1.5:只有 reasoning field 不同。
            OpenAIResponsesEvalConfig(reasoning_effort="high"),
            # §7.1.6:OpenAI config 無可變 storage/cache/plugin 欄位(全 Literal),
            # 以僅存的非 reasoning 可調欄位 connect timeout 作 drift 向量。
            OpenAIResponsesEvalConfig(connect_timeout_seconds=30.0),
        ],
        ids=["reasoning", "connect_timeout"],
    )
    async def test_runtime_config_drift_fails_before_http(self, drift_config):
        """§7.1.7:requested model 相同、只有 config hash 不同仍拒絕。"""

        adapter, calls = make_adapter(
            lambda request: fixture_response("server_500.json"), config=drift_config
        )
        call = make_call()  # standard binding + standard config
        assert drift_config.requested_model == call.binding.requested_model
        assert drift_config.config_hash != call.binding.provider_config_hash
        envelope = await adapter.generate_structured(call)
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.RUNTIME_BINDING_MISMATCH,
            reason_code="openai.request_binding_invalid",
            retryable=False,
        )
        # §7.1.8:error artifact 只能含 hash,不得洩漏 config 欄位或值。
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        blob = canonical_json(error)
        assert "reasoning_effort" not in blob
        assert "connect_timeout" not in blob
        assert (
            drift_config.config_hash in blob
            or call.binding.provider_config_hash in blob
        )


class TestAdapterHttpErrorMapping:
    async def test_400_invalid_schema_is_nonretryable_invalid_request(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("invalid_schema_400.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openai.invalid_request",
            retryable=False,
        )
        assert envelope.result.failure.provider_error_code == "invalid_json_schema"
        assert envelope.result.provider_request_id == "req_fx_400_schema"

    async def test_400_context_length_maps_to_context_window_exceeded(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("context_length_400.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openai.context_window_exceeded",
            retryable=False,
            finish_reason=FinishReason.CONTEXT_WINDOW_EXCEEDED,
        )

    async def test_401_and_403_are_nonretryable(self):
        for fixture, reason_code in (
            ("authentication_401.json", "openai.authentication_failed"),
            ("permission_403.json", "openai.permission_denied"),
        ):
            adapter, calls = make_adapter(
                lambda request, fixture=fixture: fixture_response(fixture)
            )
            envelope = await adapter.generate_structured(make_call())
            assert len(calls) == 1
            assert_failure(
                envelope,
                kind=FailureKind.AUTHENTICATION_FAILED,
                reason_code=reason_code,
                retryable=False,
            )

    async def test_429_rate_limit_is_retryable_but_quota_is_not(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("rate_limit_429.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.RATE_LIMITED,
            reason_code="openai.rate_limited",
            retryable=True,
        )

        adapter, calls = make_adapter(
            lambda request: fixture_response("quota_429.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.RATE_LIMITED,
            reason_code="openai.quota_exhausted",
            retryable=False,
        )

    async def test_500_503_connection_and_timeout_are_retryable(self):
        cases = (
            (
                lambda request: fixture_response("server_500.json"),
                FailureKind.PROVIDER_UNAVAILABLE,
                "openai.server_error",
            ),
            (
                lambda request: httpx.Response(
                    503,
                    json=json.loads((FIXTURES / "server_500.json").read_text("utf-8")),
                    headers={"x-request-id": "req_fx_503"},
                ),
                FailureKind.PROVIDER_UNAVAILABLE,
                "openai.server_error",
            ),
            (
                lambda request: httpx.ConnectError("connection refused"),
                FailureKind.TRANSPORT_ERROR,
                "openai.connection_error",
            ),
            (
                lambda request: httpx.ReadTimeout("provider stalled"),
                FailureKind.TRANSPORT_TIMEOUT,
                "openai.timeout",
            ),
        )
        for handler, kind, reason_code in cases:
            adapter, calls = make_adapter(handler)
            envelope = await adapter.generate_structured(make_call())
            assert len(calls) == 1, reason_code
            assert_failure(
                envelope, kind=kind, reason_code=reason_code, retryable=True
            )

    async def test_sdk_internal_retry_is_disabled(self):
        for handler in (
            lambda request: fixture_response("rate_limit_429.json"),
            lambda request: fixture_response("server_500.json"),
            lambda request: httpx.ReadTimeout("provider stalled"),
        ):
            adapter, calls = make_adapter(handler)
            await adapter.generate_structured(make_call())
            assert len(calls) == 1

    async def test_cancelled_error_propagates(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise asyncio.CancelledError()

        adapter, calls = make_adapter(handler)
        with pytest.raises(asyncio.CancelledError):
            await adapter.generate_structured(make_call())
        assert len(calls) == 1

    async def test_api_key_and_authorization_never_enter_artifacts(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("authentication_401.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert calls[0].headers["authorization"] == f"Bearer {API_KEY}"
        assert_no_secret_anywhere(envelope)


EXPECTED_SUCCESS_OUTPUT = {
    "schema_version": "turn_interpret_output.v1",
    "observations": [],
    "user_signal": "answer",
    "episode_signal": "continue",
    "emergent_topics": [],
    "insufficiencies": [],
}


def artifact_by_label(envelope: ModelCallEnvelope, label: str) -> dict[str, Any]:
    attempt_id = envelope.result.attempt_id
    stored = {record.ref.artifact_id: record for record in envelope.supporting_artifacts}
    record = stored[uuid5(attempt_id, label)]
    return json.loads(record.inline_content)


class TestAdapterRequestProjection:
    async def test_request_body_uses_exact_schema_and_stateless_hard_invariants(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("success_reasoning_then_message.json")
        )
        call = make_call()
        request = call.request
        envelope = await adapter.generate_structured(call)
        assert envelope.result.outcome == ModelOutcome.SUCCEEDED
        assert len(calls) == 1
        assert str(calls[0].url) == "https://api.openai.com/v1/responses"
        assert "idempotency-key" not in {name.lower() for name in calls[0].headers}
        body = json.loads(calls[0].content)

        text_format = body["text"]["format"]
        assert text_format["type"] == "json_schema"
        assert text_format["name"] == "turn_interpret_output_v1"
        assert text_format["strict"] is True
        assert canonical_hash(text_format["schema"]) == request.output_schema_hash
        assert text_format["schema"] == published_schema(
            "turn-interpret-output.v1.schema.json"
        )

        assert body["model"] == "gpt-5.6"
        assert body["instructions"] == request.instructions
        assert body["input"] == [
            {"role": "user", "content": "synthetic employee turn (test)"}
        ]
        assert body["max_output_tokens"] == request.max_output_tokens
        assert body["reasoning"] == {"mode": "standard", "effort": "medium"}
        assert body["service_tier"] == "default"
        assert body["store"] is False
        assert body["background"] is False
        assert body["stream"] is False
        assert body["truncation"] == "disabled"

        for forbidden in (
            "conversation",
            "previous_response_id",
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "context_management",
            "include",
            "prompt",
            "prompt_cache_key",
            "prompt_cache_options",
            "prompt_cache_retention",
            "temperature",
            "top_p",
            "verbosity",
            "metadata",
            "moderation",
            "safety_identifier",
            "user",
        ):
            assert forbidden not in body, forbidden


class TestAdapterResponseMatrix:
    async def test_success_ignores_reasoning_item_and_parses_unique_message(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("success_reasoning_then_message.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.SUCCEEDED
        assert result.finish_reason == FinishReason.COMPLETED
        assert result.provider_finish_reason == "completed"
        assert result.resolved_model == "gpt-5.6-sol"
        assert result.provider_request_id == "req_fx_success"
        assert result.provider_conversation_id is None
        assert result.parsed_output is not None
        assert result.parsed_output.load() == EXPECTED_SUCCESS_OUTPUT
        assert result.parsed_output.schema_id == TURN_INTERPRET_OUTPUT_SCHEMA_ID

        usage = result.usage
        assert usage.input_tokens == 1200
        assert usage.output_tokens == 350
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 256
        assert usage.reasoning_tokens == 128
        assert usage.limitations == ()

        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["http_request_id"] == "req_fx_success"
        assert raw["sdk"] == "openai-python"
        assert raw["sdk_version"] == "2.46.0"
        assert raw["response"]["id"] == "resp_fx_success"
        assert raw["response"]["output"][0]["type"] == "reasoning"

        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["schema_version"] == "provider_visible_response.v1"
        assert len(visible["items"]) == 1
        item = visible["items"][0]
        assert item["output_index"] == 1
        assert item["message_id"] == "msg_fx_1"
        assert item["type"] == "output_text"
        assert_no_secret_anywhere(envelope)

    async def test_adapter_never_uses_output_text_concatenation(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("completed_multiple_output_text.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openai.multiple_structured_outputs",
            retryable=False,
        )
        assert envelope.result.parsed_output is None
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert len(visible["items"]) == 2

    async def test_refusal_is_not_parsed_as_json_or_retried(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("refusal.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert len(calls) == 1
        assert result.outcome == ModelOutcome.REFUSED
        assert result.finish_reason == FinishReason.SAFETY_REFUSAL
        assert result.parsed_output is None
        assert result.failure is None
        refusal = result.refusal
        assert refusal is not None
        assert refusal.reason_code == "openai.refusal"
        assert refusal.safe_message == "The model declined this request."
        assert refusal.provider_category == "refusal"
        assert "I can't help" not in refusal.safe_message
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"][0]["type"] == "refusal"
        assert visible["items"][0]["text"] == "I can't help with that request."

    async def test_incomplete_max_tokens_without_visible_text_is_preserved(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("incomplete_max_output_no_visible.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.INCOMPLETE
        assert result.finish_reason == FinishReason.MAX_OUTPUT_TOKENS
        assert result.provider_finish_reason == "incomplete:max_output_tokens"
        assert result.parsed_output is None
        assert result.failure is None
        assert result.refusal is None
        assert result.usage.reasoning_tokens == 2048
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"] == []
        assert result.visible_response_artifact is not None

    async def test_incomplete_content_filter_with_partial_text_is_not_success(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("incomplete_content_filter_partial.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.INCOMPLETE
        assert result.finish_reason == FinishReason.UNKNOWN
        assert result.provider_finish_reason == "incomplete:content_filter"
        assert result.parsed_output is None
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert len(visible["items"]) == 1
        assert visible["items"][0]["message_status"] == "incomplete"

    async def test_failed_response_error_is_normalized_and_raw_is_kept(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("failed_server_error.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.PROVIDER_UNAVAILABLE,
            reason_code="openai.response_server_error",
            retryable=True,
        )
        result = envelope.result
        assert result.provider_finish_reason == "failed:server_error"
        assert result.failure.provider_error_code == "server_error"
        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["response"]["status"] == "failed"
        assert raw["response"]["error"]["code"] == "server_error"
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        assert error["classification"]["reason_code"] == "openai.response_server_error"

    async def test_cancelled_response_is_nonretryable_cancelled(self):
        adapter, _ = make_adapter(lambda request: fixture_response("cancelled.json"))
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.CANCELLED,
            reason_code="openai.cancelled",
            retryable=False,
            finish_reason=FinishReason.CANCELLED,
        )
        assert envelope.result.provider_finish_reason == "cancelled"

    async def test_nonterminal_status_is_unknown_provider_failure(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("nonterminal_in_progress.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.UNKNOWN_PROVIDER_FAILURE,
            reason_code="openai.unexpected_nonterminal_status",
            retryable=False,
            finish_reason=FinishReason.UNKNOWN,
        )
        assert envelope.result.provider_finish_reason == "unexpected:in_progress"

    async def test_completed_without_output_is_parse_failure(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("completed_no_message.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openai.missing_structured_output",
            retryable=False,
        )

    async def test_invalid_json_has_visible_and_error_artifacts(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("completed_invalid_json.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openai.output_parse_failed",
            retryable=False,
        )
        assert envelope.result.visible_response_artifact is not None
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert visible["items"][0]["text"].startswith("```json")
        assert envelope.result.parsed_output is None

    async def test_json_array_root_is_output_schema_invalid(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("completed_json_array_root.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_SCHEMA_INVALID,
            reason_code="openai.output_schema_invalid",
            retryable=False,
        )

    async def test_unexpected_tool_call_is_not_executed(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("unexpected_tool_call.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert len(calls) == 1
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openai.unexpected_output_item",
            retryable=False,
        )
        error = artifact_by_label(envelope, ERROR_ARTIFACT_LABEL)
        assert "function_call" in error["detail"]

    async def test_commentary_message_is_not_concatenated_with_final_answer(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("completed_commentary_then_final.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.OUTPUT_PARSE_FAILED,
            reason_code="openai.unexpected_output_item",
            retryable=False,
        )
        assert envelope.result.parsed_output is None
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert len(visible["items"]) == 2

    async def test_resolved_model_mismatch_fails_closed(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("resolved_model_mismatch.json")
        )
        envelope = await adapter.generate_structured(make_call())
        assert_failure(
            envelope,
            kind=FailureKind.RESOLVED_MODEL_MISMATCH,
            reason_code="openai.resolved_model_mismatch",
            retryable=False,
        )
        result = envelope.result
        assert result.resolved_model == "gpt-5.7-mini"
        assert result.provider_finish_reason == "completed"
        assert result.parsed_output is None
        raw = artifact_by_label(envelope, RAW_ARTIFACT_LABEL)
        assert raw["response"]["model"] == "gpt-5.7-mini"
        visible = artifact_by_label(envelope, VISIBLE_ARTIFACT_LABEL)
        assert len(visible["items"]) == 1

    async def test_no_prefix_or_family_auto_acceptance_for_models(self):
        # R3-C1:exact runtime preflight 下,變體 config 必須帶自己的 binding。
        variant = OpenAIResponsesEvalConfig(
            accepted_resolved_models=("gpt-5.6", "gpt-5.6-sol", "gpt-5.7"),
        )
        adapter, _ = make_adapter(
            lambda request: fixture_response("resolved_model_mismatch.json"),
            config=variant,
        )
        envelope = await adapter.generate_structured(
            make_call(binding=build_openai_reference_binding(variant), config=variant)
        )
        assert_failure(
            envelope,
            kind=FailureKind.RESOLVED_MODEL_MISMATCH,
            reason_code="openai.resolved_model_mismatch",
            retryable=False,
        )

    async def test_usage_none_uses_nulls_and_sorted_limitations(self):
        adapter, _ = make_adapter(
            lambda request: fixture_response("usage_unavailable.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.SUCCEEDED
        usage = result.usage
        assert usage.input_tokens is None
        assert usage.output_tokens is None
        assert usage.cache_read_tokens is None
        assert usage.cache_write_tokens is None
        assert usage.reasoning_tokens is None
        assert usage.limitations == ("openai response did not include usage",)

    async def test_local_constraint_violation_is_success_at_adapter_boundary(self):
        from app.interview_vnext.llm.turn_interpret import TurnInterpretOutput

        adapter, _ = make_adapter(
            lambda request: fixture_response("success_local_constraint_violation.json")
        )
        envelope = await adapter.generate_structured(make_call())
        result = envelope.result
        assert result.outcome == ModelOutcome.SUCCEEDED
        assert result.parsed_output is not None
        with pytest.raises(ValidationError):
            TurnInterpretOutput.model_validate(result.parsed_output.load())

    async def test_envelope_artifact_ids_are_deterministic_and_scoped(self):
        attempt_id = uuid4()
        call = make_call(attempt_id=attempt_id)
        request = call.request
        adapter_one, _ = make_adapter(
            lambda request: fixture_response("success_reasoning_then_message.json")
        )
        adapter_two, _ = make_adapter(
            lambda request: fixture_response("success_reasoning_then_message.json")
        )
        first = await adapter_one.generate_structured(call)
        second = await adapter_two.generate_structured(call)
        first_ids = sorted(
            str(record.ref.artifact_id) for record in first.supporting_artifacts
        )
        second_ids = sorted(
            str(record.ref.artifact_id) for record in second.supporting_artifacts
        )
        assert first_ids == second_ids
        assert first_ids == sorted(
            str(uuid5(attempt_id, label))
            for label in (RAW_ARTIFACT_LABEL, VISIBLE_ARTIFACT_LABEL)
        )
        for record in first.supporting_artifacts:
            assert record.ref.artifact_id == uuid5(
                attempt_id,
                RAW_ARTIFACT_LABEL
                if record.ref.kind == "provider.openai.response.raw"
                else VISIBLE_ARTIFACT_LABEL,
            )
            assert record.run_id == request.run_id
            assert record.session_id == request.session_id
            assert record.turn_id == request.turn_id
            assert record.operation_id == request.operation_id
            assert record.attempt_id == request.attempt_id
            assert record.retention_class == "eval"
            assert record.contains_test_data is True
