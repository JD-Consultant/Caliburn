"""
iCAP RAG 節點：根據職稱 + 工作摘要，向量檢索相近 iCAP 職能基準。
三段式信心判斷：
  >= 0.70 → high   → reference mode（iCAP 為主要參考架構）
  >= 0.55 → medium → hybrid mode（iCAP 可參考，補企業自訂）
  <  0.55 → low    → company_defined mode（不套用 iCAP）
"""
import logging

from app.graph.state import InterviewState
from app.services.icap_matcher import confidence_label, match_icap_candidates

logger = logging.getLogger("jobintel")


async def icap_rag_node(state: InterviewState) -> dict:
    match = await match_icap_candidates(
        job_title=state["job_title"],
        department=state.get("department", ""),
        job_summary=state.get("job_summary", ""),
        readiness_detail=state.get("interview_readiness_detail", {}),
    )
    candidates = match["candidates"]
    icap_mode = match["icap_mode"]
    icap_hit = match["icap_hit"]
    top_sim        = candidates[0]["similarity"] if candidates else 0.0
    top_confidence = candidates[0]["confidence"] if candidates else "low"

    logger.info(
        "icap_rag: aggregate_score=%.4f confidence=%s mode=%s hit=%s",
        top_sim, top_confidence, icap_mode, icap_hit,
    )

    return {
        "icap_candidates": candidates,
        "icap_hit":  icap_hit,
        "icap_mode": icap_mode,
        "current_stage": "icap_ref",
        "ai_response": _build_icap_response(candidates, icap_mode),
    }


def _build_icap_response(candidates: list[dict], icap_mode: str) -> str:
    if icap_mode == "company_defined" or not candidates:
        return (
            "系統暫時沒有找到高信心或可參考的 iCAP 職能基準。\n"
            "我們將以**企業自建模式**進行，以 iCAP 欄位結構為骨架，"
            "所有內容完全根據你的實際工作萃取，不引用 iCAP 官方條目。\n\n"
            "請繼續描述你的工作內容。"
        )

    lines = []
    if icap_mode == "reference":
        lines.append(
            "系統找到**高信心**的 iCAP 職能基準，將以此作為**主要參考架構**。\n"
            "知識與技能條目將優先對應 iCAP 官方定義，企業特有內容另行補充。\n"
        )
    else:  # hybrid
        lines.append(
            "系統找到**可參考**的 iCAP 職能基準，將採**混合模式**。\n"
            "通用知識技能參考 iCAP 官方條目，企業特有部分以訪談內容為準。\n"
        )

    for c in candidates:
        conf_badge = {"high": "▲", "medium": "◆", "low": "▽"}.get(c["confidence"], "")
        lines.append(
            f"{conf_badge} **{c.get('confidence_label', confidence_label(c['confidence']))}** "
            f"{c['icap_title']} — {c['recommendation']}"
        )

    lines.append("\n請用自己的話描述你每天最常做的 3 件事，不需要使用正式職務語言。")
    return "\n".join(lines)
