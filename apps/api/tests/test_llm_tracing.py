import asyncio
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langchain_core.messages import AIMessage

from app.config import settings
from app.adapters import llm_openrouter as llm_mod
from app.graph_v3.tracing import setup_tracing


class _FakeChat:
    async def ainvoke(self, msgs):
        return AIMessage(content="嗨", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})


def test_complete_text_emits_gen_ai_span(monkeypatch):
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    settings.model_indicator = "vendor/mid"
    monkeypatch.setattr(llm_mod, "get_chat_llm", lambda role, temperature=0.2: _FakeChat())

    out = asyncio.run(llm_mod.OpenRouterLlm().complete_text("p", role="indicator"))
    assert out == "嗨"
    span = next(s for s in exp.get_finished_spans() if s.name == "gen_ai.chat")
    assert span.attributes["gen_ai.system"] == "openrouter"
    assert span.attributes["gen_ai.request.model"] == "vendor/mid"
    assert span.attributes["gen_ai.usage.input_tokens"] == 11
    assert span.attributes["gen_ai.usage.output_tokens"] == 7
