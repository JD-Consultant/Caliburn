from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.graph_v3.constants import TASK_COMPLETENESS_FIELDS
from app.models import CompanyTask
from app.schemas import CompanyTaskCreate, CompanyTaskOut, CompanyTaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{profile_id}", response_model=list[CompanyTaskOut])
async def list_tasks(
    profile_id: UUID,
    limit:  int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CompanyTask)
        .where(CompanyTask.job_profile_id == profile_id)
        .order_by(CompanyTask.sort_order.asc(), CompanyTask.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/{profile_id}", response_model=CompanyTaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    profile_id: UUID,
    payload: CompanyTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    task = CompanyTask(job_profile_id=profile_id, **payload.model_dump())
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=CompanyTaskOut)
async def update_task(
    task_id: UUID,
    payload: CompanyTaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(CompanyTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(task, field, value)

    task.completeness_pct = _calc_completeness(task)
    task.missing_fields   = _get_missing_fields(task)

    await db.flush()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(CompanyTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)


def _calc_completeness(task: CompanyTask) -> int:
    filled = sum(
        1 for f in TASK_COMPLETENESS_FIELDS
        if getattr(task, f, None) not in (None, [], "")
    )
    return int(filled / len(TASK_COMPLETENESS_FIELDS) * 100)


def _get_missing_fields(task: CompanyTask) -> list[str]:
    return [
        f for f in TASK_COMPLETENESS_FIELDS
        if getattr(task, f, None) in (None, [], "")
    ]
