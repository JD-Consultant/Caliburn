"""Fixed task content/details and per-JD ordered group membership."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    and_,
    insert,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.adapters.database import Base
from caliburn.features.job_description.area_persistence import AreaSelectionRecord
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask


class TaskRevisionRecord(Base):
    __tablename__ = "jd_task_revisions"
    __table_args__ = (
        CheckConstraint("title IS NOT NULL OR description IS NOT NULL", name="has_content"),
        CheckConstraint("title IS NULL OR length(btrim(title)) > 0", name="title_content"),
        CheckConstraint(
            "description IS NULL OR length(btrim(description)) > 0", name="description_content"
        ),
    )

    job_file_id: Mapped[UUID] = mapped_column(ForeignKey("job_files.job_file_id"), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class TaskDetailRecord(Base):
    __tablename__ = "jd_task_details"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "task_id", "content_revision_id"],
            [
                "jd_task_revisions.job_file_id",
                "jd_task_revisions.task_id",
                "jd_task_revisions.content_revision_id",
            ],
            name="fk_jd_task_details_content",
        ),
        UniqueConstraint("job_file_id", "task_id", "content_revision_id", "kind", "position"),
        CheckConstraint("kind IN ('outcome', 'requirement')", name="kind"),
        CheckConstraint("length(btrim(text)) > 0", name="text_content"),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    detail_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class TaskSelectionRecord(Base):
    __tablename__ = "jd_task_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_file_id", "revision_id"],
            ["jd_revisions.job_file_id", "jd_revisions.revision_id"],
            name="fk_jd_task_selections_revision",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "revision_id", "area_id"],
            [
                "jd_area_selections.job_file_id",
                "jd_area_selections.revision_id",
                "jd_area_selections.area_id",
            ],
            name="fk_jd_task_selections_area",
        ),
        ForeignKeyConstraint(
            ["job_file_id", "task_id", "content_revision_id"],
            [
                "jd_task_revisions.job_file_id",
                "jd_task_revisions.task_id",
                "jd_task_revisions.content_revision_id",
            ],
            name="fk_jd_task_selections_content",
        ),
        UniqueConstraint(
            "job_file_id", "revision_id", "area_id", "position", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint("position >= 0", name="position"),
    )

    job_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_revision_id: Mapped[UUID]
    area_id: Mapped[UUID | None]
    position: Mapped[int] = mapped_column(Integer)


async def read_tasks(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> tuple[WorkTask, ...]:
    rows = await session.execute(
        select(TaskSelectionRecord, TaskRevisionRecord)
        .join(TaskRevisionRecord)
        .outerjoin(
            AreaSelectionRecord,
            and_(
                AreaSelectionRecord.job_file_id == TaskSelectionRecord.job_file_id,
                AreaSelectionRecord.revision_id == TaskSelectionRecord.revision_id,
                AreaSelectionRecord.area_id == TaskSelectionRecord.area_id,
            ),
        )
        .where(
            TaskSelectionRecord.job_file_id == job_file_id,
            TaskSelectionRecord.revision_id == revision_id,
        )
        .order_by(AreaSelectionRecord.position.nulls_first(), TaskSelectionRecord.position)
    )
    detail_rows = await session.scalars(
        select(TaskDetailRecord)
        .join(
            TaskSelectionRecord,
            and_(
                TaskSelectionRecord.job_file_id == TaskDetailRecord.job_file_id,
                TaskSelectionRecord.task_id == TaskDetailRecord.task_id,
                TaskSelectionRecord.content_revision_id == TaskDetailRecord.content_revision_id,
            ),
        )
        .where(
            TaskSelectionRecord.job_file_id == job_file_id,
            TaskSelectionRecord.revision_id == revision_id,
        )
        .order_by(TaskDetailRecord.kind, TaskDetailRecord.position)
    )
    details: dict[UUID, list[TaskDetail]] = {}
    for row in detail_rows:
        details.setdefault(row.task_id, []).append(
            TaskDetail(row.detail_id, DetailKind(row.kind), row.text)
        )
    return tuple(
        WorkTask(
            content.task_id,
            content.content_revision_id,
            selection.area_id,
            content.title,
            content.description,
            tuple(details.get(content.task_id, ())),
        )
        for selection, content in rows
    )


async def insert_task_content(session: AsyncSession, job_file_id: UUID, task: WorkTask) -> None:
    session.add(
        TaskRevisionRecord(
            job_file_id=job_file_id,
            task_id=task.task_id,
            content_revision_id=task.content_revision_id,
            title=task.title,
            description=task.description,
        )
    )
    await session.flush()
    for kind in DetailKind:
        for position, detail in enumerate(d for d in task.details if d.kind == kind):
            session.add(
                TaskDetailRecord(
                    job_file_id=job_file_id,
                    task_id=task.task_id,
                    content_revision_id=task.content_revision_id,
                    detail_id=detail.detail_id,
                    kind=kind.value,
                    text=detail.text,
                    position=position,
                )
            )
    await session.flush()


async def select_tasks(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    tasks: tuple[WorkTask, ...],
) -> None:
    positions: dict[UUID | None, int] = {}
    for task in tasks:
        position = positions.get(task.area_id, 0)
        positions[task.area_id] = position + 1
        session.add(
            TaskSelectionRecord(
                job_file_id=job_file_id,
                revision_id=revision_id,
                task_id=task.task_id,
                content_revision_id=task.content_revision_id,
                area_id=task.area_id,
                position=position,
            )
        )
    await session.flush()


async def copy_task_selection(
    session: AsyncSession,
    job_file_id: UUID,
    source_revision_id: UUID,
    target_revision_id: UUID,
) -> None:
    await session.execute(
        insert(TaskSelectionRecord).from_select(
            ["job_file_id", "revision_id", "task_id", "content_revision_id", "area_id", "position"],
            select(
                TaskSelectionRecord.job_file_id,
                literal(target_revision_id),
                TaskSelectionRecord.task_id,
                TaskSelectionRecord.content_revision_id,
                TaskSelectionRecord.area_id,
                TaskSelectionRecord.position,
            ).where(
                TaskSelectionRecord.job_file_id == job_file_id,
                TaskSelectionRecord.revision_id == source_revision_id,
            ),
        )
    )
