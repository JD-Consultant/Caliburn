"""新增 WorkMemory 聚合、目前項目與發布快照。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_memory"
down_revision = "0006_interviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_memories",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("published_version", sa.BigInteger()),
        sa.Column("analysis", postgresql.JSONB(none_as_null=True)),
        sa.Column("failure", postgresql.JSONB(none_as_null=True)),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_work_memories_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "version BETWEEN 0 AND 9007199254740991", name="ck_work_memories_version"
        ),
        sa.CheckConstraint(
            "published_version BETWEEN 1 AND version",
            name="ck_work_memories_published_version",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(analysis) = 'object'", name="ck_work_memories_analysis"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(failure) = 'object'", name="ck_work_memories_failure"
        ),
    )
    op.create_table(
        "memory_items",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("item_id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(collation="C"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("changed_version", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["work_memories.workspace_id"],
            name="fk_memory_items_memory",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('situation', 'understanding')", name="ck_memory_items_kind"
        ),
        sa.CheckConstraint(
            "changed_version BETWEEN 1 AND 9007199254740991",
            name="ck_memory_items_changed_version",
        ),
        sa.CheckConstraint(
            "char_length(title) > 0 AND char_length(description) > 0 "
            "AND char_length(body) > 0",
            name="ck_memory_items_content",
        ),
        sa.CheckConstraint(
            "coalesce(array_ndims(source_ids), 1) = 1 "
            "AND array_position(source_ids, NULL) IS NULL",
            name="ck_memory_items_sources",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "kind",
            "title",
            name="uq_memory_items_title",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_table(
        "memory_snapshots",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.BigInteger(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("covered_through_message_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["work_memories.workspace_id"],
            name="fk_memory_snapshots_memory",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_memory_snapshots_version"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(content) = 'object'", name="ck_memory_snapshots_content"
        ),
    )
    op.create_foreign_key(
        "fk_work_memories_published_snapshot",
        "work_memories",
        "memory_snapshots",
        ["workspace_id", "published_version"],
        ["workspace_id", "version"],
    )
    op.execute("""
        CREATE FUNCTION preserve_memory_history() RETURNS trigger LANGUAGE plpgsql
        SET search_path FROM CURRENT AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND NOT EXISTS (
                SELECT 1 FROM workspaces WHERE id = OLD.workspace_id
            ) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'Memory history is immutable' USING ERRCODE = '23514';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER preserve_memory_snapshots
        BEFORE UPDATE OR DELETE ON memory_snapshots
        FOR EACH ROW EXECUTE FUNCTION preserve_memory_history()
    """)


def downgrade() -> None:
    op.drop_constraint(
        "fk_work_memories_published_snapshot", "work_memories", type_="foreignkey"
    )
    op.drop_table("memory_snapshots")
    op.drop_table("memory_items")
    op.drop_table("work_memories")
    op.execute("DROP FUNCTION preserve_memory_history()")
