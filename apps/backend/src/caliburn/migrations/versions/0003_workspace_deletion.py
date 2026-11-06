"""Cascade Workspace deletion through JD ownership relationships."""

from alembic import op

revision = "0003_workspace_deletion"
down_revision = "0002_jd_full_snapshots"
branch_labels = None
depends_on = None

OWNERSHIP_KEYS = (
    (
        "job_descriptions",
        "fk_job_descriptions_workspace_id",
        "workspace_id",
        "workspaces",
    ),
    ("job_tasks", "fk_job_tasks_jd", "job_description_id", "job_descriptions"),
    ("duties", "fk_duties_jd", "job_description_id", "job_descriptions"),
    ("knowledge", "fk_knowledge_jd", "job_description_id", "job_descriptions"),
    ("skills", "fk_skills_jd", "job_description_id", "job_descriptions"),
    (
        "job_description_snapshots",
        "fk_jd_snapshots_jd",
        "job_description_id",
        "job_descriptions",
    ),
)

DEFINITION_REFERENCES = (
    ("task_knowledge", "fk_task_knowledge_definition"),
    ("task_skills", "fk_task_skills_definition"),
)


def upgrade() -> None:
    for table, name, column, parent in OWNERSHIP_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, parent, [column], ["id"], ondelete="CASCADE")
    # 跨分支引用在交易結束檢查，不依賴級聯 trigger 的執行順序。
    for table, name in DEFINITION_REFERENCES:
        op.execute(
            f"ALTER TABLE {table} ALTER CONSTRAINT {name} DEFERRABLE INITIALLY DEFERRED"
        )


def downgrade() -> None:
    for table, name in DEFINITION_REFERENCES:
        op.execute(
            f"ALTER TABLE {table} ALTER CONSTRAINT {name} "
            "NOT DEFERRABLE INITIALLY IMMEDIATE"
        )
    for table, name, column, parent in reversed(OWNERSHIP_KEYS):
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, parent, [column], ["id"])
