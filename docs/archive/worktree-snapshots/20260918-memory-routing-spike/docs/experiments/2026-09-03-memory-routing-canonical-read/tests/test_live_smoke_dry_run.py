from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import psycopg
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter
from openrouter.operations.listendpoints import ListEndpointsResponse
from pydantic import SecretStr, ValidationError

from memory_read_spike.live_smoke import (
    LIVE_SYSTEM_PROMPT,
    LIVE_USER_PROMPT,
    CostPreflightError,
    EmbeddingResponseError,
    LiveBudgetError,
    LiveSmokeSettings,
    MissingApiKeyError,
    _BudgetedModel,
    _CostLedger,
    _OpenRouterEmbeddingAdapter,
    _build_chat_model,
    _build_openrouter_sdk,
    _conservative_cost_upper_bound,
    _fetch_preflight_metadata,
    _message_for_receipt,
    main,
    run_live_smoke,
)
from memory_read_spike.receipts import LiveSmokeReceipt, LiveSmokeStatus
from memory_read_spike.settings import SpikeSettings
from memory_read_spike.tools import bind_memory_read_tools


def _database_settings() -> SpikeSettings:
    return SpikeSettings(
        database_url=os.environ["MEMORY_ROUTING_SPIKE_DATABASE_URL"],
        expected_database=os.environ["MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"],
        production_database_url=os.environ.get("DATABASE_URL"),
    )


def _settings(*, api_key: str | None = None) -> LiveSmokeSettings:
    return LiveSmokeSettings(
        database=_database_settings(),
        api_key=SecretStr(api_key) if api_key is not None else None,
    )


def test_frozen_case_rubric_and_prompt_hashes_match_readme() -> None:
    experiment_root = Path(__file__).resolve().parents[1]
    readme = (experiment_root / "README.md").read_text(encoding="utf-8")
    case_hash = sha256(
        (experiment_root / "cases" / "long-thread-routing-v1.json").read_bytes()
    ).hexdigest()
    rubric_hash = sha256((experiment_root / "rubric.md").read_bytes()).hexdigest()
    prompt_bytes = (
        f"System:\n{LIVE_SYSTEM_PROMPT}\n\nUser:\n{LIVE_USER_PROMPT}\n"
    ).encode("utf-8")
    prompt_hash = sha256(prompt_bytes).hexdigest()

    assert f"case_sha256: {case_hash}" in readme
    assert f"rubric_sha256: {rubric_hash}" in readme
    assert f"prompt_sha256: {prompt_hash}" in readme


def _embedding_response(
    *,
    vectors: list[tuple[int | None, list[float]]],
) -> dict[str, Any]:
    return {
        "data": [
            {
                "embedding": vector,
                "object": "embedding",
                **({"index": index} if index is not None else {}),
            }
            for index, vector in vectors
        ],
        "model": "openai/text-embedding-3-small",
        "object": "list",
        "id": "emb-test",
        "usage": {
            "prompt_tokens": 4,
            "total_tokens": 4,
            "cost": 0.000001,
        },
    }


def test_live_settings_prompt_and_receipt_contract_are_frozen() -> None:
    settings = _settings(api_key="secret-never-log")

    assert settings.chat_model == "openai/gpt-5.6-luna"
    assert settings.reasoning_effort == "medium"
    assert settings.embedding_model == "openai/text-embedding-3-small"
    assert settings.embedding_dimensions == 1536
    assert settings.allow_fallbacks is False
    assert settings.model_retry_count == 0
    assert settings.max_model_calls == 3
    assert settings.max_tool_calls == 2
    assert settings.max_completion_tokens_per_call == 1200
    assert settings.max_completion_tokens_total == 3600
    assert settings.max_input_tokens_total == 18_000
    assert settings.max_embedding_requests == 8
    assert settings.max_embedding_batch_size == 2
    assert settings.max_cost_usd == Decimal("0.20")
    assert settings.request_timeout_seconds == 60
    assert settings.run_timeout_seconds == 180
    assert "secret-never-log" not in repr(settings)
    assert "secret-never-log" not in settings.model_dump_json()

    assert LIVE_SYSTEM_PROMPT == (
        "你正在驗證長訪談的記憶讀取路徑。請只根據目前可見對話與工具結果回答。\n"
        "目前可見內容不足時，依工具各自說明的使用時機自行取得必要資料；需要核對員工精確原話"
        "或短答脈絡時才讀 canonical conversation。\n"
        "不得自行猜測 reference，不得呼叫其他工具。資料沒有說明時，直接寫「目前資料未說明，"
        "需要詢問員工」，不要補造答案。"
    )
    assert LIVE_USER_PROMPT == (
        "請一次回答：\n"
        "1. 餐飲預約網站 A 案的三個獨有細節是什麼？並核對員工描述「過敏備註」做法時使用的"
        "精確原句。\n"
        "2. A 案與健身會員網站 B 案如何區分？B 案目前採會員 API 還是 CSV？\n"
        "3. 退款例外由誰核准？"
    )

    with pytest.raises(ValidationError):
        LiveSmokeSettings(
            database=_database_settings(),
            chat_model="openai/another-model",
        )
    with pytest.raises(ValidationError):
        LiveSmokeSettings(
            database=_database_settings(),
            max_cost_usd=Decimal("0.21"),
        )


@pytest.mark.asyncio
async def test_dry_run_needs_no_key_and_builds_no_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("dry-run must not construct an external client")

    monkeypatch.setattr(live_module, "_build_openrouter_sdk", forbidden)
    receipt = await run_live_smoke(_settings(), dry_run=True)

    assert receipt.status is LiveSmokeStatus.DRY_RUN
    assert receipt.requested_model == "openai/gpt-5.6-luna"
    assert receipt.reasoning == "medium"
    assert receipt.model_calls == 0
    assert receipt.tool_calls == 0
    assert receipt.usage.input_tokens == 0
    assert receipt.model_visible_turns == ()
    assert receipt.reasoning_payloads_redacted is True
    assert "api_key" not in receipt.model_dump_json()
    assert LiveSmokeStatus.COMPLETED.value == "completed"

    with pytest.raises(MissingApiKeyError):
        await run_live_smoke(_settings(), dry_run=False)


@pytest.mark.asyncio
async def test_failed_model_request_counts_as_an_attempt() -> None:
    class FailingExternalModel:
        async def ainvoke(self, _messages: Any) -> AIMessage:
            request = httpx.Request("POST", "https://openrouter.test/chat/completions")
            raise httpx.ConnectError("connection failed", request=request)

    settings = _settings(api_key="test-only")
    budgeted = _BudgetedModel(
        inner=FailingExternalModel(),
        settings=settings,
        ledger=_CostLedger(settings.max_cost_usd),
    )

    with pytest.raises(httpx.ConnectError):
        await budgeted.ainvoke([])

    assert budgeted.model_calls == 1


@pytest.mark.asyncio
async def test_over_cap_model_response_is_recorded_before_the_run_stops() -> None:
    class OverCapExternalModel:
        async def ainvoke(self, _messages: Any) -> AIMessage:
            return AIMessage(
                content="已產生但超過成本上限的回答",
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "total_tokens": 12,
                },
                response_metadata={
                    "cost": "0.21",
                    "provider": "OpenAI",
                    "resolved_model": "openai/gpt-5.6-luna-20260709",
                    "request_id": "chat-over-cap",
                },
            )

    settings = _settings(api_key="test-only")
    ledger = _CostLedger(settings.max_cost_usd)
    budgeted = _BudgetedModel(
        inner=OverCapExternalModel(),
        settings=settings,
        ledger=ledger,
    )

    with pytest.raises(LiveBudgetError, match="cost exceeded"):
        await budgeted.ainvoke([])

    assert ledger.spent == Decimal("0.21")
    assert budgeted.model_calls == 1
    assert budgeted.input_tokens == 10
    assert budgeted.output_tokens == 2
    assert budgeted.provider == "OpenAI"
    assert budgeted.request_ids == ["chat-over-cap"]
    assert len(budgeted.turns) == 1


@pytest.mark.asyncio
async def test_missing_typed_usage_preserves_available_chat_receipt_facts() -> None:
    class MissingUsageExternalModel:
        async def ainvoke(self, _messages: Any) -> AIMessage:
            return AIMessage(
                content="可保存的模型輸出",
                additional_kwargs={
                    "reasoning_content": "不得保存的 provider-private reasoning",
                },
                response_metadata={
                    "cost": "0.01",
                    "provider": "OpenAI",
                    "resolved_model": "openai/gpt-5.6-luna-20260709",
                    "request_id": "chat-missing-usage",
                },
            )

    settings = _settings(api_key="test-only")
    ledger = _CostLedger(settings.max_cost_usd)
    budgeted = _BudgetedModel(
        inner=MissingUsageExternalModel(),
        settings=settings,
        ledger=ledger,
    )

    with pytest.raises(LiveBudgetError, match="typed usage"):
        await budgeted.ainvoke([HumanMessage(content="測試缺少 usage 的回應")])

    assert ledger.spent == Decimal("0.01")
    assert budgeted.resolved_model == "openai/gpt-5.6-luna-20260709"
    assert budgeted.provider == "OpenAI"
    assert budgeted.request_ids == ["chat-missing-usage"]
    assert len(budgeted.turns) == 1
    assert budgeted.turns[0].output == {
        "role": "assistant",
        "content": "可保存的模型輸出",
    }
    assert "provider-private reasoning" not in budgeted.turns[0].model_dump_json()


@pytest.mark.asyncio
async def test_missing_chat_cost_makes_aggregate_receipt_cost_unknown() -> None:
    class MissingCostExternalModel:
        async def ainvoke(self, _messages: Any) -> AIMessage:
            return AIMessage(
                content="缺少 cost 的模型輸出",
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "total_tokens": 12,
                },
                response_metadata={
                    "provider": "OpenAI",
                    "resolved_model": "openai/gpt-5.6-luna-20260709",
                    "request_id": "chat-missing-cost",
                },
            )

    settings = _settings(api_key="test-only")
    ledger = _CostLedger(settings.max_cost_usd)
    ledger.record("0.01")
    budgeted = _BudgetedModel(
        inner=MissingCostExternalModel(),
        settings=settings,
        ledger=ledger,
    )

    with pytest.raises(LiveBudgetError, match="omitted usage cost"):
        await budgeted.ainvoke([])

    assert ledger.spent == Decimal("0.01")
    assert ledger.receipt_cost is None


@pytest.mark.asyncio
async def test_preflight_extracts_endpoints_from_typed_sdk_operation_response() -> None:
    settings = _settings(api_key="test-only")

    class FakeModels:
        async def list_async(self, *, q: str, **_kwargs: Any) -> Any:
            return SimpleNamespace(data=[SimpleNamespace(id=q)])

    class FakeEmbeddings:
        async def list_models_async(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                data=[SimpleNamespace(id=settings.embedding_model)]
            )

    class FakeEndpoints:
        async def list_async(
            self,
            *,
            author: str,
            slug: str,
            **_kwargs: Any,
        ) -> ListEndpointsResponse:
            model_id = f"{author}/{slug}"
            return ListEndpointsResponse.model_validate(
                {
                    "data": {
                        "architecture": {
                            "input_modalities": ["text"],
                            "instruct_type": None,
                            "modality": "text->text",
                            "output_modalities": ["text"],
                            "tokenizer": "test",
                        },
                        "created": 0,
                        "description": "typed SDK fixture",
                        "endpoints": [
                            {
                                "context_length": 8192,
                                "latency_last_30m": None,
                                "max_completion_tokens": 4096,
                                "max_prompt_tokens": 8192,
                                "model_id": model_id,
                                "model_name": model_id,
                                "name": "test endpoint",
                                "pricing": {
                                    "completion": "0.000002",
                                    "prompt": "0.000001",
                                },
                                "provider_name": "test provider",
                                "quantization": "unknown",
                                "supported_parameters": [],
                                "supports_implicit_caching": False,
                                "tag": "test",
                                "throughput_last_30m": None,
                                "uptime_last_1d": None,
                                "uptime_last_30m": None,
                                "uptime_last_5m": None,
                                "status": 0,
                            }
                        ],
                        "id": model_id,
                        "name": model_id,
                    }
                }
            )

    sdk = SimpleNamespace(
        models=FakeModels(),
        embeddings=FakeEmbeddings(),
        endpoints=FakeEndpoints(),
    )

    chat_endpoints, embedding_endpoints = await _fetch_preflight_metadata(
        sdk,
        settings,
    )

    assert [endpoint.model_id for endpoint in chat_endpoints] == [
        settings.chat_model
    ]
    assert [endpoint.model_id for endpoint in embedding_endpoints] == [
        settings.embedding_model
    ]


@pytest.mark.asyncio
async def test_programming_error_during_preflight_is_not_misreported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    async def broken_preflight(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("harness defect")

    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", broken_preflight)

    with pytest.raises(AssertionError, match="harness defect"):
        await run_live_smoke(_settings(api_key="test-only"), dry_run=False)


@pytest.mark.asyncio
async def test_expected_preflight_failure_returns_blocked_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    async def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise CostPreflightError("pricing unavailable")

    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", unavailable)

    receipt = await run_live_smoke(_settings(api_key="test-only"), dry_run=False)

    assert receipt.status is LiveSmokeStatus.PREFLIGHT_BLOCKED
    assert receipt.error_code == "preflight_CostPreflightError"


@pytest.mark.asyncio
async def test_live_run_owns_and_closes_its_async_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    class TrackedAsyncClient:
        entered = False
        closed = False

        async def __aenter__(self) -> TrackedAsyncClient:
            self.entered = True
            return self

        async def __aexit__(self, *_args: Any) -> None:
            self.closed = True

    class FakeSdk:
        async def __aenter__(self) -> FakeSdk:
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

    tracked_client = TrackedAsyncClient()

    def build_sdk(
        _settings: LiveSmokeSettings,
        *,
        async_client: Any | None = None,
    ) -> FakeSdk:
        assert async_client is tracked_client
        return FakeSdk()

    async def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise CostPreflightError("pricing unavailable")

    monkeypatch.setattr(
        live_module.httpx,
        "AsyncClient",
        lambda **_kwargs: tracked_client,
    )
    monkeypatch.setattr(live_module, "_build_openrouter_sdk", build_sdk)
    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", unavailable)

    receipt = await run_live_smoke(_settings(api_key="test-only"), dry_run=False)

    assert receipt.status is LiveSmokeStatus.PREFLIGHT_BLOCKED
    assert tracked_client.entered is True
    assert tracked_client.closed is True


@pytest.mark.asyncio
async def test_whole_run_timeout_starts_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    active_timeouts: list[float] = []

    @asynccontextmanager
    async def tracked_timeout(seconds: float):
        active_timeouts.append(seconds)
        try:
            yield
        finally:
            active_timeouts.pop()

    class FakeSdk:
        async def __aenter__(self) -> FakeSdk:
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

    async def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        assert active_timeouts == [180]
        raise CostPreflightError("pricing unavailable")

    monkeypatch.setattr(live_module.asyncio, "timeout", tracked_timeout)
    monkeypatch.setattr(
        live_module,
        "_build_openrouter_sdk",
        lambda _settings, **_kwargs: FakeSdk(),
    )
    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", unavailable)

    receipt = await run_live_smoke(_settings(api_key="test-only"), dry_run=False)

    assert receipt.status is LiveSmokeStatus.PREFLIGHT_BLOCKED


@pytest.mark.asyncio
async def test_programming_error_during_live_run_is_not_misreported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    cheap_chat = SimpleNamespace(
        pricing=SimpleNamespace(
            prompt="0.00000001",
            completion="0.00000001",
            internal_reasoning=None,
            request=None,
        )
    )
    cheap_embedding = SimpleNamespace(
        pricing=SimpleNamespace(prompt="0.00000001", request=None),
        context_length=8192,
    )

    async def valid_preflight(*_args: Any, **_kwargs: Any) -> Any:
        return [cheap_chat], [cheap_embedding]

    @asynccontextmanager
    async def broken_runtime(*_args: Any, **_kwargs: Any):
        raise AssertionError("runtime wiring defect")
        yield

    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", valid_preflight)
    monkeypatch.setattr(live_module, "open_spike_runtime", broken_runtime)

    with pytest.raises(AssertionError, match="runtime wiring defect"):
        await run_live_smoke(_settings(api_key="test-only"), dry_run=False)


@pytest.mark.asyncio
async def test_database_schema_error_is_not_misreported_as_a_model_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    cheap_chat = SimpleNamespace(
        pricing=SimpleNamespace(
            prompt="0.00000001",
            completion="0.00000001",
            internal_reasoning=None,
            request=None,
        )
    )
    cheap_embedding = SimpleNamespace(
        pricing=SimpleNamespace(prompt="0.00000001", request=None),
        context_length=8192,
    )

    async def valid_preflight(*_args: Any, **_kwargs: Any) -> Any:
        return [cheap_chat], [cheap_embedding]

    @asynccontextmanager
    async def broken_runtime(*_args: Any, **_kwargs: Any):
        raise psycopg.DataError("vector schema mismatch")
        yield

    monkeypatch.setattr(live_module, "_fetch_preflight_metadata", valid_preflight)
    monkeypatch.setattr(live_module, "open_spike_runtime", broken_runtime)

    with pytest.raises(psycopg.DataError, match="vector schema mismatch"):
        await run_live_smoke(_settings(api_key="test-only"), dry_run=False)


def test_cli_writes_failed_receipt_then_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module

    receipt = LiveSmokeReceipt(
        status=LiveSmokeStatus.PREFLIGHT_BLOCKED,
        requested_model="openai/gpt-5.6-luna",
        requested_embedding_model="openai/text-embedding-3-small",
        error_code="preflight_CostPreflightError",
    )

    async def blocked_run(*_args: Any, **_kwargs: Any) -> LiveSmokeReceipt:
        return receipt

    monkeypatch.setattr(live_module, "run_live_smoke", blocked_run)
    monkeypatch.setattr(live_module, "_settings_from_env_file", lambda _path: _settings())
    revision = 99991
    output = (
        Path(live_module.__file__).resolve().parents[2]
        / "trials"
        / f"revision-{revision}-luna-medium.json"
    )
    output.unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "live-smoke",
            "--env-file",
            "unused.env",
            "--revision",
            str(revision),
        ],
    )

    try:
        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 1
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved["status"] == "preflight_blocked"
    finally:
        output.unlink(missing_ok=True)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows event-loop regression")
def test_windows_cli_uses_psycopg_compatible_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.live_smoke as live_module
    from memory_read_spike.runtime import _read_current_database

    receipt = LiveSmokeReceipt(
        status=LiveSmokeStatus.DRY_RUN,
        requested_model="openai/gpt-5.6-luna",
        requested_embedding_model="openai/text-embedding-3-small",
    )
    observed_databases: list[str] = []

    async def database_probe(
        settings: LiveSmokeSettings,
        **_kwargs: Any,
    ) -> LiveSmokeReceipt:
        observed_databases.append(
            await _read_current_database(settings.database.connection_string)
        )
        return receipt

    monkeypatch.setattr(live_module, "run_live_smoke", database_probe)
    monkeypatch.setattr(live_module, "_settings_from_env_file", lambda _path: _settings())
    revision = 99992
    output = (
        Path(live_module.__file__).resolve().parents[2]
        / "trials"
        / f"revision-{revision}-luna-medium.json"
    )
    output.unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "live-smoke",
            "--env-file",
            "unused.env",
            "--revision",
            str(revision),
        ],
    )
    original_policy = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        main()

        assert observed_databases == [
            os.environ["MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"]
        ]
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved["status"] == "dry_run"
    finally:
        asyncio.set_event_loop_policy(original_policy)
        output.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_embedding_adapter_uses_typed_sdk_request_and_restores_index_order() -> None:
    captured: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=_embedding_response(
                vectors=[
                    (1, [2.0] * 1536),
                    (0, [1.0] * 1536),
                ]
            ),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            adapter = _OpenRouterEmbeddingAdapter(sdk=sdk, settings=settings)
            vectors = await adapter(["first", "second"])

    assert vectors == [[1.0] * 1536, [2.0] * 1536]
    assert sdk.sdk_configuration.retry_config is None
    assert captured == [
        {
            "dimensions": 1536,
            "encoding_format": "float",
            "input": ["first", "second"],
            "model": "openai/text-embedding-3-small",
            "provider": {
                "allow_fallbacks": False,
                "require_parameters": True,
            },
        }
    ]
    assert adapter.request_count == 1
    assert adapter.prompt_tokens == 4
    assert adapter.cost_usd == Decimal("0.000001")


@pytest.mark.asyncio
async def test_over_cap_embedding_response_is_recorded_before_the_run_stops() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        payload = _embedding_response(vectors=[(0, [1.0] * 1536)])
        payload["usage"]["cost"] = 0.21
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        ledger = _CostLedger(settings.max_cost_usd)
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            adapter = _OpenRouterEmbeddingAdapter(
                sdk=sdk,
                settings=settings,
                ledger=ledger,
            )
            with pytest.raises(LiveBudgetError, match="cost exceeded"):
                await adapter(["first"])

    assert ledger.spent == Decimal("0.21")
    assert adapter.request_count == 1
    assert adapter.prompt_tokens == 4
    assert adapter.cost_usd == Decimal("0.21")
    assert adapter.resolved_model == "openai/text-embedding-3-small"
    assert adapter.request_ids == ["emb-test"]


@pytest.mark.asyncio
async def test_missing_embedding_cost_preserves_facts_and_unknown_aggregate() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        payload = _embedding_response(vectors=[(0, [1.0] * 1536)])
        del payload["usage"]["cost"]
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        ledger = _CostLedger(settings.max_cost_usd)
        ledger.record("0.01")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            adapter = _OpenRouterEmbeddingAdapter(
                sdk=sdk,
                settings=settings,
                ledger=ledger,
            )
            with pytest.raises(EmbeddingResponseError, match="omitted usage cost"):
                await adapter(["first"])

    assert adapter.prompt_tokens == 4
    assert adapter.cost_usd is None
    assert adapter.resolved_model == "openai/text-embedding-3-small"
    assert adapter.request_ids == ["emb-test"]
    assert ledger.spent == Decimal("0.01")
    assert ledger.receipt_cost is None


@pytest.mark.asyncio
async def test_non_object_embedding_response_makes_aggregate_cost_unknown() -> None:
    class StringEmbeddingEndpoint:
        async def generate_async(self, **_kwargs: Any) -> str:
            return "provider returned a non-object response"

    settings = _settings(api_key="test-only")
    ledger = _CostLedger(settings.max_cost_usd)
    ledger.record("0.01")
    adapter = _OpenRouterEmbeddingAdapter(
        sdk=SimpleNamespace(embeddings=StringEmbeddingEndpoint()),
        settings=settings,
        ledger=ledger,
    )

    with pytest.raises(EmbeddingResponseError, match="non-object response"):
        await adapter(["first"])

    assert adapter.cost_usd is None
    assert ledger.spent == Decimal("0.01")
    assert ledger.receipt_cost is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vectors",
    [
        [(None, [1.0] * 1536), (1, [2.0] * 1536)],
        [(0, [1.0] * 2), (1, [2.0] * 1536)],
        [(0, [1.0] * 1536)],
    ],
)
async def test_embedding_adapter_stops_on_missing_index_dimensions_or_count(
    vectors: list[tuple[int | None, list[float]]],
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_embedding_response(vectors=vectors))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            adapter = _OpenRouterEmbeddingAdapter(sdk=sdk, settings=settings)
            with pytest.raises(EmbeddingResponseError):
                await adapter(["first", "second"])
            assert adapter.request_count == 1


@pytest.mark.asyncio
async def test_embedding_adapter_rejects_unbounded_batch_before_http() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("oversized embedding batch reached the provider")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            adapter = _OpenRouterEmbeddingAdapter(sdk=sdk, settings=settings)
            with pytest.raises(LiveBudgetError, match="batch size"):
                await adapter(["one", "two", "three"])

    assert adapter.request_count == 0


@pytest.mark.asyncio
async def test_chat_model_request_freezes_reasoning_fallback_retry_and_caps() -> None:
    captured: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 1,
                "model": "openai/gpt-5.6-luna",
                "provider": "OpenAI",
                "system_fingerprint": "fp-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "完成"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "cost": 0.00001,
                    "completion_tokens_details": {"reasoning_tokens": 1},
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            model = _build_chat_model(settings, sdk=sdk)
            assert isinstance(model, ChatOpenRouter)
            assert model.max_retries == 0
            await bind_memory_read_tools(model).ainvoke("測試")

    payload = captured[-1]
    assert payload["model"] == "openai/gpt-5.6-luna"
    assert payload["max_completion_tokens"] == 1200
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["provider"] == {
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert payload["parallel_tool_calls"] is False
    assert all(tool["function"]["strict"] is True for tool in payload["tools"])


@pytest.mark.asyncio
async def test_tool_loop_resends_reasoning_transiently_but_receipt_redacts_it() -> None:
    captured: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload)
        if len(captured) == 1:
            message: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "reasoning": "provider-private-reasoning",
                "reasoning_details": [
                    {
                        "type": "reasoning.encrypted",
                        "data": "opaque-reasoning-token",
                        "id": "reasoning-1",
                        "format": "openai-responses-v1",
                        "index": 0,
                    }
                ],
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "search_semantic_memory",
                            "arguments": '{"query":"A 案"}',
                        },
                    }
                ],
            }
        else:
            message = {"role": "assistant", "content": "完成"}
        return httpx.Response(
            200,
            json={
                "id": f"chat-{len(captured)}",
                "object": "chat.completion",
                "created": len(captured),
                "model": "openai/gpt-5.6-luna",
                "provider": "OpenAI",
                "system_fingerprint": "fp-test",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if len(captured) == 1 else "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "cost": 0.00001,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.test",
    ) as async_client:
        settings = _settings(api_key="test-only")
        sdk = _build_openrouter_sdk(
            settings,
            async_client=async_client,
            server_url="https://openrouter.test/api/v1",
        )
        async with sdk:
            model = bind_memory_read_tools(_build_chat_model(settings, sdk=sdk))
            human = HumanMessage(content="請搜尋 A 案")
            first = await model.ainvoke([human])
            await model.ainvoke(
                [
                    human,
                    first,
                    ToolMessage(
                        content='{"memories":[]}',
                        tool_call_id="call-1",
                        name="search_semantic_memory",
                    ),
                ]
            )

    prior_assistant = captured[1]["messages"][1]
    assert prior_assistant["reasoning"] == "provider-private-reasoning"
    assert prior_assistant["reasoning_details"][0]["data"] == (
        "opaque-reasoning-token"
    )
    assert _message_for_receipt(first) == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "name": "search_semantic_memory",
                "args": {"query": "A 案"},
                "id": "call-1",
            }
        ],
    }


def test_receipt_serialization_never_persists_reasoning_content() -> None:
    payload = _message_for_receipt(
        AIMessage(
            content="可保存的最終回答",
            additional_kwargs={
                "reasoning_content": "不可保存的隱藏推理",
                "reasoning_details": [{"type": "reasoning.text", "text": "秘密"}],
            },
        )
    )

    assert payload == {"role": "assistant", "content": "可保存的最終回答"}
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "隱藏推理" not in serialized
    assert "秘密" not in serialized


def test_cost_preflight_uses_worst_endpoint_and_blocks_unknown_or_over_cap() -> None:
    settings = _settings(api_key="test-only")
    chat_endpoints = [
        SimpleNamespace(
            pricing=SimpleNamespace(
                prompt="0.000001",
                completion="0.000002",
                internal_reasoning=None,
                request=None,
            )
        ),
        SimpleNamespace(
            pricing=SimpleNamespace(
                prompt="0.000002",
                completion="0.000003",
                internal_reasoning="0.000004",
                request="0.001",
            )
        ),
    ]
    embedding_endpoints = [
        SimpleNamespace(
            pricing=SimpleNamespace(
                prompt="0.00000002",
                completion="0",
                internal_reasoning=None,
                request=None,
            ),
            context_length=8192,
        )
    ]

    bound = _conservative_cost_upper_bound(
        settings,
        chat_endpoints=chat_endpoints,
        embedding_endpoints=embedding_endpoints,
    )
    expected = (
        Decimal(18_000) * Decimal("0.000002")
        + Decimal(3_600) * Decimal("0.000004")
        + Decimal(3) * Decimal("0.001")
        + Decimal(8 * 2 * 8192) * Decimal("0.00000002")
    )
    assert bound == expected
    assert bound < settings.max_cost_usd

    with pytest.raises(CostPreflightError):
        _conservative_cost_upper_bound(
            settings,
            chat_endpoints=[
                SimpleNamespace(
                    pricing=SimpleNamespace(
                        prompt=None,
                        completion="0.000002",
                        internal_reasoning=None,
                        request=None,
                    )
                )
            ],
            embedding_endpoints=embedding_endpoints,
        )

    with pytest.raises(CostPreflightError):
        _conservative_cost_upper_bound(
            settings,
            chat_endpoints=chat_endpoints,
            embedding_endpoints=[],
        )

    expensive = SimpleNamespace(
        pricing=SimpleNamespace(
            prompt="0.01",
            completion="0.01",
            internal_reasoning="0.01",
            request="1",
        )
    )
    with pytest.raises(CostPreflightError):
        _conservative_cost_upper_bound(
            settings,
            chat_endpoints=[expensive],
            embedding_endpoints=embedding_endpoints,
        )
