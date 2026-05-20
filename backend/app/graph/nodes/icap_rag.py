"""
iCAP RAG 節點：根據職稱 + 工作摘要，向量檢索相近 iCAP 職能基準。
三段式信心判斷：
  >= 0.70 → high   → reference mode（iCAP 為主要參考架構）
  >= 0.55 → medium → hybrid mode（iCAP 部分參考，補企業自訂）
  <  0.55 → low    → company_defined mode（不套用 iCAP）
"""
import json
import logging

from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal
from app.graph.llm import get_embeddings
from app.graph.state import InterviewState

logger = logging.getLogger("jobintel")

_HIGH_THRESHOLD = settings.icap_high_threshold    # 0.70 → reference
_MED_THRESHOLD  = settings.icap_medium_threshold  # 0.55 → hybrid


def _confidence(sim: float) -> str:
    if sim >= _HIGH_THRESHOLD:
        return "high"
    if sim >= _MED_THRESHOLD:
        return "medium"
    return "low"


def _mode(confidence: str) -> str:
    return {"high": "reference", "medium": "hybrid", "low": "company_defined"}[confidence]


def _recommendation(sim: float) -> str:
    if sim >= _HIGH_THRESHOLD:
        return "建議參考"
    if sim >= _MED_THRESHOLD:
        return "部分參考"
    return "低信心"


async def icap_rag_node(state: InterviewState) -> dict:
    query = f"{state['job_title']} {state['department']} {state['job_summary']}"

    logger.info("icap_rag: querying for '%s'", query[:60])
    query_vector = await get_embeddings().aembed_query(query)
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    candidates = await _search_icap(vector_literal)

    top_sim        = candidates[0]["similarity"] if candidates else 0.0
    top_confidence = _confidence(top_sim)
    icap_mode      = _mode(top_confidence)
    icap_hit       = top_confidence in ("high", "medium")

    logger.info(
        "icap_rag: top_sim=%.4f confidence=%s mode=%s hit=%s",
        top_sim, top_confidence, icap_mode, icap_hit,
    )

    return {
        "icap_candidates": candidates,
        "icap_hit":  icap_hit,
        "icap_mode": icap_mode,
        "current_stage": "icap_ref",
        "ai_response": _build_icap_response(candidates, icap_mode),
    }


async def _search_icap(vector_literal: str) -> list[dict]:
    sql = text("""
        WITH deduped AS (
            SELECT DISTINCT ON (ocs_code)
                id                                                  AS icap_id,
                ocs_code,
                chunk_text,
                metadata,
                1 - (embedding <=> CAST(:vec AS vector))           AS similarity
            FROM icap_embeddings
            WHERE chunk_type = 'competency'
            ORDER BY ocs_code, embedding <=> CAST(:vec AS vector)
        )
        SELECT * FROM deduped
        ORDER BY similarity DESC
        LIMIT :k
    """)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sql,
            {"vec": vector_literal, "k": settings.icap_top_k},
        )
        rows = result.fetchall()

    candidates = []
    for row in rows:
        meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")

        def _norm(items: list) -> list[dict]:
            return [i if isinstance(i, dict) else {"name": i} for i in items]

        sim = round(float(row.similarity), 4)
        candidates.append({
            "icap_id":        str(row.icap_id),
            "ocs_code":       row.ocs_code,
            "icap_title":     meta.get("occupation_name", row.ocs_code),
            "similarity":     sim,
            "confidence":     _confidence(sim),
            "match_reason":   row.chunk_text[:120],
            "job_categories": _norm(meta.get("job_categories", [])),
            "occupations":    _norm(meta.get("occupations", [])),
            "industries":     _norm(meta.get("industries", [])),
            "notes":          meta.get("notes", ""),
            "recommendation": _recommendation(sim),
        })

    return candidates


def _build_icap_response(candidates: list[dict], icap_mode: str) -> str:
    if icap_mode == "company_defined" or not candidates:
        return (
            "系統在 iCAP 職能基準庫中找不到可靠的對應職務。\n"
            "我們將以**企業自建模式**進行，以 iCAP 欄位結構為骨架，"
            "所有內容完全根據你的實際工作萃取，不引用 iCAP 官方條目。\n\n"
            "請繼續描述你的工作內容。"
        )

    lines = []
    if icap_mode == "reference":
        lines.append(
            "系統找到高度相符的 iCAP 職能基準，將以此作為**主要參考架構**。\n"
            "知識與技能條目將優先對應 iCAP 官方定義，企業特有內容另行補充。\n"
        )
    else:  # hybrid
        lines.append(
            "系統找到部分相符的 iCAP 職能基準，將採**混合模式**。\n"
            "通用知識技能參考 iCAP 官方條目，企業特有部分以訪談內容為準。\n"
        )

    for c in candidates:
        conf_badge = {"high": "▲", "medium": "◆", "low": "▽"}.get(c["confidence"], "")
        lines.append(
            f"{conf_badge} **{int(c['similarity'] * 100)}%** {c['icap_title']} — {c['recommendation']}"
        )

    lines.append("\n請用自己的話描述你每天最常做的 3 件事，不需要使用正式職務語言。")
    return "\n".join(lines)
