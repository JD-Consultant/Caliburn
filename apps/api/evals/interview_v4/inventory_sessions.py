"""Read-only inventory of interview sessions without printing transcript text.

Run from ``apps/api`` with a valid database configuration:
    DEBUG=false .venv/Scripts/python -m evals.interview_v4.inventory_sessions

The output contains session UUIDs and aggregate metadata, but no job title,
employee text, document text, email or profile id.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models import DocumentVersion, InterviewLlmCall, InterviewReviewEvent, InterviewSession, InterviewTurn
from evals.source_score import iter_pending


_ALERT_WORDS = ("reject", "fail", "conflict", "error", "timeout", "失敗", "放棄", "拒")


def _guard_alerts(calls: list[InterviewLlmCall]) -> int:
    return sum(
        1
        for call in calls
        for verdict in (call.guard_verdicts or [])
        if any(word in str(verdict).lower() for word in _ALERT_WORDS)
    )


async def inventory(limit: int = 100) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        sessions = list((await db.execute(
            select(InterviewSession).order_by(InterviewSession.updated_at.desc()).limit(limit)
        )).scalars())
        if not sessions:
            return []
        session_ids = [row.id for row in sessions]
        profile_ids = list({row.job_profile_id for row in sessions})
        turns = list((await db.execute(
            select(InterviewTurn).where(InterviewTurn.session_id.in_(session_ids))
        )).scalars())
        reviews = list((await db.execute(
            select(InterviewReviewEvent).where(InterviewReviewEvent.session_id.in_(session_ids))
        )).scalars())
        calls = list((await db.execute(
            select(InterviewLlmCall).where(InterviewLlmCall.session_id.in_(session_ids))
        )).scalars())
        documents = list((await db.execute(
            select(DocumentVersion).where(DocumentVersion.job_profile_id.in_(profile_ids))
        )).scalars())

    turns_by: dict[Any, list[InterviewTurn]] = defaultdict(list)
    reviews_by: dict[Any, list[InterviewReviewEvent]] = defaultdict(list)
    calls_by: dict[Any, list[InterviewLlmCall]] = defaultdict(list)
    docs_by: dict[Any, list[DocumentVersion]] = defaultdict(list)
    for row in turns:
        turns_by[row.session_id].append(row)
    for row in reviews:
        reviews_by[row.session_id].append(row)
    for row in calls:
        calls_by[row.session_id].append(row)
    for row in documents:
        docs_by[row.job_profile_id].append(row)

    output: list[dict[str, Any]] = []
    for session in sessions:
        session_turns = turns_by[session.id]
        employee_turns = [row for row in session_turns if row.role == "employee"]
        review_counts = Counter(row.decision for row in reviews_by[session.id])
        session_calls = calls_by[session.id]
        call_outcomes = Counter(getattr(row, "outcome", None) or "legacy_unknown"
                                for row in session_calls)
        call_stages = Counter(getattr(row, "stage", None) or row.role
                              for row in session_calls)
        profile_docs = sorted(docs_by[session.job_profile_id], key=lambda row: row.version)
        latest = profile_docs[-1] if profile_docs else None
        pending_count = len(list(iter_pending(latest.content or {}))) if latest else 0
        alerts = _guard_alerts(session_calls)
        failure_signals: list[str] = []
        success_signals: list[str] = []
        if review_counts["rejected"] or review_counts["batch_rejected"]:
            failure_signals.append("review_rejection")
        if alerts:
            failure_signals.append("guard_alert")
        if session.status == "active" and len(employee_turns) >= 10:
            failure_signals.append("long_active_session")
        if review_counts["accepted"]:
            success_signals.append("review_acceptance")
        if session.status in ("review", "done"):
            success_signals.append("reached_review_or_done")
        if pending_count:
            success_signals.append("has_pending_projection")
        output.append({
            "session_id": str(session.id),
            "status": session.status,
            "phase": session.phase,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "turns": {
                "total": len(session_turns),
                "employee": len(employee_turns),
                "consultant": sum(row.role == "consultant" for row in session_turns),
                "employee_chars": sum(len(row.text or "") for row in employee_turns),
            },
            "reviews": dict(sorted(review_counts.items())),
            "llm_calls": len(session_calls),
            "llm_call_stages": dict(sorted(call_stages.items())),
            "llm_call_outcomes": dict(sorted(call_outcomes.items())),
            "guard_alerts": alerts,
            "document": {
                "version_rows": len(profile_docs),
                "latest_version": latest.version if latest else None,
                "latest_revision": latest.revision if latest else None,
                "latest_status": latest.status if latest else None,
                "pending_items": pending_count,
                "initial_snapshot_available": False,
            },
            "failure_signals": failure_signals,
            "success_signals": success_signals,
        })
    return output


async def _main(limit: int) -> int:
    try:
        rows = await inventory(limit)
        print(json.dumps({"sessions": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(max(1, args.limit))))
