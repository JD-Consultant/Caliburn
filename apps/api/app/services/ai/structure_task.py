"""Pure task structurer (D28 T5).

Turn a one-line free-text ``description`` into a concise formal 任務名稱 and a
suggested 職責(unit) grouping name. No indexer, no DB.

- no LLM (or blank description) → ``{"task_name": description.strip(), "unit_suggestion": ""}``.
- LLM path: expect ``{"task_name", "unit_suggestion"}``; if parsed isn't a dict or
  has no usable ``task_name`` → fall back to the description.
"""
from __future__ import annotations

from app.core.ports import LlmPort
from app.services.ai import prompts


def _fallback(description: str) -> dict:
    return {"task_name": (description or "").strip(), "unit_suggestion": ""}


async def structure_task(
    *,
    description: str,
    occupation_context: str,
    llm: LlmPort | None,
) -> dict:
    if llm is None or not (description and description.strip()):
        return _fallback(description)

    prompt = prompts.STRUCTURE_TASK.format(
        description=description.strip(),
        occupation_context=occupation_context or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return _fallback(description)

    task_name = parsed.get("task_name")
    if not (isinstance(task_name, str) and task_name.strip()):
        return _fallback(description)
    unit = parsed.get("unit_suggestion")
    return {
        "task_name": task_name.strip(),
        "unit_suggestion": unit.strip() if isinstance(unit, str) else "",
    }
