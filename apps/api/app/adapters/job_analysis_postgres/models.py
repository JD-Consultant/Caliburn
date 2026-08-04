"""SQLAlchemy rows matching the current job-analysis migration head.

Rows remain adapter-private. Repositories hydrate application/domain contracts
before returning data across the port.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


_PROPOSAL_STATUSES = (
    "status IN ('pending','deferred','accepted','edited','rejected',"
    "'revision_requested','stale')"
)
_PROPOSAL_LIFECYCLE = (
    "(status IN ('pending','deferred') AND resolved_at IS NULL) OR "
    "(status IN ('accepted','edited','rejected','revision_requested','stale') "
    "AND resolved_at IS NOT NULL)"
)
_OPKS_ENTITY_KINDS = (
    "entity_kind IN ('output','indicator','knowledge','skill','attitude')"
)
_OPKS_PROPOSAL_STATUSES = (
    "status IN ('pending','deferred','accepted','edited','rejected','stale')"
)
_OPKS_PROPOSAL_LIFECYCLE = (
    "(status IN ('pending','deferred') AND resolved_at IS NULL) OR "
    "(status IN ('accepted','edited','rejected','stale') AND resolved_at IS NOT NULL)"
)


class JobAnalysisDocumentRow(Base):
    __tablename__ = "job_analysis_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    jd_header_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    jd_header_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    work_model_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    work_model_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    active_question_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )
    authority_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("document_id", name="ja2_pk_documents"),
        CheckConstraint("btrim(title) <> ''", name="ja2_ck_documents_title"),
        CheckConstraint(
            "btrim(jd_header_schema_id) <> ''",
            name="ja2_ck_documents_jd_header_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(jd_header_json) = 'object'",
            name="ja2_ck_documents_jd_header_json",
        ),
        CheckConstraint(
            "btrim(work_model_schema_id) <> ''",
            name="ja2_ck_documents_work_model_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(work_model_json) = 'object'",
            name="ja2_ck_documents_work_model_json",
        ),
        CheckConstraint(
            "active_question_json IS NULL "
            "OR jsonb_typeof(active_question_json) = 'object'",
            name="ja2_ck_documents_active_question_json",
        ),
        CheckConstraint(
            "authority_generation >= 0",
            name="ja2_ck_documents_generation",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_documents_time_order",
        ),
        Index(
            "ja2_ix_documents_updated",
            text("updated_at DESC"),
            "document_id",
        ),
    )


class JobAnalysisJdTaskRow(Base):
    __tablename__ = "job_analysis_jd_tasks"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    task_id: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    purpose_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibility_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    enablers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    display_order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 沒有 FK:referential integrity 住 JobAnalysisState(同 OPKS task_refs 的做法),
    # 而 ON DELETE SET NULL 會在每次 duties replace 時把 Task 的職責歸屬洗掉。
    duty_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    competency_level: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "document_id",
            "task_id",
            name="ja2_pk_jd_tasks",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_jd_tasks_document",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "display_order",
            name="ja2_uq_jd_tasks_order",
        ),
        CheckConstraint(
            "btrim(task_id) <> ''",
            name="ja2_ck_jd_tasks_task_id",
        ),
        CheckConstraint(
            "btrim(statement) <> ''",
            name="ja2_ck_jd_tasks_statement",
        ),
        CheckConstraint(
            "responsibility_role IS NULL "
            "OR responsibility_role IN ('primary','shared','assist')",
            name="ja2_ck_jd_tasks_role",
        ),
        CheckConstraint(
            "jsonb_typeof(enablers_json) = 'array'",
            name="ja2_ck_jd_tasks_enablers_json",
        ),
        CheckConstraint(
            "duty_id IS NULL OR btrim(duty_id) <> ''",
            name="ja2_ck_jd_tasks_duty_id",
        ),
        CheckConstraint(
            "competency_level IS NULL OR competency_level BETWEEN 1 AND 6",
            name="ja2_ck_jd_tasks_competency_level",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="ja2_ck_jd_tasks_display_order",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_jd_tasks_time_order",
        ),
    )


class JobAnalysisJdDutyRow(Base):
    __tablename__ = "job_analysis_jd_duties"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    duty_id: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("document_id", "duty_id", name="ja2_pk_jd_duties"),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_jd_duties_document",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "display_order",
            name="ja2_uq_jd_duties_order",
        ),
        CheckConstraint("btrim(duty_id) <> ''", name="ja2_ck_jd_duties_duty_id"),
        CheckConstraint("btrim(statement) <> ''", name="ja2_ck_jd_duties_statement"),
        CheckConstraint("display_order >= 0", name="ja2_ck_jd_duties_display_order"),
        CheckConstraint(
            "updated_at >= created_at", name="ja2_ck_jd_duties_time_order"
        ),
    )


class JobAnalysisProposalRow(Base):
    __tablename__ = "job_analysis_proposals"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    proposal_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    base_authority_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proposal_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    caused_by_decision_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "document_id",
            "proposal_id",
            name="ja2_pk_proposals",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_proposals_document",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "btrim(proposal_id) <> ''",
            name="ja2_ck_proposals_id",
        ),
        CheckConstraint(_PROPOSAL_STATUSES, name="ja2_ck_proposals_status"),
        CheckConstraint(
            "base_authority_generation >= 0",
            name="ja2_ck_proposals_generation",
        ),
        CheckConstraint(
            "btrim(proposal_schema_id) <> ''",
            name="ja2_ck_proposals_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(proposal_payload) = 'object'",
            name="ja2_ck_proposals_payload",
        ),
        CheckConstraint(
            _PROPOSAL_LIFECYCLE,
            name="ja2_ck_proposals_lifecycle",
        ),
        Index(
            "ja2_ix_proposals_document_status",
            "document_id",
            "status",
            "created_at",
            "proposal_id",
        ),
        Index(
            "ja2_uq_proposals_replacement",
            "document_id",
            "caused_by_decision_id",
            unique=True,
            postgresql_where=text("caused_by_decision_id IS NOT NULL"),
        ),
    )


class JobAnalysisOpksItemRow(Base):
    __tablename__ = "job_analysis_opks_items"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entity_id: Mapped[str] = mapped_column(Text)
    entity_kind: Mapped[str] = mapped_column(Text, nullable=False)
    item_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "document_id",
            "entity_id",
            name="ja2_pk_opks_items",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_opks_items_document",
            ondelete="CASCADE",
        ),
        CheckConstraint("btrim(entity_id) <> ''", name="ja2_ck_opks_items_id"),
        CheckConstraint(_OPKS_ENTITY_KINDS, name="ja2_ck_opks_items_kind"),
        CheckConstraint(
            "btrim(item_schema_id) <> ''",
            name="ja2_ck_opks_items_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(item_payload) = 'object'",
            name="ja2_ck_opks_items_payload",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ja2_ck_opks_items_time_order",
        ),
        Index(
            "ja2_ix_opks_items_document_created",
            "document_id",
            "created_at",
            "entity_id",
        ),
    )


class JobAnalysisOpksProposalRow(Base):
    __tablename__ = "job_analysis_opks_proposals"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    proposal_id: Mapped[str] = mapped_column(Text)
    operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_kind: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    base_authority_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proposal_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "document_id",
            "proposal_id",
            name="ja2_pk_opks_proposals",
        ),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_opks_proposals_document",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "btrim(proposal_id) <> ''",
            name="ja2_ck_opks_proposals_id",
        ),
        CheckConstraint(
            "btrim(operation_id) <> ''",
            name="ja2_ck_opks_proposals_operation_id",
        ),
        CheckConstraint(
            "btrim(entity_id) <> ''",
            name="ja2_ck_opks_proposals_entity_id",
        ),
        CheckConstraint(_OPKS_ENTITY_KINDS, name="ja2_ck_opks_proposals_kind"),
        CheckConstraint(
            "action IN ('add','revise','remove')",
            name="ja2_ck_opks_proposals_action",
        ),
        CheckConstraint(
            _OPKS_PROPOSAL_STATUSES,
            name="ja2_ck_opks_proposals_status",
        ),
        CheckConstraint(
            "base_authority_generation >= 0",
            name="ja2_ck_opks_proposals_generation",
        ),
        CheckConstraint(
            "btrim(proposal_schema_id) <> ''",
            name="ja2_ck_opks_proposals_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(proposal_payload) = 'object'",
            name="ja2_ck_opks_proposals_payload",
        ),
        CheckConstraint(
            _OPKS_PROPOSAL_LIFECYCLE,
            name="ja2_ck_opks_proposals_lifecycle",
        ),
        Index(
            "ja2_ix_opks_proposals_document_status",
            "document_id",
            "status",
            "created_at",
            "proposal_id",
        ),
    )


class JobAnalysisJournalRow(Base):
    __tablename__ = "job_analysis_journal"

    journal_sequence: Mapped[int] = mapped_column(BigInteger, Identity())
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entry_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload_schema_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("journal_sequence", name="ja2_pk_journal"),
        ForeignKeyConstraint(
            ["document_id"],
            ["job_analysis_documents.document_id"],
            name="ja2_fk_journal_document",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "entry_id",
            name="ja2_uq_journal_entry",
        ),
        CheckConstraint(
            "btrim(entry_id) <> ''",
            name="ja2_ck_journal_entry_id",
        ),
        CheckConstraint(
            "kind IN ('consultant_opening','employee_turn','direct_edit',"
            "'proposal_decision','opks_generation')",
            name="ja2_ck_journal_kind",
        ),
        CheckConstraint(
            "btrim(payload_schema_id) <> ''",
            name="ja2_ck_journal_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ja2_ck_journal_payload",
        ),
        Index(
            "ja2_ix_journal_document_sequence",
            "document_id",
            text("journal_sequence DESC"),
        ),
    )
