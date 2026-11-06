"""JD 七位置來源引用、固定來源與核對狀態。"""

import sqlalchemy as sa
from alembic import op

revision = "0009_jd_citations"
down_revision = "0008_model_references"
branch_labels = None
depends_on = None

_TARGETS = (
    ("duty", "duty_id", "duties"),
    ("task", "task_id", "job_tasks"),
    ("knowledge", "knowledge_id", "knowledge"),
    ("skill", "skill_id", "skills"),
    ("collaboration", "collaboration_id", "collaboration_entries"),
    ("condition", "condition_id", "job_conditions"),
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_job_descriptions_id_workspace", "job_descriptions", ["id", "workspace_id"]
    )
    for table in ("collaboration_entries", "job_conditions"):
        op.create_unique_constraint(
            f"uq_{table}_id_jd", table, ["id", "job_description_id"]
        )
    op.create_table(
        "job_description_citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_description_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        *(sa.Column(column, sa.Uuid()) for _, column, _ in _TARGETS),
        sa.Column("message_id", sa.Uuid()),
        sa.Column("published_version", sa.BigInteger()),
        sa.Column("item_id", sa.Uuid()),
        sa.Column("jd_changed", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_description_id", "workspace_id"],
            ["job_descriptions.id", "job_descriptions.workspace_id"],
            name="fk_jd_citations_root",
            ondelete="CASCADE",
        ),
        *(
            sa.ForeignKeyConstraint(
                [column, "job_description_id"],
                [f"{table}.id", f"{table}.job_description_id"],
                name=f"fk_jd_citations_{kind}",
                ondelete="CASCADE",
            )
            for kind, column, table in _TARGETS
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["interview_messages.id"],
            name="fk_jd_citations_message",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "published_version"],
            ["memory_snapshots.workspace_id", "memory_snapshots.version"],
            name="fk_jd_citations_memory",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint(
            "num_nonnulls(duty_id, task_id, knowledge_id, skill_id, "
            "collaboration_id, condition_id) <= 1",
            name="ck_jd_citations_target",
        ),
        sa.CheckConstraint(
            "(message_id IS NOT NULL AND published_version IS NULL "
            "AND item_id IS NULL) "
            "OR (message_id IS NULL AND published_version IS NOT NULL "
            "AND item_id IS NOT NULL)",
            name="ck_jd_citations_source",
        ),
        sa.CheckConstraint(
            "published_version BETWEEN 1 AND 9007199254740991",
            name="ck_jd_citations_memory_version",
        ),
        sa.CheckConstraint("position >= 0", name="ck_jd_citations_position"),
        sa.UniqueConstraint(
            "job_description_id",
            "position",
            name="uq_jd_citations_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "job_description_id",
            *(column for _, column, _ in _TARGETS),
            "message_id",
            "published_version",
            "item_id",
            name="uq_jd_citations_relation",
            postgresql_nulls_not_distinct=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )


def downgrade() -> None:
    op.drop_table("job_description_citations")
    for table in ("collaboration_entries", "job_conditions"):
        op.drop_constraint(f"uq_{table}_id_jd", table, type_="unique")
    op.drop_constraint(
        "uq_job_descriptions_id_workspace", "job_descriptions", type_="unique"
    )
