"""Fixed collaborator content and each JD revision's ordered selection; no mutable mirror."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    insert,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description.collaborators import Collaborator


class CollaboratorRevisionRecord(Base):
    __tablename__ = "jd_collaborator_revisions"
    __table_args__ = (
        CheckConstraint("name IS NOT NULL OR scope_text IS NOT NULL", name="has_content"),
        CheckConstraint("name IS NULL OR length(btrim(name)) > 0", name="name_content"),
        CheckConstraint(
            "scope_text IS NULL OR length(btrim(scope_text)) > 0", name="scope_content"
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    collaborator_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    scope_text: Mapped[str | None] = mapped_column(Text)


class CollaboratorSelectionRecord(Base):
    __tablename__ = "jd_collaborator_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_collaborator_selections_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "collaborator_id", "content_revision_id"],
            [
                "jd_collaborator_revisions.job_file_id",
                "jd_collaborator_revisions.collaborator_id",
                "jd_collaborator_revisions.content_revision_id",
            ],
            name="fk_jd_collaborator_selections_content",
        ),
        UniqueConstraint("job_file_id", "revision_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    collaborator_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)


async def read_collaborators(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[Collaborator, ...]:
    records = await session.scalars(
        select(CollaboratorRevisionRecord)
        .join(CollaboratorSelectionRecord)
        .where(
            CollaboratorSelectionRecord.job_file_id == job_file_id,
            CollaboratorSelectionRecord.revision_id == revision_id,
        )
        .order_by(CollaboratorSelectionRecord.position)
    )
    return tuple(
        Collaborator(row.collaborator_id, row.content_revision_id, row.name, row.scope_text)
        for row in records
    )


async def insert_collaborator_content(
    session: AsyncSession, job_file_id: UUID, collaborator: Collaborator
) -> None:
    session.add(
        CollaboratorRevisionRecord(
            job_file_id=job_file_id,
            collaborator_id=collaborator.collaborator_id,
            content_revision_id=collaborator.content_revision_id,
            name=collaborator.name,
            scope_text=collaborator.scope_text,
        )
    )
    await session.flush()


async def select_collaborators(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    collaborators: tuple[Collaborator, ...],
) -> None:
    session.add_all(
        [
            CollaboratorSelectionRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                collaborator_id=collaborator.collaborator_id,
                content_revision_id=collaborator.content_revision_id,
                position=position,
            )
            for position, collaborator in enumerate(collaborators)
        ]
    )
    await session.flush()


async def copy_collaborator_selection(
    session: AsyncSession, job_file_id: UUID, source_revision_id: UUID, target_revision_id: UUID
) -> None:
    """Copy keys/order, not collaborator text, before adopting the new head."""
    await session.execute(
        insert(CollaboratorSelectionRecord).from_select(
            ["job_file_id", "revision_id", "collaborator_id", "content_revision_id", "position"],
            select(
                CollaboratorSelectionRecord.job_file_id,
                literal(target_revision_id),
                CollaboratorSelectionRecord.collaborator_id,
                CollaboratorSelectionRecord.content_revision_id,
                CollaboratorSelectionRecord.position,
            ).where(
                CollaboratorSelectionRecord.job_file_id == job_file_id,
                CollaboratorSelectionRecord.revision_id == source_revision_id,
            ),
        )
    )
