import asyncio
import logging

from langchain_core.messages import HumanMessage

from app.graph.llm import get_chat_llm
from app.utils import safe_parse_json

logger = logging.getLogger("jobintel")

_MISSING = object()


class LLMGateway:
    """LLM wrapper that adds retry on network errors and JSON parse failures."""

    def __init__(self, temperature: float = 0.3, retries: int = 2):
        self._temperature = temperature
        self._retries = retries

    async def invoke_text(self, messages: list) -> str:
        llm = get_chat_llm(self._temperature)
        for attempt in range(self._retries):
            try:
                resp = await llm.ainvoke(messages)
                return resp.content
            except Exception as exc:
                if attempt < self._retries - 1:
                    logger.warning(
                        "LLMGateway: attempt %d/%d error: %s", attempt + 1, self._retries, exc
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error("LLMGateway: all %d attempts failed: %s", self._retries, exc)
        return ""

    async def invoke_json(self, prompt: str, default):
        """Call LLM with a single user message and parse JSON; retries on parse failure."""
        for attempt in range(self._retries):
            text = await self.invoke_text([HumanMessage(content=prompt)])
            result = safe_parse_json(text, default=_MISSING)
            if result is not _MISSING:
                return result
            if attempt < self._retries - 1:
                logger.warning(
                    "LLMGateway: JSON parse failed (attempt %d/%d), retrying",
                    attempt + 1, self._retries,
                )
                await asyncio.sleep(0.5)
        logger.error("LLMGateway: JSON parse exhausted after %d attempts", self._retries)
        return default
