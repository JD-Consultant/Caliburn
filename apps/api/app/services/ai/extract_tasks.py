"""Pure task extractor (D28 T4).

Given an employee's free-text self-description (``intake``) + a candidate task list
from the occupation catalog (``[{"id", "title"}]``) + an optional ``LlmPort``, return
``{"suggested_task_ids": [str], "custom_candidates": [{"name": str}]}``.

- no LLM, OR (no candidates AND no intake) → empty result.
- LLM path: the model picks catalog task ids it likely performs and proposes any
  clearly-mentioned tasks NOT in the list as custom candidates (names only).
  suggested ids are grounded to the candidate list (AI-invented ids dropped);
  custom candidate strings → ``[{"name": s}]``.
- LLM unusable / non-dict → empty result.
"""
from __future__ import annotations

from app.graph_v3.deps import LlmPort
from app.services.ai import prompts

_EMPTY = {"suggested_task_ids": [], "custom_candidates": []}


async def extract_tasks(
    *,
    intake: str,
    candidates: list[dict],
    llm: LlmPort | None,
) -> dict:
    if llm is None or (not candidates and not (intake and intake.strip())):
        return dict(_EMPTY)

    known = {c.get("id") for c in candidates if c.get("id")}
    prompt = prompts.EXTRACT_TASKS.format(
        intake=(intake or "").strip() or "（無）",
        candidate_list="\n".join(
            f"- {c.get('id', '')} {c.get('title', '')}" for c in candidates
        ) or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return dict(_EMPTY)

    suggested = [
        i
        for i in (parsed.get("suggested_task_ids") or [])
        if isinstance(i, str) and i in known
    ]
    customs = [
        {"name": s.strip()}
        for s in (parsed.get("custom_candidates") or [])
        if isinstance(s, str) and s.strip()
    ]
    return {"suggested_task_ids": suggested, "custom_candidates": customs}
