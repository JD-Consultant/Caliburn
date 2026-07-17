"""OpenAI Responses eval-only adapter (V3-4).

Maps the official ``AsyncOpenAI.responses.create()`` call onto the neutral
``LlmPort`` contract. One durable attempt performs exactly one HTTP call: SDK
retries are disabled and every failure returns as a typed ``ModelCallEnvelope``;
only cooperative cancellation (``asyncio.CancelledError``) propagates.

Neutral ``finish_reason`` policy for FAILED results: ``provider_error``
uniformly, except context-window 400s (``context_window_exceeded``), provider
cancellations (``cancelled``) and unexpected non-terminal statuses
(``unknown``). The lossless provider view lives in ``provider_finish_reason``
and the raw artifact.

規格:docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid5

import httpx
import openai
from openai import AsyncOpenAI
from openai.types.responses import (
    Response,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseReasoningItem,
)

from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.llm.port import (
    LlmPort,
    MessageRole,
    ModelCallEnvelope,
    ModelCallRequest,
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
    RedactionStatus,
    build_inline_artifact,
)

from ..provider_config import OpenAIResponsesEvalConfig
from ..schema_catalog import (
    PublishedOutputSchemaCatalog,
    SchemaBinding,
    SchemaCatalogError,
)


OPENAI_BASE_URL = "https://api.openai.com/v1"
SDK_NAME = "openai-python"

RAW_ARTIFACT_LABEL = "artifact/openai-responses/raw/v1"
VISIBLE_ARTIFACT_LABEL = "artifact/openai-responses/visible/v1"
ERROR_ARTIFACT_LABEL = "artifact/openai-responses/error/v1"

RAW_ARTIFACT_KIND = "provider.openai.response.raw"
VISIBLE_ARTIFACT_KIND = "provider.response.visible"
ERROR_ARTIFACT_KIND = "provider.openai.error"

VISIBLE_SCHEMA_VERSION = "provider_visible_response.v1"

LIMITATION_NO_RESPONSE = "openai response was not received"
LIMITATION_NO_USAGE = "openai response did not include usage"

REFUSAL_SAFE_MESSAGE = "The model declined this request."

SAFE_MESSAGES: dict[str, str] = {
    "binding": "The model request does not match the approved eval configuration.",
    "timeout": "OpenAI did not complete the request before the attempt deadline.",
    "connection": "The adapter could not connect to OpenAI.",
    "authentication": "OpenAI rejected the configured credentials.",
    "permission": "The configured OpenAI credentials do not permit this request.",
    "invalid_request": "OpenAI rejected the model request.",
    "rate_limited": "OpenAI rate limiting prevented this request.",
    "quota": "OpenAI quota is unavailable for this request.",
    "unavailable": "OpenAI was temporarily unavailable.",
    "cancelled": "OpenAI cancelled the response.",
    "bad_output": "OpenAI returned an unusable structured response.",
    "model_mismatch": "OpenAI resolved an unapproved model.",
    "unexpected": "The adapter could not normalize the OpenAI response.",
}


@dataclass(frozen=True)
class _Failure:
    kind: FailureKind
    reason_code: str
    retryable: bool
    safe_message: str
    finish_reason: FinishReason = FinishReason.PROVIDER_ERROR
    provider_error_code: str | None = None


class _LocalBindingError(Exception):
    """Config/schema/request mismatch detected before any network I/O."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _classify_exception(exc: Exception) -> _Failure:
    code = getattr(exc, "code", None)
    if isinstance(exc, (TimeoutError, openai.APITimeoutError)):
        return _Failure(
            FailureKind.TRANSPORT_TIMEOUT, "openai.timeout", True,
            SAFE_MESSAGES["timeout"], provider_error_code=code,
        )
    if isinstance(exc, openai.APIConnectionError):
        return _Failure(
            FailureKind.TRANSPORT_ERROR, "openai.connection_error", True,
            SAFE_MESSAGES["connection"], provider_error_code=code,
        )
    if isinstance(exc, openai.AuthenticationError):
        return _Failure(
            FailureKind.AUTHENTICATION_FAILED, "openai.authentication_failed", False,
            SAFE_MESSAGES["authentication"], provider_error_code=code,
        )
    if isinstance(exc, openai.PermissionDeniedError):
        return _Failure(
            FailureKind.AUTHENTICATION_FAILED, "openai.permission_denied", False,
            SAFE_MESSAGES["permission"], provider_error_code=code,
        )
    if isinstance(exc, openai.BadRequestError):
        if code == "context_length_exceeded":
            return _Failure(
                FailureKind.INVALID_REQUEST, "openai.context_window_exceeded", False,
                SAFE_MESSAGES["invalid_request"],
                finish_reason=FinishReason.CONTEXT_WINDOW_EXCEEDED,
                provider_error_code=code,
            )
        return _Failure(
            FailureKind.INVALID_REQUEST, "openai.invalid_request", False,
            SAFE_MESSAGES["invalid_request"], provider_error_code=code,
        )
    if isinstance(exc, openai.NotFoundError):
        return _Failure(
            FailureKind.INVALID_REQUEST, "openai.not_found", False,
            SAFE_MESSAGES["invalid_request"], provider_error_code=code,
        )
    if isinstance(exc, openai.UnprocessableEntityError):
        return _Failure(
            FailureKind.INVALID_REQUEST, "openai.unprocessable_entity", False,
            SAFE_MESSAGES["invalid_request"], provider_error_code=code,
        )
    if isinstance(exc, openai.ConflictError):
        return _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openai.conflict", True,
            SAFE_MESSAGES["unavailable"], provider_error_code=code,
        )
    if isinstance(exc, openai.RateLimitError):
        if code == "insufficient_quota":
            return _Failure(
                FailureKind.RATE_LIMITED, "openai.quota_exhausted", False,
                SAFE_MESSAGES["quota"], provider_error_code=code,
            )
        return _Failure(
            FailureKind.RATE_LIMITED, "openai.rate_limited", True,
            SAFE_MESSAGES["rate_limited"], provider_error_code=code,
        )
    if isinstance(exc, openai.APIStatusError):
        status_code = exc.status_code
        if status_code == 408:
            return _Failure(
                FailureKind.TRANSPORT_TIMEOUT, "openai.timeout", True,
                SAFE_MESSAGES["timeout"], provider_error_code=code,
            )
        if status_code >= 500:
            return _Failure(
                FailureKind.PROVIDER_UNAVAILABLE, "openai.server_error", True,
                SAFE_MESSAGES["unavailable"], provider_error_code=code,
            )
        return _Failure(
            FailureKind.UNKNOWN_PROVIDER_FAILURE, "openai.api_status_error", False,
            SAFE_MESSAGES["unexpected"], provider_error_code=code,
        )
    return _Failure(
        FailureKind.UNKNOWN_PROVIDER_FAILURE, "openai.adapter_unexpected_error", False,
        SAFE_MESSAGES["unexpected"],
    )


def _classify_failed_response(error_code: str | None) -> _Failure:
    if error_code == "server_error":
        return _Failure(
            FailureKind.PROVIDER_UNAVAILABLE, "openai.response_server_error", True,
            SAFE_MESSAGES["unavailable"], provider_error_code=error_code,
        )
    if error_code == "rate_limit_exceeded":
        return _Failure(
            FailureKind.RATE_LIMITED, "openai.response_rate_limited", True,
            SAFE_MESSAGES["rate_limited"], provider_error_code=error_code,
        )
    if error_code:
        return _Failure(
            FailureKind.INVALID_REQUEST, "openai.response_invalid", False,
            SAFE_MESSAGES["invalid_request"], provider_error_code=error_code,
        )
    return _Failure(
        FailureKind.UNKNOWN_PROVIDER_FAILURE, "openai.response_failed_unknown", False,
        SAFE_MESSAGES["unexpected"],
    )


def _supporting_artifact(
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
    request: ModelCallRequest,
    response: Response,
    *,
    request_id: str | None,
    created_at: datetime,
) -> ArtifactRecord:
    payload = {
        "http_request_id": request_id,
        "sdk": SDK_NAME,
        "sdk_version": openai.__version__,
        "response": response.model_dump(mode="json", exclude_none=False),
    }
    return _supporting_artifact(
        request,
        label=RAW_ARTIFACT_LABEL,
        kind=RAW_ARTIFACT_KIND,
        payload=payload,
        created_at=created_at,
    )


def _visible_artifact(
    request: ModelCallRequest,
    items: tuple[dict[str, Any], ...],
    *,
    created_at: datetime,
) -> ArtifactRecord:
    payload = {"schema_version": VISIBLE_SCHEMA_VERSION, "items": list(items)}
    return _supporting_artifact(
        request,
        label=VISIBLE_ARTIFACT_LABEL,
        kind=VISIBLE_ARTIFACT_KIND,
        payload=payload,
        created_at=created_at,
    )


def _error_artifact(
    request: ModelCallRequest,
    *,
    failure: _Failure,
    created_at: datetime,
    detail: str | None = None,
    exception: Exception | None = None,
    status_code: int | None = None,
    request_id: str | None = None,
    body: Any = None,
) -> ArtifactRecord:
    payload = {
        "classification": {
            "failure_kind": failure.kind.value,
            "reason_code": failure.reason_code,
            "retryable": failure.retryable,
            "provider_error_code": failure.provider_error_code,
        },
        "detail": detail,
        "exception_type": type(exception).__name__ if exception is not None else None,
        "status_code": status_code,
        "request_id": request_id,
        "code": _json_safe(getattr(exception, "code", None)),
        "param": _json_safe(getattr(exception, "param", None)),
        "type": _json_safe(getattr(exception, "type", None)),
        "body": _json_safe(body),
    }
    return _supporting_artifact(
        request,
        label=ERROR_ARTIFACT_LABEL,
        kind=ERROR_ARTIFACT_KIND,
        payload=payload,
        created_at=created_at,
    )


def _usage_without_response() -> TokenUsage:
    return TokenUsage(limitations=(LIMITATION_NO_RESPONSE,))


def _map_usage(response: Response) -> TokenUsage:
    usage = response.usage
    if usage is None:
        return TokenUsage(limitations=(LIMITATION_NO_USAGE,))
    limitations: set[str] = set()

    def field(container: Any, name: str, dotted: str) -> int | None:
        value = getattr(container, name, None) if container is not None else None
        if value is None:
            limitations.add(f"openai usage did not include {dotted}")
        return value

    input_tokens = field(usage, "input_tokens", "input_tokens")
    output_tokens = field(usage, "output_tokens", "output_tokens")
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    cache_read = field(input_details, "cached_tokens", "input_tokens_details.cached_tokens")
    cache_write = field(
        input_details, "cache_write_tokens", "input_tokens_details.cache_write_tokens"
    )
    reasoning = field(
        output_details, "reasoning_tokens", "output_tokens_details.reasoning_tokens"
    )
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        reasoning_tokens=reasoning,
        limitations=tuple(sorted(limitations)),
    )


class OpenAIResponsesEvalAdapter(LlmPort):
    """Eval-only `LlmPort` implementation over the official OpenAI SDK 2.46.0."""

    def __init__(
        self,
        *,
        api_key: str,
        config: OpenAIResponsesEvalConfig | None = None,
        catalog: PublishedOutputSchemaCatalog | None = None,
        http_client: httpx.AsyncClient | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._config = config or OpenAIResponsesEvalConfig()
        self._catalog = catalog or PublishedOutputSchemaCatalog()
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._owns_http_client = http_client is None
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=OPENAI_BASE_URL,
            max_retries=self._config.sdk_max_retries,
            timeout=httpx.Timeout(60.0, connect=self._config.connect_timeout_seconds),
            http_client=http_client,
        )

    async def __aenter__(self) -> "OpenAIResponsesEvalAdapter":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._client.close()

    async def generate_structured(self, request: ModelCallRequest) -> ModelCallEnvelope:
        started_at = self._now()
        started_mono = self._monotonic()
        try:
            binding = self._validate_binding(request)
        except _LocalBindingError as exc:
            failure = _Failure(
                FailureKind.INVALID_REQUEST,
                "openai.request_binding_invalid",
                False,
                SAFE_MESSAGES["binding"],
            )
            return self._failure_envelope(
                request, failure,
                started_at=started_at, started_mono=started_mono,
                detail=exc.detail,
            )

        remaining_seconds = (request.deadline_at - started_at).total_seconds()
        if remaining_seconds <= 0:
            failure = _Failure(
                FailureKind.TRANSPORT_TIMEOUT, "openai.timeout", True,
                SAFE_MESSAGES["timeout"],
            )
            return self._failure_envelope(
                request, failure,
                started_at=started_at, started_mono=started_mono,
                detail="attempt deadline expired before the provider call",
            )

        connect_timeout = min(self._config.connect_timeout_seconds, remaining_seconds)
        http_timeout = httpx.Timeout(remaining_seconds, connect=connect_timeout)
        try:
            async with asyncio.timeout(remaining_seconds):
                response = await self._client.responses.create(
                    model=request.requested_model,
                    instructions=request.instructions,
                    input=[
                        {"role": item.role.value, "content": item.text}
                        for item in request.messages
                    ],
                    max_output_tokens=request.max_output_tokens,
                    reasoning={
                        "mode": self._config.reasoning_mode,
                        "effort": self._config.reasoning_effort,
                    },
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": binding.format_name,
                            "strict": True,
                            "schema": binding.schema,
                        }
                    },
                    service_tier=self._config.service_tier,
                    store=self._config.store,
                    background=self._config.background,
                    stream=self._config.stream,
                    truncation=self._config.truncation,
                    timeout=http_timeout,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — closed typed table in _classify_exception
            failure = _classify_exception(exc)
            return self._failure_envelope(
                request, failure,
                started_at=started_at, started_mono=started_mono,
                exception=exc,
                status_code=getattr(exc, "status_code", None),
                request_id=getattr(exc, "request_id", None),
                body=getattr(exc, "body", None),
                detail="provider call raised before a Response was received",
            )
        return self._normalize_response(
            request, response, started_at=started_at, started_mono=started_mono
        )

    # ---- pre-HTTP validation -------------------------------------------------

    def _validate_binding(self, request: ModelCallRequest) -> SchemaBinding:
        if request.provider != self._config.provider:
            raise _LocalBindingError(
                f"request provider {request.provider!r} is not approved for this adapter"
            )
        if request.requested_model != self._config.requested_model:
            raise _LocalBindingError(
                "request model does not match the approved eval config: "
                f"{request.requested_model!r} != {self._config.requested_model!r}"
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
        return binding

    # ---- envelope assembly ---------------------------------------------------

    def _timing(
        self, *, started_at: datetime, started_mono: float
    ) -> tuple[datetime, int]:
        completed_at = self._now()
        if completed_at < started_at:
            completed_at = started_at
        latency_ms = max(0, math.floor((self._monotonic() - started_mono) * 1000.0))
        return completed_at, latency_ms

    def _failure_envelope(
        self,
        request: ModelCallRequest,
        failure: _Failure,
        *,
        started_at: datetime,
        started_mono: float,
        detail: str | None = None,
        exception: Exception | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        body: Any = None,
    ) -> ModelCallEnvelope:
        completed_at, latency_ms = self._timing(
            started_at=started_at, started_mono=started_mono
        )
        error = _error_artifact(
            request,
            failure=failure,
            created_at=completed_at,
            detail=detail,
            exception=exception,
            status_code=status_code,
            request_id=request_id,
            body=body,
        )
        result = ModelCallResult(
            **_identity_fields(request),
            resolved_model=request.requested_model,
            provider_request_id=request_id,
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
            usage=_usage_without_response(),
            latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
        return ModelCallEnvelope(result=result, supporting_artifacts=(error,))

    # ---- response normalization (§9/§10) ------------------------------------

    def _normalize_response(
        self,
        request: ModelCallRequest,
        response: Response,
        *,
        started_at: datetime,
        started_mono: float,
    ) -> ModelCallEnvelope:
        completed_at, latency_ms = self._timing(
            started_at=started_at, started_mono=started_mono
        )
        request_id = getattr(response, "_request_id", None)
        raw = _raw_artifact(
            request, response, request_id=request_id, created_at=completed_at
        )
        traversal = _traverse_output(response)
        visible = _visible_artifact(
            request, traversal.visible_items, created_at=completed_at
        )
        usage = _map_usage(response)
        resolved_raw = response.model
        resolved_model = resolved_raw or request.requested_model
        base = dict(
            **_identity_fields(request),
            resolved_model=resolved_model,
            provider_request_id=request_id,
            provider_conversation_id=None,
            usage=usage,
            latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
        artifacts = (raw, visible)

        def failed(
            failure: _Failure,
            *,
            provider_finish_reason: str,
            detail: str,
        ) -> ModelCallEnvelope:
            error = _error_artifact(
                request,
                failure=failure,
                created_at=completed_at,
                detail=detail,
                status_code=None,
                request_id=request_id,
                body=response.error.model_dump(mode="json")
                if response.error is not None
                else None,
            )
            result = ModelCallResult(
                **base,
                outcome=ModelOutcome.FAILED,
                finish_reason=failure.finish_reason,
                provider_finish_reason=provider_finish_reason,
                parsed_output=None,
                visible_response_artifact=visible.ref,
                refusal=None,
                failure=ModelFailure(
                    kind=failure.kind,
                    reason_code=failure.reason_code,
                    retryable=failure.retryable,
                    safe_message=failure.safe_message,
                    provider_error_code=failure.provider_error_code,
                    error_artifact=error.ref,
                ),
            )
            return ModelCallEnvelope(
                result=result, supporting_artifacts=(*artifacts, error)
            )

        status = response.status
        provider_status = status if status is not None else "none"

        if resolved_raw is None or resolved_raw not in self._config.accepted_resolved_models:
            return failed(
                _Failure(
                    FailureKind.RESOLVED_MODEL_MISMATCH,
                    "openai.resolved_model_mismatch",
                    False,
                    SAFE_MESSAGES["model_mismatch"],
                ),
                provider_finish_reason=_provider_finish_reason(response),
                detail=f"resolved model {resolved_raw!r} is not in the eval allowlist",
            )

        if status == "incomplete":
            reason = (
                response.incomplete_details.reason
                if response.incomplete_details is not None
                else None
            )
            finish = (
                FinishReason.MAX_OUTPUT_TOKENS
                if reason == "max_output_tokens"
                else FinishReason.UNKNOWN
            )
            result = ModelCallResult(
                **base,
                outcome=ModelOutcome.INCOMPLETE,
                finish_reason=finish,
                provider_finish_reason=f"incomplete:{reason or 'unknown'}",
                parsed_output=None,
                visible_response_artifact=visible.ref,
                refusal=None,
                failure=None,
            )
            return ModelCallEnvelope(result=result, supporting_artifacts=artifacts)

        if status == "failed":
            error_code = response.error.code if response.error is not None else None
            return failed(
                _classify_failed_response(error_code),
                provider_finish_reason=f"failed:{error_code or 'unknown'}",
                detail="provider reported a failed response",
            )

        if status == "cancelled":
            return failed(
                _Failure(
                    FailureKind.CANCELLED, "openai.cancelled", False,
                    SAFE_MESSAGES["cancelled"],
                    finish_reason=FinishReason.CANCELLED,
                ),
                provider_finish_reason="cancelled",
                detail="provider cancelled the response",
            )

        if status != "completed":
            return failed(
                _Failure(
                    FailureKind.UNKNOWN_PROVIDER_FAILURE,
                    "openai.unexpected_nonterminal_status",
                    False,
                    SAFE_MESSAGES["unexpected"],
                    finish_reason=FinishReason.UNKNOWN,
                ),
                provider_finish_reason=f"unexpected:{provider_status}",
                detail=f"synchronous call returned non-terminal status {provider_status!r}",
            )

        # status == "completed": §9.4 cardinality, then §9.5 JSON parse.
        def bad_output(reason_code: str, detail: str) -> ModelCallEnvelope:
            return failed(
                _Failure(
                    FailureKind.OUTPUT_PARSE_FAILED, reason_code, False,
                    SAFE_MESSAGES["bad_output"],
                ),
                provider_finish_reason="completed",
                detail=detail,
            )

        if traversal.protocol_violations:
            return bad_output(
                "openai.unexpected_output_item",
                "; ".join(traversal.protocol_violations),
            )
        refusal_count = len(traversal.refusal_texts)
        text_count = len(traversal.final_texts)
        if refusal_count and text_count:
            return failed(
                _Failure(
                    FailureKind.OUTPUT_PARSE_FAILED,
                    "openai.ambiguous_refusal_and_output",
                    False,
                    SAFE_MESSAGES["bad_output"],
                ),
                provider_finish_reason="completed",
                detail="completed response mixed refusal and output text",
            )
        if refusal_count:
            result = ModelCallResult(
                **base,
                outcome=ModelOutcome.REFUSED,
                finish_reason=FinishReason.SAFETY_REFUSAL,
                provider_finish_reason="completed",
                parsed_output=None,
                visible_response_artifact=visible.ref,
                refusal=ModelRefusal(
                    reason_code="openai.refusal",
                    safe_message=REFUSAL_SAFE_MESSAGE,
                    provider_category="refusal",
                ),
                failure=None,
            )
            return ModelCallEnvelope(result=result, supporting_artifacts=artifacts)
        if text_count == 0:
            return bad_output(
                "openai.missing_structured_output",
                "completed response contained no output text",
            )
        if text_count > 1:
            return bad_output(
                "openai.multiple_structured_outputs",
                "completed response contained more than one output text",
            )

        text = traversal.final_texts[0]
        try:
            value = json.loads(text)
        except ValueError:
            return bad_output(
                "openai.output_parse_failed",
                "output text is not valid JSON",
            )
        if not isinstance(value, dict):
            return failed(
                _Failure(
                    FailureKind.OUTPUT_SCHEMA_INVALID,
                    "openai.output_schema_invalid",
                    False,
                    SAFE_MESSAGES["bad_output"],
                ),
                provider_finish_reason="completed",
                detail="output JSON root is not an object",
            )
        payload = build_structured_payload(
            schema_id=request.output_schema_id, value=value
        )
        result = ModelCallResult(
            **base,
            outcome=ModelOutcome.SUCCEEDED,
            finish_reason=FinishReason.COMPLETED,
            provider_finish_reason="completed",
            parsed_output=payload,
            visible_response_artifact=visible.ref,
            refusal=None,
            failure=None,
        )
        return ModelCallEnvelope(result=result, supporting_artifacts=artifacts)


def _identity_fields(request: ModelCallRequest) -> dict[str, Any]:
    return {
        "run_id": request.run_id,
        "session_id": request.session_id,
        "turn_id": request.turn_id,
        "operation_id": request.operation_id,
        "attempt_id": request.attempt_id,
        "attempt": request.attempt,
        "operation_name": request.operation_name,
        "operation_definition_hash": request.operation_definition_hash,
        "provider": request.provider,
        "requested_model": request.requested_model,
        "prompt_hash": request.prompt_hash,
        "output_schema_id": request.output_schema_id,
        "output_schema_hash": request.output_schema_hash,
        "context_hash": request.context_hash,
    }


def _provider_finish_reason(response: Response) -> str:
    status = response.status
    if status == "completed":
        return "completed"
    if status == "incomplete":
        reason = (
            response.incomplete_details.reason
            if response.incomplete_details is not None
            else None
        )
        return f"incomplete:{reason or 'unknown'}"
    if status == "failed":
        code = response.error.code if response.error is not None else None
        return f"failed:{code or 'unknown'}"
    if status == "cancelled":
        return "cancelled"
    return f"unexpected:{status if status is not None else 'none'}"


@dataclass(frozen=True)
class _Traversal:
    visible_items: tuple[dict[str, Any], ...]
    final_texts: tuple[str, ...]
    refusal_texts: tuple[str, ...]
    protocol_violations: tuple[str, ...]


def _traverse_output(response: Response) -> _Traversal:
    """§9.2 typed traversal preserving provider array order; never `output[0]`."""

    visible: list[dict[str, Any]] = []
    final_texts: list[str] = []
    refusal_texts: list[str] = []
    violations: list[str] = []
    for output_index, item in enumerate(response.output or ()):
        if isinstance(item, ResponseReasoningItem):
            continue
        if not isinstance(item, ResponseOutputMessage):
            item_type = getattr(item, "type", type(item).__name__)
            violations.append(f"unexpected output item {item_type!r} at {output_index}")
            continue
        phase = getattr(item, "phase", None)
        if phase not in (None, "final_answer"):
            violations.append(
                f"unexpected message phase {phase!r} at {output_index}"
            )
        if item.status not in (None, "completed"):
            violations.append(
                f"message status {item.status!r} at {output_index} on a terminal response"
            )
        is_final = phase in (None, "final_answer")
        for content_index, content in enumerate(item.content or ()):
            if isinstance(content, ResponseOutputText):
                visible.append(
                    _visible_item(item, output_index, content_index, "output_text", content.text)
                )
                if is_final and item.status in (None, "completed"):
                    final_texts.append(content.text)
            elif isinstance(content, ResponseOutputRefusal):
                visible.append(
                    _visible_item(item, output_index, content_index, "refusal", content.refusal)
                )
                refusal_texts.append(content.refusal)
            else:
                content_type = getattr(content, "type", type(content).__name__)
                violations.append(
                    f"unexpected content item {content_type!r} at "
                    f"{output_index}.{content_index}"
                )
    return _Traversal(
        visible_items=tuple(visible),
        final_texts=tuple(final_texts),
        refusal_texts=tuple(refusal_texts),
        protocol_violations=tuple(violations),
    )


def _visible_item(
    message: ResponseOutputMessage,
    output_index: int,
    content_index: int,
    item_type: str,
    text: str,
) -> dict[str, Any]:
    return {
        "output_index": output_index,
        "message_id": message.id,
        "message_status": message.status,
        "content_index": content_index,
        "type": item_type,
        "text": text,
    }
