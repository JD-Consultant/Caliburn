"""Add fixed Memory objects, reusable bodies and sealed revision references."""

import sqlalchemy as sa
from alembic import op

revision = "0011_memory_object_revisions"
down_revision = "0010_jd_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_objects",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "object_id"),
        sa.ForeignKeyConstraint(["job_file_id"], ["job_files.job_file_id"]),
        sa.UniqueConstraint("job_file_id", "object_id", "layer", name="uq_memory_objects_layer"),
        sa.CheckConstraint(
            "layer IN ('work_situation', 'work_understanding')",
            name=op.f("ck_memory_objects_layer"),
        ),
    )
    op.create_table(
        "memory_bodies",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("body_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("job_file_id", "object_id", "body_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id"],
            ["memory_objects.job_file_id", "memory_objects.object_id"],
            name="fk_memory_bodies_object",
        ),
        sa.CheckConstraint("length(btrim(body)) > 0", name=op.f("ck_memory_bodies_body_content")),
    )
    op.create_table(
        "memory_object_revisions",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("body_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(collation="C"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_sealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_file_id", "object_id", "revision_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id"],
            ["memory_objects.job_file_id", "memory_objects.object_id"],
            name="fk_memory_object_revisions_object",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "body_id"],
            ["memory_bodies.job_file_id", "memory_bodies.object_id", "memory_bodies.body_id"],
            name="fk_memory_object_revisions_body",
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("ck_memory_object_revisions_title_content")
        ),
        sa.CheckConstraint(
            "length(btrim(description)) > 0",
            name=op.f("ck_memory_object_revisions_description_content"),
        ),
    )
    op.create_table(
        "memory_interview_references",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("owner_layer", sa.Text(), nullable=False, server_default="work_situation"),
        sa.PrimaryKeyConstraint("job_file_id", "object_id", "revision_id", "source_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_interview_references_revision",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["formal_interviews.source_id"]),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_id"],
            ["interview_texts.job_file_id", "interview_texts.source_id"],
            name="fk_memory_interview_references_source_file",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "owner_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_interview_references_owner_layer",
        ),
        sa.CheckConstraint(
            "owner_layer = 'work_situation'",
            name=op.f("ck_memory_interview_references_owner_layer"),
        ),
    )
    op.create_table(
        "memory_situation_references",
        sa.Column("job_file_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=False),
        sa.Column("source_revision_id", sa.Uuid(), nullable=False),
        sa.Column("owner_layer", sa.Text(), nullable=False, server_default="work_understanding"),
        sa.Column("source_layer", sa.Text(), nullable=False, server_default="work_situation"),
        sa.PrimaryKeyConstraint("job_file_id", "object_id", "revision_id", "source_object_id"),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_situation_references_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_object_id", "source_revision_id"],
            [
                "memory_object_revisions.job_file_id",
                "memory_object_revisions.object_id",
                "memory_object_revisions.revision_id",
            ],
            name="fk_memory_situation_references_source_revision",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "object_id", "owner_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_situation_references_owner_layer",
        ),
        sa.ForeignKeyConstraint(
            ["job_file_id", "source_object_id", "source_layer"],
            ["memory_objects.job_file_id", "memory_objects.object_id", "memory_objects.layer"],
            name="fk_memory_situation_references_source_layer",
        ),
        sa.CheckConstraint(
            "owner_layer = 'work_understanding'",
            name=op.f("ck_memory_situation_references_owner_layer"),
        ),
        sa.CheckConstraint(
            "source_layer = 'work_situation'",
            name=op.f("ck_memory_situation_references_source_layer"),
        ),
    )
    op.execute("""
        CREATE FUNCTION reject_fixed_memory_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Fixed Memory objects, bodies and references are immutable'
                USING ERRCODE = '23514';
        END
        $$
    """)
    for table in (
        "memory_objects",
        "memory_bodies",
        "memory_interview_references",
        "memory_situation_references",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_fixed_memory_mutation()"
        )
    # A header may only seal once, after its complete reference set has been inserted.
    op.execute("""
        CREATE FUNCTION protect_memory_revision_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF OLD.is_sealed = false AND NEW.is_sealed = true
                    AND (to_jsonb(NEW) - 'is_sealed') = (to_jsonb(OLD) - 'is_sealed') THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'Memory revision content is immutable; only initial sealing is allowed'
                USING ERRCODE = '23514';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_memory_object_revisions
        BEFORE UPDATE OR DELETE ON memory_object_revisions
        FOR EACH ROW EXECUTE FUNCTION protect_memory_revision_mutation()
    """)
    op.execute("""
        CREATE FUNCTION protect_memory_reference_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            parent_is_sealed boolean;
        BEGIN
            SELECT is_sealed INTO parent_is_sealed FROM memory_object_revisions
                WHERE job_file_id = NEW.job_file_id AND object_id = NEW.object_id
                    AND revision_id = NEW.revision_id
                FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Memory reference requires its parent revision'
                    USING ERRCODE = '23503';
            END IF;
            IF parent_is_sealed THEN
                RAISE EXCEPTION 'Cannot append references to a sealed Memory revision'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    for table in ("memory_interview_references", "memory_situation_references"):
        op.execute(
            f"CREATE TRIGGER protect_{table}_insert BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION protect_memory_reference_insert()"
        )
    op.execute("""
        CREATE FUNCTION require_sealed_memory_situation_source() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM memory_object_revisions
                WHERE job_file_id = NEW.job_file_id AND object_id = NEW.source_object_id
                    AND revision_id = NEW.source_revision_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Memory understanding requires a sealed source revision'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER require_sealed_memory_situation_source
        BEFORE INSERT ON memory_situation_references
        FOR EACH ROW EXECUTE FUNCTION require_sealed_memory_situation_source()
    """)
    # Re-read the final row, not INSERT's NEW.is_sealed, when the transaction finishes.
    # This is storage completeness, not Memory publication or B2 semantic completion.
    op.execute("""
        CREATE FUNCTION require_sealed_memory_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM memory_object_revisions
                WHERE job_file_id = NEW.job_file_id AND object_id = NEW.object_id
                    AND revision_id = NEW.revision_id AND is_sealed
            ) THEN
                RAISE EXCEPTION 'Memory revisions must be sealed before commit'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER require_sealed_memory_revision
        AFTER INSERT ON memory_object_revisions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION require_sealed_memory_revision()
    """)


def downgrade() -> None:
    raise RuntimeError("Fixed Memory revisions and their sources must remain recoverable")
