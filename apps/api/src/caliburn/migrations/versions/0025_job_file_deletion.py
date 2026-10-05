"""Cascade whole-file deletion while keeping individual fixed records immutable."""

import sqlalchemy as sa
from alembic import op

revision = "0025_job_file_deletion"
down_revision = "0024_occupation_reference_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    # Existing cross-file composite keys still fence identity. CASCADE is only usable
    # for fixed rows after their job-file root has gone; the guards below enforce that.
    for table in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table):
            name = foreign_key["name"]
            if name is None:
                raise RuntimeError("Owned foreign keys must have stable names")
            options = {**foreign_key["options"], "ondelete": "CASCADE"}
            op.drop_constraint(op.f(name), table, type_="foreignkey")
            op.create_foreign_key(
                op.f(name),
                table,
                foreign_key["referred_table"],
                foreign_key["constrained_columns"],
                foreign_key["referred_columns"],
                **options,
            )

    op.execute("""
        CREATE FUNCTION job_file_row_is_present(row_data jsonb) RETURNS boolean
        LANGUAGE sql STABLE AS $$
            SELECT CASE
                WHEN row_data ? 'job_file_id' THEN EXISTS (
                    SELECT 1 FROM job_files
                    WHERE job_file_id = (row_data->>'job_file_id')::uuid
                )
                WHEN row_data ? 'execution_id' THEN EXISTS (
                    SELECT 1 FROM executions e JOIN job_files f USING (job_file_id)
                    WHERE e.execution_id = (row_data->>'execution_id')::uuid
                )
                ELSE true
            END
        $$;
    """)
    # Preserve each original protection function, including one-time Memory sealing.
    # Skip its mutation trigger only for rows cascading from an already removed root.
    triggers = connection.execute(
        sa.text("""
        SELECT t.tgname, c.relname, pg_get_triggerdef(t.oid)
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=current_schema() AND NOT t.tgisinternal
            AND (t.tgtype & 8) <> 0 AND (t.tgtype & 2) <> 0
    """)
    ).all()
    quote = connection.dialect.identifier_preparer.quote
    for name, table, definition in triggers:
        if " WHEN " in definition:
            raise RuntimeError("Review existing deletion-trigger predicates before extending")
        op.execute(sa.text(f"DROP TRIGGER {quote(name)} ON {quote(table)}"))
        op.execute(
            sa.text(
                definition.replace(
                    " EXECUTE FUNCTION ",
                    " WHEN (job_file_row_is_present(to_jsonb(OLD))) EXECUTE FUNCTION ",
                )
            )
        )
    op.execute("""
        CREATE FUNCTION protect_job_file_deletion() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM executions WHERE job_file_id=OLD.job_file_id
                       AND status IN ('active', 'paused')) THEN
                RAISE EXCEPTION 'Job file has active or paused work' USING ERRCODE='23514';
            END IF;
            RETURN OLD;
        END $$;
        CREATE TRIGGER protect_job_file_deletion BEFORE DELETE ON job_files
        FOR EACH ROW EXECUTE FUNCTION protect_job_file_deletion();
        CREATE FUNCTION protect_execution_deletion() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM job_files WHERE job_file_id=OLD.job_file_id) THEN
                RAISE EXCEPTION 'Execution history may only be removed with its job file'
                    USING ERRCODE='23514';
            END IF;
            RETURN OLD;
        END $$;
        CREATE TRIGGER protect_execution_deletion BEFORE DELETE ON executions
        FOR EACH ROW EXECUTE FUNCTION protect_execution_deletion();
    """)


def downgrade() -> None:
    raise RuntimeError("Whole-file deletion cannot restore previously removed data")
