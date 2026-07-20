"""opt-in immutable interview eval capture

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-15

Restricted eval artifacts are append-only during their retention lifetime.
DELETE remains allowed for cascade/privacy deletion; UPDATE is rejected by a
database trigger so a historical replay fixture cannot silently drift.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interview_llm_calls", sa.Column("stage", sa.Text(), nullable=True))
    op.add_column(
        "interview_llm_calls",
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
    )
    op.add_column("interview_llm_calls", sa.Column("requested_model", sa.Text(), nullable=True))
    op.add_column("interview_llm_calls", sa.Column("resolved_model", sa.Text(), nullable=True))
    op.add_column(
        "interview_llm_calls",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "interview_llm_calls",
        sa.Column(
            "outcome",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'legacy_unknown'"),
        ),
    )
    op.add_column("interview_llm_calls", sa.Column("prompt_hash", sa.Text(), nullable=True))
    op.add_column("interview_llm_calls", sa.Column("tool_schema_hash", sa.Text(), nullable=True))
    op.execute("UPDATE interview_llm_calls SET stage = role, requested_model = model")
    op.alter_column("interview_llm_calls", "stage", nullable=False)
    op.alter_column("interview_llm_calls", "requested_model", nullable=False)

    op.create_table(
        "interview_eval_captures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'capturing'")),
        sa.Column("consent_policy_version", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("initial_document_hash", sa.Text(), nullable=False),
        sa.Column("initial_state_hash", sa.Text(), nullable=False),
        sa.Column("reference_snapshot_hash", sa.Text(), nullable=False),
        sa.Column("prompt_bundle_hash", sa.Text(), nullable=False),
        sa.Column("tool_schema_hash", sa.Text(), nullable=False),
        sa.Column("code_git_sha", sa.Text(), nullable=False),
        sa.Column("dirty_worktree", sa.Boolean(), nullable=False),
        sa.Column("limitations", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('capturing', 'completed')",
            name="ck_interview_eval_capture_status",
        ),
    )
    op.create_table(
        "interview_eval_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "capture_id",
            UUID(as_uuid=True),
            sa.ForeignKey("interview_eval_captures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "capture_id", "kind", "sequence", name="uq_interview_eval_artifact_kind_seq"
        ),
    )
    op.create_index(
        "ix_interview_eval_artifacts_capture",
        "interview_eval_artifacts",
        ["capture_id", "created_at"],
    )
    op.execute("""
        CREATE FUNCTION guard_interview_eval_capture_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'capturing' AND NEW.status = 'completed'
               AND NEW.id IS NOT DISTINCT FROM OLD.id
               AND NEW.session_id IS NOT DISTINCT FROM OLD.session_id
               AND NEW.schema_version IS NOT DISTINCT FROM OLD.schema_version
               AND NEW.consent_policy_version IS NOT DISTINCT FROM OLD.consent_policy_version
               AND NEW.locale IS NOT DISTINCT FROM OLD.locale
               AND NEW.initial_document_hash IS NOT DISTINCT FROM OLD.initial_document_hash
               AND NEW.initial_state_hash IS NOT DISTINCT FROM OLD.initial_state_hash
               AND NEW.reference_snapshot_hash IS NOT DISTINCT FROM OLD.reference_snapshot_hash
               AND NEW.prompt_bundle_hash IS NOT DISTINCT FROM OLD.prompt_bundle_hash
               AND NEW.tool_schema_hash IS NOT DISTINCT FROM OLD.tool_schema_hash
               AND NEW.code_git_sha IS NOT DISTINCT FROM OLD.code_git_sha
               AND NEW.dirty_worktree IS NOT DISTINCT FROM OLD.dirty_worktree
               AND NEW.limitations IS NOT DISTINCT FROM OLD.limitations
               AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'interview eval capture metadata is immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER interview_eval_captures_guard_update
        BEFORE UPDATE ON interview_eval_captures
        FOR EACH ROW EXECUTE FUNCTION guard_interview_eval_capture_update()
    """)
    op.execute("""
        CREATE FUNCTION reject_interview_eval_artifact_update()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'interview eval artifacts are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER interview_eval_artifacts_no_update
        BEFORE UPDATE ON interview_eval_artifacts
        FOR EACH ROW EXECUTE FUNCTION reject_interview_eval_artifact_update()
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS interview_eval_captures_guard_update "
        "ON interview_eval_captures"
    )
    op.execute("DROP FUNCTION IF EXISTS guard_interview_eval_capture_update()")
    op.execute(
        "DROP TRIGGER IF EXISTS interview_eval_artifacts_no_update "
        "ON interview_eval_artifacts"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_interview_eval_artifact_update()")
    op.drop_index(
        "ix_interview_eval_artifacts_capture", table_name="interview_eval_artifacts"
    )
    op.drop_table("interview_eval_artifacts")
    op.drop_table("interview_eval_captures")
    op.drop_column("interview_llm_calls", "tool_schema_hash")
    op.drop_column("interview_llm_calls", "prompt_hash")
    op.drop_column("interview_llm_calls", "outcome")
    op.drop_column("interview_llm_calls", "attempt_count")
    op.drop_column("interview_llm_calls", "resolved_model")
    op.drop_column("interview_llm_calls", "requested_model")
    op.drop_column("interview_llm_calls", "provider")
    op.drop_column("interview_llm_calls", "stage")
