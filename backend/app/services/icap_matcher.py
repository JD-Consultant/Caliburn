"""Multi-granularity iCAP matching.

This service ranks iCAP standards by combining evidence from profile-level
chunks and task-level chunks. The score remains a retrieval confidence signal,
not a human-readable percentage.
"""
import asyncio
import json
import logging
from dataclasses import dataclass

from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal
from app.graph.llm import get_embeddings

logger = logging.getLogger("jobintel")

_PROFILE_SPECS = (
    ("competency", 0.75),
    ("unit", 0.25),
)

_TASK_AWARE_SPECS = (
    ("competency", 0.45),
    ("unit", 0.15),
    ("task", 0.20),
    ("output", 0.10),
    ("indicator", 0.10),
)

_CHUNK_LABEL = {
    "competency": "職務描述",
    "unit": "職能單元",
    "task": "工作任務",
    "output": "工作產出",
    "indicator": "行為指標",
}


@dataclass(frozen=True)
class _SearchSpec:
    chunk_type: str
    query: str
    weight: float


def confidence_for_score(score: float) -> str:
    if score >= settings.icap_high_threshold:
        return "high"
    if score >= settings.icap_medium_threshold:
        return "medium"
    return "low"


def mode_for_confidence(confidence: str) -> str:
    return {"high": "reference", "medium": "hybrid", "low": "company_defined"}[confidence]


def recommendation_for_score(score: float) -> str:
    if score >= settings.icap_high_threshold:
        return "主要參考"
    if score >= settings.icap_medium_threshold:
        return "可參考"
    return "低信心"


def confidence_label(confidence: str) -> str:
    return {
        "high": "高信心",
        "medium": "中信心",
        "low": "低信心",
    }.get(confidence, "未評估")


async def match_icap_candidates(
    *,
    job_title: str,
    department: str | None,
    job_summary: str | None,
    readiness_detail: dict | None = None,
    tasks: list[dict] | None = None,
    top_k: int | None = None,
) -> dict:
    profile_query = _build_profile_query(job_title, department, job_summary, readiness_detail)
    task_query = _build_task_query(tasks or [])
    specs = _build_specs(profile_query, task_query)
    rows_by_type = await asyncio.gather(*[_search_chunk(spec) for spec in specs])

    aggregate: dict[str, dict] = {}
    total_weight = sum(spec.weight for spec in specs)

    for spec, rows in zip(specs, rows_by_type):
        for row in rows:
            bucket = aggregate.setdefault(
                row["ocs_code"],
                {
                    "metadata": row["metadata"],
                    "best_row": row,
                    "weighted_sum": 0.0,
                    "present_weight": 0.0,
                    "evidence": {},
                },
            )
            bucket["weighted_sum"] += row["similarity"] * spec.weight
            bucket["present_weight"] += spec.weight
            bucket["evidence"][spec.chunk_type] = row
            if row["similarity"] > bucket["best_row"]["similarity"]:
                bucket["best_row"] = row
            if not bucket.get("metadata"):
                bucket["metadata"] = row["metadata"]

    candidates = [
        _build_candidate(ocs_code, bucket, total_weight)
        for ocs_code, bucket in aggregate.items()
    ]
    candidates.sort(
        key=lambda c: (
            c["similarity"],
            c["score_detail"]["coverage"],
            c["score_detail"]["evidence_count"],
        ),
        reverse=True,
    )
    candidates = candidates[: top_k or settings.icap_top_k]

    top_score = candidates[0]["similarity"] if candidates else 0.0
    top_confidence = confidence_for_score(top_score)
    return {
        "candidates": candidates,
        "icap_mode": mode_for_confidence(top_confidence),
        "icap_hit": top_confidence in ("high", "medium"),
    }


def _build_specs(profile_query: str, task_query: str) -> list[_SearchSpec]:
    if not task_query:
        return [
            _SearchSpec(chunk_type=chunk_type, query=profile_query, weight=weight)
            for chunk_type, weight in _PROFILE_SPECS
        ]
    return [
        _SearchSpec(
            chunk_type=chunk_type,
            query=profile_query if chunk_type in {"competency", "unit"} else task_query,
            weight=weight,
        )
        for chunk_type, weight in _TASK_AWARE_SPECS
    ]


def _build_profile_query(
    job_title: str,
    department: str | None,
    job_summary: str | None,
    readiness_detail: dict | None,
) -> str:
    parts = [
        f"職稱：{job_title}",
        f"部門：{department or ''}",
        f"職務摘要：{job_summary or ''}",
    ]
    signals = (readiness_detail or {}).get("detected_signals", [])
    for signal in signals:
        examples = "、".join(signal.get("examples") or [])
        if examples:
            parts.append(f"{signal.get('label', '訪談訊號')}：{examples}")
    return "\n".join(part for part in parts if part.strip())


def _build_task_query(tasks: list[dict]) -> str:
    lines = []
    for task in tasks[:8]:
        fields = [
            task.get("task_name", ""),
            task.get("description", ""),
            task.get("evidence_from_user", ""),
            "、".join(task.get("outputs") or []),
            "、".join(task.get("tools") or []),
            "、".join(task.get("workflow_steps") or []),
        ]
        text_line = " ".join(str(field) for field in fields if field)
        if text_line:
            lines.append(text_line)
    return "\n".join(lines)


async def _search_chunk(spec: _SearchSpec) -> list[dict]:
    query_vector = await get_embeddings().aembed_query(spec.query)
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"
    sql = text("""
        WITH deduped AS (
            SELECT DISTINCT ON (ocs_code)
                id,
                ocs_code,
                chunk_text,
                metadata,
                1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM icap_embeddings
            WHERE chunk_type = :chunk_type
            ORDER BY ocs_code, embedding <=> CAST(:vec AS vector)
        )
        SELECT *
        FROM deduped
        ORDER BY similarity DESC
        LIMIT :k
    """)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            sql,
            {
                "vec": vector_literal,
                "chunk_type": spec.chunk_type,
                "k": max((settings.icap_top_k or 5) * 4, 20),
            },
        )).fetchall()

    parsed = []
    for row in rows:
        meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")
        parsed.append({
            "icap_id": str(row.id),
            "ocs_code": row.ocs_code,
            "chunk_type": spec.chunk_type,
            "chunk_text": row.chunk_text,
            "metadata": meta,
            "similarity": float(row.similarity),
        })
    return parsed


def _build_candidate(ocs_code: str, bucket: dict, total_weight: float) -> dict:
    present_weight = bucket["present_weight"]
    raw_score = bucket["weighted_sum"] / present_weight if present_weight else 0.0
    coverage = present_weight / total_weight if total_weight else 0.0
    # Coverage adjusts confidence without letting a single excellent chunk become "high" by itself.
    score = round(raw_score * (0.75 + 0.25 * coverage), 4)
    confidence = confidence_for_score(score)
    meta = bucket["metadata"] or {}
    evidence = bucket["evidence"]

    def _norm(items: list) -> list[dict]:
        return [i if isinstance(i, dict) else {"name": i} for i in items]

    score_by_chunk = {
        chunk_type: round(row["similarity"], 4)
        for chunk_type, row in evidence.items()
    }
    evidence_summary = [
        f"{_CHUNK_LABEL.get(chunk_type, chunk_type)} {score:.2f}"
        for chunk_type, score in score_by_chunk.items()
    ]

    return {
        "icap_id":        bucket["best_row"]["icap_id"],
        "ocs_code":       ocs_code,
        "icap_title":     meta.get("occupation_name", ocs_code),
        "similarity":     score,
        "confidence":     confidence,
        "confidence_label": confidence_label(confidence),
        "match_reason":   "；".join(evidence_summary) or bucket["best_row"]["chunk_text"][:120],
        "job_categories": _norm(meta.get("job_categories", [])),
        "occupations":    _norm(meta.get("occupations", [])),
        "industries":     _norm(meta.get("industries", [])),
        "notes":          meta.get("notes", ""),
        "recommendation": recommendation_for_score(score),
        "score_detail": {
            "coverage": round(coverage, 4),
            "evidence_count": len(evidence),
            "by_chunk_type": score_by_chunk,
        },
    }
