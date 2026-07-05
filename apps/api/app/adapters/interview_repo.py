"""InterviewRepo(訪談引擎 v1,T2):sessions/turns/evidence/suggestions 的薄資料層。

家規對齊 persistence.py:repo 吃 session、只 raise 不決定 HTTP;
「同 profile 最多一個 active」= 應用層先查 + DB partial unique 兜底(雙保險)。
"""
from uuid import UUID

from sqlalchemy import func, select

from app.models import (
    InterviewEvidence,
    InterviewSession,
    InterviewSuggestion,
    InterviewTurn,
)


class ActiveInterviewExists(Exception):
    """同 profile 已有 active session(route 轉 409)。"""

    def __init__(self, session_id):
        self.session_id = session_id
        super().__init__(f"active interview session exists: {session_id}")


class InterviewRepo:
    def __init__(self, session):
        self.session = session

    # --- sessions ---

    async def get_active(self, job_profile_id: UUID) -> InterviewSession | None:
        stmt = select(InterviewSession).where(
            InterviewSession.job_profile_id == job_profile_id,
            InterviewSession.status == "active",
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, job_profile_id: UUID) -> InterviewSession:
        existing = await self.get_active(job_profile_id)
        if existing is not None:
            raise ActiveInterviewExists(existing.id)
        row = InterviewSession(job_profile_id=job_profile_id)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)   # 取 server_default(status/phase/jsonb)
        return row

    async def get(self, session_id: UUID) -> InterviewSession | None:
        return await self.session.get(InterviewSession, session_id)

    async def latest_session(self, job_profile_id: UUID) -> InterviewSession | None:
        """最近一個 session(不限 status;顧問視圖/續談入口用)。"""
        stmt = (select(InterviewSession)
                .where(InterviewSession.job_profile_id == job_profile_id)
                .order_by(InterviewSession.created_at.desc())
                .limit(1))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_session(self, session_id: UUID, **fields) -> InterviewSession:
        row = await self.session.get(InterviewSession, session_id)
        for k, v in fields.items():
            setattr(row, k, v)
        await self.session.flush()
        return row

    async def merge_human_touched(self, session_id: UUID, paths: list[str]) -> InterviewSession:
        """人工存檔 diff 的 path 併入(保序去重;ADR 0025 provenance)。"""
        row = await self.session.get(InterviewSession, session_id)
        merged = list(row.human_touched or [])
        for p in paths:
            if p not in merged:
                merged.append(p)
        row.human_touched = merged
        await self.session.flush()
        return row

    # --- turns(逐字稿) ---

    async def append_turn(self, session_id: UUID, *, role: str, text: str,
                          commands: list | None = None) -> InterviewTurn:
        stmt = select(func.coalesce(func.max(InterviewTurn.seq), 0)).where(
            InterviewTurn.session_id == session_id
        )
        next_seq = (await self.session.execute(stmt)).scalar_one() + 1
        row = InterviewTurn(session_id=session_id, seq=next_seq, role=role,
                            text=text, commands=commands or [])
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_turns(self, session_id: UUID, *, last_n: int | None = None) -> list[InterviewTurn]:
        stmt = (select(InterviewTurn)
                .where(InterviewTurn.session_id == session_id)
                .order_by(InterviewTurn.seq))
        rows = list((await self.session.execute(stmt)).scalars())
        return rows[-last_n:] if last_n else rows

    # --- evidence(槽值↔原話) ---

    async def add_evidence(self, session_id: UUID, *, doc_path: str, quote: str,
                           turn_seq: int, verified: bool) -> InterviewEvidence:
        row = InterviewEvidence(session_id=session_id, doc_path=doc_path,
                                quote=quote, turn_seq=turn_seq, verified=verified)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_evidence(self, session_id: UUID) -> list[InterviewEvidence]:
        stmt = (select(InterviewEvidence)
                .where(InterviewEvidence.session_id == session_id)
                .order_by(InterviewEvidence.created_at))
        return list((await self.session.execute(stmt)).scalars())

    # --- suggestions(建議層) ---

    async def add_suggestion(self, session_id: UUID, *, doc_path: str, old_value,
                             new_value, reason: str, turn_seq: int) -> InterviewSuggestion:
        row = InterviewSuggestion(session_id=session_id, doc_path=doc_path,
                                  old_value=old_value, new_value=new_value,
                                  reason=reason, turn_seq=turn_seq)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)   # 取 server_default(status)
        return row

    async def list_suggestions(self, session_id: UUID) -> list[InterviewSuggestion]:
        """全部建議(含已裁決;顧問視圖)。"""
        stmt = (select(InterviewSuggestion)
                .where(InterviewSuggestion.session_id == session_id)
                .order_by(InterviewSuggestion.created_at))
        return list((await self.session.execute(stmt)).scalars())

    async def list_pending(self, session_id: UUID) -> list[InterviewSuggestion]:
        stmt = (select(InterviewSuggestion)
                .where(InterviewSuggestion.session_id == session_id,
                       InterviewSuggestion.status == "pending")
                .order_by(InterviewSuggestion.created_at))
        return list((await self.session.execute(stmt)).scalars())

    async def set_suggestion_status(self, suggestion_id: UUID, status: str) -> InterviewSuggestion:
        row = await self.session.get(InterviewSuggestion, suggestion_id)
        row.status = status
        await self.session.flush()
        return row
