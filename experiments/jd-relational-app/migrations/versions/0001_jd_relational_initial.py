"""Initial thirteen-table JD schema for a dedicated fresh database.

Revision ID: 20260913_0001
Revises: None

Fixed migration operations, reviewed against the relational write contract.
No live metadata import: future table edits cannot rewrite this historical step.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260913_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jd_document',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('archived', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('metadata_version', sa.BigInteger(), nullable=False),
    sa.Column('create_request_key', sa.String(), nullable=False),
    sa.Column('create_payload_digest', sa.CHAR(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('metadata_version >= 1', name='ck_jd_document_metadata_version'),
    sa.PrimaryKeyConstraint('id', name='pk_jd_document'),
    sa.UniqueConstraint('create_request_key', name='uq_jd_document_create_request')
    )
    op.create_table('jd_capability',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('capability_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint("kind IN ('knowledge', 'skill')", name='ck_jd_capability_kind'),
    sa.CheckConstraint('name IS NOT NULL OR description IS NOT NULL', name='ck_jd_capability_content'),
    sa.CheckConstraint('position >= 0', name='ck_jd_capability_position'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_capability_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'capability_id', name='pk_jd_capability')
    )
    op.create_index('ix_jd_capability_order', 'jd_capability', ['document_id', 'kind', 'position', 'capability_id'], unique=False)
    op.create_table('jd_collaborator',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('collaborator_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('scope_text', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('name IS NOT NULL OR scope_text IS NOT NULL', name='ck_jd_collaborator_content'),
    sa.CheckConstraint('position >= 0', name='ck_jd_collaborator_position'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_collaborator_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'collaborator_id', name='pk_jd_collaborator')
    )
    op.create_table('jd_condition',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('condition_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint("kind IN ('work_environment', 'schedule_travel', 'shared_authority', 'shared_collaboration', 'qualification')", name='ck_jd_condition_kind'),
    sa.CheckConstraint('position >= 0', name='ck_jd_condition_position'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_condition_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'condition_id', name='pk_jd_condition')
    )
    op.create_index('ix_jd_condition_order', 'jd_condition', ['document_id', 'kind', 'position', 'condition_id'], unique=False)
    op.create_table('jd_duty',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('duty_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('scope_text', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('name IS NOT NULL OR scope_text IS NOT NULL', name='ck_jd_duty_content'),
    sa.CheckConstraint('position >= 0', name='ck_jd_duty_position'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_duty_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'duty_id', name='pk_jd_duty')
    )
    op.create_index('ix_jd_duty_order', 'jd_duty', ['document_id', 'position', 'duty_id'], unique=False)
    op.create_table('jd_profile',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('job_title', sa.Text(), nullable=True),
    sa.Column('organization_unit', sa.Text(), nullable=True),
    sa.Column('employee_name', sa.Text(), nullable=True),
    sa.Column('reports_to', sa.Text(), nullable=True),
    sa.Column('purpose', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_profile_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', name='pk_jd_profile')
    )
    op.create_table('jd_revision',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('revision_number', sa.BigInteger(), nullable=False),
    sa.Column('parent_revision_id', sa.UUID(), nullable=True),
    sa.Column('origin', sa.Text(), nullable=False),
    sa.Column('format_version', sa.Integer(), nullable=False),
    sa.Column('engine_profile', sa.Text(), nullable=False),
    sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('content_digest', sa.CHAR(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(origin = 'initial') = (parent_revision_id IS NULL)", name='ck_jd_revision_initial_parent'),
    sa.CheckConstraint("engine_profile = 'jd-relational-v1'", name='ck_jd_revision_engine_profile'),
    sa.CheckConstraint("origin IN ('initial', 'manual', 'ai')", name='ck_jd_revision_origin'),
    sa.CheckConstraint('format_version = 3', name='ck_jd_revision_format_version'),
    sa.CheckConstraint('revision_number >= 1', name='ck_jd_revision_number'),
    sa.ForeignKeyConstraint(['document_id', 'parent_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id'], name='fk_jd_revision_parent', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_revision_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'revision_id', name='pk_jd_revision'),
    sa.UniqueConstraint('document_id', 'parent_revision_id', name='uq_jd_revision_parent'),
    sa.UniqueConstraint('document_id', 'revision_number', name='uq_jd_revision_number')
    )
    op.create_index('ix_jd_revision_number', 'jd_revision', ['document_id', sa.literal_column('revision_number DESC')], unique=False)
    op.create_index('uq_jd_revision_initial', 'jd_revision', ['document_id'], unique=True, postgresql_where=sa.text("origin = 'initial'"))
    op.create_table('jd_head',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('current_revision_id', sa.UUID(), nullable=False),
    sa.Column('revision_number', sa.BigInteger(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('revision_number >= 1', name='ck_jd_head_revision_number'),
    sa.ForeignKeyConstraint(['document_id', 'current_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id'], name='fk_jd_head_revision', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_head_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', name='pk_jd_head')
    )
    op.create_table('jd_operation',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('operation_id', sa.UUID(), nullable=False),
    sa.Column('request_digest', sa.CHAR(length=64), nullable=False),
    sa.Column('origin', sa.Text(), nullable=False),
    sa.Column('ai_run_id', sa.String(), nullable=True),
    sa.Column('base_revision_id', sa.UUID(), nullable=True),
    sa.Column('result_revision_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('receipt', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(origin = 'ai') = (ai_run_id IS NOT NULL)", name='ck_jd_operation_origin_run'),
    sa.CheckConstraint("(status = 'committed' AND base_revision_id IS NOT NULL AND result_revision_id IS NOT NULL AND result_revision_id <> base_revision_id) OR (status = 'no_change' AND base_revision_id IS NOT NULL AND result_revision_id IS NOT NULL AND result_revision_id = base_revision_id) OR (status NOT IN ('committed', 'no_change') AND result_revision_id IS NULL)", name='ck_jd_operation_result'),
    sa.CheckConstraint("origin IN ('manual', 'ai')", name='ck_jd_operation_origin'),
    sa.CheckConstraint("status IN ('committed', 'no_change', 'invalid_input', 'target_missing', 'stale_view', 'relationship_conflict', 'dependent_items', 'save_failed')", name='ck_jd_operation_status'),
    sa.ForeignKeyConstraint(['document_id', 'base_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id'], name='fk_jd_operation_base', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id', 'result_revision_id'], ['jd_revision.document_id', 'jd_revision.revision_id'], name='fk_jd_operation_result', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_operation_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'operation_id', name='pk_jd_operation')
    )
    op.create_index('ix_jd_operation_ai_run', 'jd_operation', ['document_id', 'ai_run_id'], unique=False, postgresql_where=sa.text('ai_run_id IS NOT NULL'))
    op.create_index('ix_jd_operation_created', 'jd_operation', ['document_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('uq_jd_operation_committed_result', 'jd_operation', ['document_id', 'result_revision_id'], unique=True, postgresql_where=sa.text("status = 'committed'"))
    op.create_table('jd_task',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('duty_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('name IS NOT NULL OR description IS NOT NULL', name='ck_jd_task_content'),
    sa.CheckConstraint('position >= 0', name='ck_jd_task_position'),
    sa.ForeignKeyConstraint(['document_id', 'duty_id'], ['jd_duty.document_id', 'jd_duty.duty_id'], name='fk_jd_task_duty', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_task_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'task_id', name='pk_jd_task')
    )
    op.create_index('ix_jd_task_order', 'jd_task', ['document_id', 'duty_id', 'position', 'task_id'], unique=False)
    op.create_index('ix_jd_task_unassigned', 'jd_task', ['document_id', 'position', 'task_id'], unique=False, postgresql_where=sa.text('duty_id IS NULL'))
    op.create_table('jd_task_capability',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('capability_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('position >= 0', name='ck_jd_task_capability_position'),
    sa.ForeignKeyConstraint(['document_id', 'capability_id'], ['jd_capability.document_id', 'jd_capability.capability_id'], name='fk_jd_task_capability_capability', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id', 'task_id'], ['jd_task.document_id', 'jd_task.task_id'], name='fk_jd_task_capability_task', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_task_capability_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'task_id', 'capability_id', name='pk_jd_task_capability')
    )
    op.create_index('ix_jd_task_capability_reverse', 'jd_task_capability', ['document_id', 'capability_id', 'task_id'], unique=False)
    op.create_table('jd_task_detail',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('detail_id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint("kind IN ('outcome', 'requirement')", name='ck_jd_task_detail_kind'),
    sa.CheckConstraint('position >= 0', name='ck_jd_task_detail_position'),
    sa.ForeignKeyConstraint(['document_id', 'task_id'], ['jd_task.document_id', 'jd_task.task_id'], name='fk_jd_task_detail_task', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_task_detail_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'detail_id', name='pk_jd_task_detail')
    )
    op.create_index('ix_jd_task_detail_order', 'jd_task_detail', ['document_id', 'task_id', 'kind', 'position', 'detail_id'], unique=False)
    op.create_table('jd_source_link',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('source_link_id', sa.UUID(), nullable=False),
    sa.Column('source_ref', sa.Text(), nullable=False),
    sa.Column('basis_digest', sa.CHAR(length=64), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('profile_field', sa.Text(), nullable=True),
    sa.Column('collaborator_id', sa.UUID(), nullable=True),
    sa.Column('duty_id', sa.UUID(), nullable=True),
    sa.Column('task_id', sa.UUID(), nullable=True),
    sa.Column('detail_id', sa.UUID(), nullable=True),
    sa.Column('capability_id', sa.UUID(), nullable=True),
    sa.Column('condition_id', sa.UUID(), nullable=True),
    sa.Column('linked_task_id', sa.UUID(), nullable=True),
    sa.Column('linked_capability_id', sa.UUID(), nullable=True),
    sa.CheckConstraint("profile_field IN ('job_title', 'organization_unit', 'employee_name', 'reports_to', 'purpose')", name='ck_jd_source_link_profile_field'),
    sa.CheckConstraint('(linked_task_id IS NULL) = (linked_capability_id IS NULL)', name='ck_jd_source_link_relation_pair'),
    sa.CheckConstraint('num_nonnulls(profile_field, collaborator_id, duty_id, task_id, detail_id, capability_id, condition_id, linked_task_id) = 1', name='ck_jd_source_link_one_target'),
    sa.CheckConstraint('position >= 0', name='ck_jd_source_link_position'),
    sa.ForeignKeyConstraint(['document_id', 'capability_id'], ['jd_capability.document_id', 'jd_capability.capability_id'], name='fk_jd_source_link_capability', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'collaborator_id'], ['jd_collaborator.document_id', 'jd_collaborator.collaborator_id'], name='fk_jd_source_link_collaborator', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'condition_id'], ['jd_condition.document_id', 'jd_condition.condition_id'], name='fk_jd_source_link_condition', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'detail_id'], ['jd_task_detail.document_id', 'jd_task_detail.detail_id'], name='fk_jd_source_link_detail', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'duty_id'], ['jd_duty.document_id', 'jd_duty.duty_id'], name='fk_jd_source_link_duty', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'linked_task_id', 'linked_capability_id'], ['jd_task_capability.document_id', 'jd_task_capability.task_id', 'jd_task_capability.capability_id'], name='fk_jd_source_link_relation', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id', 'task_id'], ['jd_task.document_id', 'jd_task.task_id'], name='fk_jd_source_link_task', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['jd_document.id'], name='fk_jd_source_link_document', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'source_link_id', name='pk_jd_source_link')
    )
    op.create_index('ix_jd_source_link_capability_id', 'jd_source_link', ['document_id', 'capability_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('capability_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_collaborator_id', 'jd_source_link', ['document_id', 'collaborator_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('collaborator_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_condition_id', 'jd_source_link', ['document_id', 'condition_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('condition_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_detail_id', 'jd_source_link', ['document_id', 'detail_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('detail_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_duty_id', 'jd_source_link', ['document_id', 'duty_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('duty_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_profile_field', 'jd_source_link', ['document_id', 'profile_field', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('profile_field IS NOT NULL'))
    op.create_index('ix_jd_source_link_relation', 'jd_source_link', ['document_id', 'linked_task_id', 'linked_capability_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('linked_task_id IS NOT NULL'))
    op.create_index('ix_jd_source_link_task_id', 'jd_source_link', ['document_id', 'task_id', 'position', 'source_link_id'], unique=False, postgresql_where=sa.text('task_id IS NOT NULL'))


def downgrade():
    op.drop_table('jd_source_link')
    op.drop_table('jd_task_detail')
    op.drop_table('jd_task_capability')
    op.drop_table('jd_task')
    op.drop_table('jd_operation')
    op.drop_table('jd_head')
    op.drop_table('jd_revision')
    op.drop_table('jd_profile')
    op.drop_table('jd_duty')
    op.drop_table('jd_condition')
    op.drop_table('jd_collaborator')
    op.drop_table('jd_capability')
    op.drop_table('jd_document')
