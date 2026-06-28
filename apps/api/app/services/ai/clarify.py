"""Pure clarifier (D28 T6).

Given a ``task`` and the user's current (possibly too-thin) ``note``, decide whether
to ask ONE short follow-up question (Traditional Chinese) before drafting outputs/
indicators. No indexer, no DB.

- no LLM → ``None``.
- LLM path: expect ``{"question": "..." | null}``; return the question string if
  non-blank, else ``None``. Non-dict parse → ``None``.
"""
from __future__ import annotations

from app.core.ports import LlmPort
from app.services.ai import prompts


async def clarify(
    *,
    task: str,
    note: str,
    llm: LlmPort | None,
) -> str | None:
    if llm is None:
        return None

    prompt = prompts.CLARIFY.format(
        task=(task or "").strip() or "（未命名任務）",
        note=(note or "").strip() or "（空）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return None
    question = parsed.get("question")
    if isinstance(question, str) and question.strip():
        return question.strip()
    return None
