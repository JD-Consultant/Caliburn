import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, ARRAY, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    company = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profiles = relationship("JobProfile", back_populates="user", cascade="all, delete")


class JobProfile(Base):
    __tablename__ = "job_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    job_title = Column(Text, nullable=False)
    department = Column(Text)
    tenure_months = Column(Integer)
    primary_stakeholders = Column(ARRAY(Text))
    job_summary = Column(Text)

    stage = Column(Text, nullable=False, default="basic_info")
    completion_pct = Column(Integer, nullable=False, default=0)
    icap_source_type = Column(Text, default="icap_official")
    document_draft = Column(JSONB)
    graph_state = Column(JSONB, default=dict)  # 跨 API call 持久化的 graph state

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="job_profiles")
    icap_references = relationship("IcapReference", back_populates="job_profile", cascade="all, delete")
    interview_sessions = relationship("InterviewSession", back_populates="job_profile", cascade="all, delete")
    company_tasks = relationship("CompanyTask", back_populates="job_profile", cascade="all, delete")
    ksa_items = relationship("KsaItem", back_populates="job_profile", cascade="all, delete")
    document_versions = relationship("DocumentVersion", back_populates="job_profile", cascade="all, delete")


class IcapReference(Base):
    __tablename__ = "icap_references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)

    icap_id = Column(Text, nullable=False)
    icap_title = Column(Text, nullable=False)
    similarity = Column(Float, nullable=False)
    match_reason = Column(Text)
    mismatch_notes = Column(Text)
    recommendation = Column(Text)
    is_selected = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="icap_references")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)

    role = Column(Text, nullable=False)   # ai | user
    phase = Column(Text, nullable=False)  # general | star_<task> | five_w2h_<task>
    content = Column(Text, nullable=False)
    extra_data = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="interview_sessions")


class CompanyTask(Base):
    __tablename__ = "company_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)

    task_name = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(Text)            # 核心職責 | 例行工作 | 協作任務 | 待確認
    frequency = Column(Text)           # 每日 | 每週 | 每月 | 專案性 | 臨時性
    importance = Column(Text, default="中")
    responsibility_type = Column(Text, default="主責")
    sort_order = Column(Integer, default=0)

    # 5W2H
    situation = Column(Text)
    purpose = Column(Text)
    stakeholders = Column(ARRAY(Text))
    workflow_steps = Column(ARRAY(Text))
    inputs = Column(ARRAY(Text))
    outputs = Column(ARRAY(Text))
    tools = Column(ARRAY(Text))
    collaborators = Column(ARRAY(Text))
    quality_standards = Column(ARRAY(Text))
    time_standards = Column(ARRAY(Text))
    quantity_standards = Column(ARRAY(Text))
    risks_or_common_errors = Column(ARRAY(Text))

    evidence_from_user = Column(Text)
    star_case = Column(JSONB, default=dict)
    behavior_indicator_5w2h = Column(Text)
    behavior_indicator_abcd = Column(Text)
    icap_mapping = Column(JSONB, default=list)

    completeness_pct = Column(Integer, default=0)
    missing_fields = Column(ARRAY(Text))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job_profile = relationship("JobProfile", back_populates="company_tasks")
    ksa_items = relationship("KsaItem", back_populates="task", cascade="all, delete")


class KsaItem(Base):
    __tablename__ = "ksa_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("company_tasks.id", ondelete="SET NULL"), nullable=True)

    ksa_type = Column(Text, nullable=False)       # K | S | A
    content = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False, default="icap_official")
    icap_ref = Column(Text)
    confirmed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="ksa_items")
    task = relationship("CompanyTask", back_populates="ksa_items")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)

    version = Column(Integer, nullable=False, default=1)
    format = Column(Text, nullable=False)   # pdf | docx | json
    file_path = Column(Text)
    content = Column(JSONB)
    status = Column(Text, default="draft")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="document_versions")
