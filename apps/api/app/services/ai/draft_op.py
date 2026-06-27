"""Pure outputs/indicators drafter (D28 T3).

Given a task's official catalog outputs + activity-example indicators + an optional
note + an optional ``LlmPort``, return
``{"outputs": [{"name", "source"}], "indicators": [{"text", "source"}]}``.

- no note OR no LLM  → full catalog, ``source="catalog"``.
- note + LLM         → LLM personalises/rewrites outputs + indicators, ``source="ai"``.
- LLM unusable/empty → fall back to the catalog branch (panel is never left empty,
                       except when the catalog itself is empty — the "太薄回空" case).
"""
from __future__ import annotations

from app.graph_v3.deps import LlmPort
from app.services.ai import prompts


def _catalog_all(outputs_catalog: list[str], indicators_catalog: list[str]) -> dict:
    return {
        "outputs": [{"name": n, "source": "catalog"} for n in outputs_catalog],
        "indicators": [{"text": t, "source": "catalog"} for t in indicators_catalog],
    }


def _strs(items) -> list[str]:
    out: list[str] = []
    for it in items or []:
        if isinstance(it, str) and it.strip():
            out.append(it.strip())
    return out


async def draft_op(
    *,
    task_name: str,
    note: str | None,
    outputs_catalog: list[str],
    indicators_catalog: list[str],
    llm: LlmPort | None,
) -> dict:
    if not (note and note.strip()) or llm is None:
        return _catalog_all(outputs_catalog, indicators_catalog)

    prompt = prompts.DRAFT_OP.format(
        task_name=task_name or "（未命名任務）",
        note=note.strip(),
        outputs_ref="\n".join(f"- {o}" for o in outputs_catalog) or "（無）",
        indicators_ref="\n".join(f"- {i}" for i in indicators_catalog) or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return _catalog_all(outputs_catalog, indicators_catalog)

    outputs = _strs(parsed.get("outputs"))
    indicators = _strs(parsed.get("indicators"))
    if not outputs and not indicators:
        return _catalog_all(outputs_catalog, indicators_catalog)
    return {
        "outputs": [{"name": n, "source": "ai"} for n in outputs],
        "indicators": [{"text": t, "source": "ai"} for t in indicators],
    }
