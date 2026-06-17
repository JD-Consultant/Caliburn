"""v3 收尾節點：assemble_ksa（catalog K/S/A + 公司補充，interrupt 編輯）。
deterministic：K/S/A 來自 indexer pairs()，不用 LLM/不用 pgvector RAG（D13）。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState

logger = logging.getLogger("jobintel")


def _pairs_to_items(pairs_list) -> list[dict]:
    """Pair{code,name} → draft item（catalog 來源，icap_ref=code）。"""
    return [{"content": p.name, "source": "catalog", "icap_ref": p.code or None}
            for p in pairs_list if p.name]


async def assemble_ksa(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pairs = await deps.knowledge.pairs(ocs) if ocs else None

    draft = {
        "knowledge": _pairs_to_items(pairs.knowledge) if pairs else [],
        "skills": _pairs_to_items(pairs.skills) if pairs else [],
        "attitudes": _pairs_to_items(pairs.attitudes) if pairs else [],
    }

    edited = interrupt({"kind": "edit_ksa", "ksa": draft})
    ksa = edited.get("ksa", draft) if isinstance(edited, dict) else draft

    await deps.persist.flush_ksa(state["job_profile_id"], ksa)
    logger.info("assemble_ksa: flushed K=%d S=%d A=%d",
                len(ksa["knowledge"]), len(ksa["skills"]), len(ksa["attitudes"]))
    return {"ksa": ksa, "current_step": "build_doc"}
