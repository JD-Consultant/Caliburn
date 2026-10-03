"""JD-owned fixed direct references; source content remains with its original owner."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)


class JdSourceReferenceRecord(Base):
    __tablename__ = "jd_source_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_source_references_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "reviewed_revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_source_references_reviewed_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "interview_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_jd_source_references_interview",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "memory_snapshot_id"],
            ["memory_snapshots.job_file_id", "memory_snapshots.snapshot_id"],
            name="fk_jd_source_references_memory_snapshot",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "memory_object_id", "memory_revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_jd_source_references_memory_revision",
        ),
        CheckConstraint(
            "(target_kind = 'profile_field' AND target_field IS NOT NULL "
            "AND target_field IN ('job_title', 'organization_unit', 'reports_to', 'purpose') "
            "AND target_item_id IS NULL AND target_task_id IS NULL) OR "
            "(target_kind IN ('area', 'task', 'capability', 'collaborator', 'condition') "
            "AND target_field IS NULL AND target_item_id IS NOT NULL "
            "AND target_task_id IS NULL) OR "
            "(target_kind IN ('detail', 'task_capability') AND target_field IS NULL "
            "AND target_item_id IS NOT NULL AND target_task_id IS NOT NULL)",
            name="target_shape",
        ),
        CheckConstraint(
            "(source_kind = 'interview' AND interview_source_id IS NOT NULL "
            "AND memory_layer IS NULL AND memory_snapshot_id IS NULL "
            "AND memory_object_id IS NULL AND memory_revision_id IS NULL) OR "
            "(source_kind = 'memory' AND interview_source_id IS NULL "
            "AND memory_layer IS NOT NULL "
            "AND memory_layer IN ('work_situation', 'work_understanding') "
            "AND memory_snapshot_id IS NOT NULL AND memory_object_id IS NOT NULL "
            "AND memory_revision_id IS NOT NULL)",
            name="source_shape",
        ),
        CheckConstraint("position >= 0", name="position"),
        UniqueConstraint(
            "job_file_id", "revision_id", "position", name="uq_jd_source_references_position"
        ),
        # A newer source revision is still the same source on this exact target.
        UniqueConstraint(
            "job_file_id",
            "revision_id",
            "target_kind",
            "target_field",
            "target_item_id",
            "target_task_id",
            "source_kind",
            "interview_source_id",
            "memory_layer",
            "memory_object_id",
            name="uq_jd_source_references_identity",
            postgresql_nulls_not_distinct=True,
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    citation_id: Mapped[UUID] = mapped_column(primary_key=True)
    target_kind: Mapped[str] = mapped_column(Text)
    target_field: Mapped[str | None] = mapped_column(Text)
    target_item_id: Mapped[UUID | None]
    target_task_id: Mapped[UUID | None]
    source_kind: Mapped[str] = mapped_column(Text)
    interview_source_id: Mapped[UUID | None]
    memory_layer: Mapped[str | None] = mapped_column(Text)
    memory_snapshot_id: Mapped[UUID | None]
    memory_object_id: Mapped[UUID | None]
    memory_revision_id: Mapped[UUID | None]
    needs_review: Mapped[bool]
    reviewed_revision_id: Mapped[UUID]
    position: Mapped[int]


async def read_source_references(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[JdSourceReference, ...]:
    """Read only this file's fixed revision, preserving its complete reference order."""
    records = await session.scalars(
        select(JdSourceReferenceRecord)
        .where(
            JdSourceReferenceRecord.job_file_id == job_file_id,
            JdSourceReferenceRecord.revision_id == revision_id,
        )
        .order_by(JdSourceReferenceRecord.position)
    )
    return tuple(_reference(record) for record in records)


async def insert_source_references(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    references: tuple[JdSourceReference, ...],
) -> None:
    """Insert the complete set before head/operation adoption; never commit or upsert.

    The caller supplies a new revision with no references yet and validates targets
    and source eligibility. Empty input writes nothing. Repeated nonempty inserts
    conflict with the fixed positions, even when all citation IDs differ.
    """
    for position, reference in enumerate(references):
        source = reference.source
        interview = source if isinstance(source, InterviewSource) else None
        memory = source if isinstance(source, MemorySource) else None
        session.add(
            JdSourceReferenceRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                citation_id=reference.citation_id,
                target_kind=reference.target.kind,
                target_field=reference.target.field,
                target_item_id=reference.target.item_id,
                target_task_id=reference.target.task_id,
                source_kind="interview" if interview is not None else "memory",
                interview_source_id=interview.source_id if interview is not None else None,
                memory_layer=memory.layer if memory is not None else None,
                memory_snapshot_id=memory.snapshot_id if memory is not None else None,
                memory_object_id=memory.object_id if memory is not None else None,
                memory_revision_id=memory.revision_id if memory is not None else None,
                needs_review=reference.needs_review,
                reviewed_revision_id=reference.reviewed_revision_id or revision_id,
                position=position,
            )
        )
    if references:
        await session.flush()


def _reference(record: JdSourceReferenceRecord) -> JdSourceReference:
    source: JdSource
    if record.source_kind == "interview" and record.interview_source_id is not None:
        source = InterviewSource(record.interview_source_id)
    elif (
        record.source_kind == "memory"
        and record.memory_layer is not None
        and record.memory_snapshot_id is not None
        and record.memory_object_id is not None
        and record.memory_revision_id is not None
    ):
        source = MemorySource(
            MemorySourceLayer(record.memory_layer),
            record.memory_snapshot_id,
            record.memory_object_id,
            record.memory_revision_id,
        )
    else:
        raise RuntimeError("Stored JD reference violates its source shape")
    return JdSourceReference(
        citation_id=record.citation_id,
        target=JdSourceTarget(
            kind=SourceTargetKind(record.target_kind),
            field=ProfileField(record.target_field) if record.target_field is not None else None,
            item_id=record.target_item_id,
            task_id=record.target_task_id,
        ),
        source=source,
        needs_review=record.needs_review,
        reviewed_revision_id=record.reviewed_revision_id,
    )
