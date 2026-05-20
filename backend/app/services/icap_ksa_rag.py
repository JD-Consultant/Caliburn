"""Query pgvector for iCAP chunks at multiple granularity levels."""
import logging

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.graph.llm import get_embeddings

logger = logging.getLogger("jobintel")

_THRESHOLD = 0.58


async def _search_ksa(
    query: str,
    chunk_type: str,
    code_key: str,
    top_k: int,
    ocs_code_filter: str | None = None,
) -> list[dict]:
    query_vector = await get_embeddings().aembed_query(query)
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    # Optionally narrow to a specific OCS code (more targeted, avoids cross-standard noise)
    ocs_filter_clause = "AND ocs_code = :ocs_code" if ocs_code_filter else ""

    sql = text(f"""
        WITH deduped AS (
            SELECT DISTINCT ON (metadata->>:code_key)
                chunk_text,
                metadata,
                1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM icap_embeddings
            WHERE chunk_type = :chunk_type
              AND metadata->>:code_key IS NOT NULL
              AND metadata->>:code_key != ''
              {ocs_filter_clause}
            ORDER BY metadata->>:code_key, embedding <=> CAST(:vec AS vector)
        )
        SELECT * FROM deduped
        WHERE similarity >= :threshold
        ORDER BY similarity DESC
        LIMIT :k
    """)

    params: dict = {
        "vec": vector_literal,
        "chunk_type": chunk_type,
        "code_key": code_key,
        "threshold": _THRESHOLD,
        "k": top_k,
    }
    if ocs_code_filter:
        params["ocs_code"] = ocs_code_filter

    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, params)
        rows = result.fetchall()

    items = []
    for row in rows:
        meta = row.metadata if isinstance(row.metadata, dict) else {}
        first_line = row.chunk_text.split("\n")[0]
        name = first_line.split("：", 1)[-1].strip() if "：" in first_line else first_line
        items.append({
            "code":      meta.get(code_key, ""),
            "name":      name,
            "ocs_code":  meta.get("ocs_code", ""),
            "similarity": round(float(row.similarity), 4),
        })
    return items


# ── K/S/A (used by ocs_builder) ───────────────────────────────────────────────

async def search_knowledge(query: str, top_k: int = 1) -> list[dict]:
    return await _search_ksa(query, "knowledge", "knowledge_code", top_k)


async def search_skills(query: str, top_k: int = 1) -> list[dict]:
    return await _search_ksa(query, "skill", "skill_code", top_k)


async def search_attitudes(query: str, top_k: int = 1) -> list[dict]:
    return await _search_ksa(query, "attitude", "attitude_code", top_k)


# ── Task / Indicator / Output (multi-granularity RAG) ─────────────────────────

async def search_tasks(
    query: str,
    top_k: int = 3,
    ocs_code_filter: str | None = None,
) -> list[dict]:
    """Search iCAP task chunks. Filter by ocs_code for targeted lookup."""
    return await _search_ksa(query, "task", "task_code", top_k, ocs_code_filter)


async def search_indicators(
    query: str,
    top_k: int = 3,
    ocs_code_filter: str | None = None,
) -> list[dict]:
    """Search iCAP behavior indicator chunks."""
    return await _search_ksa(query, "indicator", "indicator_code", top_k, ocs_code_filter)


async def search_outputs(
    query: str,
    top_k: int = 3,
    ocs_code_filter: str | None = None,
) -> list[dict]:
    """Search iCAP work output chunks."""
    return await _search_ksa(query, "output", "output_code", top_k, ocs_code_filter)
