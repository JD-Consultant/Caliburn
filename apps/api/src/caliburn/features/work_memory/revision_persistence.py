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
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryRevisionHeader,
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


async def insert_revisions(
    session: AsyncSession, job_file_id: UUID, revisions: tuple[MemoryRevisionHeader, ...]
) -> None:
    """Assemble and seal fixed revisions in three flush phases within the caller's transaction.

    Object/body creation or reuse is the caller's decision. Sealing fixes the stored
    content and references; it neither publishes Memory nor confirms B2 analysis.
    """
    if not revisions:
        return
    records = [
        MemoryObjectRevisionRecord(
            job_file_id=job_file_id,
            object_id=revision.object_id,
            revision_id=revision.revision_id,
            body_id=revision.body_id,
            title=revision.title,
            description=revision.description,
            is_sealed=False,
        )
        for revision in revisions
    ]
    session.add_all(records)
    await session.flush()
    session.add_all(
        [
            MemoryInterviewReferenceRecord(
                job_file_id=job_file_id,
                object_id=revision.object_id,
                revision_id=revision.revision_id,
                source_id=source_id,
            )
            for revision in revisions
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
            for revision in revisions
            for source in sorted(revision.work_situation_references)
        ]
    )
    await session.flush()
    for record in records:
        record.is_sealed = True
    await session.flush()


async def read_revision_headers(
    session: AsyncSession, job_file_id: UUID, references: frozenset[MemoryRevisionReference]
) -> dict[MemoryRevisionReference, MemoryRevisionHeader]:
    """Read sealed fixed headers and both reference sets without loading bodies."""
    if not references:
        return {}
    keys = [(ref.object_id, ref.revision_id) for ref in sorted(references)]
    rows = (
        await session.execute(
            select(MemoryObjectRevisionRecord, MemoryObjectRecord.layer)
            .select_from(MemoryObjectRevisionRecord)
            .join(
                MemoryObjectRecord,
                (MemoryObjectRecord.job_file_id == MemoryObjectRevisionRecord.job_file_id)
                & (MemoryObjectRecord.object_id == MemoryObjectRevisionRecord.object_id),
            )
            .where(
                MemoryObjectRevisionRecord.job_file_id == job_file_id,
                tuple_(
                    MemoryObjectRevisionRecord.object_id, MemoryObjectRevisionRecord.revision_id
                ).in_(keys),
                MemoryObjectRevisionRecord.is_sealed.is_(True),
            )
        )
    ).all()
    interview_rows = await session.execute(
        select(
            MemoryInterviewReferenceRecord.object_id,
            MemoryInterviewReferenceRecord.revision_id,
            MemoryInterviewReferenceRecord.source_id,
        ).where(
            MemoryInterviewReferenceRecord.job_file_id == job_file_id,
            tuple_(
                MemoryInterviewReferenceRecord.object_id, MemoryInterviewReferenceRecord.revision_id
            ).in_(keys),
        )
    )
    situation_rows = await session.execute(
        select(
            MemorySituationReferenceRecord.object_id,
            MemorySituationReferenceRecord.revision_id,
            MemorySituationReferenceRecord.source_object_id,
            MemorySituationReferenceRecord.source_revision_id,
        ).where(
            MemorySituationReferenceRecord.job_file_id == job_file_id,
            tuple_(
                MemorySituationReferenceRecord.object_id, MemorySituationReferenceRecord.revision_id
            ).in_(keys),
        )
    )
    interviews: dict[MemoryRevisionReference, set[UUID]] = {}
    situations: dict[MemoryRevisionReference, set[MemoryRevisionReference]] = {}
    for object_id, revision_id, source_id in interview_rows:
        interviews.setdefault(MemoryRevisionReference(object_id, revision_id), set()).add(source_id)
    for object_id, revision_id, source_object_id, source_revision_id in situation_rows:
        situations.setdefault(MemoryRevisionReference(object_id, revision_id), set()).add(
            MemoryRevisionReference(source_object_id, source_revision_id)
        )
    result = {}
    for record, layer in rows:
        ref = MemoryRevisionReference(record.object_id, record.revision_id)
        result[ref] = MemoryRevisionHeader(
            record.object_id,
            record.revision_id,
            record.body_id,
            MemoryLayer(layer),
            record.title,
            record.description,
            frozenset(interviews.get(ref, ())),
            frozenset(situations.get(ref, ())),
        )
    return result


async def read_revision_bodies(
    session: AsyncSession, job_file_id: UUID, references: frozenset[MemoryRevisionReference]
) -> dict[MemoryRevisionReference, str]:
    """Only fetch Markdown for the selected fixed revisions, never the whole position."""
    if not references:
        return {}
    rows = await session.execute(
        select(
            MemoryObjectRevisionRecord.object_id,
            MemoryObjectRevisionRecord.revision_id,
            MemoryBodyRecord.body,
        )
        .select_from(MemoryObjectRevisionRecord)
        .join(MemoryBodyRecord)
        .where(
            MemoryObjectRevisionRecord.job_file_id == job_file_id,
            MemoryObjectRevisionRecord.is_sealed.is_(True),
            tuple_(
                MemoryObjectRevisionRecord.object_id, MemoryObjectRevisionRecord.revision_id
            ).in_([(ref.object_id, ref.revision_id) for ref in sorted(references)]),
        )
    )
    return {
        MemoryRevisionReference(object_id, revision_id): body
        for object_id, revision_id, body in rows
    }
