"""Pure outputs/indicators drafter (D28 T3).

Given a task's official catalog outputs + activity-example indicators (each a dict
with ``code`` + ``name``/``text``) + an optional note + an optional ``LlmPort``, return
``{"outputs": [{"code", "name", "source"}], "indicators": [{"code", "text", "source"}]}``.
Catalog items keep their source ``code`` (2b provenance identity); AI drafts have ``code=""``.

- no note OR no LLM  → full catalog, ``source="catalog"``.
- note + LLM         → LLM personalises/rewrites outputs + indicators, ``source="ai"``.
- LLM unusable/empty → fall back to the catalog branch (panel is never left empty,
                       except when the catalog itself is empty — the "太薄回空" case).
"""
from __future__ import annotations

from app.core.ports import LlmPort
from app.services.ai import prompts


def _catalog_all(outputs_catalog: list[dict], indicators_catalog: list[dict]) -> dict:
    return {
        "outputs": [{"code": o.get("code", ""), "name": o.get("name", ""), "source": "catalog"}
                    for o in outputs_catalog],
        "indicators": [{"code": p.get("code", ""), "text": p.get("text", ""), "source": "catalog"}
                       for p in indicators_catalog],
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
    outputs_catalog: list[dict],
    indicators_catalog: list[dict],
    llm: LlmPort | None,
) -> dict:
    if not (note and note.strip()) or llm is None:
        return _catalog_all(outputs_catalog, indicators_catalog)

    prompt = prompts.DRAFT_OP.format(
        task_name=task_name or "（未命名任務）",
        note=note.strip(),
        outputs_ref="\n".join(f"- {o.get('name', '')}" for o in outputs_catalog) or "（無）",
        indicators_ref="\n".join(f"- {p.get('text', '')}" for p in indicators_catalog) or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return _catalog_all(outputs_catalog, indicators_catalog)

    outputs = _strs(parsed.get("outputs"))
    indicators = _strs(parsed.get("indicators"))
    if not outputs and not indicators:
        return _catalog_all(outputs_catalog, indicators_catalog)
    # AI 個人化產出非官方 catalog 項 → 無來源碼（code=""）。
    return {
        "outputs": [{"code": "", "name": n, "source": "ai"} for n in outputs],
        "indicators": [{"code": "", "text": t, "source": "ai"} for t in indicators],
    }
