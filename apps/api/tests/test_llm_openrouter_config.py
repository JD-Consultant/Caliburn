"""T13(ADR 0030):OpenRouter 顯式設定——require_parameters 請求體、models 備援、
parallel_tool_calls、fallback 觸發記 trace、Retry-After 尊重。"""
import asyncio
from types import SimpleNamespace

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.adapters import llm_openrouter as llm_mod
from app.adapters.llm_openrouter import (
    _record_usage, _retry_after_seconds, openrouter_extra_body,
)
from app.config import settings
from app.observability import get_tracer, setup_tracing


def test_extra_body_always_requires_parameters():
    body = openrouter_extra_body("cheap")
    assert body["provider"] == {"allow_fallbacks": True, "require_parameters": True}
    assert "models" not in body                      # 無備援=不帶 models


def test_extra_body_models_fallback_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "model_interview_fallback", "openai/gpt-4.1")
    body = openrouter_extra_body("interview")
    assert body["models"] == [settings.model_interview, "openai/gpt-4.1"]


def test_chat_with_tools_request_body(monkeypatch):
    """請求體斷言:parallel_tool_calls=True + extra_body(provider/require_parameters)。"""
    captured: dict = {}

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            msg = SimpleNamespace(content="好的?", tool_calls=None)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                model=kwargs["model"], usage=None)

    fake = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    monkeypatch.setattr(llm_mod, "_async_client", lambda: fake)

    async def dispatch(name, args):
        return {}

    out = asyncio.run(llm_mod.OpenRouterLlm().chat_with_tools(
        role="interview", messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
        dispatch=dispatch))
    assert out.text == "好的?"
    assert captured["parallel_tool_calls"] is True
    assert captured["extra_body"]["provider"]["require_parameters"] is True


def test_record_usage_marks_fallback_and_cache():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    resp = SimpleNamespace(
        model="openai/gpt-4.1",                       # ≠ 請求模型 → fallback 觸發
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=9,
                              prompt_tokens_details=SimpleNamespace(cached_tokens=64)),
        choices=[SimpleNamespace(finish_reason="stop")])
    with get_tracer().start_as_current_span("chat x") as span:
        _record_usage(span, "openai/gpt-4.1-mini", resp)
    (s,) = exp.get_finished_spans()
    assert s.attributes["caliburn.llm.fallback_triggered"] is True
    assert s.attributes["gen_ai.response.model"] == "openai/gpt-4.1"
    assert s.attributes["gen_ai.usage.cache_read.input_tokens"] == 64


def test_retry_after_parsed_and_fallback_to_none():
    exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "2.5"}))
    assert _retry_after_seconds(exc) == 2.5
    assert _retry_after_seconds(SimpleNamespace(response=None)) is None
    bad = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "soon"}))
    assert _retry_after_seconds(bad) is None
