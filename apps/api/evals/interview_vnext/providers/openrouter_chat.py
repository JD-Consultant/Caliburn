"""OpenRouter Chat Completions eval-only adapter (V3-4R).

Maps one ``POST https://openrouter.ai/api/v1/chat/completions`` onto the neutral
``LlmPort`` contract. One durable attempt performs exactly one HTTP call: there
is no transport or adapter retry, and every failure returns as a typed
``ModelCallEnvelope``; only ``asyncio.CancelledError`` propagates.

The adapter is deliberately private to OpenRouter's wire boundary. It never
imports the OpenAI adapter and never accepts an arbitrary base URL. Since R4 it
only answers two questions: what came back on the wire (``ModelCallResult``)
and what execution facts are observable (``ProviderExecutionEvidence`` via the
pure ``openrouter_routing`` normalizer). Route/model/pipeline/cache eligibility
is decided outside the adapter by the application conformance policy; a
contaminated route is a wire success with honest evidence, never a synthetic
``ModelFailure``. Local schema + semantic verification stays in the executor.

Provider wire shape confirmed against OpenRouter official docs on 2026-07-17
(router metadata/chat response/usage) and re-checked 2026-07-19 (nested
``endpoints.available[]``, pipeline stage types, ``X-OpenRouter-Cache-Status``).
See docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-
conformance-plan.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid5

import httpx

from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.llm.binding import (
    ProviderBinding,
    RuntimeBindingMismatch,
    require_runtime_binding,
)
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
    define_provider_execution_evidence,
)
from app.interview_vnext.llm.port import (
    LlmPort,
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
    ResolvedModelCall,
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
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    RedactionStatus,
    build_inline_artifact,
)

from ..openrouter_provider_config import (
    OPENROUTER_ADAPTER_ID,
    OPENROUTER_ADAPTER_VERSION,
    OpenRouterChatEvalConfig,
)
from ..schema_catalog import (
    PublishedOutputSchemaCatalog,
    SchemaBinding,
    SchemaCatalogError,
)
from .openrouter_routing import (
    CACHE_STATUS_HEADER,
    LIMITATION_ENDPOINT_NOT_ATTESTED,
    OpenRouterRoutingFacts,
    attest_upstream_endpoint,
    normalize_openrouter_routing,
)


CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

RAW_ARTIFACT_LABEL = "artifact/openrouter-chat/raw/v1"
ROUTING_ARTIFACT_LABEL = "artifact/openrouter-chat/routing/v1"
VISIBLE_ARTIFACT_LABEL = "artifact/openrouter-chat/visible/v1"
ERROR_ARTIFACT_LABEL = "artifact/openrouter-chat/error/v1"

RAW_ARTIFACT_KIND = "provider.openrouter.response.raw"
ROUTING_ARTIFACT_KIND = "provider.openrouter.routing"
VISIBLE_ARTIFACT_KIND = "provider.response.visible"
ERROR_ARTIFACT_KIND = "provider.openrouter.error"

RAW_SCHEMA_VERSION = "openrouter_chat_raw.v1"
ROUTING_SCHEMA_VERSION = "openrouter_routing.v2"
VISIBLE_SCHEMA_VERSION = "provider_visible_response.v1"

LIMITATION_NO_RESPONSE = "openrouter response was not received"
LIMITATION_NO_USAGE = "openrouter response did not include usage"

REFUSAL_SAFE_MESSAGE = "The model declined this request."

SAFE_MESSAGES: dict[str, str] = {
    "binding": "The model request does not match the approved eval configuration.",
    "timeout": "OpenRouter did not complete the request before the attempt deadline.",
    "connection": "The adapter could not connect to OpenRouter.",
    "authentication": "OpenRouter rejected the configured credentials.",
    "permission": "The configured OpenRouter credentials do not permit this request.",
    "credits": "OpenRouter credits are unavailable for this request.",
    "invalid": "OpenRouter rejected the model request.",
    "rate": "OpenRouter rate limiting prevented this request.",
    "unavailable": "OpenRouter or the selected model endpoint was temporarily unavailable.",
    "bad_output": "OpenRouter returned an unusable structured response.",
    "route": "OpenRouter did not use the approved model routing profile.",
    "unexpected": "The adapter could not normalize the OpenRouter response.",
}

# Allowlisted response headers persisted in the raw artifact (§9.1; R4 §6.6
# adds the official cache facts — age/ttl are observability only, never an
# eligibility authority).
_ALLOWED_HEADER_KEYS = (
    "x-request-id",
    "x-generation-id",
    "retry-after",
    "x-openrouter-cache-status",
    "x-openrouter-cache-age",
    "x-openrouter-cache-ttl",
)


@dataclass(frozen=True)
class _Failure:
    kind: FailureKind
    reason_code: str
    retryable: bool
    safe_message: str
    finish_reason: FinishReason = FinishReason.PROVIDER_ERROR
    provider_error_code: str | None = None


# §10: stable error_type -> typed failure. HTTP status is only a fallback.
_ERROR_TYPE_TABLE: dict[str, _Failure] = {
    "context_length_exceeded": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.context_window_exceeded", False,
        SAFE_MESSAGES["invalid"], FinishReason.CONTEXT_WINDOW_EXCEEDED,
    ),
    "max_tokens_exceeded": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.max_tokens_exceeded", False,
        SAFE_MESSAGES["invalid"], FinishReason.MAX_OUTPUT_TOKENS,
    ),
    "token_limit_exceeded": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.token_limit_exceeded", False,
        SAFE_MESSAGES["invalid"], FinishReason.MAX_OUTPUT_TOKENS,
    ),
    "string_too_long": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.string_too_long", False,
        SAFE_MESSAGES["invalid"], FinishReason.CONTEXT_WINDOW_EXCEEDED,
    ),
    "authentication": _Failure(
        FailureKind.AUTHENTICATION_FAILED, "openrouter.authentication_failed", False,
        SAFE_MESSAGES["authentication"],
    ),
    "permission_denied": _Failure(
        FailureKind.AUTHENTICATION_FAILED, "openrouter.permission_denied", False,
        SAFE_MESSAGES["permission"],
    ),
    "payment_required": _Failure(
        FailureKind.RATE_LIMITED, "openrouter.credits_unavailable", False,
        SAFE_MESSAGES["credits"],
    ),
    "rate_limit_exceeded": _Failure(
        FailureKind.RATE_LIMITED, "openrouter.rate_limited", True,
        SAFE_MESSAGES["rate"],
    ),
    "provider_overloaded": _Failure(
        FailureKind.PROVIDER_UNAVAILABLE, "openrouter.provider_overloaded", True,
        SAFE_MESSAGES["unavailable"],
    ),
    "provider_unavailable": _Failure(
        FailureKind.PROVIDER_UNAVAILABLE, "openrouter.provider_unavailable", True,
        SAFE_MESSAGES["unavailable"],
    ),
    "timeout": _Failure(
        FailureKind.TRANSPORT_TIMEOUT, "openrouter.provider_timeout", True,
        SAFE_MESSAGES["timeout"],
    ),
    "server": _Failure(
        FailureKind.PROVIDER_UNAVAILABLE, "openrouter.server_error", True,
        SAFE_MESSAGES["unavailable"],
    ),
    "invalid_request": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.invalid_request", False,
        SAFE_MESSAGES["invalid"],
    ),
    "invalid_prompt": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.invalid_prompt", False,
        SAFE_MESSAGES["invalid"],
    ),
    "not_found": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.not_found", False,
        SAFE_MESSAGES["invalid"],
    ),
    "precondition_failed": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.precondition_failed", False,
        SAFE_MESSAGES["invalid"],
    ),
    "payload_too_large": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.payload_too_large", False,
        SAFE_MESSAGES["invalid"],
    ),
    "unprocessable": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.unprocessable", False,
        SAFE_MESSAGES["invalid"],
    ),
    "content_policy_violation": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.content_policy_violation", False,
        SAFE_MESSAGES["route"], FinishReason.SAFETY_REFUSAL,
    ),
    "refusal": _Failure(
        FailureKind.INVALID_REQUEST, "openrouter.refusal", False,
        SAFE_MESSAGES["route"], FinishReason.SAFETY_REFUSAL,
    ),
}

# error_types that are refusals (mapped to REFUSED outcome, not FAILED).
_REFUSAL_ERROR_TYPES = frozenset({"content_policy_violation", "refusal"})


def _status_fallback_failure(status: int) -> _Failure:
    table = {
        401: _Failure(
            FailureKind.AUTHENTICATION_FAILED, "openrouter.authentication_failed", False,
            SAFE_MESSAGES["authentication"],
        ),
        402: _Failure(
            FailureKind.RATE_LIMITED, "openrouter.credits_unavailable", False,
            SAFE_MESSAGES["credits"],
        ),
        403: _Failure(
            FailureKind.AUTHENTICATION_FAILED, "openrouter.permission_denied", False,
            SAFE_MESSAGES["permission"],
        ),
        404: _Failure(
            FailureKind.INVALID_REQUEST, "openrouter.not_found", False,
            SAFE_MESSAGES["invalid"],
        ),
        408: _Failure(
            FailureKind.TRANSPORT_TIMEOUT, "openrouter.provider_timeout", True,
            SAFE_MESSAGES["timeout"],
        ),
        412: _Failure(
            FailureKind.INVALID_REQUEST, "openrouter.precondition_failed", False,
            SAFE_MESSAGES["invalid"],
        ),
        413: _Failure(
            FailureKind.INVALID_REQUEST, "openrouter.payload_too_large", False,
            SAFE_MESSAGES["invalid"],
        ),
        422: _Failure(
            FailureKind.INVALID_REQUEST, "openrouter.unprocessable", False,
            SAFE_MESSAGES["invalid"],
        ),
        429: _Failure(
            FailureKind.RATE_LIMITED, "openrouter.rate_limited", True,
            SAFE_MESSAGES["rate"],
        ),
        500: _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openrouter.server_error", True,
            SAFE_MESSAGES["unavailable"],
        ),
        502: _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openrouter.provider_unavailable", True,
            SAFE_MESSAGES["unavailable"],
        ),
        503: _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openrouter.provider_overloaded", True,
            SAFE_MESSAGES["unavailable"],
        ),
        504: _Failure(
            FailureKind.TRANSPORT_TIMEOUT, "openrouter.provider_timeout", True,
            SAFE_MESSAGES["timeout"],
        ),
        524: _Failure(
            FailureKind.TRANSPORT_TIMEOUT, "openrouter.provider_timeout", True,
            SAFE_MESSAGES["timeout"],
        ),
        529: _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openrouter.provider_overloaded", True,
            SAFE_MESSAGES["unavailable"],
        ),
    }
    if status in table:
        return table[status]
    # §10: completely unknown 4xx non-retryable; unknown 5xx retryable.
    if 400 <= status < 500:
        return _Failure(
            FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.unmapped_client_error",
            False, SAFE_MESSAGES["unexpected"],
        )
    return _Failure(
        FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.unmapped_provider_error",
        True, SAFE_MESSAGES["unexpected"],
    )


def _classify_error_type(
    error_type: str | None, status: int | None
) -> _Failure:
    if error_type is not None and error_type in _ERROR_TYPE_TABLE:
        return _ERROR_TYPE_TABLE[error_type]
    if status is not None:
        return _status_fallback_failure(status)
    return _Failure(
        FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.unmapped_provider_error",
        True, SAFE_MESSAGES["unexpected"],
    )


class _LocalBindingError(Exception):
    """Config/schema/request mismatch detected before any network I/O."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class _ResponseError(Exception):
    """Structured provider/route failure detected while normalizing a response."""

    def __init__(
        self,
        failure: _Failure,
        *,
        provider_finish_reason: str,
        detail: str,
        error_type: str | None = None,
        provider_code: str | None = None,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
        status_mismatch: bool = False,
        include_visible: bool = True,
    ) -> None:
        super().__init__(detail)
        self.failure = failure
        self.provider_finish_reason = provider_finish_reason
        self.detail = detail
        self.error_type = error_type
        self.provider_code = provider_code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.status_mismatch = status_mismatch
        self.include_visible = include_visible


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        seconds = int(value.strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0 or seconds > 86400:
        return None
    return seconds


def _redact_reasoning(node: Any) -> Any:
    """Replace any reasoning text with a redaction stub before persisting (§9.1)."""

    if isinstance(node, dict):
        redacted: dict[str, Any] = {}
        for key, value in node.items():
            if key in ("reasoning", "reasoning_details", "reasoning_content") and value:
                text = value if isinstance(value, str) else canonical_json(value)
                encoded = text.encode("utf-8")
                redacted[key] = {
                    "present": True,
                    "byte_length": len(encoded),
                    "sha256": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
                    "redacted": True,
                }
            else:
                redacted[key] = _redact_reasoning(value)
        return redacted
    if isinstance(node, list):
        return [_redact_reasoning(item) for item in node]
    return node


def _reasoning_present(body: Any) -> bool:
    if isinstance(body, dict):
        for key, value in body.items():
            if key in ("reasoning", "reasoning_details", "reasoning_content") and value:
                return True
            if _reasoning_present(value):
                return True
    elif isinstance(body, list):
        return any(_reasoning_present(item) for item in body)
    return False


def _allowed_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: headers[key] for key in _ALLOWED_HEADER_KEYS if key in headers
    }


def _identity_fields(
    request: ModelCallRequest, *, gateway_provider: str
) -> dict[str, Any]:
    """Result identity:attempted request/binding identity + actual runtime gateway.

    §5.1.1 語意表:`binding_id/hash/requested_model` 保留被嘗試的 binding
    identity;`gateway_provider` 記實際 runtime adapter gateway(preflight 通過時
    兩者必然相等,唯一可見差異是 `runtime_binding_mismatch` failure)。
    """

    return {
        "run_id": request.run_id,
        "session_id": request.session_id,
        "turn_id": request.turn_id,
        "operation_id": request.operation_id,
        "attempt_id": request.attempt_id,
        "attempt": request.attempt,
        "operation_name": request.operation_name,
        "operation_definition_hash": request.operation_definition_hash,
        "binding_id": request.binding_id,
        "binding_hash": request.binding_hash,
        "gateway_provider": gateway_provider,
        "requested_model": request.requested_model,
        "prompt_hash": request.prompt_hash,
        "output_schema_id": request.output_schema_id,
        "output_schema_hash": request.output_schema_hash,
        "context_hash": request.context_hash,
    }


class OpenRouterChatEvalAdapter(LlmPort):
    """Eval-only ``LlmPort`` over OpenRouter Chat Completions (direct HTTP)."""

    def __init__(
        self,
        *,
        api_key: str,
        config: OpenRouterChatEvalConfig,
        catalog: PublishedOutputSchemaCatalog | None = None,
        http_client: httpx.AsyncClient | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._api_key = api_key
        self._config = config
        self._catalog = catalog or PublishedOutputSchemaCatalog()
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._owns_http_client = http_client is None
        self._client = http_client or httpx.AsyncClient(follow_redirects=False)

    async def __aenter__(self) -> "OpenRouterChatEvalAdapter":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._client.aclose()

    async def generate_structured(self, call: ResolvedModelCall) -> ModelCallEnvelope:
        request = call.request
        provider_binding = call.binding
        started_at = self._now()
        started_mono = self._monotonic()
        # R3-C1(修正計畫 §5.1/§6.7):neutral runtime binding preflight 先於既有
        # schema/body validation;adapter ID/version/gateway/config hash 任一不符
        # 即 fail closed,0 次 HTTP,neutral failure kind 固定 RUNTIME_BINDING_MISMATCH。
        try:
            require_runtime_binding(
                provider_binding,
                adapter_id=OPENROUTER_ADAPTER_ID,
                adapter_version=OPENROUTER_ADAPTER_VERSION,
                gateway_provider=self._config.provider,
                provider_config_hash=self._config.config_hash,
            )
        except RuntimeBindingMismatch as exc:
            failure = _Failure(
                FailureKind.RUNTIME_BINDING_MISMATCH,
                "openrouter.binding_invalid",
                False,
                SAFE_MESSAGES["binding"],
            )
            return self._failure_envelope(
                request, provider_binding, failure,
                started_at=started_at, started_mono=started_mono, detail=str(exc),
                preflight_mismatch=True,
            )
        try:
            schema_binding = self._validate_binding(request, provider_binding)
        except _LocalBindingError as exc:
            failure = _Failure(
                FailureKind.INVALID_REQUEST,
                "openrouter.binding_invalid",
                False,
                SAFE_MESSAGES["binding"],
            )
            return self._failure_envelope(
                request, provider_binding, failure,
                started_at=started_at, started_mono=started_mono, detail=exc.detail,
            )

        remaining_seconds = (request.deadline_at - started_at).total_seconds()
        if remaining_seconds <= 0:
            failure = _Failure(
                FailureKind.TRANSPORT_TIMEOUT, "openrouter.timeout", True,
                SAFE_MESSAGES["timeout"],
            )
            return self._failure_envelope(
                request, provider_binding, failure,
                started_at=started_at, started_mono=started_mono,
                detail="attempt deadline expired before the provider call",
            )

        body = self._build_body(request, schema_binding)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-OpenRouter-Metadata": "enabled",
        }
        connect_timeout = min(self._config.connect_timeout_seconds, remaining_seconds)
        http_timeout = httpx.Timeout(remaining_seconds, connect=connect_timeout)
        try:
            async with asyncio.timeout(remaining_seconds):
                response = await self._client.post(
                    CHAT_COMPLETIONS_URL,
                    headers=headers,
                    content=canonical_json(body).encode("utf-8"),
                    timeout=http_timeout,
                )
        except asyncio.CancelledError:
            raise
        except (httpx.TimeoutException, TimeoutError) as exc:
            failure = _Failure(
                FailureKind.TRANSPORT_TIMEOUT, "openrouter.timeout", True,
                SAFE_MESSAGES["timeout"],
            )
            return self._failure_envelope(
                request, provider_binding, failure,
                started_at=started_at, started_mono=started_mono,
                detail=f"transport timeout: {type(exc).__name__}",
                exception=exc,
            )
        except httpx.HTTPError as exc:
            failure = _Failure(
                FailureKind.TRANSPORT_ERROR, "openrouter.transport_error", True,
                SAFE_MESSAGES["connection"],
            )
            return self._failure_envelope(
                request, provider_binding, failure,
                started_at=started_at, started_mono=started_mono,
                detail=f"transport error: {type(exc).__name__}",
                exception=exc,
            )
        return self._normalize_response(
            request, provider_binding, response,
            started_at=started_at, started_mono=started_mono,
        )

    # ---- pre-HTTP validation (§7.1) -----------------------------------------

    def _validate_binding(
        self, request: ModelCallRequest, provider_binding: ProviderBinding
    ) -> SchemaBinding:
        if provider_binding.gateway_provider != self._config.provider:
            raise _LocalBindingError(
                f"binding gateway provider {provider_binding.gateway_provider!r} "
                "is not approved for this adapter"
            )
        if request.requested_model != self._config.requested_model:
            raise _LocalBindingError(
                "request model does not match the approved eval config: "
                f"{request.requested_model!r} != {self._config.requested_model!r}"
            )
        if self._config.accepted_resolved_models != (self._config.requested_model,):
            raise _LocalBindingError(
                "eval config accepted models are not exactly the requested model"
            )
        try:
            binding = self._catalog.resolve(request)
        except SchemaCatalogError as exc:
            raise _LocalBindingError(str(exc)) from exc
        roles = tuple(item.role for item in request.messages)
        if (
            not roles
            or roles[0] != MessageRole.USER
            or roles[-1] != MessageRole.USER
            or any(a == b for a, b in zip(roles, roles[1:], strict=False))
        ):
            raise _LocalBindingError("request messages violate the neutral turn shape")
        if self._config.reasoning_max_tokens is not None and (
            request.max_output_tokens <= self._config.reasoning_max_tokens
        ):
            raise _LocalBindingError(
                "request max_output_tokens must exceed the reasoning token budget"
            )
        return binding

    # ---- outbound request (§7.2/§7.3/§7.5) ----------------------------------

    def _build_body(
        self, request: ModelCallRequest, binding: SchemaBinding
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": request.instructions}
        ]
        messages.extend(
            {"role": item.role.value, "content": item.text} for item in request.messages
        )
        provider_block: dict[str, Any] = {
            "order": list(self._config.provider_order),
            "only": list(self._config.provider_only),
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": self._config.data_collection,
        }
        if self._config.zdr_required:
            provider_block["zdr"] = True
        body: dict[str, Any] = {
            "model": self._config.requested_model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": binding.format_name,
                    "strict": True,
                    "schema": binding.schema,
                },
            },
            "provider": provider_block,
            "plugins": [
                {"id": plugin_id, "enabled": False}
                for plugin_id in self._config.disabled_plugins
            ],
        }
        if self._config.reasoning_effort is not None:
            body["reasoning"] = {
                "effort": self._config.reasoning_effort,
                "exclude": True,
            }
        elif self._config.reasoning_max_tokens is not None:
            body["reasoning"] = {
                "max_tokens": self._config.reasoning_max_tokens,
                "exclude": True,
            }
        return body

    # ---- timing / envelope assembly -----------------------------------------

    def _timing(
        self, *, started_at: datetime, started_mono: float
    ) -> tuple[datetime, int]:
        completed_at = self._now()
        if completed_at < started_at:
            completed_at = started_at
        latency_ms = max(0, math.floor((self._monotonic() - started_mono) * 1000.0))
        return completed_at, latency_ms

    def _supporting_artifact(
        self,
        request: ModelCallRequest,
        *,
        label: str,
        kind: str,
        payload: Any,
        created_at: datetime,
    ) -> ArtifactRecord:
        return build_inline_artifact(
            artifact_id=uuid5(request.attempt_id, label),
            kind=kind,
            media_type="application/json",
            payload=payload,
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            created_at=created_at,
            retention_class="eval",
            redaction_status=RedactionStatus.NOT_REQUIRED,
            contains_test_data=True,
        )

    def _raw_artifact(
        self,
        request: ModelCallRequest,
        response: httpx.Response,
        *,
        body: Any,
        created_at: datetime,
    ) -> ArtifactRecord:
        reasoning_present = _reasoning_present(body)
        payload = {
            "schema_version": RAW_SCHEMA_VERSION,
            "gateway": "openrouter",
            "api_format": "chat_completions",
            "http": {
                "status_code": response.status_code,
                "headers": _allowed_headers(response.headers),
            },
            "body": _redact_reasoning(_json_safe(body)),
            "redaction_status": "redacted" if reasoning_present else "not_required",
            "redactions": ["reasoning"] if reasoning_present else [],
        }
        return self._supporting_artifact(
            request,
            label=RAW_ARTIFACT_LABEL,
            kind=RAW_ARTIFACT_KIND,
            payload=payload,
            created_at=created_at,
        )

    def _error_artifact(
        self,
        request: ModelCallRequest,
        *,
        failure: _Failure,
        created_at: datetime,
        detail: str | None = None,
        error_type: str | None = None,
        provider_code: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        generation_id: str | None = None,
        retry_after_seconds: int | None = None,
        status_mismatch: bool = False,
        body: Any = None,
        exception_type: str | None = None,
    ) -> ArtifactRecord:
        payload = {
            "schema_version": "openrouter_error.v1",
            "classification": {
                "failure_kind": failure.kind.value,
                "reason_code": failure.reason_code,
                "retryable": failure.retryable,
                "provider_error_code": failure.provider_error_code or provider_code,
            },
            "detail": detail,
            "http_status": status_code,
            "error_type": error_type,
            "provider_code": provider_code,
            "request_id": request_id,
            "generation_id": generation_id,
            "retry_after_seconds": retry_after_seconds,
            # R4: eligibility verdicts moved to the application conformance
            # report; the wire-error artifact keeps its v1 shape with no verdict.
            "route_conformance": None,
            "status_mismatch": status_mismatch,
            "body": _redact_reasoning(_json_safe(body)),
            "exception_type": exception_type,
        }
        return self._supporting_artifact(
            request,
            label=ERROR_ARTIFACT_LABEL,
            kind=ERROR_ARTIFACT_KIND,
            payload=payload,
            created_at=created_at,
        )

    def _failure_envelope(
        self,
        request: ModelCallRequest,
        binding: ProviderBinding,
        failure: _Failure,
        *,
        started_at: datetime,
        started_mono: float,
        detail: str | None = None,
        exception: Exception | None = None,
        preflight_mismatch: bool = False,
    ) -> ModelCallEnvelope:
        """Failure with no usable HTTP response (binding/deadline/transport)."""

        completed_at, latency_ms = self._timing(
            started_at=started_at, started_mono=started_mono
        )
        error = self._error_artifact(
            request,
            failure=failure,
            created_at=completed_at,
            detail=detail,
            exception_type=type(exception).__name__ if exception is not None else None,
        )
        usage = TokenUsage(limitations=(LIMITATION_NO_RESPONSE,))
        result = ModelCallResult(
            **_identity_fields(request, gateway_provider=self._config.provider),
            resolved_model=request.requested_model,
            provider_request_id=None,
            provider_conversation_id=None,
            outcome=ModelOutcome.FAILED,
            finish_reason=failure.finish_reason,
            provider_finish_reason=None,
            parsed_output=None,
            visible_response_artifact=None,
            refusal=None,
            failure=ModelFailure(
                kind=failure.kind,
                reason_code=failure.reason_code,
                retryable=failure.retryable,
                safe_message=failure.safe_message,
                provider_error_code=failure.provider_error_code,
                error_artifact=error.ref,
            ),
            usage=usage,
            latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
        evidence = _no_response_evidence(
            binding, request, gateway_provider=self._config.provider,
            usage=usage, preflight_mismatch=preflight_mismatch,
        )
        return ModelCallEnvelope(
            result=result, execution_evidence=evidence, supporting_artifacts=(error,)
        )

    # ---- response normalization (§9/§10/§11) --------------------------------

    def _normalize_response(
        self,
        request: ModelCallRequest,
        binding: ProviderBinding,
        response: httpx.Response,
        *,
        started_at: datetime,
        started_mono: float,
    ) -> ModelCallEnvelope:
        completed_at, latency_ms = self._timing(
            started_at=started_at, started_mono=started_mono
        )
        request_id = response.headers.get("x-request-id")
        generation_id_header = response.headers.get("x-generation-id")
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        cache_header = response.headers.get(CACHE_STATUS_HEADER)
        status = response.status_code

        try:
            body: Any = response.json()
        except ValueError:
            body = None

        raw = self._raw_artifact(
            request, response, body=body if body is not None else response.text[:2000],
            created_at=completed_at,
        )

        base = dict(
            **_identity_fields(request, gateway_provider=self._config.provider),
            provider_request_id=request_id,
            provider_conversation_id=None,
            latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )

        # §9.2.1: JSON decode failure.
        if body is None:
            no_usage = TokenUsage(limitations=(LIMITATION_NO_USAGE,))
            no_response_evidence = _no_response_evidence(
                binding, request, gateway_provider=self._config.provider,
                usage=no_usage,
            )
            if 200 <= status < 300:
                failure = _Failure(
                    FailureKind.OUTPUT_PARSE_FAILED, "openrouter.output_parse_failed",
                    False, SAFE_MESSAGES["bad_output"],
                )
                # OUTPUT_PARSE_FAILED requires a visible artifact; there is no
                # parseable body, so record an empty visible envelope.
                visible = self._visible_artifact(request, {}, created_at=completed_at)
                error = self._error_artifact(
                    request, failure=failure, created_at=completed_at,
                    detail="2xx response body was not valid JSON",
                    status_code=status, request_id=request_id,
                )
                return self._assemble_failure(
                    binding, base, failure, provider_finish_reason=f"http_error:{status}:decode",
                    usage=no_usage, evidence=no_response_evidence,
                    error=error, extra=(raw, visible), visible=visible,
                    resolved_model=request.requested_model,
                )
            failure = _status_fallback_failure(status)
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="non-2xx response body was not valid JSON",
                status_code=status, request_id=request_id, retry_after_seconds=retry_after,
                body=response.text[:2000],
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=f"http_error:{status}:non_json",
                usage=no_usage, evidence=no_response_evidence,
                error=error, extra=(raw,), visible=None,
                resolved_model=request.requested_model,
            )

        usage = _map_usage(body)

        # §7.2 step 3: pure observation before any wire verdict. Route/cache/
        # pipeline facts are normalized once from the parseable body and reused
        # by every downstream outcome — success, refusal, error — so an error
        # response never loses its known routing facts (§7.5).
        routing_artifact: ArtifactRecord | None = None
        if isinstance(body, dict):
            metadata = body.get("openrouter_metadata")
            facts = normalize_openrouter_routing(
                metadata, cache_header_value=cache_header
            )
            raw_model = body.get("model")
            resolved_actual = (
                raw_model if isinstance(raw_model, str) and raw_model.strip() else None
            )
            generation_id = _generation_id(body, generation_id_header)
            usage_dict = (
                body.get("usage") if isinstance(body.get("usage"), dict) else {}
            )
            cost_decimal = _decimal_str(usage_dict.get("cost"))
            routing_artifact = self._routing_artifact(
                request, facts, metadata=metadata, resolved_model=resolved_actual,
                generation_id=generation_id, request_id=request_id,
                cost_decimal=cost_decimal, usage_dict=usage_dict,
                cache_header_value=cache_header, created_at=completed_at,
            )
            evidence = self._facts_evidence(
                binding, request, facts=facts, resolved_model=resolved_actual,
                routing_ref=routing_artifact.ref, usage=usage,
                cost_decimal=cost_decimal, request_id=request_id,
                generation_id=generation_id,
            )
        else:
            evidence = _no_response_evidence(
                binding, request, gateway_provider=self._config.provider, usage=usage
            )

        try:
            return self._interpret_body(
                request, binding, body, base=base, usage=usage, raw=raw,
                routing_artifact=routing_artifact, evidence=evidence,
                status=status, request_id=request_id,
                generation_id_header=generation_id_header, retry_after=retry_after,
                completed_at=completed_at,
            )
        except _ResponseError as exc:
            resolved = body.get("model") if isinstance(body, dict) else None
            visible = None
            extras: tuple[ArtifactRecord, ...] = (
                (raw, routing_artifact) if routing_artifact is not None else (raw,)
            )
            if exc.include_visible:
                visible = self._visible_artifact(request, body, created_at=completed_at)
                extras = (*extras, visible)
            generation_id = _generation_id(body, generation_id_header)
            error = self._error_artifact(
                request, failure=exc.failure, created_at=completed_at, detail=exc.detail,
                error_type=exc.error_type, provider_code=exc.provider_code,
                status_code=exc.status_code if exc.status_code is not None else status,
                request_id=request_id, generation_id=generation_id,
                retry_after_seconds=exc.retry_after_seconds
                if exc.retry_after_seconds is not None else retry_after,
                status_mismatch=exc.status_mismatch, body=body,
            )
            if exc.failure.finish_reason == FinishReason.SAFETY_REFUSAL and (
                exc.error_type in _REFUSAL_ERROR_TYPES
            ):
                return self._assemble_refusal(
                    binding, base, usage=usage, visible=visible or self._visible_artifact(
                        request, body, created_at=completed_at
                    ),
                    raw=raw, routing=routing_artifact, evidence=evidence,
                    provider_category=exc.error_type or "refusal",
                    resolved_model=resolved
                    if isinstance(resolved, str) and resolved.strip()
                    else request.requested_model,
                )
            return self._assemble_failure(
                binding, base, exc.failure, provider_finish_reason=exc.provider_finish_reason,
                usage=usage, evidence=evidence, error=error, extra=extras,
                visible=visible,
                resolved_model=resolved
                if isinstance(resolved, str) and resolved.strip()
                else request.requested_model,
            )

    def _interpret_body(
        self,
        request: ModelCallRequest,
        binding: ProviderBinding,
        body: dict[str, Any],
        *,
        base: dict[str, Any],
        usage: TokenUsage,
        raw: ArtifactRecord,
        routing_artifact: ArtifactRecord | None,
        evidence: ProviderExecutionEvidence,
        status: int,
        request_id: str | None,
        generation_id_header: str | None,
        retry_after: int | None,
        completed_at: datetime,
    ) -> ModelCallEnvelope:
        # §9.2.2/§9.2.3: top-level error precedes content, regardless of HTTP 200.
        top_error = body.get("error") if isinstance(body, dict) else None
        if isinstance(top_error, dict):
            error_type, provider_code, retry_hint = _error_fields(top_error)
            failure = _classify_error_type(error_type, status if status >= 400 else None)
            if status < 400 and error_type is None:
                failure = _Failure(
                    FailureKind.UNKNOWN_PROVIDER_FAILURE,
                    "openrouter.unmapped_provider_error", True,
                    SAFE_MESSAGES["unexpected"],
                )
            raise _ResponseError(
                failure,
                provider_finish_reason=(
                    f"http_error:{status}:{error_type or 'unmapped'}"
                ),
                detail="top-level error object in response body",
                error_type=error_type, provider_code=provider_code,
                status_code=status,
                retry_after_seconds=retry_hint if retry_hint is not None else retry_after,
                status_mismatch=(status < 400),
                include_visible=False,
            )

        if not (200 <= status < 300):
            failure = _status_fallback_failure(status)
            raise _ResponseError(
                failure,
                provider_finish_reason=f"http_error:{status}:unmapped",
                detail=f"non-2xx response without a typed error object ({status})",
                status_code=status, retry_after_seconds=retry_after,
                include_visible=False,
            )

        # §9.2.4: protocol envelope.
        if not isinstance(body, dict) or body.get("object") != "chat.completion":
            raise _ResponseError(
                _Failure(
                    FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.protocol_invalid",
                    False, SAFE_MESSAGES["unexpected"],
                ),
                provider_finish_reason="chat:none",
                detail=f"unexpected response object {body.get('object')!r}",
                include_visible=False,
            )
        generation_id = _generation_id(body, generation_id_header)
        resolved_model = body.get("model")
        if not isinstance(generation_id, str) or not generation_id:
            raise _ResponseError(
                _Failure(
                    FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.protocol_invalid",
                    False, SAFE_MESSAGES["unexpected"],
                ),
                provider_finish_reason="chat:none",
                detail="response is missing a generation id",
                include_visible=False,
            )
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            # blank-only model 也不是可用的 protocol fact(NonEmptyText 下游)。
            raise _ResponseError(
                _Failure(
                    FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.protocol_invalid",
                    False, SAFE_MESSAGES["unexpected"],
                ),
                provider_finish_reason="chat:none",
                detail="response is missing a resolved model",
                include_visible=False,
            )

        # R4: no adapter-side routing/model gate. Route facts were already
        # normalized into `evidence`/`routing_artifact` (§7.2 step 3); whether
        # this execution is eligible is the application conformance policy's
        # call, after the wire result. `routing_artifact` is always present on
        # this path (the body is a dict).
        assert routing_artifact is not None

        # §9.2.6: exactly one choice at index 0.
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            visible = self._visible_artifact(request, body, created_at=completed_at)
            failure = _Failure(
                FailureKind.OUTPUT_PARSE_FAILED, "openrouter.choice_cardinality_invalid",
                False, SAFE_MESSAGES["bad_output"],
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail=f"expected exactly one choice, found "
                f"{len(choices) if isinstance(choices, list) else 'none'}",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason="chat:none", usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("index") != 0:
            visible = self._visible_artifact(request, body, created_at=completed_at)
            failure = _Failure(
                FailureKind.OUTPUT_PARSE_FAILED, "openrouter.choice_index_invalid",
                False, SAFE_MESSAGES["bad_output"],
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="choice[0] is missing or not at index 0",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason="chat:none", usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )

        # §9.2.7: embedded choice-level error precedes content.
        finish_reason = choice.get("finish_reason")
        native_finish = choice.get("native_finish_reason")
        choice_error = choice.get("error")
        if isinstance(choice_error, dict) or finish_reason == "error":
            error_type, provider_code, retry_hint = _error_fields(
                choice_error if isinstance(choice_error, dict) else {}
            )
            failure = _classify_error_type(error_type, None)
            visible = self._visible_artifact(request, body, created_at=completed_at)
            if error_type in _REFUSAL_ERROR_TYPES:
                return self._assemble_refusal(
                    binding, base, usage=usage, visible=visible, raw=raw,
                    routing=routing_artifact, evidence=evidence,
                    provider_category=error_type,
                    resolved_model=resolved_model,
                )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="choice-level embedded error",
                error_type=error_type, provider_code=provider_code,
                request_id=request_id, generation_id=generation_id,
                retry_after_seconds=retry_hint,
            )
            return self._assemble_failure(
                binding, base, failure,
                provider_finish_reason=f"embedded_error:{error_type or 'unmapped'}",
                usage=usage, evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible),
                visible=visible, resolved_model=resolved_model,
            )

        visible = self._visible_artifact(request, body, created_at=completed_at)
        provider_finish = _provider_finish(body, finish_reason, native_finish)

        # §9.5 finish reason mapping.
        message = choice.get("message")
        if isinstance(message, dict) and message.get("tool_calls"):
            failure = _Failure(
                FailureKind.OUTPUT_PARSE_FAILED, "openrouter.unexpected_tool_calls",
                False, SAFE_MESSAGES["bad_output"], FinishReason.TOOL_USE,
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="response contained tool_calls though the request has no tools",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=provider_finish, usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )

        if finish_reason == "content_filter":
            return self._assemble_refusal(
                binding, base, usage=usage, visible=visible, raw=raw,
                routing=routing_artifact, evidence=evidence,
                provider_category="content_filter", resolved_model=resolved_model,
            )

        if finish_reason == "length":
            result = ModelCallResult(
                **base, resolved_model=resolved_model,
                outcome=ModelOutcome.INCOMPLETE,
                finish_reason=FinishReason.MAX_OUTPUT_TOKENS,
                provider_finish_reason=provider_finish,
                parsed_output=None, visible_response_artifact=visible.ref,
                refusal=None, failure=None, usage=usage,
            )
            return ModelCallEnvelope(
                result=result, execution_evidence=evidence,
                supporting_artifacts=(raw, routing_artifact, visible),
            )

        if finish_reason != "stop":
            failure = _Failure(
                FailureKind.UNKNOWN_PROVIDER_FAILURE, "openrouter.unknown_finish_reason",
                False, SAFE_MESSAGES["unexpected"], FinishReason.UNKNOWN,
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail=f"unknown finish reason {finish_reason!r}",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=provider_finish, usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )

        # finish_reason == "stop": §9.4 content, then §9.5 JSON parse.
        content = _message_text(message)
        if content is None or content == "":
            failure = _Failure(
                FailureKind.OUTPUT_PARSE_FAILED, "openrouter.empty_content", True,
                SAFE_MESSAGES["bad_output"],
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="stop finish reason produced empty content",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=provider_finish, usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )
        try:
            value = json.loads(content)
        except ValueError:
            failure = _Failure(
                FailureKind.OUTPUT_PARSE_FAILED, "openrouter.output_parse_failed", False,
                SAFE_MESSAGES["bad_output"],
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="content is not valid JSON",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=provider_finish, usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )
        if not isinstance(value, dict):
            failure = _Failure(
                FailureKind.OUTPUT_SCHEMA_INVALID, "openrouter.output_schema_invalid",
                False, SAFE_MESSAGES["bad_output"],
            )
            error = self._error_artifact(
                request, failure=failure, created_at=completed_at,
                detail="output JSON root is not an object",
                request_id=request_id, generation_id=generation_id,
            )
            return self._assemble_failure(
                binding, base, failure, provider_finish_reason=provider_finish, usage=usage,
                evidence=evidence, error=error,
                extra=(raw, routing_artifact, visible), visible=visible,
                resolved_model=resolved_model,
            )
        payload = build_structured_payload(
            schema_id=request.output_schema_id, value=value
        )
        result = ModelCallResult(
            **base, resolved_model=resolved_model,
            outcome=ModelOutcome.SUCCEEDED, finish_reason=FinishReason.COMPLETED,
            provider_finish_reason=provider_finish, parsed_output=payload,
            visible_response_artifact=visible.ref, refusal=None, failure=None,
            usage=usage,
        )
        return ModelCallEnvelope(
            result=result, execution_evidence=evidence,
            supporting_artifacts=(raw, routing_artifact, visible),
        )

    # ---- routing facts artifact (R4 §7.4) -----------------------------------

    def _routing_artifact(
        self,
        request: ModelCallRequest,
        facts: OpenRouterRoutingFacts,
        *,
        metadata: Any,
        resolved_model: str | None,
        generation_id: str | None,
        request_id: str | None,
        cost_decimal: str | None,
        usage_dict: dict[str, Any],
        cache_header_value: str | None,
        created_at: datetime,
    ) -> ArtifactRecord:
        """Immutable provider-specific source artifact behind the normalized
        route facts. Pure observation — no ``eligible``/``conformance``/
        ``pipeline_clean`` verdicts (§7.4). ``attempts``/``pipeline`` keep the
        sanitized raw metadata values even when malformed."""

        metadata_dict = metadata if isinstance(metadata, dict) else {}
        payload = {
            "schema_version": ROUTING_SCHEMA_VERSION,
            "requested_model": request.requested_model,
            "metadata_requested_model": facts.metadata_requested_model,
            "resolved_model": resolved_model,
            "catalog_canonical_model": self._config.catalog_canonical_model,
            "configured_endpoint_slug": self._config.upstream_endpoint_slug,
            "expected_provider_name": self._config.expected_upstream_provider_name,
            "selected_provider_name": facts.selected_provider,
            "selected_model": facts.selected_model,
            "selected_count": facts.selected_count,
            "strategy": facts.route_strategy,
            "router_attempt": facts.router_attempt,
            "attempts": _json_safe(metadata_dict.get("attempts")),
            "pipeline": _json_safe(metadata_dict.get("pipeline")),
            "pipeline_stage_summaries": [
                {
                    "index": stage.index,
                    "type": stage.stage_type,
                    "name": stage.name,
                    "status": stage.status,
                    "transformation": stage.transformation_status.value,
                    "details_hash": stage.details_hash,
                }
                for stage in facts.pipeline_stages
            ],
            "transformation_status": facts.transformation_status.value,
            "cache_status": facts.cache_status.value,
            "cache_header_value": cache_header_value,
            "is_byok": facts.is_byok,
            "region": facts.region,
            "generation_id": generation_id,
            "http_request_id": request_id,
            "cost": cost_decimal,
            "usage_total_mismatch": _usage_total_mismatch(usage_dict),
            "normalization_limitations": sorted(set(facts.limitations)),
        }
        return self._supporting_artifact(
            request,
            label=ROUTING_ARTIFACT_LABEL,
            kind=ROUTING_ARTIFACT_KIND,
            payload=payload,
            created_at=created_at,
        )

    def _facts_evidence(
        self,
        binding: ProviderBinding,
        request: ModelCallRequest,
        *,
        facts: OpenRouterRoutingFacts,
        resolved_model: str | None,
        routing_ref: ArtifactRef,
        usage: TokenUsage,
        cost_decimal: str | None,
        request_id: str | None,
        generation_id: str | None,
    ) -> ProviderExecutionEvidence:
        """Unified facts → evidence builder for every parseable object body.

        Actual observed values only: the binding's expected provider/model are
        never copied into actual fields, and the endpoint slug is recorded only
        when §6.4 attestation holds. The wire outcome does not change what gets
        recorded here (§7.5).
        """

        upstream_endpoint = attest_upstream_endpoint(
            facts,
            outbound_requested_model=request.requested_model,
            configured_endpoint_slug=binding.upstream_endpoint or "",
            expected_upstream_provider=binding.upstream_provider or "",
            accepted_upstream_models=binding.accepted_upstream_models,
        ) or None
        limitations = set(facts.limitations)
        if upstream_endpoint is None:
            limitations.add(LIMITATION_ENDPOINT_NOT_ATTESTED)
        if cost_decimal is None:
            limitations.add("openrouter response did not include cost")
        if (
            resolved_model is None
            or facts.selected_provider is None
            or facts.selected_model is None
            or facts.route_strategy is None
            or facts.router_attempt is None
        ):
            limitations.add("openrouter route metadata was not fully available")
        return define_provider_execution_evidence(
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            adapter_id=OPENROUTER_ADAPTER_ID,
            adapter_version=OPENROUTER_ADAPTER_VERSION,
            gateway_provider=self._config.provider,
            requested_model=request.requested_model,
            gateway_resolved_model=resolved_model,
            upstream_provider=facts.selected_provider,
            upstream_model=facts.selected_model,
            upstream_endpoint=upstream_endpoint,
            route_strategy=facts.route_strategy,
            upstream_attempt_count=facts.router_attempt,
            transformation_status=facts.transformation_status,
            pipeline_stages=facts.pipeline_stages,
            cache_status=facts.cache_status,
            provider_request_id=request_id,
            generation_id=generation_id,
            usage=usage,
            cost_decimal=cost_decimal,
            limitations=tuple(sorted(limitations)),
            raw_routing_artifact=routing_ref,
        )

    def _visible_artifact(
        self, request: ModelCallRequest, body: dict[str, Any], *, created_at: datetime
    ) -> ArtifactRecord:
        payload = {
            "schema_version": VISIBLE_SCHEMA_VERSION,
            "items": _visible_items(body),
        }
        return self._supporting_artifact(
            request,
            label=VISIBLE_ARTIFACT_LABEL,
            kind=VISIBLE_ARTIFACT_KIND,
            payload=payload,
            created_at=created_at,
        )

    # ---- result assembly helpers --------------------------------------------

    def _assemble_failure(
        self,
        binding: ProviderBinding,
        base: dict[str, Any],
        failure: _Failure,
        *,
        provider_finish_reason: str,
        usage: TokenUsage,
        evidence: ProviderExecutionEvidence,
        error: ArtifactRecord,
        extra: tuple[ArtifactRecord, ...],
        visible: ArtifactRecord | None,
        resolved_model: str,
    ) -> ModelCallEnvelope:
        result = ModelCallResult(
            **base, resolved_model=resolved_model,
            outcome=ModelOutcome.FAILED, finish_reason=failure.finish_reason,
            provider_finish_reason=provider_finish_reason, parsed_output=None,
            visible_response_artifact=visible.ref if visible is not None else None,
            refusal=None,
            failure=ModelFailure(
                kind=failure.kind, reason_code=failure.reason_code,
                retryable=failure.retryable, safe_message=failure.safe_message,
                provider_error_code=failure.provider_error_code,
                error_artifact=error.ref,
            ),
            usage=usage,
        )
        return ModelCallEnvelope(
            result=result,
            execution_evidence=evidence,
            supporting_artifacts=(*extra, error),
        )

    def _assemble_refusal(
        self,
        binding: ProviderBinding,
        base: dict[str, Any],
        *,
        usage: TokenUsage,
        visible: ArtifactRecord,
        raw: ArtifactRecord,
        evidence: ProviderExecutionEvidence,
        provider_category: str,
        resolved_model: str,
        routing: ArtifactRecord | None = None,
    ) -> ModelCallEnvelope:
        extras = (raw, routing, visible) if routing is not None else (raw, visible)
        result = ModelCallResult(
            **base, resolved_model=resolved_model,
            outcome=ModelOutcome.REFUSED, finish_reason=FinishReason.SAFETY_REFUSAL,
            provider_finish_reason=f"refusal:{provider_category}",
            parsed_output=None, visible_response_artifact=visible.ref,
            refusal=ModelRefusal(
                reason_code="openrouter.refusal",
                safe_message=REFUSAL_SAFE_MESSAGE,
                provider_category=provider_category,
            ),
            failure=None, usage=usage,
        )
        return ModelCallEnvelope(
            result=result,
            execution_evidence=evidence,
            supporting_artifacts=extras,
        )


# ---- module-level pure helpers ----------------------------------------------


def _no_response_evidence(
    binding: ProviderBinding,
    request: ModelCallRequest,
    *,
    gateway_provider: str,
    usage: TokenUsage,
    preflight_mismatch: bool = False,
) -> ProviderExecutionEvidence:
    """Route-less evidence when no parseable provider body exists (§7.5):
    binding/deadline/transport failures and undecodable response bodies. All
    route facts are unknown; nothing is fabricated from binding expectations.

    adapter ID/version/gateway 描述實際 runtime adapter(§5.1.1);preflight
    mismatch 時不從不相符的 binding 複製,並以 limitation 明確記錄。
    """

    limitations = ["openrouter execution evidence unavailable for a failed attempt"]
    if preflight_mismatch:
        limitations.append(
            "openrouter runtime binding preflight failed before any provider call"
        )
    return define_provider_execution_evidence(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=OPENROUTER_ADAPTER_ID,
        adapter_version=OPENROUTER_ADAPTER_VERSION,
        gateway_provider=gateway_provider,
        requested_model=request.requested_model,
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
        usage=usage,
        cost_decimal=None,
        limitations=tuple(sorted(limitations)),
        raw_routing_artifact=None,
    )


def _decimal_str(cost: Any) -> str | None:
    """Canonicalize cost as a decimal string; never recompute with binary float."""

    if cost is None:
        return None
    if isinstance(cost, bool):
        return None
    if isinstance(cost, str):
        return cost
    if isinstance(cost, int):
        return str(cost)
    if isinstance(cost, float):
        # `repr` round-trips the exact float without adding precision noise.
        return repr(cost)
    return None


def _usage_total_mismatch(usage: dict[str, Any]) -> bool:
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (prompt, completion, total)
    ):
        return False
    return prompt + completion != total


def _error_fields(error: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
    """Return (error_type, provider_code, retry_after_seconds) from an error object."""

    metadata = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    error_type = metadata.get("error_type")
    if not isinstance(error_type, str):
        error_type = error.get("type") if isinstance(error.get("type"), str) else None
    code = error.get("code")
    provider_code = code if isinstance(code, str) else (
        str(code) if code is not None else None
    )
    retry_after = metadata.get("retry_after")
    retry_seconds = _parse_retry_after(
        str(retry_after) if retry_after is not None else None
    )
    return error_type, provider_code, retry_seconds


def _generation_id(body: dict[str, Any], header_value: str | None) -> str | None:
    body_id = body.get("id") if isinstance(body, dict) else None
    if isinstance(body_id, str) and body_id:
        return body_id
    return header_value


def _message_text(message: Any) -> str | None:
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    # OpenAI-compatible array content: concatenate text parts only.
    if isinstance(content, list):
        parts = [
            part.get("text")
            for part in content
            if isinstance(part, dict)
            and part.get("type") in ("text", "output_text")
            and isinstance(part.get("text"), str)
        ]
        if parts:
            return "".join(parts)
    return None


def _visible_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    choices = body.get("choices")
    if not isinstance(choices, list):
        return []
    items: list[dict[str, Any]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        index = choice.get("index")
        message = choice.get("message")
        text = _message_text(message)
        if text is not None:
            items.append(
                {
                    "type": "output_text",
                    "choice_index": index if isinstance(index, int) else 0,
                    "text": text,
                }
            )
        if isinstance(message, dict):
            refusal = message.get("refusal")
            if isinstance(refusal, str) and refusal:
                items.append(
                    {
                        "type": "refusal",
                        "choice_index": index if isinstance(index, int) else 0,
                        "text": refusal,
                    }
                )
    return items


def _provider_finish(
    body: dict[str, Any],
    finish_reason: Any = None,
    native_finish: Any = None,
) -> str:
    if finish_reason is None:
        choices = body.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            native_finish = choices[0].get("native_finish_reason")
    normalized = finish_reason if isinstance(finish_reason, str) else "none"
    native = native_finish if isinstance(native_finish, str) else "none"
    return f"chat:{normalized}|native:{native}"


def _map_usage(body: dict[str, Any]) -> TokenUsage:
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return TokenUsage(limitations=(LIMITATION_NO_USAGE,))
    limitations: set[str] = set()

    def field_value(container: Any, name: str, dotted: str) -> int | None:
        value = container.get(name) if isinstance(container, dict) else None
        if value is None:
            limitations.add(f"openrouter usage did not include {dotted}")
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            limitations.add(f"openrouter usage {dotted} was not an integer")
            return None
        return value

    prompt_details = usage.get("prompt_tokens_details")
    completion_details = usage.get("completion_tokens_details")
    input_tokens = field_value(usage, "prompt_tokens", "prompt_tokens")
    output_tokens = field_value(usage, "completion_tokens", "completion_tokens")
    cache_read = field_value(
        prompt_details, "cached_tokens", "prompt_tokens_details.cached_tokens"
    )
    cache_write = field_value(
        prompt_details, "cache_write_tokens", "prompt_tokens_details.cache_write_tokens"
    )
    reasoning = field_value(
        completion_details, "reasoning_tokens",
        "completion_tokens_details.reasoning_tokens",
    )
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        reasoning_tokens=reasoning,
        limitations=tuple(sorted(limitations)),
    )
