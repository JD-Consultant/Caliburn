from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import JobProfile, User
from app.schemas import JobProfileCreate, JobProfileOut, JobProfileUpdate
from app.services.persistence import DocRepo

router = APIRouter(prefix="/job-profiles", tags=["job-profiles"])


@router.post("/", response_model=JobProfileOut, status_code=status.HTTP_201_CREATED)
async def create_job_profile(
    payload: JobProfileCreate,
    user_id: UUID,          # 暫用 query param，正式版改 JWT
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = JobProfile(user_id=user_id, **payload.model_dump())
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/", response_model=list[JobProfileOut])
async def list_job_profiles(
    user_id: UUID,
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobProfile)
        .where(JobProfile.user_id == user_id)
        .order_by(JobProfile.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    profiles = result.scalars().all()
    items = []
    for p in profiles:
        st, comp = await DocRepo(db).status_of(p.id)
        item = JobProfileOut.model_validate(p)
        item.doc_status, item.completion = st, comp
        items.append(item)
    return items


@router.get("/{profile_id}", response_model=JobProfileOut)
async def get_job_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Job profile not found")
    return profile


@router.patch("/{profile_id}", response_model=JobProfileOut)
async def update_job_profile(
    profile_id: UUID,
    payload: JobProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Job profile not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return profile



@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    profile = await db.get(JobProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Job profile not found")
    await db.delete(profile)
