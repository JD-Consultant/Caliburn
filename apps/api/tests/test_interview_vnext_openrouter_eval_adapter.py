"""V3-4R OpenRouter Chat eval adapter — mocked-HTTP conformance tests.

不打 live API;所有 provider 行為經 `httpx.MockTransport` + adapter 的真 JSON
decoder。R3 覆蓋 request projection、single-call/deadline、error matrix 與
raw/error artifacts;R4(同檔)覆蓋 success/routing/usage/redaction。

規格:docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md
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
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.port import (
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
    ModelMessage,
)
from app.interview_vnext.llm.result import FailureKind, FinishReason, ModelOutcome
from app.interview_vnext.llm.schema_exports import published_schema
from app.interview_vnext.observability.artifacts import ArtifactRef

from evals.interview_vnext.openrouter_model_catalog import (
    OpenRouterEndpointSnapshot,
    OpenRouterModelSnapshot,
)
from evals.interview_vnext.openrouter_provider_config import (
    OpenRouterProbeInputs,
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


FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openrouter_chat"
CATALOG_FIXTURES = FIXTURES
API_KEY = "sk-or-eval-test-not-a-real-key"
RUN_ID = uuid5(uuid4(), "run")
CREATED_AT = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)
REQUESTED_MODEL = "testlab/analyst-large"
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


def make_request(**overrides: Any) -> ModelCallRequest:
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
        "operation_name": operation.name,
        "operation_definition_hash": operation.definition_hash,
        "idempotency_key": f"turn-interpret/{attempt_id}/1",
        "provider": "openrouter",
        "requested_model": REQUESTED_MODEL,
        "quality_profile": operation.quality_profile,
        "instructions": "You are the Caliburn turn interpreter. Test-only instructions.",
        "messages": (
            ModelMessage(role=MessageRole.USER, text="synthetic employee turn (test)"),
        ),
        "prompt_artifact": _text_ref("test-only prompt", kind="model.prompt"),
        "output_schema_id": (
            "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json"
        ),
        "output_schema_artifact": _json_ref(
            schema,
            kind="model.output_schema",
            schema_id="https://caliburn.local/schemas/turn-interpret-output.v1.schema.json",
        ),
        "context_artifact": _json_ref({"context": "synthetic"}, kind="model.context"),
        "selection_manifest_artifact": _json_ref(
            {"selection": "synthetic"}, kind="model.selection_manifest"
        ),
        "deadline_at": CREATED_AT + timedelta(seconds=60),
        "created_at": CREATED_AT,
        "max_output_tokens": operation.max_output_tokens,
    }
    values.update(overrides)
    return ModelCallRequest(**values)


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
        envelope = await adapter.generate_structured(make_request())
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
        "overrides",
        [
            {"provider": "openai"},
            {"requested_model": "testlab/analyst-mini"},
            {"operation_name": "turn.receive"},
            {"operation_definition_hash": f"sha256:{'0' * 64}"},
            {"output_schema_id": "https://caliburn.local/schemas/unknown.v1.schema.json"},
        ],
    )
    async def test_binding_mismatches_fail_before_http(self, overrides):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        envelope = await adapter.generate_structured(make_request(**overrides))
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )

    async def test_schema_hash_mismatch_fails_before_http(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        tampered = published_schema("turn-interpret-output.v1.schema.json")
        tampered["properties"]["tampered"] = {"type": "string"}
        request = make_request(
            output_schema_artifact=_json_ref(
                tampered,
                kind="model.output_schema",
                schema_id="https://caliburn.local/schemas/turn-interpret-output.v1.schema.json",
            )
        )
        envelope = await adapter.generate_structured(request)
        assert calls == []
        assert_failure(
            envelope,
            kind=FailureKind.INVALID_REQUEST,
            reason_code="openrouter.binding_invalid",
            retryable=False,
        )

    async def test_reasoning_budget_exceeding_output_fails_before_http(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"),
            config=build_config(reasoning_effort=None, reasoning_max_tokens=8192),
        )
        # operation.max_output_tokens is 4096 < 8192 reasoning budget.
        envelope = await adapter.generate_structured(make_request())
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
        request = make_request()
        envelope = await adapter.generate_structured(request)
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
        await adapter.generate_structured(make_request())
        assert "zdr" not in json.loads(calls[0].content)["provider"]

        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"),
            config=build_config(zdr_required=True),
        )
        await adapter.generate_structured(make_request())
        assert json.loads(calls[0].content)["provider"]["zdr"] is True

    async def test_reasoning_max_tokens_variant_is_exclusive_form(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"),
            config=build_config(reasoning_effort=None, reasoning_max_tokens=2048),
        )
        await adapter.generate_structured(make_request())
        assert json.loads(calls[0].content)["reasoning"] == {
            "max_tokens": 2048,
            "exclude": True,
        }

    async def test_no_reasoning_when_disabled(self):
        adapter, calls = make_adapter(
            lambda request: fixture_response("success.json"),
            config=build_config(reasoning_effort=None),
        )
        await adapter.generate_structured(make_request())
        assert "reasoning" not in json.loads(calls[0].content)

    async def test_messages_are_mapped_verbatim_including_unicode(self):
        adapter, calls = make_adapter(lambda request: fixture_response("success.json"))
        request = make_request(
            instructions="系統指示:嚴格輸出 JSON。\n第二行。",
            messages=(
                ModelMessage(role=MessageRole.USER, text="第一題:員工說了什麼?"),
                ModelMessage(role=MessageRole.ASSISTANT, text="請描述你的日常。"),
                ModelMessage(role=MessageRole.USER, text="我負責 API 設計與 code review。"),
            ),
        )
        await adapter.generate_structured(request)
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
        await adapter.generate_structured(make_request())
        assert len(calls) == 1

    async def test_transport_timeout_is_typed(self):
        adapter, calls = make_adapter(
            lambda request: httpx.ReadTimeout("provider stalled")
        )
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
            await adapter.generate_structured(make_request())
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
        await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
            envelope = await adapter.generate_structured(make_request())
            result = envelope.result
            assert result.outcome == ModelOutcome.REFUSED
            assert result.finish_reason == FinishReason.SAFETY_REFUSAL
            assert result.refusal is not None
            assert result.refusal.safe_message == "The model declined this request."
            assert error_type not in result.refusal.safe_message
            assert_no_secret_anywhere(envelope)

    async def test_http_200_top_level_error_wins_over_status(self):
        adapter, _ = make_adapter(lambda request: fixture_response("top-error-200.json"))
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
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
        envelope = await adapter.generate_structured(make_request())
        result = envelope.result
        assert result.outcome == ModelOutcome.FAILED
        assert result.failure.kind == FailureKind.UNKNOWN_PROVIDER_FAILURE
        assert result.failure.retryable is retryable

    async def test_error_type_status_mismatch_records_both(self):
        # error_type says auth (non-retryable) but HTTP status is 500.
        adapter, _ = make_adapter(
            lambda request: httpx.Response(500, json=error_body("authentication"))
        )
        envelope = await adapter.generate_structured(make_request())
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
        request = make_request()
        envelope = await adapter.generate_structured(request)
        error_ref = envelope.result.failure.error_artifact
        assert error_ref.artifact_id == uuid5(request.attempt_id, ERROR_ARTIFACT_LABEL)
        record = {r.ref.artifact_id: r for r in envelope.supporting_artifacts}[
            error_ref.artifact_id
        ]
        assert record.run_id == request.run_id
        assert record.attempt_id == request.attempt_id
        assert record.retention_class == "eval"
        assert "sk-or" not in record.inline_content
