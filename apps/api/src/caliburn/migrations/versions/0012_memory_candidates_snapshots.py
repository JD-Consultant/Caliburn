"""Fixed candidate selections, batch coordinates and immutable Memory publication.

Revision ID: 0012_memory_candidates_snapshots
Revises: 0011_memory_object_revisions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_memory_candidates_snapshots"
down_revision = "0011_memory_object_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_positions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("parent_position_id", sa.Uuid(), nullable=True),
        sa.Column("is_sealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "position_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.ForeignKeyConstraint(
            ["job_file_id", "parent_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_positions_parent",
        ),
    )
    op.create_table(
        "memory_position_members",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "position_id", "object_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_position_members_position",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_position_members_revision",
        ),
    )
    op.create_table(
        "memory_batches",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("base_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("base_position_id", sa.Uuid(), nullable=False),
        sa.Column("current_position_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("through_source_id", sa.Uuid(), nullable=False),
        sa.Column("covered_through_sequence", sa.Integer(), nullable=False),
        sa.Column("through_sequence", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "execution_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_memory_batches_execution",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "base_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_batches_base_position",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "current_position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_batches_current_position",
        ),
        sa.ForeignKeyConstraint(["through_source_id"], ["formal_interviews.source_id"]),
        sa.ForeignKeyConstraint(
            ["job_file_id", "through_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_batches_source_file",
        ),
        sa.CheckConstraint(
            "phase IN ('work_situation', 'work_understanding')",
            name=op.f("ck_memory_batches_phase"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'published', 'discarded')", name=op.f("ck_memory_batches_status")
        ),
        sa.CheckConstraint(
            "0 <= covered_through_sequence AND covered_through_sequence < through_sequence",
            name=op.f("ck_memory_batches_source_window"),
        ),
    )
    op.create_table(
        "memory_snapshots",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("through_source_id", sa.Uuid(), nullable=False),
        sa.Column("covered_through_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "snapshot_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "position_id"],
            ["memory_positions.job_file_id", "memory_positions.position_id"],
            name="fk_memory_snapshots_position",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["memory_batches.job_file_id", "memory_batches.execution_id"],
            name="fk_memory_snapshots_batch",
        ),
        sa.ForeignKeyConstraint(["through_source_id"], ["formal_interviews.source_id"]),
        sa.ForeignKeyConstraint(
            ["job_file_id", "through_source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_snapshots_source_file",
        ),
        sa.UniqueConstraint("job_file_id", "execution_id", name="uq_memory_snapshots_batch"),
        sa.CheckConstraint(
            "covered_through_sequence > 0", name=op.f("ck_memory_snapshots_coverage")
        ),
    )
    op.create_foreign_key(
        "fk_memory_batches_base_snapshot",
        "memory_batches",
        "memory_snapshots",
        ["job_file_id", "base_snapshot_id"],
        ["job_file_id", "snapshot_id"],
    )
    op.create_table(
        "memory_heads",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.ForeignKeyConstraint(
            ["job_file_id", "snapshot_id"],
            ["memory_snapshots.job_file_id", "memory_snapshots.snapshot_id"],
            name="fk_memory_heads_snapshot",
        ),
    )
    op.create_table(
        "memory_operations",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "command_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "execution_id"],
            ["executions.job_file_id", "executions.execution_id"],
            name="fk_memory_operations_execution",
        ),
    )
    # Reuse 0011's concrete fixed-Memory protection, not a second persistence framework.
    for table in ("memory_position_members", "memory_snapshots", "memory_operations"):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_memory_mutation()"
        )
    op.execute("""
        CREATE FUNCTION protect_memory_position_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.is_sealed THEN
                RAISE EXCEPTION 'Memory positions must be assembled before sealing'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.parent_position_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM memory_positions
                WHERE job_file_id = NEW.job_file_id
                    AND position_id = NEW.parent_position_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Memory position requires a sealed same-file parent'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_memory_positions_insert BEFORE INSERT ON memory_positions
        FOR EACH ROW EXECUTE FUNCTION protect_memory_position_insert()
    """)
    op.execute("""
        CREATE FUNCTION protect_memory_position_member_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            parent_is_sealed boolean;
        BEGIN
            SELECT is_sealed INTO parent_is_sealed FROM memory_positions
                WHERE job_file_id = NEW.job_file_id AND position_id = NEW.position_id
                FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Memory member requires its position'
                    USING ERRCODE = '23503';
            END IF;
            IF parent_is_sealed THEN
                RAISE EXCEPTION 'Cannot append members to a sealed Memory position'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM memory_object_revisions
                WHERE job_file_id = NEW.job_file_id AND object_id = NEW.object_id
                    AND revision_id = NEW.revision_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Memory member requires a sealed same-file revision'
                    USING ERRCODE = '23503';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_memory_position_members_insert
        BEFORE INSERT ON memory_position_members
        FOR EACH ROW EXECUTE FUNCTION protect_memory_position_member_insert()
    """)
    op.execute("""
        CREATE FUNCTION protect_memory_position_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NOT OLD.is_sealed AND NEW.is_sealed
                    AND (to_jsonb(NEW) - 'is_sealed') = (to_jsonb(OLD) - 'is_sealed') THEN
                    IF EXISTS (
                        SELECT 1
                        FROM memory_position_members m
                        JOIN memory_object_revisions r USING (job_file_id, object_id, revision_id)
                        JOIN memory_objects o USING (job_file_id, object_id)
                        WHERE m.job_file_id = NEW.job_file_id AND m.position_id = NEW.position_id
                        GROUP BY o.layer, r.title COLLATE "C" HAVING count(*) > 1
                    ) THEN
                        RAISE EXCEPTION 'Memory position requires unique exact titles per layer'
                            USING ERRCODE = '23505';
                    END IF;
                    IF EXISTS (
                        SELECT 1
                        FROM memory_position_members m
                        JOIN memory_situation_references s
                            USING (job_file_id, object_id, revision_id)
                        WHERE m.job_file_id = NEW.job_file_id AND m.position_id = NEW.position_id
                            AND NOT EXISTS (
                                SELECT 1 FROM memory_position_members source
                                WHERE source.job_file_id = m.job_file_id
                                    AND source.position_id = m.position_id
                                    AND source.object_id = s.source_object_id
                            )
                    ) THEN
                        RAISE EXCEPTION 'Memory position is missing a bound situation identity'
                            USING ERRCODE = '23503';
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'Memory positions are immutable; only initial sealing is allowed'
                USING ERRCODE = '23514';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_memory_positions BEFORE UPDATE OR DELETE ON memory_positions
        FOR EACH ROW EXECUTE FUNCTION protect_memory_position_mutation()
    """)
    # Re-read the final row at COMMIT so no unsealed aggregate can escape the transaction.
    op.execute("""
        CREATE FUNCTION require_sealed_memory_position() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM memory_positions
                WHERE job_file_id = NEW.job_file_id AND position_id = NEW.position_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Memory positions must be sealed before commit'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER require_sealed_memory_position
        AFTER INSERT ON memory_positions DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION require_sealed_memory_position()
    """)
    # Candidates bind source identities; a published snapshot must fix the exact selected pairs.
    # This protects stored relationships, without deciding B2 completion or publication authority.
    op.execute("""
        CREATE FUNCTION protect_memory_snapshot_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM memory_positions
                WHERE job_file_id = NEW.job_file_id AND position_id = NEW.position_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Snapshot requires a sealed position'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM formal_interviews
                WHERE job_file_id = NEW.job_file_id AND source_id = NEW.through_source_id
                    AND interview_sequence = NEW.covered_through_sequence
            ) THEN
                RAISE EXCEPTION 'Snapshot coverage must match its formal source'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM memory_position_members m
                JOIN memory_situation_references s USING (job_file_id, object_id, revision_id)
                WHERE m.job_file_id = NEW.job_file_id AND m.position_id = NEW.position_id
                    AND NOT EXISTS (
                        SELECT 1 FROM memory_position_members source
                        WHERE source.job_file_id = m.job_file_id
                            AND source.position_id = m.position_id
                            AND source.object_id = s.source_object_id
                            AND source.revision_id = s.source_revision_id
                    )
            ) THEN
                RAISE EXCEPTION 'Snapshot requires selected source revision pairs'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM memory_position_members m
                JOIN memory_interview_references i USING (job_file_id, object_id, revision_id)
                JOIN formal_interviews f ON f.job_file_id = i.job_file_id
                    AND f.source_id = i.source_id
                WHERE m.job_file_id = NEW.job_file_id AND m.position_id = NEW.position_id
                    AND f.interview_sequence > NEW.covered_through_sequence
            ) THEN
                RAISE EXCEPTION 'Snapshot interview source exceeds coverage'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_memory_snapshots_insert BEFORE INSERT ON memory_snapshots
        FOR EACH ROW EXECUTE FUNCTION protect_memory_snapshot_insert()
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Memory positions, snapshots and original operations must remain recoverable"
    )
