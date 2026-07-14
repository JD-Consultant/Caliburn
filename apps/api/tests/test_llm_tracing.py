"""LLM client 層 span(T6;semconv-genai:span 名 `{operation} {model}`,
`gen_ai.system` 已棄用 → `gen_ai.provider.name`,finish_reasons=string[])。"""
import asyncio
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langchain_core.messages import AIMessage

from app.config import settings
from app.adapters import llm_openrouter as llm_mod
from app.observability import setup_tracing


class _FakeChat:
    async def ainvoke(self, msgs):
        return AIMessage(
            content="嗨",
            usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18,
                            "input_token_details": {"cache_read": 8}},
            response_metadata={"model_name": "vendor/mid-2026", "finish_reason": "stop"},
        )


def test_complete_text_emits_gen_ai_span(monkeypatch):
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    settings.model_indicator = "vendor/mid"
    monkeypatch.setattr(llm_mod, "get_chat_llm", lambda role, temperature=0.2: _FakeChat())

    out = asyncio.run(llm_mod.OpenRouterLlm().complete_text("p", role="indicator"))
    assert out == "嗨"
    span = next(s for s in exp.get_finished_spans() if s.name == "chat vendor/mid")
    assert "gen_ai.system" not in span.attributes          # deprecated 名不得再用
    assert span.attributes["gen_ai.provider.name"] == "openrouter"
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.request.model"] == "vendor/mid"
    assert span.attributes["gen_ai.response.model"] == "vendor/mid-2026"
    assert span.attributes["gen_ai.usage.input_tokens"] == 11
    assert span.attributes["gen_ai.usage.output_tokens"] == 7
    assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 8
    assert list(span.attributes["gen_ai.response.finish_reasons"]) == ["stop"]
