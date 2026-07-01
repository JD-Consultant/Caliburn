"""Root occupation-catalog search (ADR 0019).

OCS 目錄是**全域共享**的知識(ARCHITECTURE:租戶隔離只在 api、知識服務全域共享),
故集合放根層、不掛 job-profile 底下——`PUT …/job-profiles/{id}/occupations` 是
「此檔已選職類」,同 URI 掛目錄搜尋會一 URI 兩義(RFC 9110 同 URI 同資源)。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_knowledge
from app.core.ports import KnowledgeClient

logger = logging.getLogger("caliburn")

router = APIRouter(prefix="/occupations", tags=["occupations"])


@router.get("")
async def search_occupations(
    q: str,
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """職類目錄搜尋:`GET /occupations?q=`(List+filter;`q` = Zalando #137 慣例參數),
    回 `{occupations:[{ocs_code, ocs_name}]}`,依 ocs_code 去重保序。
    search-only collection(indexer 無 list-all):空白 q 回空。不分頁(目錄有界、
    去重後 ≤ top_k;F6 YAGNI)。**critical 端點**(ADR 0018):indexer 掛回 502 快錯。"""
    if not q.strip():
        return {"occupations": []}
    try:
        res = await knowledge.search_occupations(q, top_k=8)
    except Exception:
        logger.warning("occupations search: indexer query failed", exc_info=True)
        raise HTTPException(status_code=502, detail="indexer unavailable")
    seen: dict[str, dict] = {}
    for h in res.hits:
        if h.ocs_code and h.ocs_code not in seen:
            seen[h.ocs_code] = {"ocs_code": h.ocs_code, "ocs_name": h.ocs_name or h.ocs_code}
    return {"occupations": list(seen.values())}
