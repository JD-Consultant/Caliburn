"""OpenRouter LLM gateway（D10）：per-role 模型分層 + JSON 解析重試。
OpenRouter 為 OpenAI 相容端點 → 用 langchain_openai.ChatOpenAI(base_url=...)。

select_schema(ADR 0024,T7):受限解碼路——直用 openai SDK 帶 response_format
json_schema+strict(spike 結論:port 吃「動態 raw schema」(池 id per-request 鎖 enum),
openai SDK 直傳最貼;Pydantic AI 的 NativeOutput 以型別類為中心,動態 enum 反而繞
——紀錄見 docs/specs/2026-07-05-select-schema-acceptance.md)。底層模型須原生支援
strict(settings.model_select;OpenRouter 對不支援者直接報錯,不靜默降級)。"""
import asyncio
import json
import logging
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.config import settings
from app.observability import GEN_AI_PROVIDER_ATTR, get_tracer
from app.utils import safe_parse_json

logger = logging.getLogger("caliburn")

_MISSING = object()


class LlmSchemaError(Exception):
    """select_schema 重試後仍失敗(網路/provider 不支援/回非 JSON)——route 轉 502/503。"""


def model_for_role(role: str) -> str:
    return {
        "deep": settings.model_deep,
        "indicator": settings.model_indicator,
        "cheap": settings.model_cheap,
        "select": settings.model_select,
        "interview": settings.model_interview,
    }.get(role, settings.model_cheap)


def schema_response_format(schema_name: str, schema: dict) -> dict:
    """OpenAI 相容 response_format(json_schema+strict)——純建構,可測。"""
    return {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
    }


@lru_cache(maxsize=1)
def _async_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openrouter_api_key,
                       base_url=settings.openrouter_base_url)


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
                # span 名照 semconv:`{operation} {model}`(spec: gen-ai-spans.md)
                with get_tracer().start_as_current_span(f"chat {model}") as span:
                    span.set_attribute(GEN_AI_PROVIDER_ATTR, "openrouter")
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.request.model", model)
                    resp = await llm.ainvoke([HumanMessage(content=prompt)])
                    um = getattr(resp, "usage_metadata", None) or {}
                    if um.get("input_tokens") is not None:
                        span.set_attribute("gen_ai.usage.input_tokens", um["input_tokens"])
                    if um.get("output_tokens") is not None:
                        span.set_attribute("gen_ai.usage.output_tokens", um["output_tokens"])
                    meta = getattr(resp, "response_metadata", None) or {}
                    if meta.get("model_name"):
                        span.set_attribute("gen_ai.response.model", meta["model_name"])
                    if meta.get("finish_reason"):
                        span.set_attribute("gen_ai.response.finish_reasons",
                                           [meta["finish_reason"]])
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

    async def chat_with_tools(self, *, role: str, messages: list[dict], tools: list[dict],
                              dispatch, max_tool_iterations: int = 5):
        """顧問 agent 手刻工具迴圈(ADR 0027 §4.2)。tools=OpenAI 工具定義;
        dispatch(name,args)->dict 執行 READ 工具。迴圈邏輯在 agent_loop.run_tool_loop
        (可測);此處只提供真實 OpenAI 呼叫(tool_choice=auto)。回 ChatResult。"""
        from app.interview.agent_loop import run_tool_loop

        model = model_for_role(role)

        async def call_once(msgs: list[dict], with_tools: bool) -> dict:
            kwargs: dict = {"model": model, "messages": msgs,
                            "temperature": 0.4, "max_tokens": 1024}
            if with_tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"      # 不強制(§8.5:強制會虛構輸入)
            with get_tracer().start_as_current_span(f"chat {model}") as span:
                span.set_attribute(GEN_AI_PROVIDER_ATTR, "openrouter")
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.request.model", model)
                resp = await _async_client().chat.completions.create(**kwargs)
                if getattr(resp, "model", None):
                    span.set_attribute("gen_ai.response.model", resp.model)
                usage = getattr(resp, "usage", None)
                if usage is not None:
                    span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
                    span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)
                fr = resp.choices[0].finish_reason
                if fr:
                    span.set_attribute("gen_ai.response.finish_reasons", [fr])
            m = resp.choices[0].message
            return {"content": m.content, "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in (m.tool_calls or [])]}

        return await run_tool_loop(call_once=call_once, dispatch=dispatch,
                                   messages=messages, max_tool_iterations=max_tool_iterations)

    async def select_schema(self, prompt: str, schema: dict, *,
                            role: str = "select", schema_name: str = "output"):
        """受限解碼:輸出必須符合 schema(ADR 0024)。失敗重試後 raise LlmSchemaError
        (與 complete_* 的靜默降級**刻意不同**——值承重路線失敗必須顯式,不能默默變提示層)。"""
        model = model_for_role(role)
        last_err: Exception | None = None
        for attempt in range(self._retries):
            try:
                with get_tracer().start_as_current_span(f"chat {model}") as span:
                    span.set_attribute(GEN_AI_PROVIDER_ATTR, "openrouter")
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.request.model", model)
                    resp = await _async_client().chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format=schema_response_format(schema_name, schema),
                        temperature=0,
                        # 驗收發現:被誘導輸出非法值時,受限解碼會逼出失控長輸出直到截斷
                        # (fail-closed 無逃逸,但燒 token)——上限鎖住成本;截斷=非法 JSON=照樣炸。
                        max_tokens=2048,
                    )
                    if getattr(resp, "model", None):
                        span.set_attribute("gen_ai.response.model", resp.model)
                    usage = getattr(resp, "usage", None)
                    if usage is not None:
                        span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
                        span.set_attribute("gen_ai.usage.output_tokens",
                                           usage.completion_tokens)
                    fr = resp.choices[0].finish_reason
                    if fr:
                        span.set_attribute("gen_ai.response.finish_reasons", [fr])
                content = resp.choices[0].message.content or ""
                return json.loads(content)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < self._retries - 1:
                    logger.warning("select_schema attempt %d failed: %s", attempt + 1, exc)
                    await asyncio.sleep(0.5 * (attempt + 1))
        logger.error("select_schema exhausted: %s", last_err)
        raise LlmSchemaError(str(last_err))
