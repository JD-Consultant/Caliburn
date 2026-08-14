"""Versioned consultant model policy, LangChain harness, and attempt receipts."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal, TypeVar
from uuid import UUID

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ContextEditingMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from langchain.agents.middleware.context_editing import ClearToolUsesEdit
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_json_schema
from opentelemetry.trace import Span
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from app.observability import get_tracer


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutputTokenParameter(StrEnum):
    MAX_TOKENS = "max_tokens"
    MAX_COMPLETION_TOKENS = "max_completion_tokens"


class ReasoningParameters(RuntimeModel):
    effort: Literal["low", "medium", "high", "max"]
    exclude: bool = True


class EffectiveModelParameters(RuntimeModel):
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    seed: int | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)
    reasoning: ReasoningParameters | None = None

    @model_validator(mode="after")
    def exactly_one_output_cap(self) -> EffectiveModelParameters:
        if (self.max_tokens is None) == (self.max_completion_tokens is None):
            raise ValueError("exactly one output token parameter is required")
        return self


class ConsultantModelProfile(RuntimeModel):
    schema_version: Literal[1] = 1
    profile_id: NonEmptyText
    revision: int = Field(ge=1)
    requested_model: NonEmptyText
    provider_allowlist: tuple[NonEmptyText, ...]
    allow_fallbacks: Literal[False] = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    seed: int | None = None
    max_output_tokens: int = Field(default=4096, ge=256)
    output_token_parameter: OutputTokenParameter = OutputTokenParameter.MAX_TOKENS
    reasoning_effort: Literal["low", "medium", "high", "max"] | None = None
    exclude_reasoning_from_response: bool = True
    timeout_seconds: float = Field(default=90, gt=0, le=600)

    @model_validator(mode="after")
    def pinned_route_is_unambiguous(self) -> ConsultantModelProfile:
        author, separator, slug = self.requested_model.partition("/")
        if (
            not separator
            or not author
            or not slug
            or ":" in self.requested_model
            or self.requested_model.startswith("~")
            or self.requested_model.casefold() == "openrouter/auto"
        ):
            raise ValueError("requested_model must be an exact model slug")
        if len(self.provider_allowlist) != 1:
            raise ValueError("first release requires exactly one provider")
        return self


class RunPolicy(RuntimeModel):
    schema_version: Literal[1] = 1
    policy_id: NonEmptyText
    revision: int = Field(ge=1)
    run_kind: NonEmptyText
    allowed_skill_ids: tuple[NonEmptyText, ...] = ()
    allowed_tool_ids: tuple[NonEmptyText, ...] = ()
    max_context_tokens: int = Field(ge=512)
    max_model_calls: int = Field(ge=1, le=10)
    max_lookup_waves: int = Field(ge=0, le=10)
    max_total_tool_calls: int = Field(ge=0, le=100)
    model_retry_count: int = Field(ge=0, le=3)
    tool_retry_count: int = Field(ge=0, le=3)
    max_elapsed_seconds: float = Field(gt=0, le=1800)
    max_total_tokens: int = Field(ge=512)
    max_cost_usd: Decimal | None = Field(default=None, ge=0)
    summary_trigger_tokens: int = Field(default=16_000, ge=512)
    summary_keep_messages: int = Field(default=8, ge=1)
    tool_result_clear_trigger_tokens: int = Field(default=12_000, ge=512)
    tool_result_keep: int = Field(default=3, ge=0)
    max_orientation_items: int = Field(default=80, ge=1)

    @model_validator(mode="after")
    def identifiers_and_budgets_are_consistent(self) -> RunPolicy:
        for label, values in (
            ("allowed_skill_ids", self.allowed_skill_ids),
            ("allowed_tool_ids", self.allowed_tool_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        if self.max_context_tokens > self.max_total_tokens:
            raise ValueError("context budget cannot exceed total token budget")
        return self


class ResolvedExecution(RuntimeModel):
    schema_version: Literal[1] = 1
    profile_id: NonEmptyText
    profile_revision: int = Field(ge=1)
    policy_id: NonEmptyText
    policy_revision: int = Field(ge=1)
    run_kind: NonEmptyText
    requested_model: NonEmptyText
    provider_allowlist: tuple[NonEmptyText, ...]
    allow_fallbacks: Literal[False]
    effective_parameters: EffectiveModelParameters
    timeout_seconds: float = Field(gt=0)
    allowed_skill_ids: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]
    max_context_tokens: int
    max_model_calls: int
    max_lookup_waves: int
    max_total_tool_calls: int
    model_retry_count: int
    tool_retry_count: int
    max_elapsed_seconds: float
    max_total_tokens: int
    max_cost_usd: Decimal | None
    summary_trigger_tokens: int
    summary_keep_messages: int
    tool_result_clear_trigger_tokens: int
    tool_result_keep: int
    max_orientation_items: int
    adapter_version: Literal["langchain-openrouter/0.2.7"] = (
        "langchain-openrouter/0.2.7"
    )
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def resolve_execution(
    profile: ConsultantModelProfile,
    policy: RunPolicy,
) -> ResolvedExecution:
    parameter_name = profile.output_token_parameter.value
    parameter_values: dict[str, Any] = {
        "temperature": profile.temperature,
        "top_p": profile.top_p,
        "frequency_penalty": profile.frequency_penalty,
        "presence_penalty": profile.presence_penalty,
        "seed": profile.seed,
        "max_tokens": None,
        "max_completion_tokens": None,
        "reasoning": (
            ReasoningParameters(
                effort=profile.reasoning_effort,
                exclude=profile.exclude_reasoning_from_response,
            )
            if profile.reasoning_effort is not None
            else None
        ),
    }
    parameter_values[parameter_name] = profile.max_output_tokens
    effective = EffectiveModelParameters.model_validate(parameter_values)
    if profile.max_output_tokens > policy.max_total_tokens:
        raise ValueError("output token cap cannot exceed total run token budget")
    return ResolvedExecution(
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        run_kind=policy.run_kind,
        requested_model=profile.requested_model,
        provider_allowlist=profile.provider_allowlist,
        allow_fallbacks=profile.allow_fallbacks,
        effective_parameters=effective,
        timeout_seconds=profile.timeout_seconds,
        allowed_skill_ids=policy.allowed_skill_ids,
        allowed_tool_ids=policy.allowed_tool_ids,
        max_context_tokens=policy.max_context_tokens,
        max_model_calls=policy.max_model_calls,
        max_lookup_waves=policy.max_lookup_waves,
        max_total_tool_calls=policy.max_total_tool_calls,
        model_retry_count=policy.model_retry_count,
        tool_retry_count=policy.tool_retry_count,
        max_elapsed_seconds=policy.max_elapsed_seconds,
        max_total_tokens=policy.max_total_tokens,
        max_cost_usd=policy.max_cost_usd,
        summary_trigger_tokens=policy.summary_trigger_tokens,
        summary_keep_messages=policy.summary_keep_messages,
        tool_result_clear_trigger_tokens=policy.tool_result_clear_trigger_tokens,
        tool_result_keep=policy.tool_result_keep,
        max_orientation_items=policy.max_orientation_items,
    )


class AttemptKind(StrEnum):
    PRIMARY = "primary"
    SUMMARIZATION = "summarization"


class AttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AttemptUsage(RuntimeModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cache_read_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)


class AttemptReceipt(RuntimeModel):
    schema_version: Literal[1] = 1
    attempt_id: UUID
    product_run_id: UUID
    status: AttemptStatus
    attempt_kind: AttemptKind = AttemptKind.PRIMARY
    requested_model: NonEmptyText
    provider_allowlist: tuple[NonEmptyText, ...]
    actual_model: str | None = None
    actual_provider: str | None = None
    profile_id: NonEmptyText
    profile_revision: int = Field(ge=1)
    policy_id: NonEmptyText
    policy_revision: int = Field(ge=1)
    effective_parameters: EffectiveModelParameters
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0)
    usage: AttemptUsage = Field(default_factory=AttemptUsage)
    cost_usd: Decimal | None = Field(default=None, ge=0)
    finish_reason: str | None = None
    route: dict[str, str] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not result.is_finite() or result < 0:
        return None
    return result


def _integer_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _message_from_result(response: LLMResult) -> AIMessage | None:
    if not response.generations or not response.generations[0]:
        return None
    message = getattr(response.generations[0][0], "message", None)
    return message if isinstance(message, AIMessage) else None


def _usage_from_message(message: AIMessage | None) -> AttemptUsage:
    usage = message.usage_metadata if message is not None else None
    if not usage:
        return AttemptUsage()
    input_details = usage.get("input_token_details") or {}
    output_details = usage.get("output_token_details") or {}
    return AttemptUsage(
        input_tokens=_integer_or_none(usage.get("input_tokens")),
        output_tokens=_integer_or_none(usage.get("output_tokens")),
        total_tokens=_integer_or_none(usage.get("total_tokens")),
        reasoning_tokens=_integer_or_none(output_details.get("reasoning")),
        cache_read_tokens=_integer_or_none(input_details.get("cache_read")),
        cache_write_tokens=_integer_or_none(input_details.get("cache_creation")),
    )


def _safe_error_details(error: BaseException) -> tuple[str, str]:
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "timeout", "model request timed out"
    if isinstance(error, httpx.HTTPStatusError):
        return (
            "provider_http_error",
            f"model provider returned HTTP {error.response.status_code}",
        )
    if isinstance(error, (ConnectionError, httpx.TransportError)):
        return "transport_error", "model transport failed"
    return "model_error", f"model call failed ({type(error).__name__})"


def classify_consultant_failure(error: BaseException) -> str:
    """Return a payload-free durable failure code for product recovery."""

    return _safe_error_details(error)[0]


class _AttemptStart:
    def __init__(
        self,
        *,
        started_at: datetime,
        monotonic_ns: int,
        span: Span,
        attempt_kind: AttemptKind,
    ) -> None:
        self.started_at = started_at
        self.monotonic_ns = monotonic_ns
        self.span = span
        self.attempt_kind = attempt_kind


class AttemptReceiptCallback(AsyncCallbackHandler):
    """One local receipt and one payload-free OTel span per actual model call."""

    def __init__(self, *, product_run_id: UUID, execution: ResolvedExecution) -> None:
        self.product_run_id = product_run_id
        self.execution = execution
        self.receipts: list[AttemptReceipt] = []
        self._starts: dict[UUID, _AttemptStart] = {}
        self._tracer = get_tracer()

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del serialized, messages, parent_run_id, tags, kwargs
        attempt_kind = (
            AttemptKind.SUMMARIZATION
            if (metadata or {}).get("lc_source") == "summarization"
            else AttemptKind.PRIMARY
        )
        span = self._tracer.start_span("consultant.model.attempt")
        span.set_attribute("consultant.product_run_id", str(self.product_run_id))
        span.set_attribute("consultant.profile_id", self.execution.profile_id)
        span.set_attribute(
            "consultant.profile_revision", self.execution.profile_revision
        )
        span.set_attribute("gen_ai.request.model", self.execution.requested_model)
        span.set_attribute("consultant.attempt_kind", attempt_kind.value)
        self._starts[run_id] = _AttemptStart(
            started_at=datetime.now(UTC),
            monotonic_ns=time.perf_counter_ns(),
            span=span,
            attempt_kind=attempt_kind,
        )

    def _pop_start(self, run_id: UUID) -> _AttemptStart:
        start = self._starts.pop(run_id, None)
        if start is not None:
            return start
        return _AttemptStart(
            started_at=datetime.now(UTC),
            monotonic_ns=time.perf_counter_ns(),
            span=self._tracer.start_span("consultant.model.attempt"),
            attempt_kind=AttemptKind.PRIMARY,
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, tags, kwargs
        start = self._pop_start(run_id)
        completed_at = datetime.now(UTC)
        message = _message_from_result(response)
        metadata = message.response_metadata if message is not None else {}
        llm_output = response.llm_output or {}
        generation_info = (
            getattr(response.generations[0][0], "generation_info", None) or {}
            if response.generations and response.generations[0]
            else {}
        )
        actual_model = (
            llm_output.get("model_name")
            or metadata.get("model_name")
            or metadata.get("model")
        )
        actual_provider = metadata.get("provider") or metadata.get("provider_name")
        finish_reason = generation_info.get("finish_reason") or metadata.get(
            "finish_reason"
        )
        cost = _decimal_or_none(metadata.get("cost"))
        latency_ms = max(0, (time.perf_counter_ns() - start.monotonic_ns) // 1_000_000)
        route = {
            key: str(value)
            for key, value in {
                "provider": actual_provider,
                "model": actual_model,
            }.items()
            if value is not None
        }
        receipt = AttemptReceipt(
            attempt_id=run_id,
            product_run_id=self.product_run_id,
            status=AttemptStatus.SUCCEEDED,
            attempt_kind=start.attempt_kind,
            requested_model=self.execution.requested_model,
            provider_allowlist=self.execution.provider_allowlist,
            actual_model=(str(actual_model) if actual_model is not None else None),
            actual_provider=(
                str(actual_provider) if actual_provider is not None else None
            ),
            profile_id=self.execution.profile_id,
            profile_revision=self.execution.profile_revision,
            policy_id=self.execution.policy_id,
            policy_revision=self.execution.policy_revision,
            effective_parameters=self.execution.effective_parameters,
            started_at=start.started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            usage=_usage_from_message(message),
            cost_usd=cost,
            finish_reason=(
                str(finish_reason) if finish_reason is not None else None
            ),
            route=route,
        )
        self.receipts.append(receipt)
        if receipt.actual_model:
            start.span.set_attribute("gen_ai.response.model", receipt.actual_model)
        if receipt.actual_provider:
            start.span.set_attribute("gen_ai.provider.name", receipt.actual_provider)
        if receipt.usage.total_tokens is not None:
            start.span.set_attribute(
                "gen_ai.usage.total_tokens", receipt.usage.total_tokens
            )
        start.span.end()

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        del parent_run_id, tags, kwargs
        start = self._pop_start(run_id)
        completed_at = datetime.now(UTC)
        error_code, error_message = _safe_error_details(error)
        receipt = AttemptReceipt(
            attempt_id=run_id,
            product_run_id=self.product_run_id,
            status=AttemptStatus.FAILED,
            attempt_kind=start.attempt_kind,
            requested_model=self.execution.requested_model,
            provider_allowlist=self.execution.provider_allowlist,
            profile_id=self.execution.profile_id,
            profile_revision=self.execution.profile_revision,
            policy_id=self.execution.policy_id,
            policy_revision=self.execution.policy_revision,
            effective_parameters=self.execution.effective_parameters,
            started_at=start.started_at,
            completed_at=completed_at,
            latency_ms=max(
                0, (time.perf_counter_ns() - start.monotonic_ns) // 1_000_000
            ),
            error_code=error_code,
            error_message=error_message,
        )
        self.receipts.append(receipt)
        start.span.set_attribute("error.type", type(error).__name__)
        start.span.end()

    async def close_open_attempts(self, error: BaseException) -> None:
        """Finish callbacks cancelled by an outer run deadline."""

        for run_id in tuple(self._starts):
            await self.on_llm_error(error, run_id=run_id)


class ConsultantRunBudgetExceeded(RuntimeError):
    def __init__(self, exceeded: Sequence[str]) -> None:
        self.exceeded = tuple(exceeded)
        super().__init__("consultant run budget exceeded: " + ", ".join(exceeded))


def verify_attempt_budget(
    execution: ResolvedExecution,
    receipts: Sequence[AttemptReceipt],
) -> None:
    exceeded: list[str] = []
    max_attempts = execution.max_model_calls * (execution.model_retry_count + 1)
    if len(receipts) > max_attempts:
        exceeded.append("provider_attempts")
    total_tokens = sum(item.usage.total_tokens or 0 for item in receipts)
    if total_tokens > execution.max_total_tokens:
        exceeded.append("total_tokens")
    total_cost = sum((item.cost_usd or Decimal(0) for item in receipts), Decimal(0))
    if execution.max_cost_usd is not None and total_cost > execution.max_cost_usd:
        exceeded.append("cost_usd")
    if receipts:
        started = min(item.started_at for item in receipts)
        completed = max(item.completed_at for item in receipts)
        if (completed - started).total_seconds() > execution.max_elapsed_seconds:
            exceeded.append("elapsed_seconds")
    if any(
        item.actual_provider is not None
        and item.actual_provider.casefold()
        not in {provider.casefold() for provider in execution.provider_allowlist}
        for item in receipts
    ):
        exceeded.append("provider_route")
    if exceeded:
        raise ConsultantRunBudgetExceeded(exceeded)


def _retryable_error(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError, httpx.TransportError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return False


class PolicyBoundSummarizationMiddleware(SummarizationMiddleware):
    """LangChain summarization without its independent hidden retry chain."""

    def __init__(self, model: BaseChatModel, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        # LangChain 1.3.15 otherwise installs model.with_retry() with three attempts.
        # The consultant run owns one explicit attempt budget and receipt chain.
        self._summary_model = model


def build_consultant_middleware(
    *,
    model: BaseChatModel,
    execution: ResolvedExecution,
    context_middleware: AgentMiddleware | None = None,
    additional_middleware: Sequence[AgentMiddleware] = (),
) -> tuple[AgentMiddleware, ...]:
    middleware: list[AgentMiddleware] = [
        ModelCallLimitMiddleware(
            run_limit=execution.max_model_calls,
            exit_behavior="error",
        ),
        ToolCallLimitMiddleware(
            run_limit=execution.max_total_tool_calls,
            exit_behavior="error",
        ),
        ModelRetryMiddleware(
            max_retries=execution.model_retry_count,
            retry_on=_retryable_error,
            on_failure="error",
            initial_delay=0,
            backoff_factor=1,
            jitter=False,
        ),
        ToolRetryMiddleware(
            max_retries=execution.tool_retry_count,
            retry_on=_retryable_error,
            on_failure="error",
            initial_delay=0,
            backoff_factor=1,
            jitter=False,
        ),
        PolicyBoundSummarizationMiddleware(
            model,
            trigger=("tokens", execution.summary_trigger_tokens),
            keep=("messages", execution.summary_keep_messages),
            summary_prompt=(
                "Summarize only the non-authoritative conversational continuity. "
                "Never treat this summary as employee evidence, an approved document, "
                "or the current source of truth. Return concise context only.\n\n"
                "<messages>{messages}</messages>"
            ),
        ),
        ContextEditingMiddleware(
            edits=(
                ClearToolUsesEdit(
                    trigger=execution.tool_result_clear_trigger_tokens,
                    keep=execution.tool_result_keep,
                    placeholder="[older read-only tool result cleared]",
                ),
            )
        ),
    ]
    if context_middleware is not None:
        middleware.append(context_middleware)
    middleware.extend(additional_middleware)
    return tuple(middleware)


def build_consultant_agent(
    *,
    model: BaseChatModel,
    execution: ResolvedExecution,
    response_schema: type[ResponseModelT],
    tools: Sequence[BaseTool | Any] = (),
    context_middleware: AgentMiddleware | None = None,
    additional_middleware: Sequence[AgentMiddleware] = (),
    context_schema: type[Any] | None = None,
    checkpointer: Any = None,
    store: Any = None,
) -> Any:
    tool_ids: list[str] = []
    for candidate in tools:
        if isinstance(candidate, BaseTool):
            tool_ids.append(candidate.name)
        elif isinstance(candidate, dict):
            name = candidate.get("name")
            if name is None and isinstance(candidate.get("function"), dict):
                name = candidate["function"].get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("consultant tool schema requires a stable name")
            tool_ids.append(name)
        else:
            name = getattr(candidate, "__name__", None)
            if not isinstance(name, str) or not name.strip():
                raise ValueError("consultant tool callable requires a stable name")
            tool_ids.append(name)
    ineligible_tools = set(tool_ids) - set(execution.allowed_tool_ids)
    if ineligible_tools:
        raise ValueError(f"agent requested ineligible tools: {sorted(ineligible_tools)}")
    response_format = ProviderStrategy(response_schema, strict=True)
    # LangChain's ProviderStrategy currently keeps Pydantic's raw $defs/$ref
    # graph, while the OpenRouter integration's supported structured-output
    # path normalizes it first.  Keep the Pydantic type for response parsing,
    # but send the same provider-safe schema used by with_structured_output().
    response_format.schema_spec.json_schema = convert_to_json_schema(response_schema)
    return create_agent(
        model=model,
        tools=tools,
        response_format=response_format,
        middleware=build_consultant_middleware(
            model=model,
            execution=execution,
            context_middleware=context_middleware,
            additional_middleware=additional_middleware,
        ),
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        name="caliburn_consultant",
    )
