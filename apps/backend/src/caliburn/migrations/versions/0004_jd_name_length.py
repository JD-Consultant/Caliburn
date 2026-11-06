"""將 JD 具名條目的名稱上限放寬為 255 字元。"""

from alembic import op

revision = "0004_jd_name_length"
down_revision = "0003_workspace_deletion"
branch_labels = None
depends_on = None

NAMED_ENTRY_TABLES = ("duties", "job_tasks", "knowledge", "skills")


def upgrade() -> None:
    for table in NAMED_ENTRY_TABLES:
        name = f"ck_{table}_name_length"
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "char_length(name) BETWEEN 1 AND 255")


def downgrade() -> None:
    for table in NAMED_ENTRY_TABLES:
        name = f"ck_{table}_name_length"
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "char_length(name) BETWEEN 1 AND 200")
