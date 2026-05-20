import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import InterviewSession, JobProfile
from app.schemas import InterviewMessageIn, InterviewMessageOut
from app.services.interview_orchestrator import InterviewOrchestrator

logger = logging.getLogger("jobintel")
router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.get("/{profile_id}/history", response_model=list[InterviewMessageOut])
async def get_interview_history(
    profile_id: UUID,
    limit:  int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.job_profile_id == profile_id)
        .order_by(InterviewSession.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/{profile_id}/chat")
async def chat(
    profile_id: UUID,
    message: InterviewMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """接收使用者訊息，推進 LangGraph 狀態機，回傳 AI 串流回應。"""
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Job profile not found")

    db.add(InterviewSession(
        job_profile_id=profile_id,
        role="user",
        phase=message.phase,
        content=message.content,
    ))
    await db.commit()

    return StreamingResponse(
        InterviewOrchestrator.stream(profile, message.phase, message.content, db),
        media_type="text/event-stream",
    )
