from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


# ── User ──────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    company: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    company: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── JobProfile ────────────────────────────────────────────────
class JobProfileCreate(BaseModel):
    job_title: str
    department: Optional[str] = None
    job_summary: Optional[str] = None


class JobProfileUpdate(BaseModel):
    job_title: Optional[str] = None
    department: Optional[str] = None
    job_summary: Optional[str] = None


class JobProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    job_title: str
    department: Optional[str]
    job_summary: Optional[str]
    selected_ocs_codes: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
