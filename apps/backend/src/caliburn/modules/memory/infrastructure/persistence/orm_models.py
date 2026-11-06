"""Memory 根、目前列與不可變發布。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.shared.infrastructure.persistence.orm_base import OrmBase


class WorkMemoryRow(OrmBase):
    __tablename__ = "work_memories"
    __table_args__ = (
        CheckConstraint(
            "version BETWEEN 0 AND 9007199254740991", name="ck_work_memories_version"
        ),
        CheckConstraint(
            "published_version BETWEEN 1 AND version",
            name="ck_work_memories_published_version",
        ),
        CheckConstraint(
            "jsonb_typeof(analysis) = 'object'", name="ck_work_memories_analysis"
        ),
        CheckConstraint(
            "jsonb_typeof(failure) = 'object'", name="ck_work_memories_failure"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "published_version"],
            ["memory_snapshots.workspace_id", "memory_snapshots.version"],
            name="fk_work_memories_published_snapshot",
            use_alter=True,
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", name="fk_work_memories_workspace", ondelete="CASCADE"
        ),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger)
    published_version: Mapped[int | None] = mapped_column(BigInteger)
    analysis: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    failure: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))


class MemoryItemRow(OrmBase):
    __tablename__ = "memory_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('situation', 'understanding')", name="ck_memory_items_kind"
        ),
        CheckConstraint(
            "changed_version BETWEEN 1 AND 9007199254740991",
            name="ck_memory_items_changed_version",
        ),
        CheckConstraint(
            "char_length(title) > 0 AND char_length(description) > 0 "
            "AND char_length(body) > 0",
            name="ck_memory_items_content",
        ),
        CheckConstraint(
            "coalesce(array_ndims(source_ids), 1) = 1 "
            "AND array_position(source_ids, NULL) IS NULL",
            name="ck_memory_items_sources",
        ),
        UniqueConstraint(
            "workspace_id",
            "kind",
            "title",
            name="uq_memory_items_title",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "work_memories.workspace_id",
            name="fk_memory_items_memory",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    item_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text(collation="C"))
    description: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid))
    changed_version: Mapped[int] = mapped_column(BigInteger)


class MemorySnapshotRow(OrmBase):
    __tablename__ = "memory_snapshots"
    __table_args__ = (
        CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_memory_snapshots_version"
        ),
        CheckConstraint(
            "jsonb_typeof(content) = 'object'", name="ck_memory_snapshots_content"
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "work_memories.workspace_id",
            name="fk_memory_snapshots_memory",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    covered_through_message_id: Mapped[UUID] = mapped_column(Uuid)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
