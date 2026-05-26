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
    tenure_months: Optional[int] = None
    primary_stakeholders: Optional[list[str]] = None
    job_summary: Optional[str] = None


class JobProfileUpdate(BaseModel):
    job_title: Optional[str] = None
    department: Optional[str] = None
    tenure_months: Optional[int] = None
    primary_stakeholders: Optional[list[str]] = None
    job_summary: Optional[str] = None
    stage: Optional[str] = None
    completion_pct: Optional[int] = None


class JobProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    job_title: str
    department: Optional[str]
    tenure_months: Optional[int]
    primary_stakeholders: Optional[list[str]]
    job_summary: Optional[str]
    stage: str
    completion_pct: int
    icap_source_type: Optional[str]
    graph_state: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── CompanyTask ───────────────────────────────────────────────
class CompanyTaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    frequency: Optional[str] = None
    importance: str = "中"
    responsibility_type: str = "主責"


class CompanyTaskUpdate(BaseModel):
    task_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    frequency: Optional[str] = None
    importance: Optional[str] = None
    responsibility_type: Optional[str] = None
    situation: Optional[str] = None
    purpose: Optional[str] = None
    stakeholders: Optional[list[str]] = None
    workflow_steps: Optional[list[str]] = None
    inputs: Optional[list[str]] = None
    outputs: Optional[list[str]] = None
    tools: Optional[list[str]] = None
    collaborators: Optional[list[str]] = None
    quality_standards: Optional[list[str]] = None
    time_standards: Optional[list[str]] = None
    quantity_standards: Optional[list[str]] = None
    risks_or_common_errors: Optional[list[str]] = None
    behavior_indicator_5w2h: Optional[str] = None
    behavior_indicator_abcd: Optional[str] = None


class CompanyTaskOut(BaseModel):
    id: UUID
    job_profile_id: UUID
    task_name: str
    description: Optional[str]
    category: Optional[str]
    frequency: Optional[str]
    importance: str
    responsibility_type: str
    completeness_pct: int
    missing_fields: Optional[list[str]]
    behavior_indicator_5w2h: Optional[str]
    behavior_indicator_abcd: Optional[str]
    icap_mapping: list
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Interview message ──────────────────────────────────────────
class InterviewMessageIn(BaseModel):
    content: str
    phase: str = "general"


class InterviewMessageOut(BaseModel):
    role: str
    content: str
    phase: str
    extra_data: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
