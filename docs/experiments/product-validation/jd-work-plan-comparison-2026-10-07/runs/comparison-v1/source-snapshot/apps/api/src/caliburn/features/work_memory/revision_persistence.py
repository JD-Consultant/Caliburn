"""SQL for fixed Memory objects, reusable bodies and sealed revision references."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    false,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionReference,
)


class MemoryObjectRecord(Base):
    __tablename__ = "memory_objects"
    __table_args__ = (
        UniqueConstraint("job_file_id", "object_id", "layer", name="uq_memory_objects_layer"),
        CheckConstraint("layer IN ('work_situation', 'work_understanding')", name="layer"),
    )

    job_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_files.job_file_id", ondelete="CASCADE"), primary_key=True
    )
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    layer: Mapped[str] = mapped_column(Text)


class MemoryBodyRecord(Base):
    __tablename__ = "memory_bodies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "object_id"],
            ["memory_objects.job_file_id", "memory_objects.object_id"],
            name="fk_memory_bodies_object",
            ondelete="CASCADE",
        ),
        CheckConstraint("length(btrim(body)) > 0", name="body_content"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    body_id: Mapped[UUID] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text)


class MemoryObjectRevisionRecord(Base):
    __tablename__ = "memory_object_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "object_id"],
            ["memory_objects.job_file_id", "memory_objects.object_id"],
            name="fk_memory_object_revisions_object",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "body_id"],
            ["memory_bodies.job_file_id", "memory_bodies.object_id", "memory_bodies.body_id"],
            name="fk_memory_object_revisions_body",
            ondelete="CASCADE",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="title_content"),
        CheckConstraint("length(btrim(description)) > 0", name="description_content"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    body_id: Mapped[UUID]
    title: Mapped[str] = mapped_column(Text(collation="C"))
    description: Mapped[str] = mapped_column(Text)
    is_sealed: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryInterviewReferenceRecord(Base):
    __tablename__ = "memory_interview_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_interview_references_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_interview_references_source_file",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "owner_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_interview_references_owner_layer",
            ondelete="CASCADE",
        ),
        CheckConstraint("owner_layer = 'work_situation'", name="owner_layer"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("formal_interviews.source_id", ondelete="CASCADE"), primary_key=True
    )
    owner_layer: Mapped[str] = mapped_column(Text, server_default="work_situation")


class MemorySituationReferenceRecord(Base):
    __tablename__ = "memory_situation_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_situation_references_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "source_object_id", "source_revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_situation_references_source_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "object_id", "owner_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_situation_references_owner_layer",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "source_object_id", "source_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_situation_references_source_layer",
            ondelete="CASCADE",
        ),
        CheckConstraint("owner_layer = 'work_understanding'", name="owner_layer"),
        CheckConstraint("source_layer = 'work_situation'", name="source_layer"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_object_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_revision_id: Mapped[UUID]
    owner_layer: Mapped[str] = mapped_column(Text, server_default="work_understanding")
    source_layer: Mapped[str] = mapped_column(Text, server_default="work_situation")


async def read_object_layer(
    session: AsyncSession, job_file_id: UUID, object_id: UUID
) -> MemoryLayer | None:
    layer = await session.scalar(
        select(MemoryObjectRecord.layer).where(
            MemoryObjectRecord.job_file_id == job_file_id,
            MemoryObjectRecord.object_id == object_id,
        )
    )
    return MemoryLayer(layer) if layer is not None else None


async def insert_object(
    session: AsyncSession, job_file_id: UUID, object_id: UUID, layer: MemoryLayer
) -> None:
    session.add(MemoryObjectRecord(job_file_id=job_file_id, object_id=object_id, layer=layer.value))
    await session.flush()


async def insert_body(
    session: AsyncSession, job_file_id: UUID, object_id: UUID, body_id: UUID, body: str
) -> None:
    session.add(
        MemoryBodyRecord(job_file_id=job_file_id, object_id=object_id, body_id=body_id, body=body)
    )
    await session.flush()


async def insert_revision(
    session: AsyncSession, job_file_id: UUID, revision: MemoryObjectRevision
) -> None:
    """Assemble and seal an existing object's revision; the caller owns the transaction.

    Object/body creation or reuse is the caller's decision. Sealing fixes the stored
    content and references; it neither publishes Memory nor confirms B2 analysis.
    """
    record = MemoryObjectRevisionRecord(
        job_file_id=job_file_id,
        object_id=revision.object_id,
        revision_id=revision.revision_id,
        body_id=revision.body_id,
        title=revision.content.title,
        description=revision.content.description,
        is_sealed=False,
    )
    session.add(record)
    await session.flush()
    session.add_all(
        [
            MemoryInterviewReferenceRecord(
                job_file_id=job_file_id,
                object_id=revision.object_id,
                revision_id=revision.revision_id,
                source_id=source_id,
            )
            for source_id in sorted(revision.interview_references)
        ]
    )
    session.add_all(
        [
            MemorySituationReferenceRecord(
                job_file_id=job_file_id,
                object_id=revision.object_id,
                revision_id=revision.revision_id,
                source_object_id=source.object_id,
                source_revision_id=source.revision_id,
            )
            for source in sorted(revision.work_situation_references)
        ]
    )
    await session.flush()
    record.is_sealed = True
    await session.flush()


async def read_revision(
    session: AsyncSession, job_file_id: UUID, object_id: UUID, revision_id: UUID
) -> MemoryObjectRevision | None:
    """Return a complete fixed revision; an unsealed header is not readable content."""
    row = (
        await session.execute(
            select(MemoryObjectRevisionRecord, MemoryBodyRecord.body, MemoryObjectRecord.layer)
            .select_from(MemoryObjectRevisionRecord)
            .join(MemoryBodyRecord)
            .join(
                MemoryObjectRecord,
                (MemoryObjectRecord.job_file_id == MemoryObjectRevisionRecord.job_file_id)
                & (MemoryObjectRecord.object_id == MemoryObjectRevisionRecord.object_id),
            )
            .where(
                MemoryObjectRevisionRecord.job_file_id == job_file_id,
                MemoryObjectRevisionRecord.object_id == object_id,
                MemoryObjectRevisionRecord.revision_id == revision_id,
                MemoryObjectRevisionRecord.is_sealed.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        return None
    record, body, layer = row
    interview_sources = await session.scalars(
        select(MemoryInterviewReferenceRecord.source_id).where(
            MemoryInterviewReferenceRecord.job_file_id == job_file_id,
            MemoryInterviewReferenceRecord.object_id == object_id,
            MemoryInterviewReferenceRecord.revision_id == revision_id,
        )
    )
    situation_sources = await session.execute(
        select(
            MemorySituationReferenceRecord.source_object_id,
            MemorySituationReferenceRecord.source_revision_id,
        ).where(
            MemorySituationReferenceRecord.job_file_id == job_file_id,
            MemorySituationReferenceRecord.object_id == object_id,
            MemorySituationReferenceRecord.revision_id == revision_id,
        )
    )
    return MemoryObjectRevision(
        object_id=record.object_id,
        revision_id=record.revision_id,
        body_id=record.body_id,
        layer=MemoryLayer(layer),
        content=MemoryContent(title=record.title, description=record.description, body=body),
        interview_references=frozenset(interview_sources),
        work_situation_references=frozenset(
            MemoryRevisionReference(source_object_id, source_revision_id)
            for source_object_id, source_revision_id in situation_sources
        ),
    )
