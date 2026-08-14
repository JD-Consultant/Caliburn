from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents.middleware import (
    ContextEditingMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel, ValidationError

from app.adapters.openrouter.langchain import build_openrouter_chat_model
import app.consultant.model_runtime as model_runtime
from app.consultant.model_runtime import (
    AttemptReceiptCallback,
    AttemptReceipt,
    AttemptKind,
    AttemptStatus,
    AttemptUsage,
    ConsultantModelProfile,
    ConsultantRunBudgetExceeded,
    OutputTokenParameter,
    RunPolicy,
    build_consultant_agent,
    build_consultant_middleware,
    resolve_execution,
    verify_attempt_budget,
)
from app.consultant.model_output import ConsultantModelOutput
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_model_attempts,
)


def _profile(
    *,
    revision: int = 1,
    model: str = "anthropic/claude-opus-5",
    provider: str = "Anthropic",
    reasoning_effort: str = "high",
):
    return ConsultantModelProfile(
        profile_id="primary-consultant",
        revision=revision,
        requested_model=model,
        provider_allowlist=(provider,),
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        output_token_parameter=OutputTokenParameter.MAX_TOKENS,
        reasoning_effort=reasoning_effort,
        timeout_seconds=90,
    )


def _policy(*, skills: tuple[str, ...] = ("work-discovery",)):
    return RunPolicy(
        policy_id="interactive-consultation",
        revision=1,
        run_kind="interactive_consultation",
        allowed_skill_ids=skills,
        allowed_tool_ids=(
            "employee_source_get",
            "employee_source_lineage",
            "employee_source_search",
        ),
        max_context_tokens=24_000,
        max_model_calls=3,
        max_lookup_waves=2,
        max_total_tool_calls=12,
        model_retry_count=1,
        tool_retry_count=1,
        max_elapsed_seconds=180,
        max_total_tokens=32_000,
        max_cost_usd=Decimal("2.00"),
    )


def test_profile_resolves_to_one_immutable_route_and_effective_parameters() -> None:
    profile = _profile()
    execution = resolve_execution(profile, _policy())

    assert execution.requested_model == "anthropic/claude-opus-5"
    assert execution.provider_allowlist == ("Anthropic",)
    assert execution.allow_fallbacks is False
    assert execution.profile_revision == 1
    assert execution.effective_parameters.model_dump(exclude_none=True) == {
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 4096,
        "reasoning": {"effort": "high", "exclude": True},
    }

    replacement = resolve_execution(
        _profile(revision=2, model="openai/gpt-5.6", provider="OpenAI"), _policy()
    )
    assert replacement.requested_model == "openai/gpt-5.6"
    assert replacement.provider_allowlist == ("OpenAI",)
    assert replacement.profile_revision == 2
    assert execution.requested_model == "anthropic/claude-opus-5"


def test_gpt_5_6_luna_max_reasoning_is_forwarded_to_openrouter() -> None:
    execution = resolve_execution(
        _profile(
            model="openai/gpt-5.6-luna",
            provider="OpenAI",
            reasoning_effort="max",
        ),
        _policy(),
    )
    model = build_openrouter_chat_model(
        execution,
        api_key="test-secret",
        base_url="https://openrouter.ai/api/v1",
    )

    assert execution.effective_parameters.reasoning is not None
    assert execution.effective_parameters.reasoning.effort == "max"
    assert model.reasoning == {"effort": "max", "exclude": True}


def test_skills_cannot_own_or_switch_the_consultant_model() -> None:
    first = resolve_execution(_profile(), _policy(skills=("task-boundary",)))
    second = resolve_execution(_profile(), _policy(skills=("knowledge", "skill")))

    assert "model" not in RunPolicy.model_fields
    assert "provider" not in RunPolicy.model_fields
    assert first.requested_model == second.requested_model
    assert first.provider_allowlist == second.provider_allowlist


def test_profile_rejects_router_aliases_multiple_providers_and_fallback() -> None:
    with pytest.raises(ValidationError, match="exact model"):
        _profile(model="openrouter/auto")
    with pytest.raises(ValidationError, match="exactly one provider"):
        ConsultantModelProfile(
            profile_id="invalid",
            revision=1,
            requested_model="anthropic/claude-opus-5",
            provider_allowlist=("Anthropic", "Google"),
        )
    with pytest.raises(ValidationError):
        ConsultantModelProfile.model_validate(
            {
                **_profile().model_dump(mode="json"),
                "allow_fallbacks": True,
            }
        )


def test_openrouter_adapter_round_trips_only_resolved_parameters() -> None:
    execution = resolve_execution(_profile(), _policy())
    model = build_openrouter_chat_model(
        execution,
        api_key="test-secret",
        base_url="https://openrouter.ai/api/v1",
    )

    assert model.model_name == execution.requested_model
    assert model.temperature == 0.2
    assert model.top_p == 0.9
    assert model.max_tokens == 4096
    assert model.max_completion_tokens is None
    assert model.reasoning == {"effort": "high", "exclude": True}
    assert model.openrouter_provider == {
        "only": ["Anthropic"],
        "order": ["Anthropic"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert model.request_timeout == 90_000
    assert model.client.sdk_configuration.timeout_ms == 90_000
    assert model.client.sdk_configuration.retry_config is None
    assert model.max_retries == 0
    assert "test-secret" not in repr(model.metadata)


def test_openrouter_adapter_preserves_actual_route_and_cost_metadata() -> None:
    execution = resolve_execution(_profile(), _policy())
    model = build_openrouter_chat_model(
        execution,
        api_key="test-secret",
        base_url="https://openrouter.ai/api/v1",
    )

    result = model._create_chat_result(  # noqa: SLF001 - adapter behavior canary
        {
            "id": "generation-1",
            "object": "chat.completion",
            "created": 1,
            "model": "anthropic/claude-opus-5-20260801",
            "provider": "Anthropic",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "完成"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "cost": 0.0123,
            },
        }
    )

    message = result.generations[0].message
    assert message.response_metadata["provider"] == "Anthropic"
    assert message.response_metadata["model_name"] == (
        "anthropic/claude-opus-5-20260801"
    )
    assert message.response_metadata["cost"] == 0.0123
    assert message.usage_metadata["total_tokens"] == 150


class ProbeResult(BaseModel):
    answer: str


class ToolCapableFakeModel(FakeMessagesListChatModel):
    bound_tool_names: list[str] = []

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ToolCapableFakeModel:
        del tool_choice, kwargs
        self.bound_tool_names = [
            getattr(tool, "name", None)
            or getattr(tool, "__name__", None)
            or tool.get("name", "")
            for tool in tools
        ]
        return self


class RetryThenStructuredModel(ToolCapableFakeModel):
    attempt_count: int = 0

    def _generate(self, *args: Any, **kwargs: Any):
        self.attempt_count += 1
        if self.attempt_count == 1:
            raise TimeoutError("retryable provider timeout")
        return super()._generate(*args, **kwargs)


class RecordingSpan:
    def __init__(self) -> None:
        self.ended = False
        self.recorded_exceptions: list[BaseException] = []

    def set_attribute(self, key: str, value: Any) -> None:
        del key, value

    def record_exception(self, error: BaseException) -> None:
        self.recorded_exceptions.append(error)

    def end(self) -> None:
        self.ended = True


class RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_span(self, name: str) -> RecordingSpan:
        del name
        span = RecordingSpan()
        self.spans.append(span)
        return span


@pytest.mark.asyncio
async def test_agent_uses_structured_output_and_builtin_limits_without_fallback() -> None:
    fake = ToolCapableFakeModel(
        responses=[
            AIMessage(
                content='{"answer":"ok"}',
            )
        ]
    )
    execution = resolve_execution(_profile(), _policy())
    middleware = build_consultant_middleware(model=fake, execution=execution)

    assert any(isinstance(item, ModelCallLimitMiddleware) for item in middleware)
    assert any(isinstance(item, ToolCallLimitMiddleware) for item in middleware)
    assert any(isinstance(item, ModelRetryMiddleware) for item in middleware)
    assert any(isinstance(item, ToolRetryMiddleware) for item in middleware)
    assert any(isinstance(item, SummarizationMiddleware) for item in middleware)
    assert any(isinstance(item, ContextEditingMiddleware) for item in middleware)
    assert not any("Fallback" in type(item).__name__ for item in middleware)

    agent = build_consultant_agent(
        model=fake,
        execution=execution,
        response_schema=ProbeResult,
    )
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="請回傳結構化結果")]}
    )

    assert result["structured_response"] == ProbeResult(answer="ok")
    assert "ProbeResult" not in fake.bound_tool_names


def test_agent_rejects_tools_outside_the_resolved_run_policy() -> None:
    @tool
    def employee_source_get(source_id: str) -> str:
        """Read one employee source by its stable ID."""
        return source_id

    @tool
    def forbidden_shell(command: str) -> str:
        """A tool that must never enter this consultant runtime."""
        return command

    model = ToolCapableFakeModel(responses=[AIMessage(content="unused")])
    execution = resolve_execution(_profile(), _policy())

    build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ProbeResult,
        tools=(employee_source_get,),
    )
    with pytest.raises(ValueError, match="ineligible tools"):
        build_consultant_agent(
            model=model,
            execution=execution,
            response_schema=ProbeResult,
            tools=(forbidden_shell,),
        )


def test_agent_uses_a_normalized_provider_native_output_schema(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def capture_create_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model_runtime, "create_agent", capture_create_agent)
    model = ToolCapableFakeModel(responses=[AIMessage(content="unused")])

    build_consultant_agent(
        model=model,
        execution=resolve_execution(_profile(), _policy()),
        response_schema=ConsultantModelOutput,
    )

    strategy = captured["response_format"]
    assert isinstance(strategy, ProviderStrategy)
    assert strategy.schema_spec.schema is ConsultantModelOutput
    assert strategy.schema_spec.strict is True

    ref_nodes: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_nodes.append(node)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(strategy.schema_spec.json_schema)
    assert "$defs" not in strategy.schema_spec.json_schema
    assert not ref_nodes


@pytest.mark.asyncio
async def test_attempt_callback_records_actual_route_usage_cost_and_error() -> None:
    execution = resolve_execution(_profile(), _policy())
    product_run_id = uuid4()
    recorder = AttemptReceiptCallback(
        product_run_id=product_run_id,
        execution=execution,
    )
    tracer = RecordingTracer()
    recorder._tracer = tracer  # noqa: SLF001 - callback span lifecycle canary
    successful = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="完成",
                response_metadata={
                    "model_name": "anthropic/claude-opus-5-20260801",
                    "provider": "Anthropic",
                    "finish_reason": "stop",
                    "cost": "0.0123",
                },
                usage_metadata={
                    "input_tokens": 120,
                    "output_tokens": 30,
                    "total_tokens": 150,
                },
            )
        ]
    )
    await successful.ainvoke(
        [HumanMessage(content="測試")],
        config={"callbacks": [recorder]},
    )

    assert len(recorder.receipts) == 1
    receipt = recorder.receipts[0]
    assert receipt.product_run_id == product_run_id
    assert receipt.status is AttemptStatus.SUCCEEDED
    assert receipt.requested_model == execution.requested_model
    assert receipt.actual_model == "anthropic/claude-opus-5-20260801"
    assert receipt.actual_provider == "Anthropic"
    assert receipt.usage.total_tokens == 150
    assert receipt.cost_usd == Decimal("0.0123")
    assert receipt.latency_ms >= 0
    assert len(tracer.spans) == 1
    assert tracer.spans[0].ended is True

    failing_recorder = AttemptReceiptCallback(
        product_run_id=product_run_id,
        execution=execution,
    )
    failing_tracer = RecordingTracer()
    failing_recorder._tracer = (  # noqa: SLF001 - payload-free span canary
        failing_tracer
    )

    class TimeoutModel(FakeMessagesListChatModel):
        def _generate(self, *args: Any, **kwargs: Any):
            del args, kwargs
            raise TimeoutError("provider timeout; echoed employee text: SECRET")

    with pytest.raises(TimeoutError, match="provider timeout"):
        await TimeoutModel(responses=[]).ainvoke(
            [HumanMessage(content="測試")],
            config={"callbacks": [failing_recorder]},
        )

    failed = failing_recorder.receipts[0]
    assert failed.status is AttemptStatus.FAILED
    assert failed.error_code == "timeout"
    assert failed.error_message == "model request timed out"
    assert "SECRET" not in failed.model_dump_json()
    assert len(failing_tracer.spans) == 1
    assert failing_tracer.spans[0].recorded_exceptions == []
    assert failing_tracer.spans[0].ended is True


@pytest.mark.asyncio
async def test_framework_retry_emits_one_receipt_per_actual_model_attempt() -> None:
    model = RetryThenStructuredModel(
        responses=[
            AIMessage(
                content='{"answer":"ok"}',
                response_metadata={
                    "model_name": "anthropic/claude-opus-5-20260801",
                    "provider": "Anthropic",
                    "cost": "0.01",
                },
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                },
            )
        ]
    )
    execution = resolve_execution(_profile(), _policy())
    recorder = AttemptReceiptCallback(
        product_run_id=uuid4(),
        execution=execution,
    )
    agent = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ProbeResult,
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="請回傳結構化結果")]},
        config={"callbacks": [recorder]},
    )

    assert result["structured_response"] == ProbeResult(answer="ok")
    assert model.attempt_count == 2
    assert [receipt.status for receipt in recorder.receipts] == [
        AttemptStatus.FAILED,
        AttemptStatus.SUCCEEDED,
    ]
    verify_model_attempts(execution, recorder.receipts)


@pytest.mark.asyncio
async def test_summarization_has_no_hidden_retry_and_each_call_has_a_receipt() -> None:
    summary_message = AIMessage(
        content="只供對話連續性的摘要",
        response_metadata={
            "model_name": "anthropic/claude-opus-5-20260801",
            "provider": "Anthropic",
            "cost": "0.005",
        },
        usage_metadata={
            "input_tokens": 600,
            "output_tokens": 20,
            "total_tokens": 620,
        },
    )
    structured_message = AIMessage(
        content='{"answer":"ok"}',
        response_metadata={
            "model_name": "anthropic/claude-opus-5-20260801",
            "provider": "Anthropic",
            "cost": "0.01",
        },
        usage_metadata={
            "input_tokens": 300,
            "output_tokens": 20,
            "total_tokens": 320,
        },
    )
    model = ToolCapableFakeModel(responses=[summary_message, structured_message])
    execution = resolve_execution(
        _profile(),
        _policy().model_copy(
            update={"summary_trigger_tokens": 512, "summary_keep_messages": 1}
        ),
    )
    recorder = AttemptReceiptCallback(
        product_run_id=uuid4(),
        execution=execution,
    )
    middleware = build_consultant_middleware(model=model, execution=execution)
    summarizer = next(
        item for item in middleware if isinstance(item, SummarizationMiddleware)
    )

    assert summarizer._summary_model is model  # noqa: SLF001 - no hidden retry canary

    agent = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ProbeResult,
    )
    history = [
        HumanMessage(content=f"第 {index} 段員工對話 " + "工作細節" * 120)
        if index % 2 == 0
        else AIMessage(content=f"第 {index} 段顧問回覆 " + "訪談摘要" * 120)
        for index in range(10)
    ]
    result = await agent.ainvoke(
        {"messages": history},
        config={"callbacks": [recorder]},
    )

    assert result["structured_response"] == ProbeResult(answer="ok")
    assert len(recorder.receipts) == 2
    assert all(receipt.status is AttemptStatus.SUCCEEDED for receipt in recorder.receipts)
    assert [receipt.attempt_kind for receipt in recorder.receipts] == [
        AttemptKind.SUMMARIZATION,
        AttemptKind.PRIMARY,
    ]
    verify_model_attempts(execution, recorder.receipts)


def test_post_attempt_budget_fails_closed_before_semantic_commit() -> None:
    execution = resolve_execution(_profile(), _policy())
    now = datetime.now(UTC)
    receipt = AttemptReceipt(
        attempt_id=uuid4(),
        product_run_id=uuid4(),
        status=AttemptStatus.SUCCEEDED,
        requested_model=execution.requested_model,
        provider_allowlist=execution.provider_allowlist,
        profile_id=execution.profile_id,
        profile_revision=execution.profile_revision,
        policy_id=execution.policy_id,
        policy_revision=execution.policy_revision,
        effective_parameters=execution.effective_parameters,
        started_at=now,
        completed_at=now,
        latency_ms=0,
        usage=AttemptUsage(total_tokens=32_001),
        cost_usd=Decimal("2.01"),
    )

    with pytest.raises(ConsultantRunBudgetExceeded) as caught:
        verify_attempt_budget(execution, (receipt,))

    assert set(caught.value.exceeded) == {"total_tokens", "cost_usd"}


def test_model_attempt_verifier_rejects_missing_or_mismatched_route_receipts() -> None:
    execution = resolve_execution(_profile(), _policy())
    now = datetime.now(UTC)
    missing_route = AttemptReceipt(
        attempt_id=uuid4(),
        product_run_id=uuid4(),
        status=AttemptStatus.SUCCEEDED,
        requested_model=execution.requested_model,
        provider_allowlist=execution.provider_allowlist,
        profile_id=execution.profile_id,
        profile_revision=execution.profile_revision,
        policy_id=execution.policy_id,
        policy_revision=execution.policy_revision,
        effective_parameters=execution.effective_parameters,
        started_at=now,
        completed_at=now,
        latency_ms=0,
    )

    with pytest.raises(ConsultantVerificationError, match="actual route"):
        verify_model_attempts(execution, (missing_route,))

    missing_usage = missing_route.model_copy(
        update={
            "attempt_id": uuid4(),
            "actual_model": execution.requested_model,
            "actual_provider": "Anthropic",
            "cost_usd": Decimal("0.01"),
        }
    )
    with pytest.raises(ConsultantVerificationError, match="usage"):
        verify_model_attempts(execution, (missing_usage,))

    missing_cost = missing_usage.model_copy(
        update={
            "attempt_id": uuid4(),
            "usage": AttemptUsage(total_tokens=120),
            "cost_usd": None,
        }
    )
    with pytest.raises(ConsultantVerificationError, match="cost"):
        verify_model_attempts(execution, (missing_cost,))

    mismatched = missing_route.model_copy(
        update={
            "attempt_id": uuid4(),
            "profile_revision": execution.profile_revision + 1,
            "actual_model": execution.requested_model,
            "actual_provider": "Anthropic",
        }
    )
    with pytest.raises(ConsultantVerificationError, match="resolved execution"):
        verify_model_attempts(execution, (mismatched,))
