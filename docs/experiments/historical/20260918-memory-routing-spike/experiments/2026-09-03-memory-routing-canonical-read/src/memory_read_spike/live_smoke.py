"""Frozen, bounded live smoke for the isolated Memory read path."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Sequence
from uuid import uuid4

import httpx
import openrouter
import psycopg
from dotenv import dotenv_values
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from openrouter.errors import OpenRouterError
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from memory_read_spike.canonical import append_canonical_round, latest_canonical_messages
from memory_read_spike.fixtures import load_canonical_rounds, semantic_memory_fixtures
from memory_read_spike.graph import (
    MemoryReadContext,
    MultipleToolCallsError,
    ToolBudgetExceededError,
    build_memory_read_graph,
    build_transient_input,
    rebuild_memory_guide,
)
from memory_read_spike.receipts import (
    LiveSmokeReceipt,
    LiveSmokeStatus,
    LiveUsage,
    ModelVisibleTurn,
)
from memory_read_spike.runtime import open_spike_runtime, seed_current_memories
from memory_read_spike.scope import TrustedReadScope
from memory_read_spike.settings import SpikeSettings
from memory_read_spike.tools import bind_memory_read_tools


LIVE_SYSTEM_PROMPT = (
    "你正在驗證長訪談的記憶讀取路徑。請只根據目前可見對話與工具結果回答。\n"
    "目前可見內容不足時，依工具各自說明的使用時機自行取得必要資料；需要核對員工精確原話"
    "或短答脈絡時才讀 canonical conversation。\n"
    "不得自行猜測 reference，不得呼叫其他工具。資料沒有說明時，直接寫「目前資料未說明，"
    "需要詢問員工」，不要補造答案。"
)

LIVE_USER_PROMPT = (
    "請一次回答：\n"
    "1. 餐飲預約網站 A 案的三個獨有細節是什麼？並核對員工描述「過敏備註」做法時使用的"
    "精確原句。\n"
    "2. A 案與健身會員網站 B 案如何區分？B 案目前採會員 API 還是 CSV？\n"
    "3. 退款例外由誰核准？"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1"


class MissingApiKeyError(RuntimeError):
    pass


class EmbeddingResponseError(RuntimeError):
    pass


class CostPreflightError(RuntimeError):
    pass


class LiveBudgetError(RuntimeError):
    pass


class LiveSmokeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database: SpikeSettings
    api_key: SecretStr | None = Field(default=None, repr=False)
    chat_model: Literal["openai/gpt-5.6-luna"] = "openai/gpt-5.6-luna"
    reasoning_effort: Literal["medium"] = "medium"
    embedding_model: Literal["openai/text-embedding-3-small"] = (
        "openai/text-embedding-3-small"
    )
    embedding_dimensions: Literal[1536] = 1536
    allow_fallbacks: Literal[False] = False
    model_retry_count: Literal[0] = 0
    max_model_calls: Literal[3] = 3
    max_tool_calls: Literal[2] = 2
    max_completion_tokens_per_call: Literal[1200] = 1200
    max_completion_tokens_total: Literal[3600] = 3600
    max_input_tokens_total: Literal[18000] = 18_000
    max_embedding_requests: Literal[8] = 8
    max_embedding_batch_size: Literal[2] = 2
    max_cost_usd: Literal[Decimal("0.20")] = Decimal("0.20")
    request_timeout_seconds: Literal[60] = 60
    run_timeout_seconds: Literal[180] = 180


def _required_key(settings: LiveSmokeSettings) -> str:
    if settings.api_key is None or not settings.api_key.get_secret_value().strip():
        raise MissingApiKeyError("live smoke requires an OpenRouter API key")
    return settings.api_key.get_secret_value()


def _build_openrouter_sdk(
    settings: LiveSmokeSettings,
    *,
    async_client: httpx.AsyncClient | None = None,
    server_url: str = OPENROUTER_URL,
) -> openrouter.OpenRouter:
    kwargs: dict[str, Any] = {
        "api_key": _required_key(settings),
        "server_url": server_url,
        "timeout_ms": settings.request_timeout_seconds * 1_000,
        "retry_config": None,
    }
    if async_client is not None:
        kwargs["async_client"] = async_client
    return openrouter.OpenRouter(**kwargs)


@asynccontextmanager
async def _open_openrouter_sdk(settings: LiveSmokeSettings):
    """Own the HTTP client outside the generated SDK's weakref finalizer."""
    async with httpx.AsyncClient(follow_redirects=True) as async_client:
        sdk = _build_openrouter_sdk(settings, async_client=async_client)
        async with sdk:
            yield sdk


class _ReceiptChatOpenRouter(ChatOpenRouter):
    """Preserve route facts discarded by the pinned LangChain integration."""

    def _create_chat_result(self, response: Any):
        payload = response if isinstance(response, dict) else response.model_dump(by_alias=True)
        result = super()._create_chat_result(response)
        for generation in result.generations:
            message = generation.message
            if payload.get("provider") is not None:
                message.response_metadata["provider"] = payload["provider"]
            if payload.get("model") is not None:
                message.response_metadata["resolved_model"] = payload["model"]
            if payload.get("id") is not None:
                message.response_metadata["request_id"] = payload["id"]
        return result


def _build_chat_model(
    settings: LiveSmokeSettings,
    *,
    sdk: openrouter.OpenRouter,
) -> ChatOpenRouter:
    return _ReceiptChatOpenRouter(
        client=sdk,
        model=settings.chat_model,
        api_key=_required_key(settings),
        max_retries=settings.model_retry_count,
        timeout=settings.request_timeout_seconds,
        max_completion_tokens=settings.max_completion_tokens_per_call,
        reasoning={
            "effort": settings.reasoning_effort,
        },
        openrouter_provider={
            "allow_fallbacks": settings.allow_fallbacks,
            "require_parameters": True,
        },
    )


@dataclass
class _CostLedger:
    cap: Decimal
    spent: Decimal = Decimal(0)
    all_costs_known: bool = True

    @property
    def receipt_cost(self) -> Decimal | None:
        return self.spent if self.all_costs_known else None

    def mark_unknown(self) -> None:
        self.all_costs_known = False

    def record(self, cost: Any) -> None:
        parsed = _nonnegative_decimal(cost, field_name="usage.cost")
        projected = self.spent + parsed
        self.spent = projected
        if projected > self.cap:
            raise LiveBudgetError("provider-reported cost exceeded the frozen cap")


class _OpenRouterEmbeddingAdapter:
    def __init__(
        self,
        *,
        sdk: openrouter.OpenRouter,
        settings: LiveSmokeSettings,
        ledger: _CostLedger | None = None,
    ) -> None:
        self._sdk = sdk
        self._settings = settings
        self._ledger = ledger or _CostLedger(settings.max_cost_usd)
        self.request_count = 0
        self.prompt_tokens = 0
        self.cost_usd: Decimal | None = Decimal(0)
        self.resolved_model: str | None = None
        self.request_ids: list[str] = []

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        if len(texts) > self._settings.max_embedding_batch_size:
            raise LiveBudgetError("embedding batch size budget exceeded")
        if self.request_count >= self._settings.max_embedding_requests:
            raise LiveBudgetError("embedding request budget exceeded")
        self.request_count += 1
        response = await self._sdk.embeddings.generate_async(
            input=texts,
            model=self._settings.embedding_model,
            dimensions=self._settings.embedding_dimensions,
            encoding_format="float",
            provider={
                "allow_fallbacks": self._settings.allow_fallbacks,
                "require_parameters": True,
            },
            retries=None,
            timeout_ms=self._settings.request_timeout_seconds * 1_000,
        )
        if isinstance(response, str):
            self.cost_usd = None
            self._ledger.mark_unknown()
            raise EmbeddingResponseError("embedding endpoint returned a non-object response")
        self.resolved_model = response.model
        if response.id:
            self.request_ids.append(response.id)
        if response.usage is not None:
            self.prompt_tokens += response.usage.prompt_tokens
        if response.usage is None or response.usage.cost is None:
            self.cost_usd = None
            self._ledger.mark_unknown()
            raise EmbeddingResponseError("embedding response omitted usage cost")

        cost = _nonnegative_decimal(response.usage.cost, field_name="embedding usage.cost")
        if self.cost_usd is not None:
            self.cost_usd += cost
        self._ledger.record(cost)

        if len(response.data) != len(texts):
            raise EmbeddingResponseError("embedding response count mismatch")

        ordered: list[list[float] | None] = [None] * len(texts)
        for item in response.data:
            if item.index is None or item.index < 0 or item.index >= len(texts):
                raise EmbeddingResponseError("embedding response index is missing or invalid")
            if ordered[item.index] is not None:
                raise EmbeddingResponseError("embedding response index is duplicated")
            if not isinstance(item.embedding, list):
                raise EmbeddingResponseError("embedding response must use float arrays")
            vector = [float(value) for value in item.embedding]
            if len(vector) != self._settings.embedding_dimensions:
                raise EmbeddingResponseError("embedding response dimension mismatch")
            ordered[item.index] = vector
        if any(vector is None for vector in ordered):
            raise EmbeddingResponseError("embedding response index set is incomplete")
        return [vector for vector in ordered if vector is not None]


def _nonnegative_decimal(value: Any, *, field_name: str) -> Decimal:
    if value is None:
        raise CostPreflightError(f"{field_name} is unavailable")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CostPreflightError(f"{field_name} is invalid") from exc
    if not result.is_finite() or result < 0:
        raise CostPreflightError(f"{field_name} is invalid")
    return result


def _optional_price(value: Any) -> Decimal:
    return Decimal(0) if value is None else _nonnegative_decimal(value, field_name="price")


def _conservative_cost_upper_bound(
    settings: LiveSmokeSettings,
    *,
    chat_endpoints: Sequence[Any],
    embedding_endpoints: Sequence[Any],
) -> Decimal:
    if not chat_endpoints or not embedding_endpoints:
        raise CostPreflightError("endpoint-level pricing is unavailable")

    chat_prompt_rates: list[Decimal] = []
    chat_output_rates: list[Decimal] = []
    chat_request_rates: list[Decimal] = []
    for endpoint in chat_endpoints:
        pricing = endpoint.pricing
        prompt = _nonnegative_decimal(pricing.prompt, field_name="chat prompt price")
        completion = _nonnegative_decimal(
            pricing.completion,
            field_name="chat completion price",
        )
        reasoning = (
            completion
            if getattr(pricing, "internal_reasoning", None) is None
            else _nonnegative_decimal(
                pricing.internal_reasoning,
                field_name="chat reasoning price",
            )
        )
        chat_prompt_rates.append(prompt)
        chat_output_rates.append(max(completion, reasoning))
        chat_request_rates.append(_optional_price(getattr(pricing, "request", None)))

    embedding_prompt_rates: list[Decimal] = []
    embedding_request_rates: list[Decimal] = []
    embedding_contexts: list[int] = []
    for endpoint in embedding_endpoints:
        pricing = endpoint.pricing
        embedding_prompt_rates.append(
            _nonnegative_decimal(
                pricing.prompt,
                field_name="embedding prompt price",
            )
        )
        embedding_request_rates.append(
            _optional_price(getattr(pricing, "request", None))
        )
        context_length = getattr(endpoint, "context_length", None)
        if not isinstance(context_length, int) or context_length <= 0:
            raise CostPreflightError("embedding context length is unavailable")
        embedding_contexts.append(context_length)

    bound = (
        Decimal(settings.max_input_tokens_total) * max(chat_prompt_rates)
        + Decimal(settings.max_completion_tokens_total) * max(chat_output_rates)
        + Decimal(settings.max_model_calls) * max(chat_request_rates)
        + Decimal(settings.max_embedding_requests)
        * Decimal(settings.max_embedding_batch_size)
        * Decimal(max(embedding_contexts))
        * max(embedding_prompt_rates)
        + Decimal(settings.max_embedding_requests) * max(embedding_request_rates)
    )
    if bound > settings.max_cost_usd:
        raise CostPreflightError("conservative provider cost exceeds frozen cap")
    return bound


def _message_for_receipt(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "name": message.name,
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            payload["tool_calls"] = [
                {"name": call["name"], "args": call["args"], "id": call["id"]}
                for call in message.tool_calls
            ]
        return payload
    role = "user" if message.type == "human" else message.type
    return {"role": role, "content": message.content}


@dataclass
class _BudgetedModel:
    inner: Any
    settings: LiveSmokeSettings
    ledger: _CostLedger
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    latency_seconds: float = 0.0
    resolved_model: str | None = None
    provider: str | None = None
    request_ids: list[str] = field(default_factory=list)
    turns: list[ModelVisibleTurn] = field(default_factory=list)

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        if self.model_calls >= self.settings.max_model_calls:
            raise LiveBudgetError("model call budget exceeded")
        self.model_calls += 1
        started = perf_counter()
        async with asyncio.timeout(self.settings.request_timeout_seconds):
            response = await self.inner.ainvoke(messages)
        latency = perf_counter() - started
        if not isinstance(response, AIMessage):
            self.ledger.mark_unknown()
            raise LiveBudgetError("model response omitted typed usage")

        self.tool_calls += len(response.tool_calls)
        self.latency_seconds += latency
        self.resolved_model = response.response_metadata.get("resolved_model")
        self.provider = response.response_metadata.get("provider")
        request_id = response.response_metadata.get("request_id")
        if isinstance(request_id, str):
            self.request_ids.append(request_id)
        self.turns.append(
            ModelVisibleTurn(
                call_index=self.model_calls,
                input=tuple(_message_for_receipt(message) for message in messages),
                output=_message_for_receipt(response),
            )
        )

        usage = response.usage_metadata
        input_tokens = 0
        output_tokens = 0
        if usage is not None:
            input_tokens = int(usage.get("input_tokens", 0))
            output_tokens = int(usage.get("output_tokens", 0))
            input_details = usage.get("input_token_details") or {}
            output_details = usage.get("output_token_details") or {}
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cache_read_tokens += int(input_details.get("cache_read", 0) or 0)
            self.cache_write_tokens += int(input_details.get("cache_creation", 0) or 0)
            self.reasoning_tokens += int(output_details.get("reasoning", 0) or 0)

        cost = response.response_metadata.get("cost")
        if cost is None:
            self.ledger.mark_unknown()
        else:
            self.ledger.record(cost)

        if usage is None:
            raise LiveBudgetError("model response omitted typed usage")
        if cost is None:
            raise LiveBudgetError("model response omitted usage cost")

        if output_tokens > self.settings.max_completion_tokens_per_call:
            raise LiveBudgetError("per-call completion token budget exceeded")
        if self.input_tokens > self.settings.max_input_tokens_total:
            raise LiveBudgetError("total input token budget exceeded")
        if self.output_tokens > self.settings.max_completion_tokens_total:
            raise LiveBudgetError("total completion token budget exceeded")
        if self.tool_calls > self.settings.max_tool_calls:
            raise LiveBudgetError("tool call budget exceeded")
        return response


async def _fetch_preflight_metadata(
    sdk: openrouter.OpenRouter,
    settings: LiveSmokeSettings,
) -> tuple[Sequence[Any], Sequence[Any]]:
    timeout_ms = settings.request_timeout_seconds * 1_000
    chat_models = await sdk.models.list_async(
        q=settings.chat_model,
        retries=None,
        timeout_ms=timeout_ms,
    )
    if not any(model.id == settings.chat_model for model in chat_models.data):
        raise CostPreflightError("requested chat model is unavailable")
    embedding_models = await sdk.embeddings.list_models_async(
        retries=None,
        timeout_ms=timeout_ms,
    )
    if not any(model.id == settings.embedding_model for model in embedding_models.data):
        raise CostPreflightError("requested embedding model is unavailable")

    chat_author, chat_slug = settings.chat_model.split("/", 1)
    embedding_author, embedding_slug = settings.embedding_model.split("/", 1)
    chat = await sdk.endpoints.list_async(
        author=chat_author,
        slug=chat_slug,
        retries=None,
        timeout_ms=timeout_ms,
    )
    embedding = await sdk.endpoints.list_async(
        author=embedding_author,
        slug=embedding_slug,
        retries=None,
        timeout_ms=timeout_ms,
    )
    return chat.data.endpoints, embedding.data.endpoints


def _empty_receipt(
    settings: LiveSmokeSettings,
    *,
    status: LiveSmokeStatus,
    latency_ms: int = 0,
    cost_upper_bound_usd: Decimal | None = None,
    error_code: str | None = None,
) -> LiveSmokeReceipt:
    return LiveSmokeReceipt(
        status=status,
        requested_model=settings.chat_model,
        requested_embedding_model=settings.embedding_model,
        reasoning=settings.reasoning_effort,
        latency_ms=latency_ms,
        cost_upper_bound_usd=cost_upper_bound_usd,
        error_code=error_code,
    )


async def run_live_smoke(
    settings: LiveSmokeSettings,
    *,
    dry_run: bool,
) -> LiveSmokeReceipt:
    if dry_run:
        return _empty_receipt(settings, status=LiveSmokeStatus.DRY_RUN)
    _required_key(settings)

    run_started = perf_counter()
    cost_bound: Decimal | None = None
    async with _open_openrouter_sdk(settings) as sdk:
        try:
            async with asyncio.timeout(settings.run_timeout_seconds):
                chat_endpoints, embedding_endpoints = await _fetch_preflight_metadata(
                    sdk,
                    settings,
                )
            cost_bound = _conservative_cost_upper_bound(
                settings,
                chat_endpoints=chat_endpoints,
                embedding_endpoints=embedding_endpoints,
            )
        except (
            CostPreflightError,
            OpenRouterError,
            httpx.HTTPError,
            TimeoutError,
        ) as exc:
            return _empty_receipt(
                settings,
                status=LiveSmokeStatus.PREFLIGHT_BLOCKED,
                latency_ms=int((perf_counter() - run_started) * 1000),
                error_code=f"preflight_{type(exc).__name__}",
            )

        ledger = _CostLedger(settings.max_cost_usd)
        embedder = _OpenRouterEmbeddingAdapter(
            sdk=sdk,
            settings=settings,
            ledger=ledger,
        )
        budgeted: _BudgetedModel | None = None
        try:
            remaining_run_seconds = max(
                0.0,
                settings.run_timeout_seconds - (perf_counter() - run_started),
            )
            async with asyncio.timeout(remaining_run_seconds):
                scope = TrustedReadScope(
                    run_id=uuid4(),
                    document_id=uuid4(),
                    thread_id=f"live-smoke-{uuid4()}",
                )
                async with open_spike_runtime(
                    settings.database,
                    embed=embedder,
                ) as runtime:
                    for human, assistant in load_canonical_rounds():
                        await append_canonical_round(runtime, scope, human, assistant)
                    await seed_current_memories(
                        runtime,
                        scope,
                        semantic_memory_fixtures(scope),
                    )
                    canonical = await latest_canonical_messages(runtime, scope)
                    guide = await rebuild_memory_guide(runtime.store, scope)
                    model = bind_memory_read_tools(_build_chat_model(settings, sdk=sdk))
                    budgeted = _BudgetedModel(model, settings, ledger)
                    graph = build_memory_read_graph(budgeted, store=runtime.store)
                    result = await graph.ainvoke(
                        build_transient_input(
                            system_instructions=LIVE_SYSTEM_PROMPT,
                            user_request=LIVE_USER_PROMPT,
                            canonical_messages=canonical,
                            memory_guide=guide,
                        ),
                        context=MemoryReadContext(
                            scope=scope,
                            canonical_runtime=runtime,
                        ),
                    )
                    final_message = result["messages"][-1]
                    if not isinstance(final_message, AIMessage) or final_message.tool_calls:
                        raise LiveBudgetError("graph did not finish with a final answer")

            assert budgeted is not None
            return LiveSmokeReceipt(
                status=LiveSmokeStatus.COMPLETED,
                requested_model=settings.chat_model,
                resolved_model=budgeted.resolved_model,
                provider=budgeted.provider,
                requested_embedding_model=settings.embedding_model,
                resolved_embedding_model=embedder.resolved_model,
                reasoning=settings.reasoning_effort,
                model_calls=budgeted.model_calls,
                tool_calls=budgeted.tool_calls,
                usage=LiveUsage(
                    input_tokens=budgeted.input_tokens,
                    output_tokens=budgeted.output_tokens,
                    cache_read_tokens=budgeted.cache_read_tokens,
                    cache_write_tokens=budgeted.cache_write_tokens,
                    reasoning_tokens=budgeted.reasoning_tokens,
                    embedding_tokens=embedder.prompt_tokens,
                ),
                latency_ms=int((perf_counter() - run_started) * 1000),
                cost_usd=ledger.receipt_cost,
                cost_upper_bound_usd=cost_bound,
                request_ids=tuple(embedder.request_ids + budgeted.request_ids),
                model_visible_turns=tuple(budgeted.turns),
                final_answer=str(final_message.content),
            )
        except (
            EmbeddingResponseError,
            LiveBudgetError,
            MultipleToolCallsError,
            OpenRouterError,
            ToolBudgetExceededError,
            httpx.HTTPError,
            psycopg.OperationalError,
            TimeoutError,
        ) as exc:
            return LiveSmokeReceipt(
                status=LiveSmokeStatus.FAILED,
                requested_model=settings.chat_model,
                resolved_model=budgeted.resolved_model if budgeted else None,
                provider=budgeted.provider if budgeted else None,
                requested_embedding_model=settings.embedding_model,
                resolved_embedding_model=embedder.resolved_model,
                reasoning=settings.reasoning_effort,
                model_calls=budgeted.model_calls if budgeted else 0,
                tool_calls=budgeted.tool_calls if budgeted else 0,
                usage=LiveUsage(
                    input_tokens=budgeted.input_tokens if budgeted else 0,
                    output_tokens=budgeted.output_tokens if budgeted else 0,
                    cache_read_tokens=budgeted.cache_read_tokens if budgeted else 0,
                    cache_write_tokens=budgeted.cache_write_tokens if budgeted else 0,
                    reasoning_tokens=budgeted.reasoning_tokens if budgeted else 0,
                    embedding_tokens=embedder.prompt_tokens,
                ),
                latency_ms=int((perf_counter() - run_started) * 1000),
                cost_usd=ledger.receipt_cost,
                cost_upper_bound_usd=cost_bound,
                request_ids=tuple(
                    embedder.request_ids + (budgeted.request_ids if budgeted else [])
                ),
                model_visible_turns=tuple(budgeted.turns if budgeted else ()),
                error_code=f"live_{type(exc).__name__}",
            )


def _settings_from_env_file(path: Path) -> LiveSmokeSettings:
    values = dotenv_values(path)
    api_key = values.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    return LiveSmokeSettings(
        database=SpikeSettings.from_environment(),
        api_key=SecretStr(api_key) if api_key else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    receipt = asyncio.run(
        run_live_smoke(
            _settings_from_env_file(args.env_file),
            dry_run=args.dry_run,
        ),
        loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None,
    )
    experiment_root = Path(__file__).resolve().parents[2]
    output = experiment_root / "trials" / f"revision-{args.revision}-luna-medium.json"
    with output.open("x", encoding="utf-8") as handle:
        handle.write(receipt.model_dump_json(indent=2))
        handle.write("\n")
    print(f"{receipt.status.value}: {output}")
    if receipt.status in {
        LiveSmokeStatus.PREFLIGHT_BLOCKED,
        LiveSmokeStatus.FAILED,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
