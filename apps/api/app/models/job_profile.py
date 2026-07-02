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

    # revision：單一列的編輯回合計數（與 version 的「文件世系」語意分開，ADR 0015 精化）。
    # SQLAlchemy version_id_col：每次 ORM UPDATE 自動 SET revision=n+1 WHERE … AND revision=n（CAS）；
    # 0 rows（同毫秒競態）→ StaleDataError。INSERT 新列 revision 從 1 起。
    # https://docs.sqlalchemy.org/en/20/orm/versioning.html
    revision = Column(Integer, nullable=False, default=1, server_default=text("1"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job_profile = relationship("JobProfile", back_populates="document_versions")

    __mapper_args__ = {"version_id_col": revision}
