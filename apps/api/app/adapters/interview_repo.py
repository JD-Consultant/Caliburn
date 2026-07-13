"""InterviewRepo(訪談引擎):sessions/turns/審閱事件/LLM 稽核的薄資料層。

家規對齊 persistence.py:repo 吃 session、只 raise 不決定 HTTP;
「同 profile 最多一個 active」= 應用層先查 + DB partial unique 兜底(雙保險)。
"""
from uuid import UUID

from sqlalchemy import func, select

from app.models import (
    InterviewLlmCall,
    InterviewReviewEvent,
    InterviewSession,
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

    # evidence/suggestions 層已退場(T12;ADR 0030):溯源住文件 `_pending.src`、
    # 審閱住 interview_review_events;migration 0008 落表。

    # --- LLM 呼叫稽核(T13;每回合每次呼叫一列) ---

    async def add_llm_call(self, session_id: UUID, *, turn_seq: int, role: str, model: str,
                           duration_ms: int, tool_calls: list | None = None,
                           guard_verdicts: list | None = None,
                           prompt_tokens: int | None = None,
                           completion_tokens: int | None = None) -> InterviewLlmCall:
        row = InterviewLlmCall(session_id=session_id, turn_seq=turn_seq, role=role, model=model,
                               duration_ms=duration_ms, tool_calls=tool_calls or [],
                               guard_verdicts=guard_verdicts or [],
                               prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_llm_calls(self, session_id: UUID) -> list[InterviewLlmCall]:
        stmt = (select(InterviewLlmCall)
                .where(InterviewLlmCall.session_id == session_id)
                .order_by(InterviewLlmCall.created_at))
        return list((await self.session.execute(stmt)).scalars())

    # --- 審閱事件(ADR 0030 T2:✓/✗/批量的無聲記帳) ---

    async def add_review_events(self, session_id: UUID, events: list[dict]) -> int:
        """批量落審閱事件;event = {doc_path, decision, op_meta?}。回寫入筆數。"""
        for e in events:
            self.session.add(InterviewReviewEvent(
                session_id=session_id,
                doc_path=e["doc_path"],
                decision=e["decision"],
                op_meta=e.get("op_meta") or {},
            ))
        await self.session.flush()
        return len(events)

    async def list_review_events(
        self, session_id: UUID, *, decision: str | None = None
    ) -> list[InterviewReviewEvent]:
        stmt = (select(InterviewReviewEvent)
                .where(InterviewReviewEvent.session_id == session_id)
                .order_by(InterviewReviewEvent.seq))
        if decision is not None:
            stmt = stmt.where(InterviewReviewEvent.decision == decision)
        return list((await self.session.execute(stmt)).scalars())
