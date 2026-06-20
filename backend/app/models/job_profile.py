import uuid

from sqlalchemy import (
    Column, DateTime, ForeignKey,
    Integer, Text, ARRAY, func, text,
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
    job_summary = Column(Text)
    selected_ocs_codes = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="job_profiles")
    document_versions = relationship("DocumentVersion", back_populates="job_profile", cascade="all, delete")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_profile_id = Column(UUID(as_uuid=True), ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=False)

    version = Column(Integer, nullable=False, default=1)
    content = Column(JSONB)
    status = Column(Text, default="draft")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="document_versions")
