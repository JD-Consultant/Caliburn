"""OpenRouter LLM gateway（D10）：per-role 模型分層 + JSON 解析重試。
OpenRouter 為 OpenAI 相容端點 → 用 langchain_openai.ChatOpenAI(base_url=...)。"""
import asyncio
import logging
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.graph_v3.tracing import get_tracer
from app.utils import safe_parse_json

logger = logging.getLogger("jobintel")

_MISSING = object()


def model_for_role(role: str) -> str:
    return {
        "deep": settings.model_deep,
        "indicator": settings.model_indicator,
        "cheap": settings.model_cheap,
    }.get(role, settings.model_cheap)


@lru_cache(maxsize=8)
def _build_chat(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
    )


def get_chat_llm(role: str, temperature: float = 0.2) -> ChatOpenAI:
    return _build_chat(model_for_role(role), temperature)


class OpenRouterLlm:
    """LlmPort 實作（網路）。retries 涵蓋網路錯誤與 JSON 解析失敗。
    Note: ``complete_json`` wraps ``complete_text``, so a fully-failing
    ``complete_json`` call performs up to ``retries * retries`` underlying
    network attempts (e.g. 4 with the default ``retries=2``)."""

    def __init__(self, retries: int = 2):
        self._retries = retries

    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str:
        llm = get_chat_llm(role)
        model = model_for_role(role)
        for attempt in range(self._retries):
            try:
                with get_tracer().start_as_current_span("gen_ai.chat") as span:
                    span.set_attribute("gen_ai.system", "openrouter")
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.request.model", model)
                    resp = await llm.ainvoke([HumanMessage(content=prompt)])
                    um = getattr(resp, "usage_metadata", None) or {}
                    if um.get("input_tokens") is not None:
                        span.set_attribute("gen_ai.usage.input_tokens", um["input_tokens"])
                    if um.get("output_tokens") is not None:
                        span.set_attribute("gen_ai.usage.output_tokens", um["output_tokens"])
                content = resp.content
                return content if isinstance(content, str) else str(content)
            except Exception as exc:  # noqa: BLE001
                if attempt < self._retries - 1:
                    logger.warning("OpenRouterLlm text attempt %d failed: %s", attempt + 1, exc)
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error("OpenRouterLlm text exhausted: %s", exc)
        return ""

    async def complete_json(self, prompt: str, *, role: str = "cheap", default=None):
        for attempt in range(self._retries):
            text = await self.complete_text(prompt, role=role)
            parsed = safe_parse_json(text, default=_MISSING)
            if parsed is not _MISSING:
                return parsed
            if attempt < self._retries - 1:
                await asyncio.sleep(0.3)
        return default
