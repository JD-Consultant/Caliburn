"""JD 引用關聯表及固定來源映射；來源正文不存入 JD。"""

from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    CitationTargetKind,
    InterviewReference,
    MemoryReference,
    SourceReference,
)
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase

TARGET_COLUMNS: tuple[tuple[CitationTargetKind, str, str], ...] = (
    ("duty", "duty_id", "duties"),
    ("task", "task_id", "job_tasks"),
    ("knowledge", "knowledge_id", "knowledge"),
    ("skill", "skill_id", "skills"),
    ("collaboration", "collaboration_id", "collaboration_entries"),
    ("condition", "condition_id", "job_conditions"),
)


class CitationRow(OrmBase):
    __tablename__ = "job_description_citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_description_id", "workspace_id"],
            ["job_descriptions.id", "job_descriptions.workspace_id"],
            name="fk_jd_citations_root",
            ondelete="CASCADE",
        ),
        *(
            ForeignKeyConstraint(
                [column, "job_description_id"],
                [f"{table}.id", f"{table}.job_description_id"],
                name=f"fk_jd_citations_{kind}",
                ondelete="CASCADE",
            )
            for kind, column, table in TARGET_COLUMNS
        ),
        ForeignKeyConstraint(
            ["workspace_id", "published_version"],
            ["memory_snapshots.workspace_id", "memory_snapshots.version"],
            name="fk_jd_citations_memory",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "num_nonnulls(duty_id, task_id, knowledge_id, skill_id, "
            "collaboration_id, condition_id) <= 1",
            name="ck_jd_citations_target",
        ),
        CheckConstraint(
            "(message_id IS NOT NULL AND published_version IS NULL "
            "AND item_id IS NULL) "
            "OR (message_id IS NULL AND published_version IS NOT NULL "
            "AND item_id IS NOT NULL)",
            name="ck_jd_citations_source",
        ),
        CheckConstraint(
            "published_version BETWEEN 1 AND 9007199254740991",
            name="ck_jd_citations_memory_version",
        ),
        CheckConstraint("position >= 0", name="ck_jd_citations_position"),
        UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_jd_citations_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "job_description_id",
            "duty_id",
            "task_id",
            "knowledge_id",
            "skill_id",
            "collaboration_id",
            "condition_id",
            "message_id",
            "published_version",
            "item_id",
            name="uq_jd_citations_relation",
            postgresql_nulls_not_distinct=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(Uuid)
    workspace_id: Mapped[UUID] = mapped_column(Uuid)
    duty_id: Mapped[UUID | None] = mapped_column(Uuid)
    task_id: Mapped[UUID | None] = mapped_column(Uuid)
    knowledge_id: Mapped[UUID | None] = mapped_column(Uuid)
    skill_id: Mapped[UUID | None] = mapped_column(Uuid)
    collaboration_id: Mapped[UUID | None] = mapped_column(Uuid)
    condition_id: Mapped[UUID | None] = mapped_column(Uuid)
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "interview_messages.id",
            name="fk_jd_citations_message",
            deferrable=True,
            initially="DEFERRED",
        )
    )
    published_version: Mapped[int | None] = mapped_column(BigInteger)
    item_id: Mapped[UUID | None] = mapped_column(Uuid)
    jd_changed: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(Integer)


def citation_from_row(row: CitationRow) -> Citation:
    target_kind: CitationTargetKind = "job_description"
    target_id = row.job_description_id
    selected = [
        (kind, getattr(row, column))
        for kind, column, _ in TARGET_COLUMNS
        if getattr(row, column) is not None
    ]
    if len(selected) > 1:
        raise ValueError("引用有多個目標")
    if selected:
        target_kind, target_id = selected[0]
    source: SourceReference
    if row.message_id is not None:
        if row.published_version is not None or row.item_id is not None:
            raise ValueError("引用來源種類混合")
        source = InterviewReference(
            workspace_id=row.workspace_id, message_id=row.message_id
        )
    else:
        if row.published_version is None or row.item_id is None:
            raise ValueError("Memory 引用缺少固定版或項目")
        source = MemoryReference(
            workspace_id=row.workspace_id,
            published_version=row.published_version,
            item_id=row.item_id,
        )
    return Citation(
        id=row.id,
        target_kind=target_kind,
        target_id=target_id,
        source=source,
        jd_changed=row.jd_changed,
    )


def citation_to_row(
    citation: Citation, *, job_description_id: UUID, position: int
) -> CitationRow:
    source = citation.source
    return CitationRow(
        id=citation.id,
        job_description_id=job_description_id,
        workspace_id=source.workspace_id,
        **{
            column: citation.target_id if citation.target_kind == kind else None
            for kind, column, _ in TARGET_COLUMNS
        },
        message_id=source.message_id
        if isinstance(source, InterviewReference)
        else None,
        published_version=source.published_version
        if isinstance(source, MemoryReference)
        else None,
        item_id=source.item_id if isinstance(source, MemoryReference) else None,
        jd_changed=citation.jd_changed,
        position=position,
    )
