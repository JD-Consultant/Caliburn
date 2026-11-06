"""JD 目前關聯式內容與每版完整快照，共用一個交易。"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from caliburn.modules.workspace.infrastructure.persistence.orm_models import (
    WorkspaceRow,
)
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase

# 沿 Python whitespace 產生 CHECK，避免手抄另一份空白集合。
_WHITESPACE_SQL = (
    "U&'"
    + "".join(
        f"\\{point:04x}" if point <= 0xFFFF else f"\\+{point:06x}"
        for point in range(0x110000)
        if chr(point).isspace()
    )
    + "'"
)


def _required_text(table: str, column: str) -> CheckConstraint:
    return CheckConstraint(
        f"btrim({column}, {_WHITESPACE_SQL}) <> ''",
        name=f"ck_{table}_{column}_required",
    )


def _source_identifier(column: str) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IS NULL OR (char_length({column}) <= 200 "
        f"AND btrim({column}, {_WHITESPACE_SQL}) <> '')",
        name=f"ck_jd_snapshots_{column}",
    )


class JobDescriptionRow(OrmBase):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_job_descriptions_workspace_id"),
        UniqueConstraint("id", "workspace_id", name="uq_job_descriptions_id_workspace"),
        CheckConstraint("version > 0", name="ck_job_descriptions_version_positive"),
        CheckConstraint(
            "baseline_competency_level BETWEEN 1 AND 6",
            name="ck_job_descriptions_baseline_competency_level",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 明示共享 DB 的關係，避免依賴呼叫端偶然先匯入 Workspace metadata。
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            WorkspaceRow.id, name="fk_job_descriptions_workspace_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    job_title: Mapped[str | None] = mapped_column(Text)
    organization_unit: Mapped[str | None] = mapped_column(Text)
    reports_to: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    baseline_competency_level: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)


class JobTaskRow(OrmBase):
    __tablename__ = "job_tasks"
    __table_args__ = (
        _required_text("job_tasks", "name"),
        UniqueConstraint("id", "job_description_id", name="uq_job_tasks_id_jd"),
        UniqueConstraint(
            "job_description_id",
            "name",
            name="uq_job_tasks_name",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255", name="ck_job_tasks_name_length"
        ),
        ForeignKeyConstraint(
            ["duty_id", "job_description_id"],
            ["duties.id", "duties.job_description_id"],
            name="fk_job_tasks_duty",
        ),
        UniqueConstraint(
            "job_description_id",
            "duty_id",
            "position",
            name="uq_job_tasks_position",
            postgresql_nulls_not_distinct=True,
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_job_tasks_position"),
        CheckConstraint(
            "competency_level BETWEEN 1 AND 6", name="ck_job_tasks_competency_level"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", name="fk_job_tasks_jd", ondelete="CASCADE")
    )
    duty_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text(collation="C"))
    description: Mapped[str | None] = mapped_column(Text)
    competency_level: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)


class DutyRow(OrmBase):
    __tablename__ = "duties"
    __table_args__ = (
        _required_text("duties", "name"),
        UniqueConstraint("id", "job_description_id", name="uq_duties_id_jd"),
        UniqueConstraint(
            "job_description_id",
            "name",
            name="uq_duties_name",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255", name="ck_duties_name_length"
        ),
        UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_duties_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_duties_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", name="fk_duties_jd", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text(collation="C"))
    scope: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class TaskOutcomeRow(OrmBase):
    __tablename__ = "task_outcomes"
    __table_args__ = (
        _required_text("task_outcomes", "text"),
        UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_outcomes_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_task_outcomes_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_tasks.id", name="fk_task_outcomes_task", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class TaskRequirementRow(OrmBase):
    __tablename__ = "task_requirements"
    __table_args__ = (
        _required_text("task_requirements", "text"),
        UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_requirements_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_task_requirements_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_tasks.id", name="fk_task_requirements_task", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class KnowledgeRow(OrmBase):
    __tablename__ = "knowledge"
    __table_args__ = (
        _required_text("knowledge", "name"),
        UniqueConstraint("id", "job_description_id", name="uq_knowledge_id_jd"),
        UniqueConstraint(
            "job_description_id",
            "name",
            name="uq_knowledge_name",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255", name="ck_knowledge_name_length"
        ),
        UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_knowledge_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_knowledge_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", name="fk_knowledge_jd", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text(collation="C"))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class SkillRow(OrmBase):
    __tablename__ = "skills"
    __table_args__ = (
        _required_text("skills", "name"),
        UniqueConstraint("id", "job_description_id", name="uq_skills_id_jd"),
        UniqueConstraint(
            "job_description_id",
            "name",
            name="uq_skills_name",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255", name="ck_skills_name_length"
        ),
        UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_skills_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_skills_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_descriptions.id", name="fk_skills_jd", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text(collation="C"))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class TaskKnowledgeRow(OrmBase):
    __tablename__ = "task_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "job_description_id"],
            ["job_tasks.id", "job_tasks.job_description_id"],
            name="fk_task_knowledge_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["knowledge_id", "job_description_id"],
            ["knowledge.id", "knowledge.job_description_id"],
            name="fk_task_knowledge_definition",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_knowledge_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_task_knowledge_position"),
    )
    task_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    knowledge_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)


class TaskSkillRow(OrmBase):
    __tablename__ = "task_skills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "job_description_id"],
            ["job_tasks.id", "job_tasks.job_description_id"],
            name="fk_task_skills_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["skill_id", "job_description_id"],
            ["skills.id", "skills.job_description_id"],
            name="fk_task_skills_definition",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_skills_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_task_skills_position"),
    )
    task_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    skill_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)


class CollaborationEntryRow(OrmBase):
    __tablename__ = "collaboration_entries"
    __table_args__ = (
        UniqueConstraint(
            "id", "job_description_id", name="uq_collaboration_entries_id_jd"
        ),
        _required_text("collaboration_entries", "collaborator_name"),
        UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_collaboration_entries_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_collaboration_entries_position"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job_descriptions.id",
            name="fk_collaboration_entries_jd",
            ondelete="CASCADE",
        )
    )
    collaborator_name: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class JobConditionRow(OrmBase):
    __tablename__ = "job_conditions"
    __table_args__ = (
        UniqueConstraint("id", "job_description_id", name="uq_job_conditions_id_jd"),
        _required_text("job_conditions", "text"),
        UniqueConstraint(
            "job_description_id",
            "kind",
            "position",
            name="uq_job_conditions_position",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        CheckConstraint("position >= 0", name="ck_job_conditions_position"),
        CheckConstraint(
            "kind IN ('work_environment', 'schedule_travel', 'shared_authority', "
            "'shared_collaboration', 'qualification')",
            name="ck_job_conditions_kind",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job_descriptions.id", name="fk_job_conditions_jd", ondelete="CASCADE"
        )
    )
    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class JobDescriptionSnapshotRow(OrmBase):
    __tablename__ = "job_description_snapshots"
    __table_args__ = (
        _source_identifier("correlation_id"),
        _source_identifier("reverts_correlation_id"),
        CheckConstraint("version > 0", name="ck_jd_snapshots_version"),
        CheckConstraint("schema_version > 0", name="ck_jd_snapshots_schema_version"),
        CheckConstraint(
            "jsonb_typeof(content) = 'object'", name="ck_jd_snapshots_content"
        ),
        CheckConstraint(
            "(kind = 'created' AND version = 1 AND restored_from_version IS NULL "
            "AND reverts_correlation_id IS NULL) OR "
            "(kind = 'edited' AND version > 1 AND restored_from_version IS NULL "
            "AND reverts_correlation_id IS NULL) OR "
            "(kind = 'restored' AND restored_from_version IS NOT NULL "
            "AND restored_from_version < version)",
            name="ck_jd_snapshots_kind",
        ),
        ForeignKeyConstraint(
            ["job_description_id", "restored_from_version"],
            [
                "job_description_snapshots.job_description_id",
                "job_description_snapshots.version",
            ],
            name="fk_jd_snapshots_restore_target",
        ),
    )
    job_description_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job_descriptions.id", name="fk_jd_snapshots_jd", ondelete="CASCADE"
        ),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    schema_version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(Text)
    restored_from_version: Mapped[int | None] = mapped_column(Integer)
    correlation_id: Mapped[str | None] = mapped_column(Text)
    reverts_correlation_id: Mapped[str | None] = mapped_column(Text)
