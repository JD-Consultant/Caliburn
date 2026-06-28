"""Pure K/S recommender (D28 T2).

Given a task's official catalog K/S candidates + an optional note + an optional
``LlmPort``, return ``{"knowledge": [...], "skills": [...]}`` where each item is
``{code, name, source, reason?}``.

- no note OR no LLM  → full catalog, ``source="catalog"`` (no reason).
- note + LLM         → LLM filters/ranks catalog codes and gives a one-line reason;
                       items are mapped back to catalog names (``source="catalog"``).
- LLM unusable/empty → fall back to full catalog (panel is never left empty).

Candidates are ``[{"code": str, "name": str}, ...]``; the indexer is grounded so
recommendations stay within the catalog (no AI-invented codes).
"""
from __future__ import annotations

from app.core.ports import LlmPort
from app.services.ai import prompts


def _catalog_all(k_candidates: list[dict], s_candidates: list[dict]) -> dict:
    return {
        "knowledge": [
            {"code": c.get("code", ""), "name": c.get("name", ""), "source": "catalog"}
            for c in k_candidates
        ],
        "skills": [
            {"code": c.get("code", ""), "name": c.get("name", ""), "source": "catalog"}
            for c in s_candidates
        ],
    }


def _pick(items, by_code: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        code = it.get("code") or ""
        if code in by_code and code not in seen:
            seen.add(code)
            entry = {"code": code, "name": by_code[code], "source": "catalog"}
            reason = (it.get("reason") or "").strip()
            if reason:
                entry["reason"] = reason
            out.append(entry)
    return out


async def recommend_ks(
    *,
    task_name: str,
    note: str | None,
    k_candidates: list[dict],
    s_candidates: list[dict],
    llm: LlmPort | None,
) -> dict:
    if not (note and note.strip()) or llm is None:
        return _catalog_all(k_candidates, s_candidates)

    k_by_code = {c["code"]: c.get("name", "") for c in k_candidates if c.get("code")}
    s_by_code = {c["code"]: c.get("name", "") for c in s_candidates if c.get("code")}
    prompt = prompts.RECOMMEND_KS.format(
        task_name=task_name or "（未命名任務）",
        note=note.strip(),
        k_list="\n".join(f"- {c.get('code', '')} {c.get('name', '')}" for c in k_candidates) or "（無）",
        s_list="\n".join(f"- {c.get('code', '')} {c.get('name', '')}" for c in s_candidates) or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return _catalog_all(k_candidates, s_candidates)

    k = _pick(parsed.get("knowledge"), k_by_code)
    s = _pick(parsed.get("skills"), s_by_code)
    if not k and not s:
        return _catalog_all(k_candidates, s_candidates)
    return {"knowledge": k, "skills": s}
