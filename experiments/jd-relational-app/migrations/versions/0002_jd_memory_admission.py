"""Runtime background admission row for this App's own B work.

Revision ID: 20260914_0002
Revises: 20260913_0001

Fixed migration operations, reviewed against ADR0076 and the background
admission design. No live metadata import: future table edits cannot rewrite
this historical step. The thirteen JD content tables gain no column here; this
adds one runtime table, so the App's total becomes fourteen.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260914_0002"
down_revision = "20260913_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jd_memory_admission',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('target_reference', sa.Text(), nullable=True),
    sa.Column('source_reference', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('error_code', sa.Text(), nullable=True),
    sa.Column('recovery_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint("status IN ('idle', 'queued', 'running', 'blocked')",
                       name='ck_jd_memory_admission_status'),
    sa.CheckConstraint('recovery_count >= 0', name='ck_jd_memory_admission_recovery'),
    sa.CheckConstraint(
        "(status = 'idle' AND target_reference IS NULL AND source_reference IS NULL "
        "AND error_code IS NULL)"
        " OR (status = 'queued' AND target_reference IS NOT NULL AND error_code IS NULL)"
        " OR (status = 'running' AND target_reference IS NOT NULL "
        "AND source_reference IS NOT NULL AND error_code IS NULL)"
        " OR (status = 'blocked' AND error_code IS NOT NULL)",
        name='ck_jd_memory_admission_state'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'],
                            name='fk_jd_memory_admission_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', name='pk_jd_memory_admission')
    )


def downgrade():
    op.drop_table('jd_memory_admission')
